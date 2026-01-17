
import os
import sys
import urllib.request
import urllib.parse
import json
from dotenv import load_dotenv

# Load .env
load_dotenv()

client_id = os.getenv("naver_client_id")
client_secret = os.getenv("naver_secret")

if not client_id or not client_secret:
    print("Error: naver_client_id or naver_secret not found in .env")
    sys.exit(1)

def fetch_news(query, sort_type):
    encText = urllib.parse.quote(query)
    # display=5, sort=sim or date
    url = f"https://openapi.naver.com/v1/search/news?query={encText}&display=5&sort={sort_type}"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    try:
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            data = json.loads(response.read().decode('utf-8'))
            return [item['title'] for item in data.get('items', [])]
        return []
    except Exception as e:
        print(f"Error fetching {sort_type}: {e}")
        return []

query = "삼성전자"
print(f"--- Query: {query} ---")

# 1. 관련도순 (sim)
print("\n[1] 관련도순 (sort=sim)")
sim_titles = fetch_news(query, "sim")
for i, title in enumerate(sim_titles, 1):
    clean_title = title.replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
    print(f"{i}. {clean_title}")

# 2. 최신순 (date)
print("\n[2] 최신순 (sort=date)")
date_titles = fetch_news(query, "date")
for i, title in enumerate(date_titles, 1):
    clean_title = title.replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
    print(f"{i}. {clean_title}")
