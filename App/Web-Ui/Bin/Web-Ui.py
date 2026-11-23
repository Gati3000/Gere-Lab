import http.server, socketserver, sys, posixpath, urllib.parse, json, os, yaml
from pathlib import Path


# Paths.py is in App/ (three levels above this file)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from Paths import WEB_UI_UI, WEB_UI_BIN, LANGUAGE, WEB_CONFIG, INDEXES

PORT = 8080
ROUTES = {"Ui": WEB_UI_UI, "Bin": WEB_UI_BIN, "Language": LANGUAGE}
MAX_BODY = 64 * 1024
MAX_LINKS = 200
MASK = "********"
# section -> field -> (type, secret). Only these fields can be saved from Settings
WHATSAPP_FIELDS = {
    "cloud_api": {
        "enabled": (bool, False), "host": (str, False), "port": (int, False), "path": (str, False), "phone_number_id": (str, False),
        "verify_token": (str, True), "app_secret": (str, True), "access_token": (str, True),
    },
    "bridge": {"enabled": (bool, False), "url": (str, False), "session": (str, False), "api_key": (str, True)},
    "provider": {"enabled": (bool, False), "account_id": (str, False), "sender_number": (str, False), "auth_token": (str, True)},
}


def read_config(path=WEB_CONFIG):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_config(cfg, path=WEB_CONFIG):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    os.replace(part, path)


def whatsapp_view(cfg):
    saved = cfg.get("whatsapp") if isinstance(cfg.get("whatsapp"), dict) else {}
    out = {}
    for section, fields in WHATSAPP_FIELDS.items():
        values = saved.get(section) if isinstance(saved.get(section), dict) else {}
        out[section] = {}
        for name, (kind, secret) in fields.items():
            value = values.get(name)
            if kind is bool:
                out[section][name] = value is True
            elif value in (None, ""):
                out[section][name] = ""
            else:
                out[section][name] = MASK if secret else value
    return out


def whatsapp_merge(cfg, incoming):
    if not isinstance(cfg.get("whatsapp"), dict):
        cfg["whatsapp"] = {}
    for section, fields in WHATSAPP_FIELDS.items():
        sent = incoming.get(section)
        if not isinstance(sent, dict):
            continue
        if not isinstance(cfg["whatsapp"].get(section), dict):
            cfg["whatsapp"][section] = {}
        target = cfg["whatsapp"][section]
        for name, (kind, secret) in fields.items():
            if name not in sent:
                continue
            if kind is bool:
                target[name] = sent[name] is True
                continue
            value = str(sent[name]).strip()
            # masked secret means "unchanged"
            if secret and value == MASK:
                continue
            if value == "":
                target.pop(name, None)
                continue
            target[name] = kind(value)


def clean_link(data):
    name = str(data.get("name", "")).strip()[:80]
    url = str(data.get("url", "")).strip()[:500]
    desc = str(data.get("desc", "")).strip()[:200]
    parts = urllib.parse.urlparse(url)
    # only web links, so a saved link can never run a script
    if not name or parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("bad link")
    return {"name": name, "url": url, "desc": desc}


def links_list(cfg):
    out = []
    for item in cfg.get("links") or []:
        try:
            out.append(clean_link(item))
        except (ValueError, AttributeError):
            continue
    return out


class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = posixpath.normpath(urllib.parse.unquote(urllib.parse.urlparse(path).path))
        parts = [p for p in path.split("/") if p and p not in (".", "..")]
        if not parts or parts[0] not in ROUTES:
            return str(WEB_UI_UI / "__not_found__")
        return str(ROUTES[parts[0]].joinpath(*parts[1:]))

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def send_json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/Ui/Home.html")
            self.end_headers()
            return
        if urllib.parse.urlparse(self.path).path == "/api/config":
            try:
                return self.send_json(200, {"whatsapp": whatsapp_view(read_config())})
            except (OSError, yaml.YAMLError):
                return self.send_error(500, "Config read failed")
        if urllib.parse.urlparse(self.path).path == "/api/links":
            try:
                return self.send_json(200, {"links": links_list(read_config(INDEXES))})
            except (OSError, yaml.YAMLError):
                return self.send_error(500, "Links read failed")
        super().do_GET()

    def read_json(self):
        # JSON content type blocks simple cross-site form posts
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self.send_error(415)
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return None
        if length <= 0 or length > MAX_BODY:
            self.send_error(400)
            return None
        try:
            return json.loads(self.rfile.read(length))
        except ValueError:
            self.send_error(400)
            return None

    def save_config(self, data):
        try:
            cfg = read_config()
            whatsapp_merge(cfg, data["whatsapp"])
        except (ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError):
            return self.send_error(400)
        try:
            write_config(cfg)
        except OSError:
            return self.send_error(500, "Config write failed")
        self.send_json(200, {"whatsapp": whatsapp_view(cfg)})

    def save_link(self, data):
        try:
            link = clean_link(data)
            cfg = read_config(INDEXES)
            links = links_list(cfg)
            if len(links) >= MAX_LINKS:
                raise ValueError("too many links")
            links.append(link)
            cfg["links"] = links
        except (ValueError, TypeError, AttributeError, yaml.YAMLError):
            return self.send_error(400)
        try:
            write_config(cfg, INDEXES)
        except OSError:
            return self.send_error(500, "Links write failed")
        self.send_json(200, {"links": links})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path not in ("/api/config", "/api/links"):
            return self.send_error(404, "Not found")
        data = self.read_json()
        if data is None:
            return
        if path == "/api/links":
            return self.save_link(data)
        self.save_config(data)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer(("0.0.0.0", PORT), H).serve_forever()
