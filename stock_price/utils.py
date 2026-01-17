from datetime import datetime, time
from stock_price.services.kis_rest_client import kis_rest_client

def is_market_open():
    """
    현재 시각이 한국 장 운영 시간(평일 09:00 ~ 15:30)인지 확인.
    휴일 여부는 KIS API를 통해 정확히 확인.
    """
    now = datetime.now()
    now_time = now.time()

    # 1. Check if Today is a Business Day (via API)
    # Note: API call handles weekends and public holidays.
    # If API fails or returns False, we assume closed.
    is_business_day = kis_rest_client.get_market_operation_status()
    if not is_business_day:
        return False

    # 2. Check Market Hours (09:00 ~ 15:30)
    market_start = time(9, 0)
    market_end = time(15, 30)

    if market_start <= now_time <= market_end:
        return True
    
    return False
