"""Minimal web server for Truth Mirror MVP."""

from __future__ import annotations

import json
import uuid
import concurrent.futures
from urllib.parse import urlparse, parse_qs
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import base64
from dotenv import load_dotenv

load_dotenv()
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "+923135247525")

from truth_mirror import TruthMirrorPipeline
from truth_mirror.models import GeopoliticalResult
from truth_mirror.pipeline_status import set_stage, get_status, clear_status
from dataclasses import asdict

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


class TruthMirrorHandler(BaseHTTPRequestHandler):
    pipeline = TruthMirrorPipeline()

    def _check_auth(self) -> bool:
        if not AUTH_PASSWORD:
            return True
        auth_header = self.headers.get("Authorization")
        if auth_header and auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, password = decoded.split(":", 1)
                if password == AUTH_PASSWORD:
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Truth Mirror"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def _write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._check_auth():
            return
        if self.path in {"/", "/index.html"}:
            html = INDEX_FILE.read_text(encoding="utf-8")
            if WHATSAPP_NUMBER:
                html = html.replace("{{WHATSAPP_NUMBER}}", WHATSAPP_NUMBER)
            html_bytes = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
            return
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/status":
            query = parse_qs(parsed_path.query)
            req_id = query.get("request_id", ["__global__"])[0]
            self._write_json(get_status(req_id), status=200)
            return
        self._write_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        if not self._check_auth():
            return
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
        request_id = payload.get("request_id", str(uuid.uuid4()))
        if not claim:
            self._write_json({"error": "Claim is required"}, status=400)
            return
        
        set_stage("classifying", request_id=request_id)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.pipeline.verify, claim, request_id=request_id)
                try:
                    result = future.result(timeout=300)  # 5-minute hard timeout
                except concurrent.futures.TimeoutError:
                    self._write_json({
                        "error": "Analysis timed out",
                        "verdict": "TIMEOUT",
                        "verdict_data": {
                            "verdict": "TIMEOUT",
                            "confidence": 0.0,
                            "confidence_label": "N/A",
                            "one_line_verdict": "The system is under heavy load. Please try again in a few minutes.",
                            "full_reasoning": "The analysis pipeline exceeded the 5-minute timeout. This usually means upstream API services are slow or unresponsive.",
                            "what_is_true": "N/A — analysis timed out.",
                            "what_is_false": "N/A — analysis timed out.",
                            "what_is_unclear": "N/A — analysis timed out.",
                        },
                        "is_geopolitical": True,
                    }, status=503)
                    return

            if isinstance(result, GeopoliticalResult):
                res_dict = asdict(result)
                res_dict["final_verdict"] = res_dict.get("verdict")
                res_dict["request_id"] = request_id
                self._write_json(res_dict, status=200)
            else:
                res_dict = self.pipeline.to_json(result)
                res_dict["request_id"] = request_id
                self._write_json(res_dict, status=200)
        finally:
            clear_status(request_id)


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), TruthMirrorHandler)
    print(f"Truth Mirror running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()

