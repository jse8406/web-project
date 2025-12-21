import json
import re
from channels.generic.websocket import AsyncWebsocketConsumer
from .stock_master import stock_master

class StockConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # URL에서 stock_code 추출
        self.stock_code = self.scope['url_route']['kwargs'].get('stock_code')
        clean_code = re.sub(r'[^a-zA-Z0-9_.-]', '', str(self.stock_code))[:100]
        self.group_name = f"stock_{clean_code}"
        print(f"[DEBUG] stock_code(raw): {self.stock_code}")
        print(f"[DEBUG] group_name: {self.group_name}")

        # 1. Redis 그룹에 가입
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        print(f"[StockConsumer] Client connected to {self.group_name}")
        
        # 2. 마스터에게 구독 요청 (이미 구독 중이면 무시됨, 연결 안되어있으면 연결 시작)
        await stock_master.subscribe(self.stock_code)

    async def disconnect(self, close_code):
        # Redis 그룹에서 탈퇴
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        print(f"[StockConsumer] Client disconnected from {self.group_name}")
        
        # (선택) 마스터에게 구독 취소 알림 (지금은 구현 X)
        await stock_master.unsubscribe(self.stock_code)

    async def stock_update(self, event):
        """
        StockMaster가 Redis 그룹으로 쏜 데이터를 받아서
        연결된 개별 클라이언트(브라우저)에게 전달
        type: 'stock_update'와 매핑됨
        """
        data = event['data']
        # 이미 JSON 시리얼라이즈 된 데이터(dict)가 옴
        await self.send(text_data=json.dumps(data))
