from django.shortcuts import render
from django.views.generic import ListView, View
from django.template.response import TemplateResponse
from asgiref.sync import sync_to_async
from .models import Theme
import json
import asyncio
from django.db.models import Count

from stock_price.services.kis_rest_client import kis_rest_client
from stock_price.utils import is_market_open

class DailyThemeListView(ListView):
    model = Theme
    template_name = 'stock_theme/theme_list.html'
    context_object_name = 'themes'
    
    def get_queryset(self):
        # 1. Get Selected Date from URL
        selected_date_str = self.request.GET.get('date')
        
        # 2. Base Queryset
        #theme에 대한 stocks와 theme stocks에 대한 stock을 미리 가져옴
        queryset = Theme.objects.prefetch_related('stocks', 'stocks__stock').all()
        
        # 3. Filter
        if selected_date_str:
            queryset = queryset.filter(date=selected_date_str)
        else:
            # Default to the latest date available
            latest_theme = Theme.objects.order_by('-date').first()
            if latest_theme:
                queryset = queryset.filter(date=latest_theme.date)
                
        # 4. Sort by Stock Count (Descending)
        queryset = queryset.annotate(stock_count=Count('stocks')).order_by('-stock_count', '-created_at')
                
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get list of available dates for the dropdown/navigation
        # ValuesList returns distinct dates, ordered by latest first
        dates = Theme.objects.values_list('date', flat=True).distinct().order_by('-date')
        
        # Current selected date
        selected_date = self.request.GET.get('date')
        if not selected_date and dates:
            selected_date = str(dates[0])
            
        context['available_dates'] = dates
        context['selected_date'] = selected_date
        return context

class ThemeHeatmapView(View):
    template_name = 'stock_theme/theme_heatmap.html'

    async def get(self, request, *args, **kwargs):
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

        # 2. Parallel Execution: DB Fetch + API Ranking Fetch
        db_task = asyncio.create_task(get_theme_data())
        rank_task = asyncio.create_task(kis_rest_client.get_fluctuation_rank())
        
        # Wait for both
        (latest_themes, stock_codes), rank_data = await asyncio.gather(db_task, rank_task)
        
        # 3. Process Ranking Data
        top_30_list = []
        initial_price_data = {}
        
        if rank_data:
            for item in rank_data:
                code = item.get('stck_shrt_cd') or item.get('STCK_SHRT_CD') or item.get('stck_shrn_iscd') or item.get('STCK_SHRN_ISCD')
                name = item.get('hts_kor_isnm') or item.get('HTS_KOR_ISNM') or code
                rate = item.get('prdy_ctrt') or item.get('PRDY_CTRT') or "0.00"
                current_price = item.get('stck_prpr') or item.get('STCK_PRPR') or "-"

                if code:
                    stock_codes.add(code)
                    top_30_list.append({
                        'code': code,
                        'name': name,
                        'rate': rate,
                        'price': current_price
                    })
                    
                    initial_price_data[code] = {
                        'rate': rate,
                        'current_price': current_price,
                        'volume': '0'
                    }
        
        # 4. Fetch Missing Stock Prices (Async)
        current_keys = set(initial_price_data.keys())
        missing_codes = list(stock_codes - current_keys)
        
        if missing_codes:
            # Create fetch tasks for all missing codes
            tasks = [kis_rest_client.get_current_price_async(code) for code in missing_codes]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for code, result in zip(missing_codes, results):
                if isinstance(result, Exception) or not result:
                    continue
                    
                data = result
                initial_price_data[code] = {
                    'rate': data.get('prdy_ctrt', '0.00'),
                    'current_price': data.get('stck_prpr', '0'),
                    'volume': data.get('acml_vol', '0'),
                }

        # 5. Build Context & Return Response
        context = {
            'themes': latest_themes,
            'is_market_open': is_market_open(),
            'target_stock_codes': json.dumps(list(stock_codes)),
            'top_30_list': json.dumps(top_30_list),
            'initial_price_data': json.dumps(initial_price_data)
        }
        
        return TemplateResponse(request, self.template_name, context)
