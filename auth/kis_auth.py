import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import logging

# .env 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

APP_KEY = os.getenv('g_appkey')
APP_SECRET = os.getenv('g_appsecret')
DOMAIN = "https://openapi.koreainvestment.com:9443"

# 토큰 캐시 파일 경로 (프로젝트 루트에 저장)
TOKEN_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.kis_token_cache.json')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KIS Auth")

# Add a global variable to track if the cached token log has been displayed
_cached_token_logged = False


def _load_cached_token():
    """캐시 파일에서 토큰 정보를 로드"""
    if not os.path.exists(TOKEN_CACHE_FILE):
        return None
    try:
        with open(TOKEN_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load token cache: {e}")
        return None


def _save_token_cache(token_data):
    """토큰 정보를 캐시 파일에 저장"""
    try:
        with open(TOKEN_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(token_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Token cached to {TOKEN_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Failed to save token cache: {e}")


def _is_token_expired(token_data):
    """토큰이 만료되었는지 확인 (5분 여유를 둠)"""
    if not token_data or 'access_token_token_expired' not in token_data:
        return True
    try:
        # 만료 시간 형식: "2025-12-23 23:30:43"
        expired_str = token_data['access_token_token_expired']
        expired_dt = datetime.strptime(expired_str, "%Y-%m-%d %H:%M:%S")
        # 5분 여유를 두고 만료 판단
        from datetime import timedelta
        now = datetime.now()
        return now >= (expired_dt - timedelta(minutes=5))
    except Exception as e:
        logger.warning(f"Failed to parse expiration time: {e}")
        return True


def get_approval_key(appkey=APP_KEY, appsecret=APP_SECRET):
    """
    한국투자증권 OpenAPI Approval Key 발급
    :param appkey: 앱키 (없으면 .env에서 로드)
    :param appsecret: 앱시크릿 (없으면 .env에서 로드)
    :return: approval_key (str) or None
    """
    url = f"{DOMAIN}/oauth2/Approval"
    payload = {
        "grant_type": "client_credentials",
        "appkey": appkey or APP_KEY,
        "secretkey": appsecret or APP_SECRET
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code == 200:
            body = r.json()
            return body.get("approval_key")
    except Exception as e:
        logger.warning(f"Approval Key Error: {e}")
    return None


def _fetch_new_access_token(appkey=None, appsecret=None):
    """
    새로운 access token을 서버에서 발급받음 (내부용)
    """
    url = f"{DOMAIN}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": appkey or APP_KEY,
        "appsecret": appsecret or APP_SECRET
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code == 200:
            body = r.json()
            logger.info(f"New access token issued, expires: {body.get('access_token_token_expired')}")
            return body
    except Exception as e:
        logger.warning(f"Access Token Error: {e}")
    return None


def get_access_token(appkey=None, appsecret=None, force_refresh=False):
    global _cached_token_logged

    """
    Access Token을 반환. 캐시된 토큰이 유효하면 재사용하고, 만료되었으면 새로 발급.
    
    Args:
        appkey: 앱키 (기본값: .env에서 로드)
        appsecret: 앱시크릿 (기본값: .env에서 로드)
        force_refresh: True면 캐시 무시하고 강제 재발급
        
    Returns:
        dict: 토큰 정보 {'access_token': ..., 'access_token_token_expired': ..., ...}
    """
    # 1. 강제 갱신이 아니면 캐시 확인
    if not force_refresh:
        cached = _load_cached_token()
        if cached and not _is_token_expired(cached):
            if not _cached_token_logged:
                logger.info(f"Using cached token (expires: {cached.get('access_token_token_expired')})")
                _cached_token_logged = True
            return cached
        elif cached:
            logger.info("Cached token expired, fetching new one...")
        else:
            logger.info("No cached token found, fetching new one...")
    
    # 2. 새 토큰 발급
    new_token = _fetch_new_access_token(appkey, appsecret)
    if new_token:
        _save_token_cache(new_token)
        return new_token
    
    return None


def get_current_price(stock_code, appkey=None, appsecret=None):
    """
    주식 현재가(시세) 정보를 REST API로 조회
    
    Args:
        stock_code: 종목코드 (예: '005930')
        appkey: 앱키 (기본값: .env에서 로드)
        appsecret: 앱시크릿 (기본값: .env에서 로드)
        
    Returns:
        dict: 현재가 정보 (output 필드) 또는 None
    """
    # 1. Access Token 가져오기 (캐시 or 새로 발급)
    token_data = get_access_token(appkey, appsecret)
    if not token_data or 'access_token' not in token_data:
        logger.warning("Failed to get access token for current price")
        return None
    
    access_token = token_data['access_token']
    
    # 2. 현재가 조회 API 호출
    url = f"{DOMAIN}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": appkey or APP_KEY,
        "appsecret": appsecret or APP_SECRET,
        "tr_id": "FHKST01010100"  # 주식 현재가 시세 조회
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # 주식/ETF/ETN
        "FID_INPUT_ISCD": stock_code
    }
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            body = r.json()
            if body.get('rt_cd') == '0':
                return body.get('output')
            else:
                logger.warning(f"Current price API error: {body.get('msg1')}")
        else:
            logger.warning(f"Current price HTTP error: {r.status_code}")
    except Exception as e:
        logger.warning(f"Current price request error: {e}")
    
    return None
