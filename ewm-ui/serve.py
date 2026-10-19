#!/usr/bin/env python3
"""Fiori 스타일 목업 EWM UI 정적 서버.

사용법: python3 ewm-ui/serve.py [포트]   (기본 8077)
브라우저에서 http://localhost:8077/ 접속.

이 UI는 SAP Fiori 디자인 언어를 자체 HTML/CSS로 재현한 목업이며
실제 SAP 시스템이 아니다. 데이터는 같은 폴더의 ewm-state.json
(샘플 run의 EWM 전송 단계가 갱신)을 읽는다.
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8077
    handler = partial(SimpleHTTPRequestHandler, directory=str(UI_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print("Mock EWM UI: http://localhost:%d/  (종료: Ctrl+C)" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
