import argparse
import logging
import signal
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import Clients
import Invoices
from Inquiries import load_config, open_db, now

DELAY_MINUTES = 5
log = logging.getLogger("gere")


def run_once(conn):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=Invoices.delay_minutes())).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT id, contact, vin, request_text FROM inquiries "
        "WHERE status = 'new' AND needs_human = 0 AND vin_valid = 1 AND last_message_at <= ? "
        "ORDER BY id", (cutoff,)).fetchall()
    done = 0
    for row in rows:
        client_id = None
        if row["contact"]:
            try:
                client_id, _ = Clients.create_client(row["contact"])
            except ValueError:
                client_id = None
        items = [{"name": row["request_text"] or "Brak opisu części", "qty": 1, "price": "0.00"}]
        try:
            invoice = Invoices.create_invoice(
                items, client_id=client_id, contact=row["contact"] or "",
                inquiry_id=row["id"], note=f"VIN {row['vin']}. Brak ceny.", source="invoicer")
        except (ValueError, OSError) as exc:
            log.warning("Zapytanie %s: faktura nie powstała: %s", row["id"], exc)
            continue
        conn.execute("UPDATE inquiries SET status = 'invoiced', updated_at = ? WHERE id = ?", (now(), row["id"]))
        conn.commit()
        log.info("Zapytanie %s: faktura %s", row["id"], invoice["id"])
        done += 1
    return done


def run_loop():
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    cfg = load_config()
    conn = open_db(cfg["db_path"])
    log.info("Start Invoicer, interwał: %ss", cfg["interval_seconds"])
    while not stop.is_set():
        try:
            cfg = load_config()
            run_once(conn)
        except Exception:
            log.exception("Błąd w obiegu, próbuję dalej")
        stop.wait(cfg["interval_seconds"])
    conn.close()
    log.info("Zatrzymano")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("once")
    sub.add_parser("run")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.cmd == "run":
        run_loop()
    else:
        conn = open_db(load_config()["db_path"])
        print(f"Nowe faktury: {run_once(conn)}")


if __name__ == "__main__":
    main()
