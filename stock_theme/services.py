import os
import json
import logging
import urllib.request
import urllib.parse
from datetime import date
from asgiref.sync import sync_to_async
from django.db import transaction
from openai import OpenAI
from stock_price.services.kis_rest_client import kis_rest_client
from stock_theme.models import Theme, ThemeStock
from stock_price.models import StockInfo

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

class ThemeAnalyzeService:
    def __init__(self):
        self.news_collector = NewsCollector()
        self.client = OpenAI(
            api_key=os.getenv("upstage_secret_key"),
            base_url="https://api.upstage.ai/v1"
        )
        self.model = "solar-pro2"

    async def analyze_and_save_themes(self):
        """
        1. KIS API에서 급등주/거래량 상위 종목 수집
        2. 각 종목별 뉴스 수집 (Sim 4 + Date 2)
        3. LLM(Solar Pro)에게 "Micro-Theme" 분석 요청
        4. DB 저장
        """
        # 1. 데이터 수집
        print("[ThemeService] Fetching stock rankings...")
        fluctuation_ranks = await kis_rest_client.get_fluctuation_rank()
        if not fluctuation_ranks:
            logger.error("Failed to fetch fluctuation ranks.")
            return

        # 상위 30개 분석 (히트맵 구성을 위해 확장)
        top_stocks = fluctuation_ranks[:30]
        
        analysis_targets = []
        total_stocks = len(top_stocks)
        
        for idx, item in enumerate(top_stocks, 1):
            name = item.get('hts_kor_isnm')
            code = item.get('stck_shrn_iscd')
            
            print(f"[ThemeService] Collecting news for {name} ({idx}/{total_stocks})...")
            
            # 뉴스 수집
            news_list = self.news_collector.collect_news(name)
            
            analysis_targets.append({
                "code": code,
                "name": name,
                "news_headlines": news_list
            })

        # 2. LLM 프롬프트 구성 (Micro-Theme 지향)
        prompt = f"""
        다음은 오늘 급등한 주식 종목 30개와 관련 뉴스 헤드라인입니다.
        이 정보를 바탕으로, 오늘 시장을 주도한 **'구체적이고 단기적인 이슈 테마(Micro-Theme)'**를 추출해주세요.

        [데이터]
        {json.dumps(analysis_targets, ensure_ascii=False, indent=2)}

        [분석 지침]
        1. **Broad Sector 지양**: '반도체', '화학', '자동차' 같은 너무 넓은 대분류로 묶지 마세요.
        2. **Specific Issue 지향**: 뉴스를 분석하여 **'트럼프 관세 부과', '홍해 물류 대란', '비만치료제 임상 성공'** 같이 구체적인 사건/이슈 중심으로 테마명을 정하세요.
        3. **연관성**: 같은 이슈로 묶이는 종목끼리 그룹화하세요. 만약 독립적인 이슈라면 단독 테마로 구성해도 좋습니다.
        4. **이유 요약**: 해당 종목이 왜 그 테마에 속하는지 뉴스에 기반하여 한 문장으로 명확히 설명하세요.

        [응답 형식 (JSON Only)]
        {{
            "themes": [
                {{
                    "name": "구체적인 테마명 (예: 초전도체 LK-99 검증)",
                    "description": "테마 발생 원인 및 시장 상황 요약",
                    "stocks": [
                        {{"code": "종목코드", "name": "종목명", "reason": "뉴스에 기반한 구체적 등락 사유"}}
                    ]
                }}
            ]
        }}
        """

        # 3. LLM 호출
        print(f"[ThemeService] Requesting analysis to {self.model}...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful financial analyst specializing in Korean stock market trends. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            
            content = response.choices[0].message.content
            # Markdown code block 제거 (혹시 포함될 경우)
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content)
            
        except Exception as e:
            logger.error(f"LLM Analysis Failed: {e}")
            print(f"Error: {e}")
            return

        # 4. DB 저장
        await sync_to_async(self._save_to_db)(result.get("themes", []))
        print("[ThemeService] Analysis completed and saved.")

    def _save_to_db(self, themes_data):
        today = date.today()
        
        with transaction.atomic():
            # (옵션) 오늘자 기존 분석 데이터가 있다면 삭제 후 재생성? or 추가?
            # 여기서는 중복 방지를 위해 오늘자 테마 삭제 후 재생성 전략 사용
            Theme.objects.filter(date=today).delete()

            for theme_item in themes_data:
                theme_obj = Theme.objects.create(
                    name=theme_item['name'],
                    description=theme_item['description']
                )

                for stock_item in theme_item.get('stocks', []):
                    # StockInfo가 DB에 없으면 생성 (혹은 건너뛰기)
                    stock_obj, created = StockInfo.objects.get_or_create(
                        short_code=stock_item['code'],
                        defaults={'name': stock_item['name']}
                    )
                    
                    ThemeStock.objects.create(
                        theme=theme_obj,
                        stock=stock_obj,
                        reason=stock_item.get('reason', '')
                    )
