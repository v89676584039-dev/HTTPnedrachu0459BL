from flask import Flask, request, jsonify, send_from_directory
import time
import collections
import threading
import os

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024

# хранилище: сид -> {"text", "pos", "sid_at"}
DATA = {}
# хранилище анимаций: сид -> {"frames", "pos"}
ANIMS = {}

# ---------- защита от флуда и баны ----------

_lock = threading.Lock()
_hits = collections.defaultdict(collections.deque)

def _allow(key, limit, window):
    """True, если запрос в лимитах."""
    now = time.time()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

# ============================================================
#  ПАРОЛЬ АДМИНКИ. МЕНЯТЬ ТОЛЬКО ЗДЕСЬ.
#  Впишите свой пароль МЕЖДУ кавычками ниже.
#  Кавычки должны быть прямыми: "  а не " или "
#  Пример: ADMIN_KEY = "krasnodar-panel-qw91"
# ============================================================
ADMIN_KEY = os.environ.get("ADMIN_KEY", "moi-parol-1234")

BAN_TIME = 300  # бан живёт 5 минут
BLOCKED_IPS = {}   # ip  -> время окончания бана
BLOCKED_SIDS = {}  # sid -> время окончания бана
LOG = collections.deque(maxlen=300)

def _banned(storage, key):
    exp = storage.get(key)
    if exp is None:
        return False
    if time.time() >= exp:  # срок вышел - бан исчезает сам
        storage.pop(key, None)
        return False
    return True

def _sid_from_request():
    if request.args.get("sid"):
        return request.args.get("sid")[:64]
    body = request.get_json(silent=True)
    if isinstance(body, dict) and "sid" in body:
        return str(body["sid"])[:64]
    return ""

@app.before_request
def guard():
    if os.environ.get("SHUTDOWN") == "1":
        return jsonify({"value": "00000000"}), 429
    ip = (request.headers.get("X-Forwarded-For")
          or request.remote_addr or "?").split(",")[0].strip()
    sid = _sid_from_request()
    reason = ""
    if _banned(BLOCKED_IPS, ip):
        reason = "IP заблокирован"
    elif sid and _banned(BLOCKED_SIDS, sid):
        reason = "SID заблокирован"
    elif not _allow("G", 120, 10):
        reason = "лимит сервера"
    elif not _allow("ip:" + ip, 40, 10):
        reason = "флуд с IP"
    elif sid and not _allow("sid:" + sid, 30, 10):
        reason = "флуд по SID"
    LOG.appendleft({
        "t": time.strftime("%H:%M:%S"),
        "ip": ip, "sid": sid or "-",
        "m": request.method, "p": request.path,
        "r": reason or "ok"
    })
    if reason:
        code = 403 if "заблокирован" in reason else 429
        return jsonify({"value": "00000000"}), code

def _valid_sid(sid):
    return bool(sid) and len(sid) <= 64 and all(
        c.isalnum() or c in "-_" for c in sid)

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
    бит 1 - SHIFT, бит 2 - индикатор печати,
    биты 3-8 - символ."""
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


@app.route("/editor")
def editor():
    return send_from_directory(".", "editor.html")


# ---------- API для сайта ----------

@app.route("/api/send", methods=["POST"])
def api_send():
    body = request.get_json(silent=True) or {}
    sid = str(body.get("sid", "")).strip()
    text = str(body.get("text", ""))[:5000]
    if not _valid_sid(sid):
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


# ---------- анимация для панели RGB2 ----------
# работает как печатная машинка, только для пикселей.
# редактор шлёт кадры, игра опрашивает по ОДНОМУ
# пикселю за запрос, указатель двигается сам.
# ответ ровно 8 бит (под 8 входов передатчика):
# бит 1: статус - 1 пока идёт анимация,
#        0 когда всё показано (или анимации нет)
# биты 2-7: пиксель RRGGBB - в каждом канале два
#        бита, яркий (170) и тусклый (85):
#        11=255, 10=170, 01=85, 00=0
#        входы: 2=красный яркий, 3=красный тусклый,
#        4=зелёный яркий, 5=зелёный тусклый,
#        6=синий яркий, 7=синий тусклый
# бит 8: 0 (резерв)
# пример: ярко-синий пиксель во время показа:
# 1 000011 0 = 10000110
# нумерация пикселей: по кадрам подряд, внутри кадра
# по строкам слева направо, сверху вниз.
# после конца анимации последний пиксель последнего
# кадра держится на панели, как последняя буква.
# скорость задаёт не сервер, а частота опроса игрой -
# как у печатной машинки.


@app.route("/api/gif", methods=["POST"])
def api_gif():
    body = request.get_json(silent=True) or {}
    sid = str(body.get("sid", "")).strip()
    if not _valid_sid(sid):
        return jsonify({"ok": False}), 400
    raw = body.get("frames")
    if not raw:  # пустой список - стоп анимации
        ANIMS.pop(sid, None)
        return jsonify({"ok": True, "frames": 0})
    frames = []
    for f in raw[:600]:  # максимум 600 кадров
        if isinstance(f, list) and len(f) == 256:
            # каждый элемент - код цвета "rrggbb"
            # по 2 бита на канал, как в редакторе
            row = []
            for c in f:
                c = str(c)[:6].ljust(6, "0")
                ok = all(ch in "01" for ch in c)
                row.append(c if ok else "000000")
            frames.append("".join(row))
    if not frames:
        return jsonify({"ok": False}), 400
    ANIMS[sid] = {
        "frames": frames,
        "pos": 0
    }
    return jsonify({"ok": True, "frames": len(frames)})


def _px_bits(a, n):
    """6 бит пикселя с номером n (по кадрам подряд)."""
    frame = a["frames"][n // 256]
    return frame[(n % 256) * 6:(n % 256) * 6 + 6]


@app.route("/pixel", methods=["GET", "POST"])
def pixel():
    sid = request.args.get("sid", "").strip()
    if not sid:
        return jsonify({"value": "00000000"})
    a = ANIMS.get(sid)
    if not a:
        return jsonify({"value": "00000000"})

    # отмотать указатель на начало
    if request.args.get("reset") == "1":
        a["pos"] = 0
        return jsonify({"value": "00000000"})

    # подсмотреть конкретный пиксель, не двигая указатель
    idx = request.args.get("idx", "")
    if idx.isdigit():
        j = int(idx)
        total = len(a["frames"]) * 256
        if j >= total:
            j = total - 1
        return jsonify({"value": "1" + _px_bits(a, j) + "0"})

    total = len(a["frames"]) * 256
    i = a["pos"]

    # всё показано: статус гаснет, последний пиксель
    # последнего кадра держится на панели
    if i >= total:
        return jsonify({"value": "0" + _px_bits(a, total - 1) + "0"})

    # идёт показ: статус горит, указатель двигается
    a["pos"] = i + 1
    return jsonify({"value": "1" + _px_bits(a, i) + "0"})


# статусный вход: горит 1 на первом входе, пока идёт
# показ, 0 - когда всё показано или анимации нет.
# цвет не возвращает и указатель не двигает
@app.route("/pixel/status")
def pixel_status_peek():
    sid = request.args.get("sid", "").strip()
    a = ANIMS.get(sid)
    if not a:
        return jsonify({"value": "00000000"})
    total = len(a["frames"]) * 256
    if a["pos"] >= total:
        return jsonify({"value": "00000000"})
    return jsonify({"value": "10000000"})


# ---------- API для Build Logic ----------
# печатная машинка: ответ 14 бит -
# биты 1-6: статус - 100000 во время буквы, 000000 когда текст кончился
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


# адрес как в гайде intensblapi: /type?sid=... - то же, что /text
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
# первые 4 бита - десятки, последние 4 - единицы
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


# ---------- секретная админка ----------

def _is_admin():
    key = request.args.get("key") or ""
    if not key:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            key = str(body.get("key", ""))
    return key == ADMIN_KEY


@app.route("/admin")
def admin_page():
    return send_from_directory(".", "admin.html")


@app.route("/api/admin/data")
def admin_data():
    if not _is_admin():
        return jsonify({"ok": False}), 403
    now = time.time()
    ips = {k: max(0, round(v - now))
           for k, v in BLOCKED_IPS.items() if v > now}
    sids = {k: max(0, round(v - now))
            for k, v in BLOCKED_SIDS.items() if v > now}
    return jsonify({"log": list(LOG)[:100], "ips": ips, "sids": sids})


@app.route("/api/admin/block", methods=["POST"])
def admin_block():
    if not _is_admin():
        return jsonify({"ok": False}), 403
    b = request.get_json(silent=True) or {}
    typ = b.get("type")
    val = str(b.get("value", "")).strip()
    act = b.get("action", "block")
    if typ not in ("ip", "sid") or not val:
        return jsonify({"ok": False}), 400
    storage = BLOCKED_IPS if typ == "ip" else BLOCKED_SIDS
    if act == "block":
        storage[val] = time.time() + BAN_TIME
    else:
        storage.pop(val, None)
    return jsonify({"ok": True})


# даже если что-то сломается, игра получит JSON, а не ошибку
@app.errorhandler(500)
def server_error(e):
    return jsonify({"value": "00000000"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
