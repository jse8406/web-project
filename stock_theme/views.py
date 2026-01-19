from django.shortcuts import render
from django.views.generic import ListView
from .models import Theme
import json
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
        queryset = Theme.objects.prefetch_related('stocks', 'stocks__stock').all()
        
        # 3. Filter
        if selected_date_str:
            queryset = queryset.filter(date=selected_date_str)
        else:
            # Default to the latest date available
            latest_theme = Theme.objects.order_by('-date').first()
            if latest_theme:
                queryset = queryset.filter(date=latest_theme.date)
                
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

class ThemeHeatmapView(ListView):
    template_name = 'stock_theme/theme_heatmap.html'
    context_object_name = 'themes'



    def get_queryset(self):
        # 오늘(혹은 가장 최신) 날짜의 테마들만 가져옴 (Meta ordering이 -date이므로 first가 최신)
        last_theme = Theme.objects.first()
        if not last_theme:
            return Theme.objects.none()
        
        # [Filter] Show only themes with >= 3 stocks (Major Themes)
        return Theme.objects.filter(date=last_theme.date).annotate(stock_count=Count('stocks')).filter(stock_count__gte=3).prefetch_related('stocks', 'stocks__stock')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. 가장 최신의 테마 날짜 기준
        latest_date_themes = self.get_queryset()
        
        stock_codes = set()
        for theme in latest_date_themes:
            for theme_stock in theme.stocks.all():
                stock_codes.add(theme_stock.stock.short_code)
        
        # 2. 실시간 상승 Top 30 종목들 (Sync 호출) - 초기 데이터 소스로 사용
        top_30_list = []
        initial_price_data = {}

        try:
            rank_data = kis_rest_client.get_fluctuation_rank_sync()
            if rank_data:
                for item in rank_data:
                    # Key compatibility: Handle both upper and lower case cases just in case
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
                        
                        # Populate Initial Price Data from Ranking
                        initial_price_data[code] = {
                            'rate': rate,
                            'current_price': current_price,
                            'volume': '0'
                        }
        except Exception as e:
            print(f"Error fetching top 30 rank in heatmap view: {e}")

        # [Supplementary Logic] Fetch prices for stocks NOT in the Ranking/Top30
        # If Ranking API returned data, it only covers ~30 stocks. 
        # But we might have other stocks in our Themes that are not in Top 30.
        # We need to fetch their initial prices too, otherwise they show 0.00% until WS updates.
        
        current_keys = set(initial_price_data.keys())
        missing_codes = stock_codes - current_keys

        if missing_codes:
            print(f"[Heatmap] Fetching {len(missing_codes)} missing stock prices...")
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def fetch_price(code):
                try:
                    data = kis_rest_client.get_current_price(code)
                    if data:
                        return code, data
                except:
                    pass
                return code, None

            # Fetch for MISSING stock codes only
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_code = {executor.submit(fetch_price, code): code for code in missing_codes}
                for future in as_completed(future_to_code):
                    try:
                        code, data = future.result()
                        if data:
                            initial_price_data[code] = {
                                'rate': data.get('prdy_ctrt', '0.00'),
                                'current_price': data.get('stck_prpr', '0'),
                                'volume': data.get('acml_vol', '0'),
                            }
                    except Exception as exc:
                        print(f"Stock fetch generated an exception: {exc}")
                        
            print(f"[Heatmap] Supplementary Fetch Complete.")

        # Final Context Data

        context['is_market_open'] = is_market_open()
        context['target_stock_codes'] = json.dumps(list(stock_codes))
        context['top_30_list'] = json.dumps(top_30_list)
        context['initial_price_data'] = json.dumps(initial_price_data)
        return context
