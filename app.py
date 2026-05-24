"""Minimal web server for Truth Mirror MVP."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from truth_mirror import TruthMirrorPipeline

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


class TruthMirrorHandler(BaseHTTPRequestHandler):
    pipeline = TruthMirrorPipeline()

    def _write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            html = INDEX_FILE.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        self._write_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        if self.path != "/api/verify":
            self._write_json({"error": "Not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._write_json({"error": "Missing body"}, status=400)
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_json({"error": "Invalid JSON"}, status=400)
            return
        claim = str(payload.get("claim", "")).strip()
        if not claim:
            self._write_json({"error": "Claim is required"}, status=400)
            return
        result = self.pipeline.verify(claim)
        self._write_json(self.pipeline.to_json(result), status=200)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), TruthMirrorHandler)
    print(f"Truth Mirror running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()

