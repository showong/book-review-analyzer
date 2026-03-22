# collector/google_books.py
import httpx

class GoogleBooksCollector:
    BASE = "https://www.googleapis.com/books/v1/volumes"

    async def get_reviews(self, book_title: str, author: str = "") -> list[dict]:
        query = f"intitle:{book_title}"
        if author:
            query += f"+inauthor:{author}"

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(self.BASE, params={
                "q": query, "maxResults": 1, "langRestrict": "en"
            })
            items = r.json().get("items", [])
            if not items:
                return []

            volume = items[0]["volumeInfo"]
            reviews = []

            # 에디터 리뷰
            for review in volume.get("industryIdentifiers", []):
                pass

            # 책 설명을 리뷰로 활용
            description = volume.get("description", "")
            if description:
                reviews.append({
                    "source": "google_books",
                    "title": volume.get("title", ""),
                    "content": description,
                    "url": volume.get("infoLink", ""),
                    "author": "",
                    "date": volume.get("publishedDate", ""),
                    "rating": volume.get("averageRating"),
                    "ratings_count": volume.get("ratingsCount", 0)
                })

            return reviews