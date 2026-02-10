from django.shortcuts import render
from django.views.generic import ListView, View
from django.template.response import TemplateResponse
from asgiref.sync import sync_to_async
from .models import Theme
import json
import asyncio
from django.db.models import Count

from stock_price.services.kis_rest_client import kis_rest_client
from stock_price.utils import is_market_open, is_market_open_async

import time
import logging

logger = logging.getLogger(__name__)

class DailyThemeListView(ListView):
    model = Theme
    template_name = 'stock_theme/theme_list.html'
    context_object_name = 'themes'
    
    def get_queryset(self):
        start_time = time.time()
        
        # 1. Get Selected Date from URL
        selected_date_str = self.request.GET.get('date')
        
        # 2. Base Queryset
        #theme에 대한 stocks와 theme stocks에 대한 stock을 미리 가져옴
        queryset = Theme.objects.prefetch_related('stocks', 'stocks__stock').all()
        
        # 3. Filter
        if selected_date_str:
            try:
                from django.core.exceptions import ValidationError
                queryset = queryset.filter(date=selected_date_str)
            except ValidationError:
                queryset = queryset.none()
        else:
            # Default to the latest date available
            latest_theme = Theme.objects.order_by('-date').first()
            if latest_theme:
                queryset = queryset.filter(date=latest_theme.date)
                
        # 4. Sort by Stock Count (Descending)
        queryset = queryset.annotate(stock_count=Count('stocks')).order_by('-stock_count', '-created_at')
        
        end_time = time.time()
        logger.info(f"[DailyThemeListView] get_queryset took {end_time - start_time:.4f}s")
        return queryset

    def get_context_data(self, **kwargs):
        start_time = time.time()
        context = super().get_context_data(**kwargs)
        
        # Current selected date
        selected_date = self.request.GET.get('date')
        if not selected_date:
            # If no date selected, default to the latest date available
            latest_theme = Theme.objects.order_by('-date').first()
            if latest_theme:
                selected_date = str(latest_theme.date)
            
        context['selected_date'] = selected_date
        
        end_time = time.time()
        logger.info(f"[DailyThemeListView] get_context_data took {end_time - start_time:.4f}s")
        return context

class ThemeHeatmapView(View):
    template_name = 'stock_theme/theme_heatmap.html'

    async def get(self, request, *args, **kwargs):
        start_total = time.time()
        
        # 1. Define Async DB Fetcher
        @sync_to_async
        def get_theme_data():
            # Get latest theme date
            last_theme = Theme.objects.first()
            if not last_theme:
                return [], set()

            # Filter logic: date=last_theme.date, stock_count >= 3
            themes_qs = Theme.objects.filter(date=last_theme.date).annotate(stock_count=Count('stocks')).filter(stock_count__gte=3).prefetch_related('stocks', 'stocks__stock')
            
            # Force evaluation to list to perform DB query inside this sync wrapper
            # and extract stock codes safely.
            themes_list = list(themes_qs)
            
            codes = set()
            for theme in themes_list:
                for theme_stock in theme.stocks.all():
                    codes.add(theme_stock.stock.short_code)
            
            return themes_list, codes

        # 2. Fetch DB Data First (Fast enough to await sequentially)
        step1_start = time.time()
        latest_themes, stock_codes = await get_theme_data()
        logger.info(f"[ThemeHeatmapView] DB Fetch took {time.time() - step1_start:.4f}s")
        
        # 3. Parallel Execution: Rank API + All Theme Stocks Price API + Market Status
        step2_start = time.time()
        
        task_rank = asyncio.create_task(kis_rest_client.get_fluctuation_rank())
        task_prices = asyncio.create_task(kis_rest_client.fetch_prices_batch(list(stock_codes)))
        task_market = asyncio.create_task(is_market_open_async())
        
        rank_data, batch_prices, is_open = await asyncio.gather(task_rank, task_prices, task_market)
        logger.info(f"[ThemeHeatmapView] Parallel API Fetch (Rank + {len(stock_codes)} Stocks + MarketStatus) took {time.time() - step2_start:.4f}s")
        
        # 4. Merge Data
        top_30_list = []
        initial_price_data = {}
        
        # 4-1. Process Rank Data (For Top 30 List + identifying overlapping stocks)
        if rank_data:
            for item in rank_data:
                code = item.get('stck_shrt_cd') or item.get('STCK_SHRT_CD') or item.get('stck_shrn_iscd') or item.get('STCK_SHRN_ISCD')
                name = item.get('hts_kor_isnm') or item.get('HTS_KOR_ISNM') or code
                rate = item.get('prdy_ctrt') or item.get('PRDY_CTRT') or "0.00"
                current_price = item.get('stck_prpr') or item.get('STCK_PRPR') or "-"

                if code:
                    top_30_list.append({
                        'code': code,
                        'name': name,
                        'rate': rate,
                        'price': current_price
                    })
                    
                    # If this stock is in our target theme list, populate price data
                    if code in stock_codes:
                        initial_price_data[code] = {
                            'rate': rate,
                            'current_price': current_price,
                            'volume': '0' # Rank API might not give volume in same format, or we ignore
                        }
        
        # 4-2. Process Batch Price Data (Fill in the rest or overwrite)
        if batch_prices:
            for code, data in batch_prices.items():
                # If we prefer the dedicated price API data (usually more detailed), execute this:
                # Or if we only want to fill missing: if code not in initial_price_data:
                
                # Dedicated API (inquire-price) is reliable, so let's use it for all theme stocks
                initial_price_data[code] = {
                    'rate': data.get('prdy_ctrt', '0.00'),
                    'current_price': data.get('stck_prpr', '0'),
                    'volume': data.get('acml_vol', '0'),
                }

        # 5. Build Context & Return Response
        context = {
            'themes': latest_themes,
            'is_market_open': is_open,
            'target_stock_codes': json.dumps(list(stock_codes)),
            'top_30_list': json.dumps(top_30_list),
            'initial_price_data': json.dumps(initial_price_data)
        }
        
        logger.info(f"[ThemeHeatmapView] Total Execution took {time.time() - start_total:.4f}s")
        return TemplateResponse(request, self.template_name, context)
