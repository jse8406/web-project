import requests
import os
from dotenv import load_dotenv

# .env 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

APP_KEY = os.getenv('g_appkey')
APP_SECRET = os.getenv('g_appsecret') or os.getenv('g_appsceret')


def get_approval_key(appkey=None, appsecret=None):
    """
    한국투자증권 OpenAPI Approval Key 발급
    :param appkey: 앱키 (없으면 .env에서 로드)
    :param appsecret: 앱시크릿 (없으면 .env에서 로드)
    :return: approval_key (str) or None
    """
    url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
    payload = {
        "grant_type": "client_credentials",
        "appkey": appkey or APP_KEY,
        "secretkey": appsecret or APP_SECRET
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code == 200:
            body = r.json()
            return body.get("approval_key") or body.get("approvalKey")
    except Exception as e:
        print(f"[KIS Auth] Approval Key Error: {e}")
    return None
