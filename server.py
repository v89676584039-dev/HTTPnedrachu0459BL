import json
import time
from http.server import (
    HTTPServer,
    SimpleHTTPRequestHandler
)
from datetime import (
    datetime, timezone
)

DATA = {
    "message":
        "Привет! Это данные с сервера",
    "items":
        ["текст", "числа", 42,
         {"nested": True}],
    "updated_at": None,
}


class Handler(SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith(
                "/api/data"):
            DATA["updated_at"] = (
                datetime
                .now(timezone.utc)
                .isoformat())
            self.send_json(200, DATA)
        elif self.path.startswith(
                "/api/time"):
            now = datetime.now(timezone.utc)
            self.send_json(200, {
                "utc": now.isoformat(),
                "unix": time.time(),
            })
        else:
            super().do_GET()

    def send_json(self, code, obj):
        body = json.dumps(
            obj,
            ensure_ascii=False
        ).encode("utf-8")
        self.send_response(code)
        self.send_header(
            "Content-Type",
            "application/json; "
            "charset=utf-8")
        self.send_header(
            "Access-Control-Allow-Origin",
            "*")
        self.send_header(
            "Content-Length",
            str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    host, port = "0.0.0.0", 8000
    print("Сервер запущен:")
    print("http://localhost:" + str(port))
    HTTPServer((host, port), Handler
        ).serve_forever()
