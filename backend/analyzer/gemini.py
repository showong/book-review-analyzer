from google import genai
import os
import json
import re

client = genai.Client(api_key=os.getenv("GEMINI_API"))


def _parse(text: str) -> dict:
    """Gemini 응답에서 JSON 추출 — 잘린 경우 복구 시도"""
    text = text.strip()
    # 코드블록 제거
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # 1차: 그대로 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2차: 중간에 잘린 경우 — 마지막 완전한 필드까지만 복구
    try:
        # JSON 시작 { 부터 마지막으로 완전히 닫힌 } 찾기
        brace = 0
        last_valid = 0
        in_string = False
        escape = False
        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if ch == '{':
                    brace += 1
                elif ch == '}':
                    brace -= 1
                    if brace == 0:
                        last_valid = i

        if last_valid > 0:
            return json.loads(text[:last_valid + 1])
    except Exception:
        pass

    # 3차: 정규식으로 JSON 블록 추출
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    raise ValueError(f"JSON 파싱 실패: {text[:200]}")


def _generate(prompt: str, max_retries: int = 2) -> str:
    """Gemini 호출 — 실패 시 재시도"""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )
            return response.text
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
    return ""


def get_english_title(book_title: str, author: str = "") -> dict:
    """한글 책 제목을 영어 원서명으로 변환"""
    prompt = f"""
아래 책의 영어 원서명과 영어 저자명을 알려줘.
책 제목: {book_title}
저자: {author}

JSON으로만 응답 (마크다운 없이):
{{
  "english_title": "영어 원서명 (없으면 한글 제목 그대로)",
  "english_author": "영어 저자명 (없으면 빈 문자열)",
  "is_korean_original": true
}}
"""
    try:
        return _parse(_generate(prompt))
    except Exception:
        return {"english_title": book_title, "english_author": author, "is_korean_original": False}


def translate_reviews_to_korean(reviews: list[dict]) -> list[dict]:
    """영어 리뷰(Google Books, Reddit)를 한글로 번역"""
    english_reviews = [r for r in reviews if r.get("source") in ["google_books", "reddit"]]
    korean_reviews  = [r for r in reviews if r.get("source") not in ["google_books", "reddit"]]

    if not english_reviews:
        return reviews

    # 50개씩 나눠서 번역 (토큰 초과 방지)
    chunk_size = 50
    for i in range(0, len(english_reviews), chunk_size):
        chunk = english_reviews[i:i + chunk_size]
        texts = [r["content"] for r in chunk]
        numbered = chr(10).join([f"{j+1}. {t}" for j, t in enumerate(texts)])

        prompt = f"""아래 영어 텍스트들을 자연스러운 한국어로 번역해줘.
번호 순서 그대로 JSON 배열로만 응답. 마크다운 없이:

{numbered}

["1번 번역", "2번 번역", ...]"""

        try:
            text = _generate(prompt)
            text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            translated = json.loads(text)
            for j, review in enumerate(chunk):
                if j < len(translated):
                    review["content_original"] = review["content"]
                    review["content"] = translated[j]
        except Exception:
            pass

    return korean_reviews + english_reviews


def analyze_reviews(book_title: str, reviews: list[dict]) -> dict:
    """Step 1: 전체 리뷰 분석"""
    texts = list(dict.fromkeys([r["content"] for r in reviews if r.get("content")]))

    # 토큰 초과 방지 — 최대 150개, 각 500자로 제한
    texts = [t[:500] for t in texts[:150]]

    prompt = f"""
"{book_title}" 책 리뷰 {len(texts)}개를 분석해서 JSON으로만 응답해줘. 순수 JSON만, 마크다운 없이.

리뷰 목록:
{chr(10).join([f"{i+1}. {t}" for i, t in enumerate(texts)])}

{{
  "summary": "전체 독자 반응 5~7문장 요약. 독자들의 감정, 주목한 장면 포함",
  "common_themes": ["공통 주제 키워드 7~10개"],
  "pros": ["긍정 반응 3가지, 각 2문장"],
  "cons": ["부정 반응 3가지, 각 2문장"],
  "controversy": "의견이 갈리는 지점 3~5문장",
  "unique_reviews": [
    {{"content": "이색 리뷰 원문", "reason": "독특한 이유 2문장", "source_index": 번호}},
    {{"content": "이색 리뷰 원문", "reason": "독특한 이유 2문장", "source_index": 번호}},
    {{"content": "이색 리뷰 원문", "reason": "독특한 이유 2문장", "source_index": 번호}}
  ],
  "emotional_response": "독자들의 감정적 반응 3~4문장",
  "reading_tip": "읽기 전 참고사항 3~4문장"
}}
"""
    return _parse(_generate(prompt))


def find_similar_reviews(book_title: str, my_review: str, reviews: list[dict]) -> dict:
    """Step 3: 내 리뷰와 타인 리뷰 유사도 분석"""
    texts = [r["content"] for r in reviews if r.get("content")]
    texts = list(dict.fromkeys(texts))[:100]
    # 각 300자로 제한
    texts = [t[:300] for t in texts]

    numbered = chr(10).join([f"{i+1}. {t}" for i, t in enumerate(texts)])

    prompt = f"""
"{book_title}" 책에서 [내 리뷰]와 다른 독자 리뷰들의 유사도를 분석해줘.

[내 리뷰]
{my_review[:1000]}

[다른 독자 리뷰 {len(texts)}개]
{numbered}

JSON으로만 응답 (마크다운 없이):
{{
  "overall_similarity_score": 0~100 정수,
  "similarity_label": "매우 독창적" 또는 "독창적" 또는 "보통" 또는 "비슷한 편" 또는 "매우 유사",
  "my_unique_points": ["나만의 시각 2~3가지"],
  "common_with_others": ["공통점 2~3가지"],
  "top_similar_reviews": [
    {{"index": 번호, "content": "원문", "similarity_score": 0~100, "reason": "이유 한 문장"}}
  ],
  "analysis_comment": "총평 2~3문장"
}}

top_similar_reviews는 유사도 높은 순 5개.
"""
    result = _parse(_generate(prompt))

    for sr in result.get("top_similar_reviews", []):
        idx = sr.get("index", 1) - 1
        if 0 <= idx < len(reviews):
            sr["source"] = reviews[idx].get("source", "")
            sr["url"]    = reviews[idx].get("url", "")
            sr["title"]  = reviews[idx].get("title", "")

    return result
