import httpx

class RedditCollector:
    BASE = "https://www.reddit.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    SUBREDDITS = ["books", "literature", "booksuggestions", "52books", "printSF"]

    async def get_reviews(self, book_title: str, author: str = "", count: int = 50) -> list[dict]:
        query = f"{book_title} {author}".strip()
        reviews = []

        async with httpx.AsyncClient(timeout=15, headers=self.HEADERS) as client:

            # ── 1. 서브레딧별 검색 ──
            for sub in self.SUBREDDITS:
                try:
                    r = await client.get(
                        f"{self.BASE}/r/{sub}/search.json",
                        params={"q": query, "sort": "relevance", "limit": 15, "restrict_sr": "true"}
                    )
                    if r.status_code != 200:
                        continue

                    posts = r.json().get("data", {}).get("children", [])
                    for post in posts:
                        d = post["data"]
                        content = d.get("selftext", "").strip()
                        title = d.get("title", "").strip()

                        # 본문 없으면 제목만이라도 사용
                        main_text = content if len(content) > 50 else title
                        if len(main_text) < 20:
                            continue

                        reviews.append({
                            "source": "reddit",
                            "subreddit": sub,
                            "title": title,
                            "content": main_text[:800],
                            "url": f"https://reddit.com{d.get('permalink', '')}",
                            "author": d.get("author", ""),
                            "date": str(d.get("created_utc", "")),
                            "score": d.get("score", 0),
                            "num_comments": d.get("num_comments", 0)
                        })

                except Exception:
                    continue

            # ── 2. 전체 Reddit 검색 (서브레딧 무관) ──
            try:
                r = await client.get(
                    f"{self.BASE}/search.json",
                    params={"q": f"{query} review", "sort": "relevance", "limit": 20, "type": "link"}
                )
                if r.status_code == 200:
                    posts = r.json().get("data", {}).get("children", [])
                    for post in posts:
                        d = post["data"]
                        # books 관련 서브레딧만 필터
                        sub_name = d.get("subreddit", "").lower()
                        if not any(kw in sub_name for kw in ["book", "read", "lit", "novel", "fiction", "sf", "fantasy"]):
                            continue

                        content = d.get("selftext", "").strip()
                        title = d.get("title", "").strip()
                        main_text = content if len(content) > 50 else title
                        if len(main_text) < 20:
                            continue

                        reviews.append({
                            "source": "reddit",
                            "subreddit": d.get("subreddit", ""),
                            "title": title,
                            "content": main_text[:800],
                            "url": f"https://reddit.com{d.get('permalink', '')}",
                            "author": d.get("author", ""),
                            "date": str(d.get("created_utc", "")),
                            "score": d.get("score", 0),
                            "num_comments": d.get("num_comments", 0)
                        })
            except Exception:
                pass

        # 중복 URL 제거 + 추천수 높은 순 정렬
        seen = set()
        unique = []
        for r in reviews:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        unique.sort(key=lambda x: (x["score"] + x["num_comments"] * 2), reverse=True)
        return unique[:count]