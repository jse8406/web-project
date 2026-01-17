# Django REST Framework 프로젝트 - AI 기반 주식 테마 분석 플랫폼

Django REST Framework와 한국투자증권(KIS) Open API를 활용한 실시간 주식 테마 분석 및 시각화 플랫폼입니다.

## 🚀 주요 기능

### 1. 🔥 실시간 테마 히트맵 (Real-time Theme Heatmap)
- **URL**: `/stock/theme/heatmap/`
- 오늘의 주도 테마와 해당 테마에 속한 종목들을 시각적인 히트맵으로 제공합니다.
- **초고속 로딩 (Hybrid Loading)**:
    - **초기 로딩**: 서버 사이드 렌더링(SSR) 시 Ranking API를 활용해 0초 만에 시세 데이터를 표시
    - **실시간 업데이트**: 웹소켓을 통해 실세 없이 가격 변동 반영
- **지능형 데이터 로딩 (Smart Fallback)**:
    - 주말/휴일에는 Ranking API 데이터 부재 시, 자동으로 개별 조회를 수행하여 "0.00%" 현상 방지
    - 휴장일에는 웹소켓 연결을 자동으로 차단하여 리소스 절약

### 2. 🤖 AI 테마 분석
- 뉴스 데이터를 분석하여 오늘의 인기 테마를 자동으로 발굴하고 분류합니다.
- Upstage Solar (LLM) 활용 (예정)

### 3. 📊 실시간 랭킹 및 차트
- **실시간 상승률 Top 30**: `/stock/ranking/`
- **개별 종목 상세**: `/stock/detail/<code >/`
    - 실시간 호가창 및 차트 제공

---

## 📚 문서화 (Documentation)

이 프로젝트의 상세한 API 구조와 아키텍처는 별도 문서로 관리됩니다.
- **[API 아키텍처 문서 (docs/api_architecture.md)](docs/api_architecture.md)**: 내부 API, 외부 KIS API 연동 구조, 웹소켓 및 데이터 흐름도

---

## 🛠 기술 스택
- **Backend**: Django, Django REST Framework (DRF)
- **Real-time**: Django Channels (WebSocket), Redis
- **Frontend**: HTML5, Vanilla JS, CSS Grid
- **External API**: Korea Investment Securities (KIS) Open API

## 📂 프로젝트 구조

```text
web-project/
├── config/              # Django 설정
├── stock_theme/         # [메인] 테마 분석 및 히트맵 앱
├── stock_price/         # [코어] 주식 시세, 랭킹, KIS API 연동
├── docs/                # 프로젝트 문서 (API 아키텍처 등)
├── templates/           # 공통 템플릿 (base.html 등)
└── manage.py
```

## 🚀 설치 및 실행

### 1. 가상환경 및 패키지 설치
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Redis 실행 (필수)
WebSocket 기능을 위해 Redis 서버가 실행 중이어야 합니다.

### 3. 서버 실행
```bash
python manage.py runserver
```
접속: http://localhost:8000/stock/theme/heatmap/

---
*Developed by Antigravity*
