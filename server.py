from flask import Flask, request, jsonify, send_from_directory
import time

app = Flask(__name__, static_folder=None)

# хранилище: сид -> {"text", "pos", "sid_at"}
DATA = {}

# ---------- таблица символов Text Panel ----------

# обычные символы: строчные буквы, цифры, знаки
PANEL6 = {}
for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    PANEL6[ch] = format(i + 1, "06b")
for i, ch in enumerate("1234567890"):
    PANEL6[ch] = format(0b011011 + i, "06b")
PANEL6.update({
    "-": "100101", "=": "100110", ".": "100111",
    ",": "101000", ";": "101001", "/": "101010",
    "à": "101011", "â": "101100", "ç": "101101",
    "è": "101110", "é": "101111", "ê": "110000",
    "î": "110001", "ï": "110010", "û": "110011",
    "|": "110100", "[": "110101", "]": "110110",
    '"': "110111",
    "◀": "111000", "▼": "111001",
    "▲": "111010", "▶": "111011",
})

# SHIFT-ряд: заглавные буквы и верхние знаки.
# значение — обычный символ, код которого берём из PANEL6
SHIFT6 = {}
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    SHIFT6[ch] = "abcdefghijklmnopqrstuvwxyz"[i]
SHIFT6.update({
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "?": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", ":": ";", "~": "/",
    "'": ",",
    "À": "à", "Â": "â", "Ç": "ç", "È": "è", "É": "é",
    "Ê": "ê", "Î": "î", "Ï": "ï", "Û": "û",
    "¦": "|", "{": "[", "}": "]", "^": '"',
})


def _code(text, i):
    """Код одного символа в 8 битах:
    бит 1 — пустой, бит 2 — SHIFT, биты 3-8 — символ."""
    if i >= len(text):
        if not text:
            return "00000000"
        i = len(text) - 1
    ch = text[i]
    shift = False
    if ch in SHIFT6:
        shift = True
        ch = SHIFT6[ch]
    code = PANEL6.get(ch.lower(), "000000")
    return ("1" if shift else "0") + "0" + code


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
        "pos": 0,
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
# каждая просьба отдаёт код СЛЕДУЮЩЕЙ буквы,
# 8 бит: пустой бит + SHIFT + 6 бит символа

@app.route("/text", methods=["GET", "POST"])
def text():
    sid = request.args.get("sid", "").strip()
    fmt = request.args.get("mode", "panel")
    if not sid:
        return jsonify({"value": "00000000"})
    item = DATA.get(sid)
    if not item:
        return jsonify({"value": "00000000"})

    # отмотать указатель на начало
    if request.args.get("reset") == "1":
        item["pos"] = 0
        return jsonify({"value": "00000000"})

    # посмотреть конкретную букву, не двигая указатель
    idx = request.args.get("idx", "")
    if idx.isdigit():
        return jsonify({"value": _code(item["text"], int(idx))})

    i = item.get("pos", 0)
    if fmt == "text":
        # обычный текст без панели: по одному символу
        raw = item["text"]
        value = raw[i] if i < len(raw) else ""
        if i < len(raw):
            item["pos"] = i + 1
        return jsonify({"value": value})

    code = _code(item["text"], i)
    if i < len(item["text"]):
        item["pos"] = i + 1
    return jsonify({"value": code})


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
