import signal
import subprocess
import sys
import threading
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "App"))
from Paths import WEB_UI_BIN, WHATSAPP_BUSINESS, WEB_CONFIG, INQUIRIES

WEB_SERVE = WEB_UI_BIN / "Web-Ui.py"
PORT = 8080


def cloud_api_enabled():
    try:
        cfg = yaml.safe_load(WEB_CONFIG.read_text(encoding="utf-8")) or {}
        return cfg["whatsapp"]["cloud_api"]["enabled"] is True
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return False


def main():
    if not WEB_SERVE.is_file():
        sys.exit(f"Web UI server not found: {WEB_SERVE}")

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    web = subprocess.Popen([sys.executable, str(WEB_SERVE)])
    print(f"Web UI started (PID {web.pid}): http://localhost:{PORT}", flush=True)

    wa = None
    if not cloud_api_enabled():
        print("WhatsApp Cloud API wyłączone w Settings, webhook nie startuje.", flush=True)
    elif not WHATSAPP_BUSINESS.is_file():
        print(f"Brak pliku webhooka: {WHATSAPP_BUSINESS}", flush=True)
    else:
        wa = subprocess.Popen([sys.executable, str(WHATSAPP_BUSINESS)])
        print(f"WhatsApp webhook started (PID {wa.pid})", flush=True)

    inq = None
    if INQUIRIES.is_file():
        inq = subprocess.Popen([sys.executable, str(INQUIRIES), "run"])
        print(f"Inquiries processor started (PID {inq.pid})", flush=True)
    else:
        print(f"Brak pliku: {INQUIRIES}", flush=True)

    try:
        while not stop.is_set():
            code = web.poll()
            if code is not None:
                sys.exit(f"Web UI stopped unexpectedly (exit code {code})")
            if wa is not None and wa.poll() is not None:
                print(f"WhatsApp webhook zakończył się (kod {wa.returncode}), Web UI działa dalej.", flush=True)
                wa = None
            if inq is not None and inq.poll() is not None:
                print(f"Inquiries processor zakończył się (kod {inq.returncode}), Web UI działa dalej.", flush=True)
                inq = None
            stop.wait(1)
    finally:
        for name, proc in (("Inquiries processor", inq), ("WhatsApp webhook", wa), ("Web UI", web)):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print(f"{name} stopped.", flush=True)


if __name__ == "__main__":
    main()
