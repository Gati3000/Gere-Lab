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
from urllib.parse import parse_qs, urlparse

import yaml

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))
from Messages import save_message

ROOT = APP.parent
LAUNCHER_CONFIG = ROOT / "User" / "Config.yml"
WEB_CONFIG = ROOT / "User" / "Web-Config.yml"
DEFAULT_INBOX = "Database/inbox"
MAX_BODY = 1024 * 1024
log = logging.getLogger("whatsapp")


def read_yaml(path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config():
    section = read_yaml(WEB_CONFIG).get("whatsapp") or {}
    cloud = section.get("cloud_api") or {}
    inbox = Path(str(read_yaml(LAUNCHER_CONFIG).get("inbox_dir", DEFAULT_INBOX))).expanduser()
    return {
        "host": str(cloud.get("host", "0.0.0.0")),
        "port": int(cloud.get("port", 8081)),
        "path": str(cloud.get("path", "/webhook")),
        "verify_token": os.environ.get("WHATSAPP_VERIFY_TOKEN") or str(cloud.get("verify_token") or ""),
        "app_secret": os.environ.get("WHATSAPP_APP_SECRET") or str(cloud.get("app_secret") or ""),
        "phone_number_id": str(cloud.get("phone_number_id") or ""),
        "inbox_dir": inbox if inbox.is_absolute() else ROOT / inbox,
    }


def signature_ok(body, header, secret):
    if not secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), header[7:].encode())


def message_text(msg):
    kind = msg.get("type")
    if kind == "text":
        return (msg.get("text") or {}).get("body", "")
    if kind in ("image", "video", "document"):
        return (msg.get(kind) or {}).get("caption", "")
    if kind == "button":
        return (msg.get("button") or {}).get("text", "")
    if kind == "interactive":
        interactive = msg.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("title", "")
    return ""


def store_message(msg, inbox):
    sender = re.sub(r"\D", "", str(msg.get("from") or ""))
    msg_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(msg.get("id") or ""))
    if not sender or not msg_id:
        log.warning("Wiadomość bez nadawcy lub id, pomijam")
        return 0
    text = str(message_text(msg)).strip()
    if not text:
        log.warning("Wiadomość %s (typ %s) nie ma tekstu, pomijam", msg_id, msg.get("type"))
        return 0
    try:
        sent_ts = int(msg.get("timestamp"))
    except (TypeError, ValueError):
        sent_ts = None
    saved = save_message(sender, msg_id, text, sent_ts)
    if saved:
        log.info("Zapisano wiadomość od %s: %s", sender, msg_id)
    return saved


def save_messages(payload, cfg):
    if payload.get("object") != "whatsapp_business_account":
        return 0
    inbox = cfg["inbox_dir"]
    inbox.mkdir(parents=True, exist_ok=True)
    saved = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            number_id = str((value.get("metadata") or {}).get("phone_number_id") or "")
            if cfg["phone_number_id"] and number_id and number_id != cfg["phone_number_id"]:
                log.warning("Wiadomość dla innego numeru (%s), pomijam", number_id)
                continue
            for msg in value.get("messages") or []:
                saved += store_message(msg, inbox)
    return saved


class Handler(BaseHTTPRequestHandler):
    server_version = "GereWhatsApp"

    def log_message(self, fmt, *args):
        log.debug("%s %s", self.address_string(), fmt % args)

    def reply(self, code, body=b""):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        cfg = load_config()
        url = urlparse(self.path)
        if url.path != cfg["path"]:
            return self.reply(404)
        query = parse_qs(url.query)
        mode = query.get("hub.mode", [""])[0]
        token = query.get("hub.verify_token", [""])[0]
        challenge = query.get("hub.challenge", [""])[0]
        if mode == "subscribe" and cfg["verify_token"] and hmac.compare_digest(
                token.encode(), cfg["verify_token"].encode()):
            log.info("Weryfikacja webhooka przeszła")
            return self.reply(200, challenge.encode())
        log.warning("Weryfikacja webhooka odrzucona")
        self.reply(403)

    def do_POST(self):
        cfg = load_config()
        if urlparse(self.path).path != cfg["path"]:
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
        if not signature_ok(body, self.headers.get("X-Hub-Signature-256", ""), cfg["app_secret"]):
            log.warning("Zły podpis żądania, odrzucam")
            return self.reply(403)
        try:
            payload = json.loads(body)
        except ValueError:
            return self.reply(400)
        if not isinstance(payload, dict):
            return self.reply(400)
        try:
            save_messages(payload, cfg)
        except OSError:
            log.exception("Nie udało się zapisać wiadomości")
            return self.reply(500)
        self.reply(200)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    missing = [key for key in ("verify_token", "app_secret") if not cfg[key]]
    if missing:
        sys.exit("Brak w User/Web-Config.yml (whatsapp.cloud_api): " + ", ".join(missing))
    server = ThreadingHTTPServer((cfg["host"], cfg["port"]), Handler)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: threading.Thread(target=server.shutdown).start())
    log.info("Start. Webhook: http://%s:%s%s, inbox: %s", cfg["host"], cfg["port"], cfg["path"], cfg["inbox_dir"])
    server.serve_forever()
    server.server_close()
    log.info("Zatrzymano")


if __name__ == "__main__":
    main()
