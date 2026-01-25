import os
import json
import asyncio
import websockets
from collections import defaultdict
from channels.layers import get_channel_layer
from ..serializers import StockRequestSerializer, StockResponseSerializer, StockAskingPriceResponseSerializer
from dotenv import load_dotenv
from auth.kis_auth import get_approval_key

# .env 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

APP_KEY = os.getenv('g_appkey')
APP_SECRET = os.getenv('g_appsecret')

WS_BASE_URL = "ws://ops.koreainvestment.com:21000"
TR_ID_HOGA = "H0UNASP0"
TR_ID_HOGA_ELW = "H0STASP0"
TR_ID_EXEC = "H0STCNT0"

class KISWebSocketClient:
    def __init__(self):
        self.approval_key = None
        self.ws = None
        self.connected = False
        self.lock = asyncio.Lock()
        self._subscriber_counts = defaultdict(int) 
        self.logged_stocks = set()
        self.channel_layer = get_channel_layer()
        self.running = False
        self.task = None

    async def _get_approval_key(self):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_approval_key)

    async def _connect_and_run(self):
        if self.running: return

        self.running = True
        print("[KIS Client] Starting connection...")
        
        while self.running:
            try:
                if not self.approval_key:
                    self.approval_key = await self._get_approval_key()
                    if not self.approval_key:
                        await asyncio.sleep(5)
                        continue

                async with websockets.connect(WS_BASE_URL, ping_interval=None) as ws:
                    self.ws = ws
                    self.connected = True
                    print("[KIS Client] Connected to KIS WebSocket!")

                    # 재연결 시 기존에 시청자가 있는 종목들 다시 구독
                    await self._resubscribe_all()

                    while self.running:
                        try:
                            data = await ws.recv()
                            await self._handle_message(data)
                        except websockets.ConnectionClosed:
                            print("[KIS Client] Connection closed.")
                            break
                        except Exception as e:
                            print(f"[KIS Client] Error in loop: {e}")
                            break
            except Exception as e:
                print(f"[KIS Client] Connection failed: {e}. Retry in 5s...")
                await asyncio.sleep(5)
            finally:
                self.connected = False
                self.ws = None
    
    def _is_elw(self, stock_code):
        if stock_code.isdigit() and len(stock_code) == 6: return False
        if any(ord('가') <= ord(c) <= ord('힣') for c in stock_code): return False
        return any(c.isalpha() for c in stock_code) or stock_code.endswith('W')

    def _get_hoga_tr_id(self, stock_code):
        return TR_ID_HOGA_ELW if self._is_elw(stock_code) else TR_ID_HOGA

    async def _handle_message(self, data):
        # 핑퐁 등 시스템 메시지 처리
        if isinstance(data, str) and data.startswith("{"):
            try:
                js = json.loads(data)
                tr_id = js.get("header", {}).get("tr_id")
                if tr_id == "PINGPONG":
                    if self.ws: await self.ws.pong(data) # 퐁 응답
                    return
            except:
                pass
            return

        # 실시간 데이터 처리 (파이프라인 포맷)
        if isinstance(data, str) and '|' in data:
            parts = data.split('|')
            if len(parts) > 3:
                tr_id = parts[1]
                stock_code = parts[3]
                
                SerializerClass = None
                if tr_id in [TR_ID_HOGA, TR_ID_HOGA_ELW]:
                    SerializerClass = StockAskingPriceResponseSerializer
                elif tr_id == TR_ID_EXEC:
                    SerializerClass = StockResponseSerializer

                if SerializerClass and stock_code:
                    # ^ 문자열로 정보가 구분되어 옴
                    clean_code = stock_code.split("^")[0]
                    
                    parsed_dict = SerializerClass.parse_from_raw(data)
                    if parsed_dict:
                        serializer = SerializerClass(data=parsed_dict)
                        if serializer.is_valid():
                            # [DEBUG] 최초 1회 로그
                            if clean_code not in self.logged_stocks:
                                print(f"[KIS Client] First Data for {clean_code}")
                                self.logged_stocks.add(clean_code)
                                
                            group_name = f"stock_{clean_code}"
                            await self.channel_layer.group_send(
                                group_name,
                                {"type": "stock_update", "data": serializer.data}
                            )

    async def subscribe(self, stock_code):
        """Consumer가 호출: 구독 요청 (카운팅 적용)"""
        async with self.lock:
            self._subscriber_counts[stock_code] += 1
            count = self._subscriber_counts[stock_code]
            
            print(f"[KIS Client] Subscribe {stock_code} (Total watchers: {count})")

            # 이 종목의 '첫 번째' 시청자일 때만 실제 API 구독 요청
            if count == 1:
                await self._send_subscription_packet(stock_code)
            
            # 백그라운드 태스크 시작 확인
            if not self.running or (self.task and self.task.done()):
                self.task = asyncio.create_task(self._connect_and_run())

    async def unsubscribe(self, stock_code):
        """Consumer가 호출: 구독 취소 (카운팅 적용)"""
        async with self.lock:
            if self._subscriber_counts[stock_code] > 0:
                self._subscriber_counts[stock_code] -= 1
            
            count = self._subscriber_counts[stock_code]
            print(f"[KIS Client] Unsubscribe {stock_code} (Remaining watchers: {count})")

            # 시청자가 0명이 되면? 
            # (선택사항) 여기서 API에 구독 해제 패킷을 보낼 수도 있고,
            # 빈번한 해제를 막기 위해 그냥 둬도 됩니다. 
            # 일단은 카운트만 줄이는 것으로 충분합니다.

    async def _resubscribe_all(self):
        """재연결 시 시청자가 있는 종목만 다시 구독"""
        for code, count in self._subscriber_counts.items():
            if count > 0:
                await self._send_subscription_packet(code)

    async def _send_subscription_packet(self, stock_code):
        if not self.ws or not self.connected or not self.approval_key:
            return

        # 1. 호가 등록
        hoga_tr_id = self._get_hoga_tr_id(stock_code)
        payload_hoga = StockRequestSerializer.build_payload(
            self.approval_key, hoga_tr_id, stock_code
        )
        await self.ws.send(json.dumps(payload_hoga))

        # 2. 체결 등록
        payload_exec = StockRequestSerializer.build_payload(
            self.approval_key, TR_ID_EXEC, stock_code
        )
        await self.ws.send(json.dumps(payload_exec))
        
        print(f"[KIS Client] Sent API Request for {stock_code}")

# 모듈 레벨에서 인스턴스 생성 (이 파일이 import 될 때 딱 한 번 생성됨)
kis_client = KISWebSocketClient()