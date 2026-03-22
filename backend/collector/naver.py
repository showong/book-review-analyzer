import httpx
import os
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

        # 키 확인 로그
        client_id = os.getenv("NAVER_CLIENT_ID")
        logger.info(f"NAVER_CLIENT_ID: {client_id[:5] if client_id else 'None'}...")

        queries = [
            f"{book_title} {author} 독후감".strip(),
            f"{book_title} {author} 책 리뷰".strip(),
            f"{book_title} {author} 서평".strip(),
        ]

        for query in queries:
            if len(reviews) >= count:
                break

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
                        logger.info(f"네이버 API 상태코드: {r.status_code} / query: {query[:20]}")

                        r.raise_for_status()
                        items = r.json().get("items", [])
                        logger.info(f"수집된 항목 수: {len(items)}")

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

                        if len(items) < 100:
                            break

                    except Exception as e:
                        logger.error(f"네이버 API 에러: {e}")
                        break

        seen = set()
        unique = []
        for r in reviews:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        logger.info(f"최종 수집 수: {len(unique)}")
        return unique[:count]