import http.server, socketserver, sys, posixpath, urllib.parse
from pathlib import Path


# Paths.py is in App/ (three levels above this file)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from Paths import WEB_UI_UI, WEB_UI_BIN, LANGUAGE

PORT = 8080
ROUTES = {"Ui": WEB_UI_UI, "Bin": WEB_UI_BIN, "Language": LANGUAGE}

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

    def do_GET(self):
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/Ui/Home.html")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer(("0.0.0.0", PORT), H).serve_forever()
import http.server, socketserver, sys, posixpath, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from Paths import WEB_UI_UI, WEB_UI_BIN, LANGUAGE

PORT = 8080
ROUTES = {"Ui": WEB_UI_UI, "Bin": WEB_UI_BIN, "Language": LANGUAGE}

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

    def do_GET(self):
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/Ui/Home.html")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer(("0.0.0.0", PORT), H).serve_forever()
