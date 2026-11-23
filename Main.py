import runpy, sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "App"))
from Paths import WEB_UI_BIN


import signal
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "App"))
from Paths import WEB_UI_BIN

WEB_SERVE = WEB_UI_BIN / "Web-Ui.py"
PORT = 8080 


def main():
    if not WEB_SERVE.is_file():
        sys.exit(f"Web UI server not found: {WEB_SERVE}")

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    web = subprocess.Popen([sys.executable, str(WEB_SERVE)])
    print(f"Web UI started (PID {web.pid}): http://localhost:{PORT}", flush=True)

    try:
       
        while not stop.is_set():
            code = web.poll()
            if code is not None:
                sys.exit(f"Web UI stopped unexpectedly (exit code {code})")
            stop.wait(1)
    finally:
        if web.poll() is None:
            web.terminate()
            try:
                web.wait(timeout=5)
            except subprocess.TimeoutExpired:
                web.kill()
        print("Web UI stopped.", flush=True)


if __name__ == "__main__":
    main()
