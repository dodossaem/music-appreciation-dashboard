# 음악 감상문 분석 대시보드

**감정 및 음악 요소 시각화 도구** — 학급 감상평을 AI·키워드로 분석하고, 레이더 차트와 워드클라우드로 즉각 피드백하는 교육용 웹 앱

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)

---

## 프로젝트 소개

국악·서양 클래식 등 감상 수업에서 학생들이 Google Forms나 Padlet에 남긴 짧은 감상평을 모아, **감정**과 **음악적 요소**를 자동으로 분류·집계한 뒤 한 화면에서 보여주는 도구입니다.

감상 직후 프로젝터에 띄워 이렇게 대화할 수 있습니다.

> 「우리 반은 이 곡의 **장단**과 **경쾌함**에 가장 집중했구나!」

---

## 개발 배경

음악 감상 수업에서는 학생 한 명 한 명의 감상문보다, **학급 전체가 무엇을 느꼈는지**를 빠르게 공유하는 것이 수업 몰입과 토론의 출발점이 됩니다.  
그러나 CSV·패들렛 댓글을 직접 읽어서 정리하려면 시간이 많이 들고, 수업 흐름이 끊기기 쉽습니다.

이 프로젝트는 다음을 목표로 만들었습니다.

| 문제 | 해결 방향 |
|------|-----------|
| 감상평을 일일이 읽고 분류하기 어렵다 | 감정·음악 요소를 규칙(키워드) + Gemini로 자동 추출 |
| 수업 직후 피드백이 늦다 | 업로드 → 분석 → 시각화까지 한 화면 워크플로 |
| LLM이 없거나 키가 없을 때도 써야 한다 | API 키 없이도 키워드 분석으로 폴백 |
| 교실에서 바로 쓰기 쉬워야 한다 | Gemini 키를 대시보드에서 입력, 브라우저에만 저장 |

교육 현장의 **즉각성**과 **기술 접근성**을 동시에 고려한 포트폴리오·수업 보조 도구입니다.

---

## 주요 기능

- **CSV 업로드** — Google Forms·Padlet 등에서 보낸 CSV 자동 열 인식 (`감상`, `내용`, `답변` 등)
- **직접 입력** — 감상평을 한 줄에 하나씩 붙여넣어 분석
- **이중 분석 엔진**
  - **Gemini LLM** — 문맥을 보고 감정·음악 요소 분류 (키 입력 시)
  - **키워드 사전** — 슬픔, 경쾌함, 가락, 장단 등 국어·국악 용어 기반 폴백
- **시각화**
  - 감정 **레이더 차트** (학급 감정 분포)
  - 음악 요소 **워드클라우드**
  - 한 줄 **인사이트** 배너 + 순위·미리보기
- **Gemini API 키 UI** — [Google AI Studio](https://aistudio.google.com/apikey) 발급 키를 화면에서 입력, `localStorage`에만 보관 (서버에 영구 저장하지 않음)

### 분석 카테고리 예시

| 구분 | 항목 |
|------|------|
| 감정 | 슬픔, 기쁨, 경쾌함, 웅장함, 평온함, 긴장감, 감동, 신비로움 |
| 음악 요소 | 가락, 리듬, 장단, 음색, 화성, 다이나믹, 표현, 악기, 형식, 분위기 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | Python 3.9+, FastAPI, Uvicorn |
| AI | Google Gemini (`gemini-2.0-flash`) via `google-generativeai` |
| Frontend | HTML/CSS/JS, Chart.js, WordCloud2 |
| 데이터 | CSV 업로드 (`utf-8` / `cp949` 등 인코딩 대응) |

---

## 시스템 구조

```
학생 감상평 (CSV / 직접 입력)
        │
        ▼
┌───────────────────┐
│  FastAPI 서버     │
│  · CSV 파싱       │
│  · Gemini 분석    │  ← 키 있으면
│  · 키워드 폴백    │  ← 키 없으면
└─────────┬─────────┘
          │ JSON
          ▼
┌───────────────────┐
│  대시보드 UI      │
│  레이더 · 워드클라우드 │
│  인사이트 · 순위  │
└───────────────────┘
```

```
music-appreciation-dashboard/
├── app/
│   ├── main.py          # FastAPI 라우트 · CSV 파싱
│   ├── analyzer.py      # Gemini + 키워드 분석
│   └── keywords.py      # 감정·음악 요소 사전
├── static/
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── sample_data/
│   └── sample_reviews.csv
├── requirements.txt
├── run.py
└── README.md
```

---

## 패들렛 연동

[Padlet](https://padlet.com/)에 모인 학생 감상평을 **링크로 불러와 CSV로 변환**한 뒤, 곧바로 감정·음악 요소 분석까지 이어갈 수 있습니다.

### 워크플로

```
Padlet 보드 URL
    → board_id 추출
    → Padlet Public API로 포스트 수집  (또는 데모 샘플)
    → Padlet Export와 같은 CSV 형식
    → 감정 레이더 · 워드클라우드 분석
```

### CSV 양식 (Padlet Export 호환)

`Created At, Author, Subject, Body, Section, Attachment`

샘플: [`sample_data/padlet_export_sample.csv`](sample_data/padlet_export_sample.csv)  
또는 대시보드에서 [샘플 다운로드](/api/padlet/sample.csv)

### 사용 방법

1. 대시보드 **패들렛 링크** 탭 선택  
2. 실제 보드: Padlet [Public API](https://padlet.help/l/en/article/3933026qoo-api-public) 키 입력 후 URL 붙여넣기 → **CSV로 변환** → **변환 후 분석**  
3. API 키 없이: **데모 샘플로 체험** → 미리보기 → 분석  
4. 대안: 패들렛 **Share → Export → CSV** 후 **CSV 업로드** 탭

> 공식 Public API는 Padlet 유료 구독이 필요할 수 있습니다. 교실에서는 Export CSV 업로드도 동일하게 동작합니다.

---

## 실행 방법

### 요구 사항

- Python 3.9 이상
- (선택) [Gemini API 키](https://aistudio.google.com/apikey) — 없으면 키워드 분석만 동작

### 1. 클론 및 의존성 설치

```bash
git clone https://github.com/<사용자명>/music-appreciation-dashboard.git
cd music-appreciation-dashboard

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 서버 실행

```bash
python run.py
```

브라우저에서 **http://localhost:8765** 접속

### 3. 사용 순서

1. (선택) 대시보드에 Gemini API 키 입력 → 「Gemini 분석 준비됨」 확인  
2. `sample_data/sample_reviews.csv` 업로드 또는 감상평 직접 입력  
3. **분석 시작** → 레이더 차트·워드클라우드·인사이트 확인  

### (선택) 환경 변수로 키 지정

대시보드 입력 대신 서버 환경 변수를 쓸 수도 있습니다.

```bash
export GEMINI_API_KEY="AIza..."
python run.py
```

---

## 샘플 데이터

`sample_data/sample_reviews.csv`에 학생 15명 분량의 예시 감상평이 포함되어 있습니다.  
Google Forms CSV와 같이 `타임스탬프,이름,감상` 형태의 열을 가정하며, `감상`·`내용`·`답변` 등이 있으면 자동으로 텍스트 열을 찾습니다.

---

## API 요약

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/` | 대시보드 UI |
| `GET` | `/api/health` | 서버·Gemini SDK 상태 |
| `POST` | `/api/analyze` | CSV 파일 분석 (`file`, `use_llm`, `gemini_api_key`) |
| `POST` | `/api/analyze-text` | 텍스트 직접 분석 |

---

## 보안 · 유의사항

- API 키는 **브라우저 localStorage**에만 저장되며, 분석 요청 시 서버로 전달된 뒤 분석에만 사용합니다. 저장소·코드에 커밋하지 마세요.
- 교실에서 공용 PC를 쓸 경우 분석 후 화면의 키 **삭제(✕)** 를 권장합니다.
- Gemini 무료 티어는 요청 한도(RPM/RPD)가 있으며, 실패 시 키워드 분석으로 폴백합니다.

---

## 향후 개선 아이디어

- 반·차시별 결과 저장 및 이전 수업과 비교
- 국악 장단(진양·중모리 등) 세분화 리포트
- 교사용 출력용 PDF / 스크린샷 모드

---

## 라이선스

개인·교육용 포트폴리오 프로젝트입니다. 수업·포트폴리오 활용을 환영합니다.

---

**음악 감상 직후, 학급의 감정을 한눈에.** ♫
