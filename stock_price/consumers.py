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

        # 1. Global Group Join (For Theme Updates)
        await self.channel_layer.group_add("theme_global", self.channel_name)

        # URL에 코드가 있으면 즉시 구독 (Legacy/Detail Page)
        if self.url_stock_code:
            await self.add_subscription(self.url_stock_code)

    # ... (receive & add_subscription methods unchanged) ...

    async def disconnect(self, close_code):
        # Global Group Discard
        await self.channel_layer.group_discard("theme_global", self.channel_name)

        # 모든 구독 그룹에서 탈퇴
        for code in self.subscribed_stocks:
            group_name = f"stock_{code}"
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
        print(f"[StockConsumer] Client disconnected. Cleared {len(self.subscribed_stocks)} subscriptions.")
        
        # 마스터에게 구독 취소 알림 (시청자 수 감소)
        for code in self.subscribed_stocks:
             await kis_client.unsubscribe(code)

    async def stock_update(self, event):
        """
        StockMaster가 Redis 그룹으로 쏜 데이터를 받아서
        연결된 개별 클라이언트(브라우저)에게 전달
        """
        if 'data' in event:
             await self.send(text_data=json.dumps(event['data']))
        else:
             await self.send(text_data=json.dumps(event))

    async def theme_update(self, event):
        """
        ThemeSyncService가 'theme_global' 그룹으로 쏜 데이터를 전달
        """
        # event: {'type': 'theme_update', 'message': 'New theme added', 'stock': ...}
        await self.send(text_data=json.dumps(event))
