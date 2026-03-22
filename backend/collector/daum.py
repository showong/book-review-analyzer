import httpx
import os
import re

class DaumCollector:
    """
    Kakao REST API로 Daum 블로그 + 브런치 리뷰 수집
    API 키 발급: https://developers.kakao.com → 앱 생성 → REST API 키 복사
    """
    BLOG_URL = "https://dapi.kakao.com/v2/search/blog"
    WEB_URL  = "https://dapi.kakao.com/v2/search/web"

    def __init__(self):
        self.api_key = os.getenv("KAKAO_REST_API_KEY")
        self.headers = {"Authorization": f"KakaoAK {self.api_key}"}

    def _clean(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()

    async def get_reviews(self, book_title: str, author: str = "", count: int = 500) -> list[dict]:
        reviews = []

        # ── 1. Daum 블로그 검색 (일반 블로그) ──
        daum_reviews = await self._search_blog(book_title, author, count // 2)
        reviews.extend(daum_reviews)

        # ── 2. 브런치 전용 검색 ──
        brunch_reviews = await self._search_brunch(book_title, author, count // 2)
        reviews.extend(brunch_reviews)

        # URL 기준 중복 제거
        seen = set()
        unique = []
        for r in reviews:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        return unique[:count]

    async def _search_blog(self, book_title: str, author: str, count: int) -> list[dict]:
        reviews = []
        queries = [
            f"{book_title} {author} 독후감".strip(),
            f"{book_title} {author} 서평".strip(),
        ]

        for query in queries:
            if len(reviews) >= count:
                break
            for page in range(1, 6):  # 최대 5페이지 × 50개 = 250개
                if len(reviews) >= count:
                    break
                params = {
                    "query": query,
                    "size": 50,
                    "page": page,
                    "sort": "accuracy"
                }
                async with httpx.AsyncClient(timeout=10) as client:
                    try:
                        r = await client.get(self.BLOG_URL, headers=self.headers, params=params)
                        r.raise_for_status()
                        data = r.json()
                        docs = data.get("documents", [])

                        for doc in docs:
                            content = self._clean(doc.get("contents", ""))
                            if len(content) > 30:
                                reviews.append({
                                    "source": "daum",
                                    "title": self._clean(doc.get("title", "")),
                                    "content": content,
                                    "url": doc.get("url", ""),
                                    "author": doc.get("blogname", ""),
                                    "date": doc.get("datetime", "")[:10]
                                })

                        # 마지막 페이지면 중단
                        if data.get("meta", {}).get("is_end", True):
                            break

                    except Exception:
                        break

        return reviews

    async def _search_brunch(self, book_title: str, author: str, count: int) -> list[dict]:
        """브런치(brunch.co.kr) 전용 — 웹 검색 API로 site 필터링"""
        reviews = []
        queries = [
            f"{book_title} {author} 독후감 site:brunch.co.kr".strip(),
            f"{book_title} {author} 책 리뷰 site:brunch.co.kr".strip(),
        ]

        for query in queries:
            if len(reviews) >= count:
                break
            for page in range(1, 4):
                if len(reviews) >= count:
                    break
                params = {
                    "query": query,
                    "size": 50,
                    "page": page,
                }
                async with httpx.AsyncClient(timeout=10) as client:
                    try:
                        r = await client.get(self.WEB_URL, headers=self.headers, params=params)
                        r.raise_for_status()
                        data = r.json()
                        docs = data.get("documents", [])

                        for doc in docs:
                            url = doc.get("url", "")
                            if "brunch.co.kr" not in url:
                                continue
                            content = self._clean(doc.get("contents", ""))
                            if len(content) > 30:
                                reviews.append({
                                    "source": "brunch",
                                    "title": self._clean(doc.get("title", "")),
                                    "content": content,
                                    "url": url,
                                    "author": "",
                                    "date": doc.get("datetime", "")[:10] if doc.get("datetime") else ""
                                })

                        if data.get("meta", {}).get("is_end", True):
                            break

                    except Exception:
                        break

        return reviews
