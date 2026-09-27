"""A fake RAG service for local testing of the integration (no dependencies).

    python3 tools/fake_rag.py            # listens on http://localhost:8090/ask
    RAG_URL=http://localhost:8090/ask    # in the backend environment

It implements the contract from docs/rag.md: takes the question with the student's
context and answers with the sources of the step the question is about. Replace it with
the real RAG service: only RAG_URL (and RAG_TOKEN, if the service checks one) change.
Flags: --port N, --delay SECONDS (to test the timeout), --fail (always answer 500).
"""

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def make_handler(delay: float, fail: bool, token: str | None) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if token and self.headers.get("Authorization") != f"Bearer {token}":
                self._send(401, {"error": "bad token"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            request = json.loads(self.rfile.read(length) or b"{}")
            time.sleep(delay)
            if fail:
                self._send(500, {"error": "fake failure"})
                return
            step = request.get("step") or (request.get("route") or [None])[0]
            region = request.get("region_title") or "регион не указан"
            answer = f"[fake RAG] Вопрос: «{request.get('question')}». Регион: {region}."
            if step:
                answer += f" Подробнее — в шаге «{step['title']}»: {step['short_description']}"
            self._send(
                200,
                {
                    "answer": answer,
                    "sources": (step or {}).get("sources", [])[:3],
                    "step_code": (step or {}).get("code"),
                },
            )

        def _send(self, status: int, body: dict[str, object]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--token", help="Require this bearer token (RAG_TOKEN)")
    args = parser.parse_args()
    server = HTTPServer(("0.0.0.0", args.port), make_handler(args.delay, args.fail, args.token))
    print(f"Fake RAG on http://localhost:{args.port}/ask — Ctrl+C to stop")
    server.serve_forever()


if __name__ == "__main__":
    main()
