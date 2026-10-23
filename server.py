from flask import Flask, request, jsonify, send_from_directory
import time

app = Flask(__name__, static_folder=None)

# хранилище: сид -> {"text", "pos", "sid_at"}
DATA = {}

# ---------- таблица символов Text Panel ----------

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


def _code(text, i, busy):
    """Код одного символа в 8 битах:
    бит 1 — SHIFT, бит 2 — индикатор печати,
    биты 3-8 — символ."""
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
    return ("1" if shift else "0") + ("1" if busy else "0") + code


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
# печатная машинка: ответ 14 бит —
# биты 1-6: статус — 100000 во время буквы, 000000 когда текст кончился
# бит 7: SHIFT, бит 8: индикатор печати (горит, пока печатается буква)
# биты 9-14: символ
# пример: буква m -> 100000 0 1 001101 = 10000001001101

@app.route("/text", methods=["GET", "POST"])
def text():
    sid = request.args.get("sid", "").strip()
    fmt = request.args.get("mode", "panel")
    if not sid:
        return jsonify({"value": "0" * 14})
    item = DATA.get(sid)
    if not item:
        return jsonify({"value": "0" * 14})

    # отмотать указатель на начало
    if request.args.get("reset") == "1":
        item["pos"] = 0
        return jsonify({"value": "0" * 14})

    # посмотреть конкретную букву, не двигая указатель
    idx = request.args.get("idx", "")
    if idx.isdigit():
        j = int(idx)
        n = len(item["text"])
        if j >= n:
            return jsonify({"value": "000000" + _code(item["text"], j, False)})
        return jsonify({"value": "100000" + _code(item["text"], j, True)})

    i = item.get("pos", 0)
    if fmt == "text":
        # обычный текст без панели: по одному символу
        raw = item["text"]
        value = raw[i] if i < len(raw) else ""
        if i < len(raw):
            item["pos"] = i + 1
        return jsonify({"value": value})

    n = len(item["text"])
    if n == 0:
        return jsonify({"value": "0" * 14})

    # текст закончился: статус и индикатор гаснут,
    # последняя буква держится на панели
    if i >= n:
        return jsonify({"value": "000000" + _code(item["text"], n - 1, False)})

    # идёт буква: статус 100000, индикатор горит
    item["pos"] = i + 1
    return jsonify({"value": "100000" + _code(item["text"], i, True)})


# адрес как в гайде intensblapi: /type?sid=... — то же, что /text
@app.route("/type", methods=["GET", "POST"])
def type_alias():
    return text()


# статусный вход: смотрит ТЕКУЩУЮ букву, не съедая её.
# им пользуйтесь для второго передатчика (лампы/статуса),
# чтобы лишний опрос не пропускал буквы
@app.route("/status")
def status_peek():
    sid = request.args.get("sid", "").strip()
    if not sid or sid not in DATA:
        return jsonify({"value": "0" * 14})
    item = DATA[sid]
    n = len(item["text"])
    if n == 0:
        return jsonify({"value": "0" * 14})
    i = item.get("pos", 0)
    if i >= n:
        return jsonify({"value": "000000" + _code(item["text"], n - 1, False)})
    return jsonify({"value": "100000" + _code(item["text"], i, True)})


# ---------- часы ----------
# формат как у intensblapi: 8 бит одним значением,
# первые 4 бита — десятки, последние 4 — единицы
# 50 минут -> 01010000, 55 минут -> 01010101, 23 часа -> 00100011
# offset часового пояса: ?offset=3 или заголовок offset

def _offset():
    try:
        return int(
            request.args.get("offset",
              request.headers.get("offset", "0"))
        )
    except (ValueError, TypeError):
        return 0


def _clock(value):
    s = str(value).zfill(2)
    bits = format(int(s[0]), "04b") + format(int(s[1]), "04b")
    return jsonify({"value": bits})


def _now(kind):
    t = time.localtime(
        time.time() + _offset() * 3600)
    if kind.startswith("h"):
        return t.tm_hour
    if kind.startswith("m"):
        return t.tm_min
    return t.tm_sec


@app.route("/clock/hours")
def clock_hours():
    return _clock(_now("hours"))


@app.route("/clock/minutes")
def clock_minutes():
    return _clock(_now("minutes"))


@app.route("/clock/seconds")
def clock_seconds():
    return _clock(_now("seconds"))


# даже если что-то сломается, игра получит JSON, а не ошибку
@app.errorhandler(500)
def server_error(e):
    return jsonify({"value": "00000000"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
