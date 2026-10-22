import json
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 10000))

# сид -> {"text": ..., "sid_at": ...}
DATA = {}


def _sid_and_offset(path):
    q = urllib.parse.parse_qs(
        urllib.parse.urlparse(path).query)
    sid = (q.get("sid") or [""])[0].strip()
    off = 0
    if "offset" in q:
        try:
            off = int(q["offset"][0])
        except ValueError:
            pass
    return sid, off


class Handler(BaseHTTPRequestHandler):

    def _send(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length",
            str(len(body)))
        self.send_header("Cache-Control",
            "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name, ctype):
        try:
            with open(name, "rb") as f:
                self._send(200, ctype, f.read())
        except FileNotFoundError:
            self._send(404,
                "text/plain; charset=utf-8",
                "not found")

    def _clock(self, part):
        _, off = _sid_and_offset(self.path)
        now = datetime.now(timezone.utc) \
            + timedelta(hours=off)
        value = getattr(now, part)
        self._send(200,
            "text/plain; charset=utf-8",
            str(value))

    def do_GET(self):
        path = urllib.parse.urlparse(
            self.path).path
        sid, _ = _sid_and_offset(self.path)
        if path == "/":
            self._file("index.html",
                "text/html; charset=utf-8")
        elif path == "/typewriter":
            self._file("typewriter.html",
                "text/html; charset=utf-8")
        elif path == "/clock":
            self._file("clock.html",
                "text/html; charset=utf-8")
        elif path == "/receiver":
            self._file("receiver.html",
                "text/html; charset=utf-8")
        elif path == "/settings":
            self._file("settings.html",
                "text/html; charset=utf-8")
        elif path == "/api/data":
            rec = DATA.get(sid)
            if rec:
                self._send(200,
                    "application/json; charset=utf-8",
                    json.dumps({
                        "sid": sid,
                        "text": rec["text"],
                        "sid_at": rec["sid_at"]
                    }, ensure_ascii=False))
            else:
                self._send(200,
                    "application/json; charset=utf-8",
                    json.dumps({"sid": "",
                        "text": "", "sid_at": ""}))
        elif path == "/text":
            rec = DATA.get(sid)
            self._send(200,
                "text/plain; charset=utf-8",
                rec["text"] if rec else "")
        elif path == "/clock/hours":
            self._clock("hour")
        elif path == "/clock/minutes":
            self._clock("minute")
        elif path == "/clock/seconds":
            self._clock("second")
        else:
            self._send(404,
                "text/plain; charset=utf-8",
                "not found")

    def do_POST(self):
        if self.path.split("?")[0] != "/api/send":
            self._send(404,
                "text/plain; charset=utf-8",
                "not found")
            return
        try:
            length = int(
                self.headers.get(
                    "Content-Length", 0))
            body = json.loads(
                self.rfile.read(length) or b"{}")
        except (ValueError,
                json.JSONDecodeError):
            self._send(400,
                "application/json; charset=utf-8",
                json.dumps({"ok": False,
                    "error": "bad json"}))
            return
        sid = str(body.get("sid", "")).strip()
        if not sid.isdigit():
            self._send(400,
                "application/json; charset=utf-8",
                json.dumps({"ok": False,
                    "error": "sid must be digits"}))
            return
        DATA[sid] = {
            "text": str(body.get("text", "")),
            "sid_at": datetime.now(
                timezone.utc).strftime("%H:%M:%S UTC")
        }
        self._send(200,
            "application/json; charset=utf-8",
            json.dumps({"ok": True}))


HTTPServer(("0.0.0.0", PORT),
    Handler).serve_forever()
