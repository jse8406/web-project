import logging
from django.core.cache import cache
from .analyze_service import ThemeAnalyzeService
from stock_theme.models import Theme, ThemeStock
from stock_price.models import StockInfo

logger = logging.getLogger(__name__)

class ThemeSyncService:
    """
    실시간 랭킹과 테마 분석 데이터 간의 동기화를 담당하는 서비스.
    Redis 캐시를 사용하여 '신규 진입 종목'을 감지하고, 증분 분석(Incremental Analysis)을 수행한다.
    """
    CACHE_KEY_TOP30 = "theme:current_top_30"
    CACHE_TIMEOUT = 60 * 60 * 24  # 24시간 (장 마감 후 초기화 고려)

    def __init__(self):
        self.analyze_service = ThemeAnalyzeService()

    def get_cached_top30(self):
        """Redis에서 이전에 분석했던 Top 30 종목 코드 집합(Set)을 가져온다."""
        cached_data = cache.get(self.CACHE_KEY_TOP30)
        if cached_data is None:
            return set()
        return cached_data

    def update_cached_top30(self, stock_codes_list):
        """새로운 Top 30 리스트로 캐시를 갱신한다."""
        cache.set(self.CACHE_KEY_TOP30, set(stock_codes_list), self.CACHE_TIMEOUT)

    async def detect_and_process_changes(self, current_rank_data):
        """
        [Core Logic]
        1. 현재 랭킹 데이터(current_rank_data)와 Redis 캐시를 비교.
        2. 새로운 진입 종목(New Entrants)을 식별.
        3. 각 신규 종목에 대해 '증분 테마 분석' 수행.
        4. 결과를 DB에 저장하고 캐시 업데이트.
        
        Args:
            current_rank_data (list): KIS API get_fluctuation_rank() 결과 리스트
        Returns:
            list: 새로 분석되어 추가된 종목 코드 리스트
        """
        if not current_rank_data:
            return []

        # 1. Diff Calculation
        current_codes = {item['stck_shrn_iscd'] for item in current_rank_data if 'stck_shrn_iscd' in item}
        cached_codes = self.get_cached_top30()
        
        new_entrants_codes = current_codes - cached_codes
        
        if not new_entrants_codes:
            # 변경 없음
            return []

        # [Cold Start Check]
        from datetime import date
        today = date.today()
        # Sync-to-Async DB check
        from asgiref.sync import sync_to_async
        themes_exist = await sync_to_async(Theme.objects.filter(date=today).exists)()

        if not themes_exist:
            logger.info("[ThemeSync] No themes found for today. Triggering FULL BATCH analysis.")
            await self.analyze_service.analyze_and_save_themes()
            
            # Update cache with ALL current codes (since we just analyzed them all)
            all_current_codes = {item['stck_shrn_iscd'] for item in current_rank_data if 'stck_shrn_iscd' in item}
            self.update_cached_top30(all_current_codes)
            
            # Broadcast Refresh
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                "theme_global",
                {
                    "type": "theme_update",
                    "data": {"message": "Full theme analysis completed", "new_stocks": []}
                }
            )
            return list(all_current_codes)

        logger.info(f"[ThemeSync] New entrants detected: {new_entrants_codes}")
        
        processed_stocks = []
        
        # 2. Process New Entrants
        # 한꺼번에 너무 많이 요청하면 LLM 부하가 걸리므로, 최대 5개까지만 처리 (Throttling)
        targets_to_process = list(new_entrants_codes)[:5] 
        
        # Mapping for quick access
        code_to_data = {item['stck_shrn_iscd']: item for item in current_rank_data}

        for code in targets_to_process:
            stock_data = code_to_data.get(code)
            name = stock_data.get('hts_kor_isnm', 'Unknown')
            
            # 3. Incremental Analysis (LLM)
            # 기존 analyze_service에 'analyze_single_stock' 메서드를 추가해야 함.
            success = await self.analyze_service.analyze_single_stock_incremental(code, name)
            
            if success:
                processed_stocks.append(code)
                
        # 4. Update Cache (성공한 것들만 캐시에 추가하여 다음번에 중복 분석 방지)
        # 실패한 종목은 캐시에 넣지 않음 -> 다음 루프때 다시 시도.
        # 단, 계속 실패하면 무한 루프 돌 수 있으므로 별도 '실패 캐시' 관리 필요하지만 일단 단순화.
        if processed_stocks:
            updated_cache = cached_codes.union(set(processed_stocks))
            self.update_cached_top30(updated_cache)
            logger.info(f"[ThemeSync] Successfully processed & cached: {processed_stocks}")
            
            # 5. Broadcast Update to WebSocket (Global Group)
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            
            await channel_layer.group_send(
                "theme_global",
                {
                    "type": "theme_update",
                    "data": {
                        "message": "New theme data available",
                        "new_stocks": processed_stocks
                    }
                }
            )
            
        return processed_stocks
