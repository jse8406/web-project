import os
import django
import sys

# Setup Django Environment
sys.path.append('c:\\Users\\jse\\Desktop\\vscode\\web-project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from stock_price.services.kis_rest_client import kis_rest_client

def test_kis_api():
    print("=== Testing KIS API on Weekend ===")
    
    # 1. Test Ranking API
    print("\n1. Testing Ranking API (get_fluctuation_rank_sync)...")
    try:
        rank_data = kis_rest_client.get_fluctuation_rank_sync()
        print(f"Result count: {len(rank_data)}")
        if rank_data:
            print(f"First item: {rank_data[0]}")
    except Exception as e:
        print(f"Error: {e}")

    # 2. Test Individual Price API
    print("\n2. Testing Individual Price API (005930 - Samsung)...")
    try:
        price_data = kis_rest_client.get_current_price('005930') # Samsung Electronics
        print(f"Result: {price_data}")
        if price_data:
            print(f"Current Price: {price_data.get('stck_prpr')}")
            print(f"Rate: {price_data.get('prdy_ctrt')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_kis_api()
