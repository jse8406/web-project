import json
import re
from channels.generic.websocket import AsyncWebsocketConsumer
from .services.kis_ws_client import kis_client

class StockConsumer(AsyncWebsocketConsumer):
    _logged_stocks = set() # 최초 1회 로그 출력 여부 확인용

    async def connect(self):
        self.subscribed_stocks = set()
        
        # URL에서 stock_code 추출 (Optional)
        self.url_stock_code = self.scope['url_route']['kwargs'].get('stock_code')
        
        await self.accept()
        print(f"[StockConsumer] Client connected. URL Code: {self.url_stock_code}")

        # URL에 코드가 있으면 즉시 구독 (Legacy/Detail Page)
        if self.url_stock_code:
            await self.add_subscription(self.url_stock_code)

    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신 (구독 요청 등)"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'subscribe':
                code = data.get('code')
                if code:
                    await self.add_subscription(code)
        except Exception as e:
            print(f"[StockConsumer] Receive Error: {e}")

    async def add_subscription(self, raw_code):
        """특정 종목 구독 및 그룹 가입 공통 로직"""
        clean_code = re.sub(r'[^a-zA-Z0-9_.-]', '', str(raw_code))[:100]
        group_name = f"stock_{clean_code}"
        
        if clean_code not in self.subscribed_stocks:
            # 1. Redis 그룹 가입
            await self.channel_layer.group_add(group_name, self.channel_name)
            self.subscribed_stocks.add(clean_code)
            
            # 2. 마스터(KIS Client)에게 구독 요청
            await kis_client.subscribe(clean_code)
            
            if clean_code not in StockConsumer._logged_stocks:
                print(f"[DEBUG] Subscribed to group: {group_name}")
                StockConsumer._logged_stocks.add(clean_code)

    async def disconnect(self, close_code):
        # 모든 구독 그룹에서 탈퇴
        for code in self.subscribed_stocks:
            group_name = f"stock_{code}"
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
        print(f"[StockConsumer] Client disconnected. Cleared {len(self.subscribed_stocks)} subscriptions.")
        
        # 마스터에게 구독 취소 알림 (시청자 수 감소)
        # 중요: 서버의 "Total watchers" 카운트를 정확히 관리하기 위해 필수입니다.
        for code in self.subscribed_stocks:
             await kis_client.unsubscribe(code)

    async def stock_update(self, event):
        """
        StockMaster가 Redis 그룹으로 쏜 데이터를 받아서
        연결된 개별 클라이언트(브라우저)에게 전달
        """
        # data structure: { 'type': 'stock_update', 'data': { ... } }
        # We need to send pure JSON
        if 'data' in event:
             await self.send(text_data=json.dumps(event['data']))
        else:
             # Fallback if event is already the data payload
             await self.send(text_data=json.dumps(event))
