import httpx
import os
import re

class NaverBlogCollector:
    BASE = "https://openapi.naver.com/v1/search/blog.json"

    def __init__(self):
        self.headers = {
            "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
            "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET")
        }

    def _clean(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()

    async def get_reviews(self, book_title: str, author: str = "", count: int = 500) -> list[dict]:
        reviews = []

        # 쿼리 2가지 교차 사용 (더 다양한 리뷰 수집)
        queries = [
            f"{book_title} {author} 독후감".strip(),
            f"{book_title} {author} 책 리뷰".strip(),
            f"{book_title} {author} 서평".strip(),
        ]

        for query in queries:
            if len(reviews) >= count:
                break

            # 네이버 API: start 최대 1000, display 최대 100
            for start in range(1, 1000, 100):
                if len(reviews) >= count:
                    break

                params = {
                    "query": query,
                    "display": 100,
                    "start": start,
                    "sort": "sim"
                }
                async with httpx.AsyncClient(timeout=10) as client:
                    try:
                        r = await client.get(self.BASE, headers=self.headers, params=params)
                        r.raise_for_status()
                        items = r.json().get("items", [])

                        for item in items:
                            content = self._clean(item.get("description", ""))
                            if len(content) > 30:
                                reviews.append({
                                    "source": "naver",
                                    "title": self._clean(item.get("title", "")),
                                    "content": content,
                                    "url": item.get("link", ""),
                                    "author": item.get("bloggername", ""),
                                    "date": item.get("postdate", "")
                                })

                        # 100개 미만이면 더 이상 결과 없음
                        if len(items) < 100:
                            break

                    except Exception:
                        break

        # URL 기준 중복 제거
        seen = set()
        unique = []
        for r in reviews:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        return unique[:count]