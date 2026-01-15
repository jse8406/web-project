import os
import asyncio
import json
# from auth.kis_auth import get_current_price
from .services import kis_rest_client
from django.views.generic import TemplateView, View
from django.template.response import TemplateResponse

class StockRealtimeView(TemplateView):
    template_name = "stock_realtime.html"

class StockDetailView(TemplateView):
    template_name = "stock_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_code = self.kwargs.get('stock_code', '005930') # Default Samsung Electronics
        
        # Fetch data
        data = kis_rest_client.get_current_price(stock_code)
        
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
        return context

class StockRankingView(View):
    template_name = "stock_ranking.html"

    async def get(self, request, *args, **kwargs):
        # 비동기로 API 호출 (병렬 처리)
        rank_fluctuation, rank_volume, rank_theme = await asyncio.gather(
            kis_rest_client.get_fluctuation_rank(),
            kis_rest_client.get_volume_rank(),
            kis_rest_client.get_theme_rank()
        )

        context = {
            "rank_fluctuation": rank_fluctuation if rank_fluctuation else [],
            "rank_volume": rank_volume if rank_volume else [],
            "rank_theme": rank_theme if rank_theme else [],
        }

        return TemplateResponse(request, self.template_name, context)
