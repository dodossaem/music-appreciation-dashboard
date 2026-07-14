"""감상평 텍스트 분석: 키워드 매칭 + Gemini LLM 보강"""

import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from .keywords import EMOTION_CATEGORIES, EMOTION_LIST, MUSICAL_ELEMENTS, MUSICAL_LIST

try:
    import google.generativeai as genai

    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _match_keywords(text: str, categories: dict) -> Counter:
    counts: Counter = Counter()
    lower = text.lower()
    for category, keywords in categories.items():
        for kw in keywords:
            if kw in text or kw in lower:
                counts[category] += text.count(kw) + lower.count(kw.lower())
    return counts


def _keyword_analysis(texts: List[str]) -> Dict[str, Any]:
    emotion_total: Counter = Counter()
    musical_total: Counter = Counter()
    per_review = []

    for text in texts:
        text = _normalize(text)
        if not text:
            continue
        emotions = _match_keywords(text, EMOTION_CATEGORIES)
        musical = _match_keywords(text, MUSICAL_ELEMENTS)
        emotion_total.update(emotions)
        musical_total.update(musical)
        per_review.append({
            "text": text,
            "emotions": dict(emotions),
            "musical_elements": dict(musical),
        })

    return {
        "emotions": dict(emotion_total),
        "musical_elements": dict(musical_total),
        "reviews": per_review,
        "method": "keyword",
    }


def _llm_analysis(texts: List[str], api_key: str) -> Optional[Dict[str, Any]]:
    """Gemini API로 감정·음악 요소 추출"""
    if not HAS_GEMINI or not api_key:
        return None

    combined = "\n---\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts[:50]))
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    prompt = f"""당신은 음악 교육 전문가입니다. 아래 학생들의 음악 감상평을 분석하세요.

감상평 목록:
{combined}

각 감상평에서 다음을 추출하세요:
1. 감정: {', '.join(EMOTION_LIST)} 중 해당하는 것 (없으면 빈 배열)
2. 음악적 요소: {', '.join(MUSICAL_LIST)} 중 해당하는 것 (없으면 빈 배열)

반드시 아래 JSON 형식으로만 응답하세요. 다른 설명은 포함하지 마세요:
{{
  "reviews": [
    {{"index": 1, "emotions": ["경쾌함"], "musical_elements": ["가락", "장단"]}}
  ],
  "summary": {{
    "top_emotion": "가장 많이 언급된 감정",
    "top_musical": "가장 많이 언급된 음악 요소",
    "insight": "학급 전체 감상 한 줄 요약 (한국어)"
  }}
}}"""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        content = response.text or ""
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None
        data = json.loads(match.group())

        emotion_total: Counter = Counter()
        musical_total: Counter = Counter()
        per_review = []

        for i, text in enumerate(texts):
            item = next((r for r in data.get("reviews", []) if r.get("index") == i + 1), None)
            emotions = item.get("emotions", []) if item else []
            musical = item.get("musical_elements", []) if item else []
            for e in emotions:
                if e in EMOTION_LIST:
                    emotion_total[e] += 1
            for m in musical:
                if m in MUSICAL_LIST:
                    musical_total[m] += 1
            per_review.append({
                "text": text,
                "emotions": {e: 1 for e in emotions if e in EMOTION_LIST},
                "musical_elements": {m: 1 for m in musical if m in MUSICAL_LIST},
            })

        return {
            "emotions": dict(emotion_total),
            "musical_elements": dict(musical_total),
            "reviews": per_review,
            "summary": data.get("summary", {}),
            "method": "gemini",
        }
    except Exception:
        return None


def _resolve_api_key(api_key: Optional[str]) -> str:
    return (api_key or "").strip() or os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")


def analyze_reviews(
    texts: List[str],
    use_llm: bool = True,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """감상평 목록 분석. LLM 실패 시 키워드 방식으로 폴백."""
    texts = [_normalize(t) for t in texts if t and _normalize(t)]
    if not texts:
        return {
            "emotions": {},
            "musical_elements": {},
            "reviews": [],
            "summary": {"insight": "분석할 감상평이 없습니다."},
            "method": "none",
        }

    resolved_key = _resolve_api_key(api_key)
    if use_llm and resolved_key:
        result = _llm_analysis(texts, resolved_key)
        if result:
            kw = _keyword_analysis(texts)
            for cat, cnt in kw["emotions"].items():
                result["emotions"][cat] = result["emotions"].get(cat, 0) + cnt
            for cat, cnt in kw["musical_elements"].items():
                result["musical_elements"][cat] = result["musical_elements"].get(cat, 0) + cnt
            if "summary" not in result or not result["summary"].get("insight"):
                result["summary"] = _build_summary(result["emotions"], result["musical_elements"])
            return result

    result = _keyword_analysis(texts)
    result["summary"] = _build_summary(result["emotions"], result["musical_elements"])
    return result


def _build_summary(emotions: dict, musical: dict) -> dict:
    top_emotion = max(emotions, key=emotions.get) if emotions else "—"
    top_musical = max(musical, key=musical.get) if musical else "—"
    insight = f"우리 반은 이 곡의 '{top_musical}'과 '{top_emotion}'에 가장 집중했어요!"
    return {
        "top_emotion": top_emotion,
        "top_musical": top_musical,
        "insight": insight,
    }


def radar_data(emotions: dict) -> dict:
    labels = EMOTION_LIST
    values = [emotions.get(label, 0) for label in labels]
    max_val = max(values) if values and max(values) > 0 else 1
    normalized = [round(v / max_val * 100, 1) for v in values]
    return {"labels": labels, "values": values, "normalized": normalized}


def wordcloud_data(musical: dict) -> List[dict]:
    if not musical:
        return []
    max_count = max(musical.values())
    return [
        {"text": word, "size": max(12, int(16 + 40 * count / max_count))}
        for word, count in sorted(musical.items(), key=lambda x: -x[1])
    ]
