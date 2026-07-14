"""Padlet 링크 → 게시글 수집 → CSV 변환

공식 Padlet Public API(https://api.padlet.dev)를 사용해
공개/접근 가능한 보드의 포스트를 Padlet Export CSV 형식으로 변환합니다.
API 키가 없으면 데모 샘플 CSV로 흐름을 체험할 수 있습니다.
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_PADLET_CSV = BASE_DIR / "sample_data" / "padlet_export_sample.csv"

# Padlet Share → Export CSV 와 동일한 헤더(영문)
PADLET_CSV_HEADERS = [
    "Created At",
    "Author",
    "Subject",
    "Body",
    "Section",
    "Attachment",
]

BOARD_ID_RE = re.compile(r"([a-zA-Z0-9]{16})(?:/)?$")
PADLET_HOSTS = ("padlet.com", "www.padlet.com", "padlet.org", "padlet.dev")


def extract_board_id(url_or_id: str) -> Optional[str]:
    """패들렛 URL 또는 board_id에서 16자 board_id 추출"""
    text = (url_or_id or "").strip()
    if not text:
        return None

    # 순수 board_id
    if re.fullmatch(r"[a-zA-Z0-9]{16}", text):
        return text

    parsed = urlparse(text if "://" in text else f"https://{text}")
    path = parsed.path.rstrip("/")
    # 예: /username/my-title-abcd1234efgh5678
    for part in reversed(path.split("/")):
        m = re.search(r"([a-zA-Z0-9]{16})$", part)
        if m:
            return m.group(1)
    return None


def is_padlet_url(url: str) -> bool:
    try:
        host = urlparse(url if "://" in url else f"https://{url}").hostname or ""
        return any(host == h or host.endswith("." + h) for h in PADLET_HOSTS)
    except Exception:
        return False


def posts_to_csv(posts: List[Dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PADLET_CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for post in posts:
        writer.writerow({h: post.get(h, "") for h in PADLET_CSV_HEADERS})
    return buf.getvalue()


def load_sample_posts() -> Tuple[List[Dict[str, str]], str]:
    """공식 Export CSV 샘플 로드"""
    text = SAMPLE_PADLET_CSV.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    posts = [dict(row) for row in reader]
    return posts, text


def _attr(obj: dict, *keys: str, default: str = "") -> str:
    cur: Any = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    if cur is None:
        return default
    return str(cur).strip()


def _parse_api_posts(payload: dict) -> Tuple[str, List[Dict[str, str]]]:
    """Padlet JSON:API 응답 → (title, posts)"""
    data = payload.get("data") or {}
    included = payload.get("included") or []
    title = _attr(data, "attributes", "title", default="Padlet")

    posts: List[Dict[str, str]] = []
    for item in included:
        if item.get("type") != "post":
            continue
        attrs = item.get("attributes") or {}
        subject = (attrs.get("subject") or attrs.get("contentSubject") or "").strip()
        body = (attrs.get("body") or attrs.get("content") or attrs.get("contentBody") or "").strip()
        # HTML 태그 간단 제거
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        author = ""
        author_obj = attrs.get("author") or attrs.get("writer") or {}
        if isinstance(author_obj, dict):
            author = (
                author_obj.get("name")
                or author_obj.get("fullName")
                or author_obj.get("displayName")
                or author_obj.get("username")
                or ""
            )
        else:
            author = str(author_obj or "")
        created = attrs.get("createdAt") or attrs.get("publishedAt") or ""
        section = ""
        if isinstance(attrs.get("section"), dict):
            section = attrs["section"].get("title") or ""
        attachment = ""
        atts = attrs.get("attachment") or attrs.get("attachmentUrl") or ""
        if isinstance(atts, dict):
            attachment = atts.get("url") or atts.get("name") or ""
        else:
            attachment = str(atts or "")

        if not body and not subject:
            continue
        posts.append(
            {
                "Created At": created,
                "Author": author,
                "Subject": subject,
                "Body": body or subject,
                "Section": section,
                "Attachment": attachment,
            }
        )
    return title, posts


def fetch_padlet_via_api(board_id: str, api_key: str) -> Tuple[str, List[Dict[str, str]]]:
    if not HAS_HTTPX:
        raise RuntimeError("httpx가 설치되지 않았습니다. pip install httpx 를 실행해 주세요.")
    if not api_key:
        raise ValueError("Padlet API 키가 필요합니다.")

    url = f"https://api.padlet.dev/v1/boards/{board_id}?include=posts,sections,comments"
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/vnd.api+json",
    }
    with httpx.Client(timeout=30.0) as client:
        res = client.get(url, headers=headers)
        if res.status_code == 401:
            raise PermissionError("Padlet API 키가 유효하지 않습니다.")
        if res.status_code == 403:
            raise PermissionError(
                "이 보드에 접근할 수 없습니다. 구독·API 권한 또는 보드 관리자 권한을 확인해 주세요."
            )
        if res.status_code == 404:
            raise FileNotFoundError("패들렛을 찾을 수 없습니다. URL·board_id를 확인해 주세요.")
        if res.status_code >= 400:
            raise RuntimeError(f"Padlet API 오류 ({res.status_code}): {res.text[:200]}")
        payload = res.json()

    title, posts = _parse_api_posts(payload)
    if not posts:
        raise ValueError("게시글(포스트)을 찾지 못했습니다. 보드가 비어 있거나 include 응답 형식이 다릅니다.")
    return title, posts


def convert_padlet(
    url: str,
    api_key: Optional[str] = None,
    use_demo: bool = False,
) -> Dict[str, Any]:
    """
    패들렛 링크를 CSV로 변환.

    Returns:
      title, board_id, posts, csv, source (api|demo), preview
    """
    resolved_key = (api_key or "").strip() or os.getenv("PADLET_API_KEY", "")

    if use_demo or (url or "").strip().lower() in ("demo", "sample", "샘플"):
        posts, csv_text = load_sample_posts()
        return {
            "title": "데모 · 음악 감상 패들렛",
            "board_id": "demo0000sample001",
            "posts": posts,
            "csv": csv_text,
            "source": "demo",
            "total_posts": len(posts),
            "preview": [p.get("Body") or p.get("Subject") or "" for p in posts[:5]],
        }

    board_id = extract_board_id(url)
    if not board_id:
        raise ValueError(
            "패들렛 URL에서 board_id를 찾을 수 없습니다. "
            "예: https://padlet.com/username/제목-abcd1234efgh5678"
        )

    if not resolved_key:
        raise PermissionError(
            "Padlet API 키가 필요합니다. "
            "Padlet Settings → Developer에서 키를 발급하거나, "
            "아래에서 '데모 샘플로 체험'을 눌러 주세요. "
            "(공식 Public API는 유료 구독이 필요할 수 있습니다. "
            "또는 패들렛 Share → Export → CSV 로 내려받아 업로드하세요.)"
        )

    title, posts = fetch_padlet_via_api(board_id, resolved_key)
    csv_text = posts_to_csv(posts)
    return {
        "title": title,
        "board_id": board_id,
        "posts": posts,
        "csv": csv_text,
        "source": "api",
        "total_posts": len(posts),
        "preview": [p.get("Body") or p.get("Subject") or "" for p in posts[:5]],
    }


def texts_from_padlet_posts(posts: List[Dict[str, str]]) -> List[str]:
    """분석용 텍스트 추출: Body 우선, 없으면 Subject"""
    texts = []
    for p in posts:
        body = (p.get("Body") or "").strip()
        subject = (p.get("Subject") or "").strip()
        if body and subject and body != subject:
            texts.append(f"{subject} {body}".strip())
        elif body:
            texts.append(body)
        elif subject:
            texts.append(subject)
    return texts
