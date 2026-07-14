"""Music appreciation dashboard API"""

import csv
import io
import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import HAS_GEMINI, analyze_reviews, radar_data, wordcloud_data

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Music Appreciation Dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _detect_text_column(headers: List[str], rows: List[List[str]]) -> int:
    candidates = ["감상", "내용", "comment", "text", "답변", "의견", "평가", "response"]
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
    col_idx = _detect_text_column(headers, data_rows)

    texts = []
    for row in data_rows:
        if col_idx < len(row) and row[col_idx].strip():
            texts.append(row[col_idx].strip())
    return texts


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
    }


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
            "error": "CSV에서 감상평 텍스트를 찾을 수 없습니다. '감상', '내용' 등의 열이 있는지 확인해 주세요."
        }

    result = analyze_reviews(texts, use_llm=use_llm, api_key=gemini_api_key)
    return {
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
    return {
        "total_reviews": len(lines),
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
