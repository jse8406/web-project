# Django REST Framework 프로젝트

Django REST Framework를 사용한 REST API 백엔드 프로젝트입니다.

## 프로젝트 구조

```
web-project/
├── config/              # Django 프로젝트 설정
│   ├── settings.py     # 프로젝트 설정 파일
│   ├── urls.py         # 메인 URL 라우팅
│   └── wsgi.py         # WSGI 설정
├── api/                # API 앱
│   ├── models.py       # 데이터 모델
│   ├── serializers.py  # DRF 시리얼라이저
│   ├── views.py        # API 뷰
│   ├── urls.py         # API URL 라우팅
│   └── tests.py        # 테스트 코드
├── manage.py           # Django 관리 명령어
└── requirements.txt    # 패키지 의존성
```

## 설치 및 실행

### 1. 가상환경 활성화
```bash
.venv\Scripts\activate  # Windows
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 데이터베이스 마이그레이션
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. 슈퍼유저 생성 (선택사항)
```bash
python manage.py createsuperuser
```

### 5. 개발 서버 실행
```bash
python manage.py runserver
```

서버가 시작되면 http://localhost:8000 에서 접속할 수 있습니다.

## API 엔드포인트

### 테스트 엔드포인트
- `GET /api/hello/` - Hello World 응답

### DRF 브라우저블 API
- `GET /api/` - API 루트 (DRF 라우터)

### 관리자 페이지
- `GET /admin/` - Django 관리자 페이지

## 설정된 기능

- Django REST Framework
- CORS 헤더 설정 (localhost:3000, localhost:8080 허용)
- 기본 인증 (SessionAuthentication)
- 페이지네이션 (10개 단위)
- 한국어/한국 시간대 설정

## 테스트 실행

```bash
python manage.py test api
```

## 다음 단계

1. `api/models.py`에 데이터 모델 추가
2. `api/serializers.py`에 시리얼라이저 작성
3. `api/views.py`에 ViewSet 또는 APIView 구현
4. `api/urls.py`에 라우터 등록
5. 마이그레이션 생성 및 적용
