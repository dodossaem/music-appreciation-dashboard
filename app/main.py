"""Music appreciation dashboard API"""

import csv
import io
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import HAS_GEMINI, analyze_reviews, radar_data, wordcloud_data
from .padlet import convert_padlet, texts_from_padlet_posts

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Music Appreciation Dashboard", version="1.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _detect_text_column(headers: List[str], rows: List[List[str]]) -> int:
    candidates = [
        "감상",
        "내용",
        "body",
        "subject",
        "comment",
        "text",
        "답변",
        "의견",
        "평가",
        "response",
        "본문",
        "제목",
    ]
    for i, h in enumerate(headers):
        h_lower = (h or "").lower()
        if any(c in h_lower for c in candidates):
            return i
    if not rows:
        return 0
    col_scores = []
    for i in range(len(headers)):
        total_len = sum(len(row[i]) if i < len(row) else 0 for row in rows[:20])
        col_scores.append((total_len, i))
    return max(col_scores, key=lambda x: x[0])[1] if col_scores else 0


def _parse_csv(content: bytes) -> List[str]:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("utf-8", errors="replace")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    headers = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else rows

    # Padlet Export: Body + Subject 병합
    header_lower = [(h or "").strip().lower() for h in headers]
    if "body" in header_lower or "subject" in header_lower:
        body_i = header_lower.index("body") if "body" in header_lower else None
        subj_i = header_lower.index("subject") if "subject" in header_lower else None
        texts = []
        for row in data_rows:
            body = row[body_i].strip() if body_i is not None and body_i < len(row) else ""
            subj = row[subj_i].strip() if subj_i is not None and subj_i < len(row) else ""
            if body and subj and body != subj:
                texts.append(f"{subj} {body}")
            elif body:
                texts.append(body)
            elif subj:
                texts.append(subj)
        return texts

    col_idx = _detect_text_column(headers, data_rows)
    texts = []
    for row in data_rows:
        if col_idx < len(row) and row[col_idx].strip():
            texts.append(row[col_idx].strip())
    return texts


def _analysis_payload(texts: List[str], result: dict, extra: Optional[dict] = None) -> dict:
    payload = {
        "total_reviews": len(texts),
        "emotions": result["emotions"],
        "musical_elements": result["musical_elements"],
        "radar": radar_data(result["emotions"]),
        "wordcloud": wordcloud_data(result["musical_elements"]),
        "summary": result.get("summary", {}),
        "method": result.get("method", "keyword"),
        "sample_reviews": [
            r["text"][:80] + ("…" if len(r["text"]) > 80 else "")
            for r in result.get("reviews", [])[:5]
        ],
    }
    if extra:
        payload.update(extra)
    return payload


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    env_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return {
        "status": "ok",
        "provider": "gemini",
        "gemini_sdk": HAS_GEMINI,
        "env_key_configured": env_key,
        "padlet_env_key": bool(os.getenv("PADLET_API_KEY")),
    }


@app.post("/api/padlet/convert")
async def padlet_convert(
    url: str = Form(...),
    padlet_api_key: str = Form(default=""),
    use_demo: bool = Form(default=False),
):
    """패들렛 링크 → CSV 변환 (미리보기)"""
    try:
        result = convert_padlet(url, api_key=padlet_api_key, use_demo=use_demo)
        return {
            "ok": True,
            "title": result["title"],
            "board_id": result["board_id"],
            "source": result["source"],
            "total_posts": result["total_posts"],
            "preview": result["preview"],
            "csv": result["csv"],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/padlet/sample.csv")
async def padlet_sample_csv():
    """Padlet Export 형식 샘플 CSV 다운로드"""
    path = BASE_DIR / "sample_data" / "padlet_export_sample.csv"
    return FileResponse(
        path,
        media_type="text/csv",
        filename="padlet_export_sample.csv",
    )


@app.post("/api/analyze-padlet")
async def analyze_padlet(
    url: str = Form(...),
    padlet_api_key: str = Form(default=""),
    use_demo: bool = Form(default=False),
    use_llm: bool = Form(default=True),
    gemini_api_key: str = Form(default=""),
):
    """패들렛 링크 → CSV 변환 → 감정·음악 요소 분석"""
    try:
        converted = convert_padlet(url, api_key=padlet_api_key, use_demo=use_demo)
    except Exception as e:
        return {"error": str(e)}

    texts = texts_from_padlet_posts(converted["posts"])
    if not texts:
        return {"error": "변환된 게시글에서 텍스트를 찾지 못했습니다."}

    result = analyze_reviews(texts, use_llm=use_llm, api_key=gemini_api_key)
    return _analysis_payload(
        texts,
        result,
        extra={
            "padlet_title": converted["title"],
            "padlet_source": converted["source"],
            "padlet_board_id": converted["board_id"],
            "csv": converted["csv"],
        },
    )


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    use_llm: bool = Form(default=True),
    gemini_api_key: str = Form(default=""),
):
    content = await file.read()
    texts = _parse_csv(content)
    if not texts:
        return {
            "error": "CSV에서 감상평 텍스트를 찾을 수 없습니다. "
            "Padlet Export의 Body/Subject 열 또는 '감상', '내용' 열이 있는지 확인해 주세요."
        }

    result = analyze_reviews(texts, use_llm=use_llm, api_key=gemini_api_key)
    return _analysis_payload(texts, result)


@app.post("/api/analyze-text")
async def analyze_text(
    texts: str = Form(...),
    use_llm: bool = Form(default=True),
    gemini_api_key: str = Form(default=""),
):
    lines = [line.strip() for line in texts.split("\n") if line.strip()]
    if not lines:
        return {"error": "감상평을 입력해 주세요."}

    result = analyze_reviews(lines, use_llm=use_llm, api_key=gemini_api_key)
    return _analysis_payload(lines, result)
