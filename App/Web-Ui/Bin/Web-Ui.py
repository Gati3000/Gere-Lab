import http.server, socketserver, sys, posixpath, urllib.parse, urllib.request, urllib.error, json, os, yaml
from pathlib import Path


# Paths.py is in App/ (three levels above this file)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from Paths import WEB_UI_UI, WEB_UI_BIN, LANGUAGE, WEB_CONFIG, INDEXES
from Messages import prune, read_messages, retention_days
import Invoices

PORT = 8080
ROUTES = {"Ui": WEB_UI_UI, "Bin": WEB_UI_BIN, "Language": LANGUAGE}
MAX_BODY = 64 * 1024
MAX_LINKS = 200
MASK = "********"
TEST_TIMEOUT = 5
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


TEST_REQUIRED = {
    "cloud_api": ("phone_number_id", "access_token"),
    "bridge": ("url",),
    "provider": ("account_id", "auth_token", "sender_number"),
}


def http_check(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TEST_TIMEOUT):
            return "waTestOk"
    except urllib.error.HTTPError as e:
        return "waTestBadKey" if e.code in (400, 401, 403) else "waTestFail"
    except (urllib.error.URLError, OSError, ValueError):
        return "waTestNoConn"


def whatsapp_test(cfg, section):
    saved = cfg.get("whatsapp") if isinstance(cfg.get("whatsapp"), dict) else {}
    values = saved.get(section) if isinstance(saved.get(section), dict) else {}
    if any(not values.get(name) for name in TEST_REQUIRED[section]):
        return "waTestMissing"
    if section == "cloud_api":
        url = "https://graph.facebook.com/" + urllib.parse.quote(str(values["phone_number_id"]), safe="")
        return http_check(url, {"Authorization": "Bearer " + str(values["access_token"])})
    if section == "bridge":
        url = str(values["url"]).strip()
        # only web links, so a test can never read a local file
        if urllib.parse.urlparse(url).scheme not in ("http", "https"):
            return "waTestMissing"
        headers = {"X-Api-Key": str(values["api_key"])} if values.get("api_key") else {}
        return http_check(url, headers)
    # TODO provider: real request once the provider is chosen, for now only checks that the fields are filled
    return "waTestFilled"


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


def invoice_route(path):
    """'/api/invoices/INV-000001/approve' -> ('INV-000001', 'approve'); inaczej None."""
    parts = path.strip("/").split("/")
    if len(parts) == 4 and parts[:2] == ["api", "invoices"] and parts[3] in ("approve", "reject"):
        return parts[2], parts[3]
    return None


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
                cfg = read_config()
                return self.send_json(200, {"whatsapp": whatsapp_view(cfg), "messages": {"retention_days": retention_days(cfg)}})
            except (OSError, yaml.YAMLError):
                return self.send_error(500, "Config read failed")
        if urllib.parse.urlparse(self.path).path == "/api/messages":
            try:
                return self.send_json(200, {"messages": read_messages(retention_days())})
            except (OSError, yaml.YAMLError):
                return self.send_error(500, "Messages read failed")
        if urllib.parse.urlparse(self.path).path == "/api/links":
            try:
                return self.send_json(200, {"links": links_list(read_config(INDEXES))})
            except (OSError, yaml.YAMLError):
                return self.send_error(500, "Links read failed")
        if urllib.parse.urlparse(self.path).path == "/api/invoices":
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            status = (query.get("status") or [None])[0]
            if status is not None and status not in Invoices.STATUSES:
                return self.send_error(400)
            try:
                return self.send_json(200, {"invoices": Invoices.list_invoices(status)})
            except OSError:
                return self.send_error(500, "Invoices read failed")
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
            messages = data.get("messages")
            if isinstance(messages, dict) and "retention_days" in messages:
                days = int(str(messages["retention_days"]).strip() or 0)
                if days < 0:
                    raise ValueError("retention_days < 0")
                if not isinstance(cfg.get("messages"), dict):
                    cfg["messages"] = {}
                cfg["messages"]["retention_days"] = days
        except (ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError):
            return self.send_error(400)
        try:
            write_config(cfg)
        except OSError:
            return self.send_error(500, "Config write failed")
        removed = prune(retention_days(cfg))
        self.send_json(200, {"whatsapp": whatsapp_view(cfg), "messages": {"retention_days": retention_days(cfg), "removed": len(removed)}})

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

    def run_test(self, data):
        section = data.get("section") if isinstance(data, dict) else None
        if section not in TEST_REQUIRED:
            return self.send_error(400)
        try:
            code = whatsapp_test(read_config(), section)
        except (OSError, yaml.YAMLError):
            return self.send_error(500, "Config read failed")
        self.send_json(200, {"code": code})

    def create_invoice(self, data):
        try:
            invoice = Invoices.create_invoice(
                data["items"], client_id=data.get("client_id"), contact=data.get("contact", ""),
                inquiry_id=data.get("inquiry_id"), note=str(data.get("note", "")).strip()[:500], source="api")
        except (ValueError, KeyError, TypeError, AttributeError):
            return self.send_error(400)
        except OSError:
            return self.send_error(500, "Invoice write failed")
        self.send_json(201, {"invoice": invoice})

    def decide_invoice(self, invoice_id, action, data):
        status = "approved" if action == "approve" else "rejected"
        reason = str(data.get("reason", "")).strip()[:500] if isinstance(data, dict) else ""
        try:
            invoice = Invoices.decide(invoice_id, status, reason)
        except ValueError:
            return self.send_error(400)
        except Invoices.NotFound:
            return self.send_error(404, "No such invoice")
        except Invoices.AlreadyDecided:
            return self.send_error(409, "Already decided")
        except OSError:
            return self.send_error(500, "Invoice write failed")
        self.send_json(200, {"invoice": invoice})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        route = invoice_route(path)
        if path not in ("/api/config", "/api/links", "/api/test", "/api/invoices") and route is None:
            return self.send_error(404, "Not found")
        data = self.read_json()
        if data is None:
            return
        if path == "/api/invoices":
            return self.create_invoice(data)
        if route is not None:
            return self.decide_invoice(route[0], route[1], data)
        if path == "/api/links":
            return self.save_link(data)
        if path == "/api/test":
            return self.run_test(data)
        self.save_config(data)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer(("0.0.0.0", PORT), H).serve_forever()
