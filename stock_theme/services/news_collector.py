import os
import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

class NewsCollector:
    """
    종목별 관련 뉴스를 수집하는 클래스.
    현재는 실제 뉴스 API가 연결되지 않았으므로, 
    1) 추후 Naver/Google API 연동을 위한 인터페이스 정의
    2) (임시) 종목명 기반의 더미 뉴스 데이터 생성 
    역할을 수행합니다.
    """
    def _fetch_naver_news(self, query, display, sort):
        client_id = os.getenv("naver_client_id")
        client_secret = os.getenv("naver_secret")
        
        if not client_id or not client_secret:
            return []

        try:
            enc_text = urllib.parse.quote(query)
            url = f"https://openapi.naver.com/v1/search/news?query={enc_text}&display={display}&sort={sort}"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            response = urllib.request.urlopen(request, timeout=5)
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                items = data.get('items', [])
                
                cleaned_items = []
                for item in items:
                    title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                    desc = item['description'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                    cleaned_items.append(f"{title}") # 제목 위주로 전달 (요약은 LLM이)
                return cleaned_items
            return []
        except Exception as e:
            logger.error(f"Naver API Error ({sort}): {e}")
            return []

    def collect_news(self, stock_name):
        # 1. 관련도순 4개 (핵심 이슈 파악)
        sim_news = self._fetch_naver_news(stock_name, 4, 'sim')
        
        # 2. 최신순 2개 (속보성 이슈 파악)
        date_news = self._fetch_naver_news(stock_name, 2, 'date')
        
        # 중복 제거 및 합치기
        all_news = list(dict.fromkeys(sim_news + date_news))
        
        if not all_news:
             return [f"{stock_name} (Mock) 뉴스 데이터...", f"{stock_name} 관련 이슈 (Mock)"]
             
        return all_news
