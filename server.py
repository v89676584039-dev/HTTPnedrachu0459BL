import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = {
    "message": "Привет! Это данные с сервера",
    "status": "ok",
    "count": 42,
    "nested": {"nested": True},
    "items": ["a", "b", "числа", 42],
    "sid": "",
    "text": "",
    "sid_at": ""
}

def read_file(path):
    with open(path, "rb") as f:
        return f.read()

def as_json(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/data":
            DATA["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._send(200, "application/json; charset=utf-8", as_json(DATA))
        elif self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", read_file("index.html"))
        elif self.path in ("/receiver", "/receiver.html"):
            self._send(200, "text/html; charset=utf-8", read_file("receiver.html"))
        else:
            self._send(404, "application/json; charset=utf-8", b'{"error": "not found"}')

    def do_POST(self):
        if self.path != "/api/send":
            self._send(404, "application/json; charset=utf-8", b'{"error": "not found"}')
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception:
            req = {}
        sid = str(req.get("sid", "")).strip()
        text = str(req.get("text", ""))
        if not sid.isdigit():
            self._send(400, "application/json; charset=utf-8", as_json({
                "ok": False,
                "error": "sid: только числа"
            }))
            return
        DATA["sid"] = sid
        DATA["text"] = text
        DATA["sid_at"] = datetime.now(timezone.utc).isoformat()
        self._send(200, "application/json; charset=utf-8", as_json({
            "ok": True,
            "sid": sid,
            "text": text
        }))

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("Server on port", port)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
