import os
from dotenv import load_dotenv
import asyncio
import websockets
import json
from auth.kis_auth import get_current_price
from .services import kis_rest_client

# .env 파일에서 환경변수 로드
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

APP_KEY = os.getenv('g_appkey')
APP_SECRET = os.getenv('g_appsceret')
TR_ID = "H0STCNT0"  # 주식체결가 TR
STOCK_CODE = "005930"  # 예시: 삼성전자

async def get_realtime_stock_price():
    url = "wss://openapi.koreainvestment.com:9443/websocket"
    async with websockets.connect(url) as ws:
        senddata = {
            "header": {
                "appkey": APP_KEY,
                "appsecret": APP_SECRET,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": TR_ID,
                    "tr_key": STOCK_CODE
                }
            }
        }
        await ws.send(json.dumps(senddata))
        while True:
            data = await ws.recv()
            print(data)  # 실시간 체결가 데이터 출력

# 테스트용: python manage.py shell에서 아래 실행
# import asyncio; from api.views import get_realtime_stock_price; asyncio.run(get_realtime_stock_price())
from rest_framework import viewsets, status

# 실시간 주가 웹페이지 렌더링용 View
from django.views.generic import TemplateView

class StockRealtimeView(TemplateView):
    template_name = "stock_realtime.html"

class StockDetailView(TemplateView):
    template_name = "stock_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_code = self.kwargs.get('stock_code', '005930') # Default Samsung Electronics
        
        # Fetch data
        data = get_current_price(stock_code)
        
        # Load stock list to find the name
        stock_name = None
        try:
            # Assuming the file is at stock_price/static/stock_price/stock_list.json
            # When running with uvicorn directly, __file__ is stock_price/views.py
            base_dir = os.path.dirname(__file__)
            json_path = os.path.join(base_dir, 'static', 'stock_price', 'stock_list.json')
            
            # Debug print
            print(f"Loading stock list from: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                stock_list_data = json.load(f)
                results = stock_list_data.get('results', [])
                for item in results:
                    if item.get('short_code') == stock_code:
                        stock_name = item.get('name')
                        break
        except Exception as e:
            print(f"Error loading stock list: {e}")

        # If name not found in json, fallback to code or handle gracefully
        if not stock_name:
             stock_name = stock_code

        context['stock_code'] = stock_code
        context['stock_name'] = stock_name
        context['stock_data'] = data
        context['stock_data'] = data
        return context

class StockRankingView(TemplateView):
    template_name = "stock_ranking.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 상위 30개 등락률 순위
        rank_fluctuation = kis_rest_client.get_fluctuation_rank()
        # 상위 30개 거래량 순위
        rank_volume = kis_rest_client.get_volume_rank()
        # 테마별 순위
        rank_theme = kis_rest_client.get_theme_rank()

        context['rank_fluctuation'] = rank_fluctuation if rank_fluctuation else []
        context['rank_volume'] = rank_volume if rank_volume else []
        context['rank_theme'] = rank_theme if rank_theme else []
        
        return context

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User

@api_view(['GET'])
def hello_world(request):
    """
    간단한 테스트용 API 엔드포인트
    """
    return Response({
        'message': 'Hello, World!',
        'status': 'success'
    })

