import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "App"))
from Paths import WEB_UI_BIN, WHATSAPP_BUSINESS, WEB_CONFIG, INQUIRIES, INVOICER

WEB_SERVE = WEB_UI_BIN / "Web-Ui.py"
PORT = 8080


def cloud_api_enabled():
    try:
        cfg = yaml.safe_load(WEB_CONFIG.read_text(encoding="utf-8")) or {}
        return cfg["whatsapp"]["cloud_api"]["enabled"] is True
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return False


def start_webhook():
    """Uruchamia webhook WhatsApp według aktualnych ustawień. Zwraca Popen albo None."""
    if not cloud_api_enabled():
        print("WhatsApp Cloud API wyłączone w Settings, webhook nie startuje.", flush=True)
        return None
    if not WHATSAPP_BUSINESS.is_file():
        print(f"Brak pliku webhooka: {WHATSAPP_BUSINESS}", flush=True)
        return None
    proc = subprocess.Popen([sys.executable, str(WHATSAPP_BUSINESS)])
    print(f"WhatsApp webhook started (PID {proc.pid})", flush=True)
    return proc


def stop_proc(name, proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print(f"{name} stopped.", flush=True)


def main():
    if not WEB_SERVE.is_file():
        sys.exit(f"Web UI server not found: {WEB_SERVE}")

    stop = threading.Event()
    restart_wa = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    signal.signal(signal.SIGUSR1, lambda *_: restart_wa.set())

    web = subprocess.Popen([sys.executable, str(WEB_SERVE)],
                           env={**os.environ, "GERE_MAIN_PID": str(os.getpid())})
    print(f"Web UI started (PID {web.pid}): http://localhost:{PORT}", flush=True)

    wa = start_webhook()

    inq = None
    if INQUIRIES.is_file():
        inq = subprocess.Popen([sys.executable, str(INQUIRIES), "run"])
        print(f"Inquiries processor started (PID {inq.pid})", flush=True)
    else:
        print(f"Brak pliku: {INQUIRIES}", flush=True)

    inv = None
    if INVOICER.is_file():
        inv = subprocess.Popen([sys.executable, str(INVOICER), "run"])
        print(f"Invoicer started (PID {inv.pid})", flush=True)
    else:
        print(f"Brak pliku: {INVOICER}", flush=True)

    try:
        while not stop.is_set():
            code = web.poll()
            if code is not None:
                sys.exit(f"Web UI stopped unexpectedly (exit code {code})")
            if restart_wa.is_set():
                restart_wa.clear()
                print("Restart webhooka WhatsApp (zmiana ustawień).", flush=True)
                stop_proc("WhatsApp webhook", wa)
                wa = start_webhook()
            if wa is not None and wa.poll() is not None:
                print(f"WhatsApp webhook zakończył się (kod {wa.returncode}), Web UI działa dalej.", flush=True)
                wa = None
            if inq is not None and inq.poll() is not None:
                print(f"Inquiries processor zakończył się (kod {inq.returncode}), Web UI działa dalej.", flush=True)
                inq = None
            if inv is not None and inv.poll() is not None:
                print(f"Invoicer zakończył się (kod {inv.returncode}), Web UI działa dalej.", flush=True)
                inv = None
            stop.wait(1)
    finally:
        for name, proc in (("Invoicer", inv), ("Inquiries processor", inq), ("WhatsApp webhook", wa), ("Web UI", web)):
            stop_proc(name, proc)


if __name__ == "__main__":
    main()
