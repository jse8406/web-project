from django.shortcuts import render
from django.views.generic import ListView
from .models import Theme

from stock_price.services.kis_rest_client import kis_rest_client
from stock_price.utils import is_market_open

class DailyThemeListView(ListView):
    model = Theme
    template_name = 'stock_theme/theme_list.html'
    context_object_name = 'themes'
    
    def get_queryset(self):
        # 최신 날짜순, 같은 날짜 내에서는 분석 시각 역순
        return Theme.objects.prefetch_related('stocks', 'stocks__stock').all()

class ThemeHeatmapView(ListView):
    template_name = 'stock_theme/theme_heatmap.html'
    context_object_name = 'themes'

    def get_queryset(self):
        # 오늘(혹은 가장 최신) 날짜의 테마들만 가져옴 (Meta ordering이 -date이므로 first가 최신)
        last_theme = Theme.objects.first()
        if not last_theme:
            return Theme.objects.none()
        return Theme.objects.filter(date=last_theme.date).prefetch_related('stocks', 'stocks__stock')

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
                    code = item.get('stck_shrt_cd') or item.get('STCK_SHRT_CD')
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

        # [Fallback Logic] If Ranking API returned no data (e.g. Weekend), fetch individual prices manually.
        # This prevents the "0.00%" issue when Ranking API is silent.
        if not top_30_list:
            print("[Heatmap] Ranking API returned empty. Falling back to individual stock price fetching...")
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def fetch_price(code):
                try:
                    data = kis_rest_client.get_current_price(code)
                    if data:
                        return code, data
                except:
                    pass
                return code, None

            # Fetch for ALL target stock codes (Theme stocks)
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_code = {executor.submit(fetch_price, code): code for code in stock_codes}
                for future in as_completed(future_to_code):
                    code, data = future.result()
                    if data:
                        initial_price_data[code] = {
                            'rate': data.get('prdy_ctrt', '0.00'),
                            'current_price': data.get('stck_prpr', '0'),
                            'volume': data.get('acml_vol', '0'),
                        }
            print(f"[Heatmap] Fallback Fetch Complete. Loaded {len(initial_price_data)} stocks.")

        context['is_market_open'] = is_market_open()
        context['target_stock_codes'] = list(stock_codes)
        context['top_30_list'] = top_30_list
        context['initial_price_data'] = initial_price_data
        return context
