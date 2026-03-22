# LEKT — 책 리뷰 분석기 v2

네이버 · 구글 블로그 리뷰를 수집하고 Gemini AI로 분석 → 나의 리뷰와 유사도까지 비교

---

## 서비스 흐름

```
Step 1  책 제목 + 저자 입력
        → 네이버 블로그 API (최대 200개)
        → Google CSE API (최대 100개)
        → Gemini 분석: 공통 주제, 이색 리뷰, 요약

Step 2  나의 리뷰 입력
        → 자유롭게 감상 작성

Step 3  유사도 분석
        → 전체 대비 유사도 점수 (0~100)
        → 나만의 독창적 시각 vs 공통 부분
        → 가장 유사한 리뷰 Top 5 (원문 + 출처 링크)
```

---

## 실행 방법

### 1. API 키 발급 (전부 무료)

| 키 | 발급 주소 |
|---|---|
| 네이버 Client ID + Secret | https://developers.naver.com → 애플리케이션 등록 → **검색** API 체크 |
| Google API Key | https://console.cloud.google.com → Custom Search API 활성화 |
| Google CX | https://programmablesearchengine.google.com → 새 검색엔진 생성 |
| Gemini API Key | https://aistudio.google.com → Get API Key |

### 2. 로컬 실행

```bash
cd backend

# 가상환경
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# 패키지 설치
pip install -r requirements.txt

# 환경변수 설정
cp ../.env.example .env
# .env 파일을 열어서 API 키 4개 입력

# 서버 시작
uvicorn main:app --reload --port 8000
```

브라우저에서 `frontend/index.html` 파일을 열면 바로 사용 가능.

### 3. 온라인 배포 (5인 공유)

**백엔드 → Render.com (무료)**
1. https://render.com 가입 → New Web Service
2. GitHub에 이 프로젝트 업로드 후 연결
3. Root Directory: `backend`
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Environment Variables에 .env 내용 4개 입력
7. 배포 완료 후 URL 확인 (예: https://lekt-api.onrender.com)

**프론트엔드 → Vercel (무료)**
1. https://vercel.com 가입 → New Project → GitHub 연결
2. Root Directory: `frontend`
3. `index.html` 1번째 줄 `const API = "http://localhost:8000"` 을
   `const API = "https://lekt-api.onrender.com"` 으로 수정 후 배포

---

## 프로젝트 구조

```
book-review-v2/
├── backend/
│   ├── main.py                   # FastAPI 엔드포인트
│   ├── collector/
│   │   ├── naver.py              # 네이버 블로그 수집
│   │   └── google.py             # 구글 블로그 수집
│   ├── analyzer/
│   │   └── gemini.py             # Gemini 분석 + 유사도
│   ├── requirements.txt
│   └── cache.json                # 분석 결과 캐시 (자동 생성)
├── frontend/
│   └── index.html                # 3단계 UI
└── .env.example
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | /analyze | 리뷰 수집 + AI 분석 (Step 1) |
| POST | /similar | 나의 리뷰 유사도 분석 (Step 3) |
| GET  | /history | 분석한 책 목록 |
# book-review-analyzer
