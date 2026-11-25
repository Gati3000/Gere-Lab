"""Odbiornik webhooka z mostu do zwykłego WhatsApp (WAHA, WhatsApp Web).

WAHA wysyła każdą przychodzącą wiadomość (event "message") na ten serwer.
Wiadomość trafia przez save_message() do tego samego miejsca co z Cloud API:
dzienny plik YYYY-MM-DD.jsonl w Gere-Drive/Messeges (albo Database/Messeges,
gdy Gere-Drive nie jest pobrany) - to miejsce wyznacza Paths.py.

Ustawienia: User/Web-Config.yml -> whatsapp.bridge (hmac_key, host, port, path, session).
W WAHA ustaw webhook: url = http://<ten serwer>:<port><path>, events = ["message"],
hmac.key = to samo co hmac_key tutaj.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))
from Messages import save_message
from Paths import WEB_CONFIG

MAX_BODY = 1024 * 1024
log = logging.getLogger("whatsapp-bridge")

# czaty, których nie zapisujemy: grupy, statusy, kanały
SKIP_SUFFIXES = ("@g.us", "@broadcast", "@newsletter")


def read_yaml(path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config():
    section = (read_yaml(WEB_CONFIG).get("whatsapp") or {}).get("bridge") or {}
    return {
        "host": str(section.get("host") or "0.0.0.0"),
        "port": int(section.get("port") or 8082),
        "path": str(section.get("path") or "/waha"),
        "hmac_key": os.environ.get("WHATSAPP_BRIDGE_HMAC_KEY") or str(section.get("hmac_key") or ""),
        "session": str(section.get("session") or ""),
    }


def signature_ok(body, header, key):
    """WAHA: HMAC-SHA512 (hex, małe litery) z surowego body, nagłówek X-Webhook-Hmac."""
    if not key or not header:
        return False
    expected = hmac.new(key.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected.encode(), header.strip().lower().encode())


def to_timestamp(value):
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    return ts // 1000 if ts > 10 ** 11 else ts   # WAHA podaje sekundy, na wszelki wypadek obsługa ms


def store_event(event, cfg):
    if event.get("event") != "message":
        return 0
    if cfg["session"] and str(event.get("session") or "") != cfg["session"]:
        log.debug("Inna sesja (%s), pomijam", event.get("session"))
        return 0
    msg = event.get("payload") or {}
    if not isinstance(msg, dict) or msg.get("fromMe"):
        return 0
    chat = str(msg.get("from") or "")
    if not chat or chat.endswith(SKIP_SUFFIXES):
        return 0
    sender = re.sub(r"\D", "", chat.split("@")[0])
    msg_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(msg.get("id") or ""))
    if not sender or not msg_id:
        log.warning("Wiadomość bez nadawcy lub id, pomijam")
        return 0
    text = str(msg.get("body") or "").strip()
    if not text:
        log.warning("Wiadomość %s nie ma tekstu, pomijam", msg_id)
        return 0
    saved = save_message(sender, msg_id, text, to_timestamp(msg.get("timestamp")))
    if saved:
        log.info("Zapisano wiadomość od %s: %s", sender, msg_id)
    return saved


class Handler(BaseHTTPRequestHandler):
    server_version = "GereWhatsAppBridge"

    def log_message(self, fmt, *args):
        log.debug("%s %s", self.address_string(), fmt % args)

    def reply(self, code, body=b""):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        cfg = load_config()
        if self.path.split("?")[0] != cfg["path"]:
            return self.reply(404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.reply(400)
        if length > MAX_BODY:
            return self.reply(413)
        if length <= 0:
            return self.reply(400)
        body = self.rfile.read(length)
        if not signature_ok(body, self.headers.get("X-Webhook-Hmac", ""), cfg["hmac_key"]):
            log.warning("Zły podpis żądania, odrzucam")
            return self.reply(403)
        try:
            event = json.loads(body)
        except ValueError:
            return self.reply(400)
        if not isinstance(event, dict):
            return self.reply(400)
        try:
            store_event(event, cfg)
        except OSError:
            log.exception("Nie udało się zapisać wiadomości")
            return self.reply(500)   # WAHA ponowi wysyłkę
        self.reply(200)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    if not cfg["hmac_key"]:
        sys.exit("Brak w User/Web-Config.yml (whatsapp.bridge): hmac_key")
    server = ThreadingHTTPServer((cfg["host"], cfg["port"]), Handler)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: threading.Thread(target=server.shutdown).start())
    log.info("Start. Webhook: http://%s:%s%s", cfg["host"], cfg["port"], cfg["path"])
    server.serve_forever()
    server.server_close()
    log.info("Zatrzymano")


if __name__ == "__main__":
    main()
