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
from .news_collector import NewsCollector

logger = logging.getLogger(__name__)

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

    async def analyze_single_stock_incremental(self, code, name):
        """
        신규 진입 종목 1개에 대해 '증분 테마 분석'을 수행한다.
        기존에 생성된 테마 목록과 비교하여, 기존 테마에 편입시키거나 새로운 마이크로 테마를 생성한다.
        """
        print(f"[ThemeService] Incremental Analysis for {name} ({code})...")
        
        # 1. 오늘 날짜의 기존 테마 목록 조회 (Sync to Async)
        today = date.today()
        existing_themes = await sync_to_async(list)(Theme.objects.filter(date=today))
        
        existing_themes_prompt = []
        for t in existing_themes:
            existing_themes_prompt.append(f"- ID {t.id}: {t.name} ({t.description})")
            
        existing_themes_text = "\n".join(existing_themes_prompt)
        
        if not existing_themes_text:
            print("[ThemeService] No existing themes found for today. Skipping incremental.")
            return False

        # 2. 뉴스 수집
        news_list = self.news_collector.collect_news(name)
        
        # 3. LLM 프롬프트 구성
        prompt = f"""
        다음은 현재 실시간 급등 순위에 새로 진입한 주식 '{name}'({code})과 관련 뉴스입니다.
        
        [뉴스 헤드라인]
        {json.dumps(news_list, ensure_ascii=False, indent=2)}
        
        [현재 활성화된 테마 목록]
        {existing_themes_text}
        
        [지시사항]
        이 종목이 위 '현재 활성화된 테마' 중 하나에 강력하게 속한다면 그 **테마 ID(숫자)만** 반환하세요.
        만약 속하지 않고, 이 종목만의 새로운 강력한 '단기 이슈/테마'가 있다면 새로운 테마명으로 정의하세요.
        단순한 등락이나 특별한 이유가 없다면 "None"을 반환하세요.
        
        **주의**: 'reason' 필드에는 테마 ID나 내부 시스템 정보를 절대 언급하지 마세요. 사용자가 이해할 수 있는 자연어 설명만 포함하세요.
        
        [응답 형식 (JSON Only)]
        {{
            "action": "JOIN" | "CREATE" | "NONE",
            "theme_id": 123 (JOIN일 경우 테마 ID),
            "new_theme_name": "새로운 테마명 (CREATE일 경우)",
            "new_theme_desc": "새로운 테마 설명 (CREATE일 경우)",
            "reason": "테마 편입 또는 생성 이유 (한 문장)"
        }}
        """

        # 4. LLM 호출
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial analyst. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            
            # Robust JSON extraction using Regex
            import re
            match = re.search(r'(\{.*\})', content, re.DOTALL)
            if match:
                json_str = match.group(1)
                result = json.loads(json_str)
            else:
                # Fallback: Try raw content if regex fails
                result = json.loads(content)

            
            action = result.get("action")
            reason = result.get("reason", "")
            
            print(f"[ThemeService] LLM Decision for {name}: {action}")
            
            if action == "NONE":
                return False
                
            # 5. DB 업데이트 (Sync to Async)
            await sync_to_async(self._save_incremental_result)(code, name, result, today)
            return True
            
        except Exception as e:
            logger.error(f"Incremental Analysis Failed: {e}")
            print(f"Error ({name}): {e}")
            return False

    def _save_incremental_result(self, code, name, result, today):
        action = result.get("action")
        reason = result.get("reason", "")
        
        stock_obj, _ = StockInfo.objects.get_or_create(
            short_code=code, defaults={'name': name}
        )
        
        if action == "JOIN":
            theme_id = result.get("theme_id")
            try:
                theme_obj = Theme.objects.get(id=theme_id)
                # 이미 있는지 확인
                if not ThemeStock.objects.filter(theme=theme_obj, stock=stock_obj).exists():
                    ThemeStock.objects.create(theme=theme_obj, stock=stock_obj, reason=reason)
                    print(f"[ThemeService] Joined existing theme: {theme_obj.name}")
            except Theme.DoesNotExist:
                print(f"[ThemeService] Theme ID {theme_id} not found.")

        elif action == "CREATE":
            new_name = result.get("new_theme_name")
            new_desc = result.get("new_theme_desc")
            if new_name:
                theme_obj = Theme.objects.create(
                    name=new_name,
                    description=new_desc,
                    date=today
                )
                ThemeStock.objects.create(theme=theme_obj, stock=stock_obj, reason=reason)
                print(f"[ThemeService] Created new theme: {new_name}")
