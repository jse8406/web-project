import os
import json
import asyncio
import websockets
from channels.layers import get_channel_layer
from .serializers import StockRequestSerializer, StockResponseSerializer, StockAskingPriceResponseSerializer
from dotenv import load_dotenv
from auth.kis_auth import get_approval_key

# .env 로드 (consumers.py와 동일)
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

APP_KEY = os.getenv('g_appkey')
APP_SECRET = os.getenv('g_appsecret') or os.getenv('g_appsceret')

WS_BASE_URL = "ws://ops.koreainvestment.com:21000"
WS_PATH = "" 
TR_ID_HOGA = "H0UNASP0"
TR_ID_EXEC = "H0STCNT0"

class StockMaster:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StockMaster, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.initialized = True
        self.approval_key = None
        self.ws = None
        self.connected = False
        self.lock = asyncio.Lock()
        self.active_stocks = set() # 현재 구독 중인 종목 코드들
        self.channel_layer = get_channel_layer()
        self.running = False
        self.task = None

    async def get_approval_key(self):
        # 동기 함수이므로 run_in_executor로 실행
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, get_approval_key)

    async def connect_and_run(self):
        """마스터 연결 시작"""
        if self.running: 
            return

        self.running = True
        print("[StockMaster] Starting master connection...")
        
        while self.running:
            try:
                if not self.approval_key:
                    self.approval_key = await self.get_approval_key()
                    if not self.approval_key:
                        print("[StockMaster] Failed to get approval key. Retrying in 5s...")
                        await asyncio.sleep(5)
                        continue

                url = f"{WS_BASE_URL}{WS_PATH}"
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    self.connected = True
                    print("[StockMaster] Connected to KIS WebSocket!")

                    # 끊겼다가 재연결된 경우, 기존 구독 종목들 다시 구독 신청
                    await self.resubscribe_all()

                    while self.running:
                        try:
                            data = await ws.recv()
                            await self.handle_message(data)
                        except websockets.ConnectionClosed:
                            print("[StockMaster] Connection closed. Reconnecting...")
                            break
                        except Exception as e:
                            print(f"[StockMaster] Error in loop: {e}")
                            break
            except Exception as e:
                print(f"[StockMaster] Connection failed: {e}. Retrying in 5s...")
                await asyncio.sleep(5)
            finally:
                self.connected = False
                self.ws = None

    async def handle_message(self, data):
        """수신된 데이터를 분석하여 Redis 채널로 브로드캐스팅"""
        # PINGPONG 등 비데이터 처리 (필요시)
        if isinstance(data, str) and data.startswith("{"):
             # JSON 메시지 (에러 등)
             try:
                 js = json.loads(data)
                 # print(f"[StockMaster] System Msg: {js}")
             except:
                 pass
             return

        if isinstance(data, str) and '|' in data:
            parts = data.split('|')
            if len(parts) > 3:

                tr_id = parts[1]

                tr_key = parts[3] 
                stock_code = tr_key
                
                SerializerClass = None
                if tr_id == TR_ID_HOGA:
                    SerializerClass = StockAskingPriceResponseSerializer
                elif tr_id == TR_ID_EXEC: # H0STCNT0 or H0UNCNT0
                    SerializerClass = StockResponseSerializer

                if SerializerClass and stock_code:
                    parsed_dict = SerializerClass.parse_from_raw(data)
                    if parsed_dict:
                        serializer = SerializerClass(data=parsed_dict)
                        if serializer.is_valid():
                            # [DEBUG] Response Body 출력
                            print(f"[StockMaster] Response Body ({tr_id}):\n{json.dumps(serializer.data, indent=2, ensure_ascii=False)}")
                            group_name = f"stock_{stock_code}"
                            
                            await self.channel_layer.group_send(
                                group_name,
                                {
                                    "type": "stock_update", 
                                    "data": serializer.data
                                }
                            )

    async def subscribe(self, stock_code):
        """특정 종목 구독 요청"""
        async with self.lock:
            if stock_code not in self.active_stocks:
                self.active_stocks.add(stock_code)
                print(f"[StockMaster] New subscription added: {stock_code}")
                # 이미 연결되어 있다면 즉시 구독 패킷 전송
                if self.connected and self.ws:
                    await self.send_subscription_packet(stock_code)
            
            # 마스터 태스크가 안 돌고 있으면 시작
            if not self.running or (self.task and self.task.done()):
                self.task = asyncio.create_task(self.connect_and_run())

    async def unsubscribe(self, stock_code):
        """
        구독 취소 처리는 신중해야 함.
        다른 유저도 보고 있을 수 있으므로, 여기선 '카운팅'을 하거나,
        단순하게 '현재는 취소 기능을 구현 안 함' (계속 받아도 됨) 정책을 쓸 수 있음.
        메모리 누수 방지를 위해선 Reference Counting이 필요함.
        지금 간단한 버전에서는 '구독 목록'에서 제거하지 않고 계속 유지하거나,
        Consumer 쪽에서 연결 수를 관리하는 별도 로직이 필요함.
        
        일단 단순하게: 아무것도 안 함 (다른 유저가 있을 수 있으므로).
        *나중에 고도화: Redis에 '시청자 수' 저장해서 0명이면 구독 해제*
        """
        pass

    async def resubscribe_all(self):
        """재연결 시 기존 목록 다시 구독"""
        for code in self.active_stocks:
            await self.send_subscription_packet(code)

    async def send_subscription_packet(self, stock_code):
        if not self.ws or not self.approval_key:
            return

        # 호가
        payload_hoga = StockRequestSerializer.build_payload(
            self.approval_key, TR_ID_HOGA, stock_code
        )
        print(f"[StockMaster] Request Body (Hoga):\n{json.dumps(payload_hoga, indent=2, ensure_ascii=False)}")
        await self.ws.send(json.dumps(payload_hoga))

        # 체결
        payload_exec = StockRequestSerializer.build_payload(
            self.approval_key, TR_ID_EXEC, stock_code
        )
        print(f"[StockMaster] Request Body (Exec):\n{json.dumps(payload_exec, indent=2, ensure_ascii=False)}")
        await self.ws.send(json.dumps(payload_exec))
        print(f"[StockMaster] Sent subscription for {stock_code}")

# 싱글톤 인스턴스
stock_master = StockMaster()
