import os
import json
import logging
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
    def collect_news(self, stock_name):
        # TODO: 실제 뉴스 검색 API (Naver Open API 등) 연동 필요
        # user가 뉴스 API 키를 제공하면 여기에 requests.get(...) 로직 추가
        
        # 임시: 테마 분석 테스트를 위한 합성 데이터 리턴
        # 실제 서비스 시에는 이 부분을 실제 크롤링/API로 대체해야 함
        return [
            f"{stock_name}, 주가 급등... 관련 이슈 주목",
            f"특징주: {stock_name} 거래량 폭발, 이유는?",
            f"산업 동향: {stock_name} 등 관련 섹터 강세"
        ]

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
        2. 각 종목별 뉴스 수집 (현재는 Mock)
        3. LLM(Solar Pro)에게 테마 분석 요청
        4. DB 저장
        """
        # 1. 데이터 수집
        print("[ThemeService] Fetching stock rankings...")
        fluctuation_ranks = await kis_rest_client.get_fluctuation_rank()
        if not fluctuation_ranks:
            logger.error("Failed to fetch fluctuation ranks.")
            return

        # 상위 10개만 분석 (API 비용/속도 고려)
        top_stocks = fluctuation_ranks[:10]
        
        analysis_targets = []
        for item in top_stocks:
            name = item.get('hts_kor_isnm')
            code = item.get('stck_shrn_iscd')
            
            # 뉴스 수집
            news_list = self.news_collector.collect_news(name)
            
            analysis_targets.append({
                "code": code,
                "name": name,
                "news_headlines": news_list
            })

        # 2. LLM 프롬프트 구성
        prompt = f"""
        다음은 오늘 급등한 주식 종목들과 관련 뉴스 헤드라인입니다.
        이 정보를 바탕으로, 오늘 시장을 주도한 '핵심 테마'를 1~3개로 그룹화하고 요약해주세요.

        [데이터]
        {json.dumps(analysis_targets, ensure_ascii=False, indent=2)}

        [요청사항]
        1. 각 테마의 이름은 직관적이고 명확하게 (예: '2차전지', '초전도체', '정치 테마주').
        2. 해당 테마가 형성된 이유를 한 문장으로 요약.
        3. 각 테마에 속하는 종목들을 매핑.
        4. 반드시 아래 JSON 형식으로만 응답해주세요 (Markdown 코드블럭 없이).

        {{
            "themes": [
                {{
                    "name": "테마명",
                    "description": "테마 상승 이유 요약",
                    "stocks": [
                        {{"code": "종목코드", "name": "종목명", "reason": "이 종목이 해당 테마에 포함된 구체적 사유"}}
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
