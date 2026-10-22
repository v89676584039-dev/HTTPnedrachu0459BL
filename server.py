from flask import Flask, request, jsonify, send_from_directory
import time

app = Flask(__name__, static_folder=None)

# хранилище: сид -> {"text": ..., "sid_at": ...}
DATA = {}


# ---------- страницы ----------

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/typewriter")
def typewriter():
    return send_from_directory(".", "typewriter.html")


@app.route("/clock")
def clock_page():
    return send_from_directory(".", "clock.html")


@app.route("/receiver")
def receiver():
    return send_from_directory(".", "receiver.html")


@app.route("/settings")
def settings():
    return send_from_directory(".", "settings.html")


# ---------- API для сайта ----------

@app.route("/api/send", methods=["POST"])
def api_send():
    body = request.get_json(silent=True) or {}
    sid = str(body.get("sid", "")).strip()
    text = str(body.get("text", ""))
    if not sid or not sid.isdigit():
        return jsonify({"ok": False}), 400
    DATA[sid] = {
        "text": text,
        "sid_at": time.strftime("%H:%M:%S")
    }
    return jsonify({"ok": True})


@app.route("/api/data")
def api_data():
    sid = request.args.get("sid", "").strip()
    item = DATA.get(sid)
    if not item:
        return jsonify({})
    return jsonify({
        "sid": sid,
        "text": item["text"],
        "sid_at": item["sid_at"]
    })


# ---------- API для Build Logic ----------

@app.route("/text")
def text():
    sid = request.args.get("sid", "").strip()
    fmt = request.args.get("mode", "bin")
    if not sid:
        return jsonify({"value": ""})
    item = DATA.get(sid)
    if not item:
        return jsonify({"value": ""})
    raw = item["text"]
    if fmt == "bin":
        raw = "".join(
            format(b, "08b")
            for b in raw.encode("utf-8"))
    return jsonify({"value": raw})


# ---------- часы ----------

def _offset():
    try:
        return int(
            request.args.get("offset",
              request.headers.get("offset", "0"))
        )
    except (ValueError, TypeError):
        return 0


@app.route("/clock/hours")
def clock_hours():
    t = time.localtime(
        time.time() + _offset() * 3600)
    return str(t.tm_hour)


@app.route("/clock/minutes")
def clock_minutes():
    t = time.localtime(
        time.time() + _offset() * 3600)
    return str(t.tm_min)


@app.route("/clock/seconds")
def clock_seconds():
    t = time.localtime(
        time.time() + _offset() * 3600)
    return str(t.tm_sec)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
