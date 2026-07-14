#!/usr/bin/env python3
"""음악 감상문 분석 대시보드 실행 스크립트"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8765,
        reload=False,
    )
