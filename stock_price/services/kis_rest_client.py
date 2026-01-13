import requests
import os
from auth.kis_auth import get_access_token
from dotenv import load_dotenv

# .env 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

class KISRestClient:
    """
    한국투자증권 REST API (HTTP 요청) 전용 클라이언트
    """
    def __init__(self):
        self.app_key = os.getenv('g_appkey')
        self.app_secret = os.getenv('g_appsecret')
        self.domain = "https://openapi.koreainvestment.com:9443"
        self.access_token = None

    def _get_headers(self, tr_id, tr_cont=''):
        """공통 헤더 생성 헬퍼 메서드"""
        token_data = get_access_token()
        if not token_data or 'access_token' not in token_data:
            print("[Stock Service] Token is missing")
            return None
        
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token_data['access_token']}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "tr_cont": tr_cont,
            "custtype": "P",
        }

    def get_fluctuation_rank(self, limit=30):
        """등락률 순위 조회 (상위 30개)"""
        headers = self._get_headers("FHPST01700000")
        if not headers: return None

        url = f"{self.domain}/uapi/domestic-stock/v1/ranking/fluctuation"
        
        params = {
            "fid_rsfl_rate2": "",
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20170",
            "fid_input_iscd": "0000",
            "fid_rank_sort_cls_code": "0", # 0: 상승률순
            "fid_input_cnt_1": "0",
            "fid_prc_cls_code": "1",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0",
            "fid_rsfl_rate1": "",
        }

        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            data = r.json()
            
            if data.get('rt_cd') != '0':
                print(f"[Stock Service] Fluctuation Rank Error: {data.get('msg1')}")
                return None
                
            return data.get('output', [])
        except Exception as e:
            print(f"[Stock Service] Request Error: {e}")
            return None

    def get_volume_rank(self):
        """거래량 순위 조회"""
        headers = self._get_headers("FHPST01710000")
        if not headers: return None

        url = f"{self.domain}/uapi/domestic-stock/v1/quotations/volume-rank"
        
        params = {
           "FID_COND_MRKT_DIV_CODE": "J",
           "FID_COND_SCR_DIV_CODE": "20171",
           "FID_INPUT_ISCD": "0000",
           "FID_DIV_CLS_CODE": "0",
           "FID_BLNG_CLS_CODE": "0",
           "FID_TRGT_CLS_CODE": "111111111",
           "FID_TRGT_EXLS_CLS_CODE": "0000000000",
           "FID_INPUT_PRICE_1": "",
           "FID_INPUT_PRICE_2": "",
           "FID_VOL_CNT": "",
           "FID_INPUT_DATE_1": ""
        }
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            data = r.json()

            if data.get('rt_cd') == '0':
                output = data.get('output', [])
                # 템플릿 호환성을 위해 키 소문자 변환
                return [{k.lower(): v for k, v in item.items()} for item in output]
            else:
                print(f"[Stock Service] Volume Rank Error: {data.get('msg1')}")
                return None
        except Exception as e:
            print(f"[Stock Service] Request Error: {e}")
            return None

    def get_current_price(self, iscd):
        """특정 종목 현재가 조회"""
        headers = self._get_headers("FHKST01010100")
        if not headers: return None

        url = f"{self.domain}/uapi/domestic-stock/v1/quotations/inquire-price"
        
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": iscd
        }
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=5)
            data = r.json()
            if data.get('rt_cd') == '0':
                return data.get('output', {})
            return None
        except Exception as e:
            print(f"[Stock Service] Get Price Error ({iscd}): {e}")
            return None

    def get_theme_rank(self):
        """주요 테마별 등락률 순위"""
        # 테마 정의는 나중에 DB나 설정 파일로 뺄 수도 있습니다.
        themes = {
            "반도체": ["005930", "000660", "042700"],
            "2차전지": ["373220", "006400", "003670", "247540"],
            "자동차": ["005380", "000270", "012330"],
            "인터넷/플랫폼": ["035420", "035720"],
            "바이오": ["207940", "068270", "019170"],
            "엔터/콘텐츠": ["352820", "041510", "122870"],
            "금융": ["105560", "055550", "086790"],
            "방산": ["012450", "042660"],
        }
        
        theme_results = []
        
        for theme_name, codes in themes.items():
            total_rate = 0
            count = 0
            for code in codes:
                data = self.get_current_price(code) # 내부 메서드 호출
                if data and 'prdy_ctrt' in data:
                    try:
                        rate = float(data['prdy_ctrt'])
                        total_rate += rate
                        count += 1
                    except:
                        continue
            
            if count > 0:
                avg_rate = total_rate / count
                theme_results.append({
                    'name': theme_name,
                    'rate': round(avg_rate, 2),
                    'is_rising': avg_rate > 0
                })
                
        theme_results.sort(key=lambda x: x['rate'], reverse=True)
        return theme_results

# 싱글톤 인스턴스 생성
kis_rest_client = KISRestClient()