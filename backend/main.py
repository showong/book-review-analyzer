from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import json, os

load_dotenv()
APP_TOKEN = os.getenv("APP_TOKEN")

from collector.naver import NaverBlogCollector
from collector.google import GoogleBlogCollector
from collector.reddit import RedditCollector
from collector.daum import DaumCollector
from analyzer.gemini import analyze_reviews, find_similar_reviews, get_english_title, translate_reviews_to_korean

app = FastAPI(title="은둔책방 리뷰 분석기")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://book-review-analyzer.vercel.app",
        "http://localhost:3000"
        ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 모듈 레벨에서 한 번만 생성
naver_col  = NaverBlogCollector()
google_col = GoogleBlogCollector()
reddit_col = RedditCollector()
daum_col   = DaumCollector()

CACHE_FILE = "cache.json"
cache: dict = {}

def load_cache():
    global cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

load_cache()


class AnalyzeRequest(BaseModel):
    book_title: str
    author: str = ""

class SimilarRequest(BaseModel):
    book_title: str
    author: str = ""
    my_review: str

class DeleteRequest(BaseModel):
    keys: list[str]


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest, x_token: str = Header(None)):
    if APP_TOKEN and x_token != APP_TOKEN:
        raise HTTPException(401, "인증실패")
    try:
        cache_key = f"{req.book_title}||{req.author}"

        if cache_key in cache:
            return {"cached": True, "data": cache[cache_key]}

        # 영어 제목 변환 (Google Books, Reddit 검색용)
        en = get_english_title(req.book_title, req.author)
        en_title  = en.get("english_title", req.book_title)
        en_author = en.get("english_author", req.author)

        # 수집 (4개 플랫폼)
        naver_reviews  = await naver_col.get_reviews(req.book_title, req.author, 500)
        google_reviews = await google_col.get_reviews(en_title, en_author, 10)
        reddit_reviews = await reddit_col.get_reviews(en_title, en_author, 50)
        daum_reviews   = await daum_col.get_reviews(req.book_title, req.author, 200)

        all_reviews = naver_reviews + google_reviews + reddit_reviews + daum_reviews

        if not all_reviews:
            raise HTTPException(404, "리뷰를 찾을 수 없습니다.")

        # 영어 리뷰 한글 번역
        all_reviews = translate_reviews_to_korean(all_reviews)

        # AI 분석
        analysis = analyze_reviews(req.book_title, all_reviews)

        # unique_reviews에 출처 URL 매핑
        for ur in analysis.get("unique_reviews", []):
            idx = ur.get("source_index", 1) - 1
            if 0 <= idx < len(all_reviews):
                ur["url"]    = all_reviews[idx].get("url", "")
                ur["source"] = all_reviews[idx].get("source", "")

        result = {
            "book_title": req.book_title,
            "author": req.author,
            "english_title": en_title,
            "english_author": en_author,
            "review_count": {
                "naver":  len(naver_reviews),
                "google": len(google_reviews),
                "reddit": len(reddit_reviews),
                "daum":   len(daum_reviews),
                "total":  len(all_reviews)
            },
            "analysis": analysis,
            "_reviews": all_reviews
        }

        cache[cache_key] = result
        save_cache()
        return {"cached": False, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/similar")
async def similar(req: SimilarRequest, x_token: str = Header(None)):
    if APP_TOKEN and x_token !=APP_TOKEN:
        raise HTTPException(401, "인증 실패")
    
    try:
        cache_key = f"{req.book_title}||{req.author}"

        if cache_key not in cache:
            raise HTTPException(404, "먼저 /analyze를 실행해주세요.")

        reviews = cache[cache_key].get("_reviews", [])
        if not reviews:
            raise HTTPException(404, "저장된 리뷰 데이터가 없습니다.")

        result = find_similar_reviews(req.book_title, req.my_review, reviews)
        return {"similarity": result}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
def history():
    return {"books": [
        {
            "key": k,
            "title": v["book_title"],
            "author": v["author"],
            "total": v["review_count"]["total"]
        }
        for k, v in cache.items()
        if isinstance(v, dict) and "book_title" in v
    ]}


@app.delete("/history")
def delete_history(req: DeleteRequest):
    """선택한 캐시 항목 삭제"""
    deleted = []
    for key in req.keys:
        if key in cache:
            del cache[key]
            deleted.append(key)
    save_cache()
    return {"deleted": deleted}
