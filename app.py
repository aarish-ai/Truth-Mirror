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
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")
AUTH_USERNAMES = {"john", "mary", "test"}
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")

import uuid as _uuid
_active_sessions = {}  # token -> username

def _create_session(username: str) -> str:
    token = str(_uuid.uuid4())
    _active_sessions[token] = username
    return token

def _check_session(handler) -> bool:
    auth_header = handler.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token in _active_sessions:
            return True
    handler.send_response(401)
    handler.send_header("Content-Type", "application/json")
    body = json.dumps({"error": "Unauthorized"}).encode("utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return False

from truth_mirror import TruthMirrorPipeline
from truth_mirror.models import GeopoliticalResult
from truth_mirror.pipeline_status import set_stage, get_status, clear_status
from dataclasses import asdict

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"

_STATIC_CACHE = {}

def _get_static_file(filepath: Path, as_text: bool = False):
    if filepath not in _STATIC_CACHE:
        if as_text:
            _STATIC_CACHE[filepath] = filepath.read_text(encoding="utf-8")
        else:
            _STATIC_CACHE[filepath] = filepath.read_bytes()
    return _STATIC_CACHE[filepath]

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)


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
            html = _get_static_file(INDEX_FILE, as_text=True)
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
        if parsed_path.path.startswith("/static/"):
            filename = parsed_path.path.split("/")[-1]
            filepath = STATIC_DIR / filename
            if filepath.exists() and filepath.is_file():
                if filename.endswith(".css"):
                    content_type = "text/css"
                elif filename.endswith(".js"):
                    content_type = "application/javascript"
                else:
                    content_type = "text/plain"
                
                content = _get_static_file(filepath, as_text=False)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self._write_json({"error": "Not found"}, status=404)
                return

        if parsed_path.path == "/api/status":
            if not _check_session(self):
                return
            query = parse_qs(parsed_path.query)
            req_id = query.get("request_id", ["__global__"])[0]
            self._write_json(get_status(req_id), status=200)
            return
        self._write_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        if self.path == "/api/login":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._write_json({"error": "Invalid JSON"}, status=400)
                return
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", ""))
            if username.lower() in AUTH_USERNAMES and password == AUTH_PASSWORD:
                token = _create_session(username)
                self._write_json({"token": token, "username": username})
            else:
                self._write_json({"error": "Invalid username or password"}, status=401)
            return

        if self.path == "/api/verify":
            if not _check_session(self):
                return
        else:
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
            future = _executor.submit(self.pipeline.verify, claim, request_id=request_id)
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
            except Exception as e:
                self._write_json({
                    "error": "Internal server error during analysis",
                    "details": str(e),
                    "verdict": "ERROR",
                    "verdict_data": {
                        "verdict": "ERROR",
                        "confidence": 0.0,
                        "confidence_label": "N/A",
                        "one_line_verdict": "An internal error occurred during claim processing.",
                        "full_reasoning": f"Unhandled exception during claim analysis: {e}",
                        "what_is_true": "N/A — system error.",
                        "what_is_false": "N/A — system error.",
                        "what_is_unclear": "N/A — system error.",
                    },
                    "is_geopolitical": True,
                }, status=500)
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
    logger.info(f"Truth Mirror running on http://127.0.0.1:{port} (bound to {host})")
    server.serve_forever()


if __name__ == "__main__":
    run_server()

