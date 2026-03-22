import httpx
import os

class GoogleBlogCollector:
    BASE = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")

    async def get_reviews(self, book_title: str, author: str = "", count: int = 10) -> list[dict]:
        reviews = []

        # ── 1. 제목+저자로 검색 ──
        query = f"intitle:{book_title}"
        if author:
            query += f"+inauthor:{author}"

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(self.BASE, params={
                    "q": query,
                    "maxResults": 10,
                    "printType": "books",
                    "key": self.api_key
                })
                r.raise_for_status()
                items = r.json().get("items", [])

                for item in items:
                    info = item.get("volumeInfo", {})

                    # 책 설명 (description)
                    desc = info.get("description", "").strip()
                    if len(desc) > 50:
                        reviews.append({
                            "source": "google_books",
                            "title": info.get("title", ""),
                            "content": desc[:800],
                            "url": info.get("infoLink", ""),
                            "author": "",
                            "date": info.get("publishedDate", ""),
                            "rating": info.get("averageRating"),
                            "ratings_count": info.get("ratingsCount", 0)
                        })

                    # 에디터 리뷰 (있는 경우만)
                    for review in item.get("volumeInfo", {}).get("industryIdentifiers", []):
                        pass  # 향후 확장용

            except Exception:
                pass

            # ── 2. 제목만으로 추가 검색 (저자 없이 더 넓게) ──
            if author:
                try:
                    r2 = await client.get(self.BASE, params={
                        "q": f"intitle:{book_title}",
                        "maxResults": 5,
                        "printType": "books",
                        "langRestrict": "en",   # 영어 결과 추가 수집
                        "key": self.api_key
                    })
                    r2.raise_for_status()
                    for item in r2.json().get("items", []):
                        info = item.get("volumeInfo", {})
                        desc = info.get("description", "").strip()
                        if len(desc) > 50:
                            reviews.append({
                                "source": "google_books",
                                "title": info.get("title", ""),
                                "content": desc[:800],
                                "url": info.get("infoLink", ""),
                                "author": "",
                                "date": info.get("publishedDate", ""),
                                "rating": info.get("averageRating"),
                                "ratings_count": info.get("ratingsCount", 0)
                            })
                except Exception:
                    pass

        # 중복 URL 제거
        seen = set()
        unique = []
        for r in reviews:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        # 평점 있는 것 우선 정렬
        unique.sort(key=lambda x: (x.get("ratings_count") or 0), reverse=True)
        return unique[:count]
