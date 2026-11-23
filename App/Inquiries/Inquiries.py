import argparse
import json
import logging
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from WhatsApp.WA_Extractor import extract
from Paths import DRIVE_MESSAGES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CONFIG = ROOT / "User" / "Config.yml"
DEFAULTS = {
    "interval_seconds": 10,
    "inbox_dir": "Database/inbox",
    "db_path": "Database/gere.db",
    "conversation_window_minutes": 60,
}
log = logging.getLogger("gere")

SCHEMA = """
CREATE TABLE IF NOT EXISTS inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact TEXT,
    vin TEXT,
    vin_valid INTEGER NOT NULL DEFAULT 0,
    request_text TEXT NOT NULL DEFAULT '',
    needs_human INTEGER NOT NULL DEFAULT 1,
    reason TEXT,
    extractor_version TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    last_message_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    contact TEXT,
    text TEXT NOT NULL,
    received_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    inquiry_id INTEGER REFERENCES inquiries(id)
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        cfg.update(yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {})
    for key in ("inbox_dir", "db_path"):
        p = Path(str(cfg[key])).expanduser()
        cfg[key] = p if p.is_absolute() else ROOT / p
    cfg["interval_seconds"] = max(1, int(cfg["interval_seconds"]))
    cfg["conversation_window_minutes"] = max(1, int(cfg["conversation_window_minutes"]))
    return cfg


def open_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(messages)")}
    if "inquiry_id" not in columns:
        sys.exit("Stara struktura bazy. Usuń Database/gere.db* i uruchom ponownie.")
    return conn


def read_inbox(inbox, settle_seconds=2):
    inbox.mkdir(parents=True, exist_ok=True)
    found = []
    for path in sorted(inbox.glob("*.txt")):
        try:
            stat = path.stat()
            if time.time() - stat.st_mtime < settle_seconds:
                continue
            text = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("Nie można odczytać %s: %s", path.name, exc)
            continue
        if not text:
            continue
        contact = path.stem.split("__", 1)[0] if "__" in path.stem else None
        when = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        found.append((path.name, contact, text, when.isoformat(timespec="seconds")))
    return found


def read_drive_messages():
    found = []
    if not DRIVE_MESSAGES.is_dir():
        return found
    for path in sorted(DRIVE_MESSAGES.glob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("Nie można odczytać %s: %s", path.name, exc)
            continue
        for line in lines:
            try:
                m = json.loads(line)
                sender = str(m["from"])
                msg_id = str(m["id"])
                text = str(m["text"]).strip()
                when = datetime.fromisoformat(m["time"]).astimezone(timezone.utc)
            except (ValueError, KeyError, TypeError):
                continue
            if text:
                found.append((f"{sender}__{msg_id}.txt", sender, text, when.isoformat(timespec="seconds")))
    return found


def open_inquiry(conn, contact, received_at, window_minutes):
    if contact is None:
        return None
    row = conn.execute(
        "SELECT id, last_message_at FROM inquiries WHERE contact = ? "
        "ORDER BY last_message_at DESC, id DESC LIMIT 1", (contact,)).fetchone()
    if row is None:
        return None
    gap = datetime.fromisoformat(received_at) - datetime.fromisoformat(row["last_message_at"])
    return row["id"] if gap <= timedelta(minutes=window_minutes) else None


def run_once(cfg, conn):
    new = 0
    for source_id, contact, text, received_at in read_inbox(cfg["inbox_dir"]) + read_drive_messages():
        cur = conn.execute(
            "INSERT OR IGNORE INTO messages (source_id, contact, text, received_at, created_at) "
            "VALUES (?, ?, ?, ?, ?)", (source_id, contact, text, received_at, now()))
        new += cur.rowcount
        if cur.rowcount:
            log.info("Nowa wiadomość: %s", source_id)
    conn.commit()

    pending = conn.execute(
        "SELECT id, contact, received_at FROM messages WHERE inquiry_id IS NULL "
        "ORDER BY received_at, id").fetchall()
    touched = []
    for m in pending:
        inquiry_id = open_inquiry(conn, m["contact"], m["received_at"], cfg["conversation_window_minutes"])
        if inquiry_id is None:
            inquiry_id = conn.execute(
                "INSERT INTO inquiries (contact, last_message_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)", (m["contact"], m["received_at"], now(), now())).lastrowid
        conn.execute("UPDATE messages SET inquiry_id = ? WHERE id = ?", (inquiry_id, m["id"]))
        conn.execute("UPDATE inquiries SET last_message_at = MAX(last_message_at, ?) WHERE id = ?",
                     (m["received_at"], inquiry_id))
        if inquiry_id not in touched:
            touched.append(inquiry_id)

    for inquiry_id in touched:
        rows = conn.execute(
            "SELECT text FROM messages WHERE inquiry_id = ? ORDER BY received_at, id", (inquiry_id,))
        r = extract("\n".join(row["text"] for row in rows))
        conn.execute(
            "UPDATE inquiries SET vin = ?, vin_valid = ?, request_text = ?, needs_human = ?, "
            "reason = ?, extractor_version = ?, updated_at = ? WHERE id = ?",
            (r["vin"], int(r["vin_valid"]), r["request_text"], int(r["needs_human"]),
             r["reason"], r["extractor_version"], now(), inquiry_id))
        if r["needs_human"]:
            log.info("Zapytanie %s wymaga Gere: %s", inquiry_id, r["reason"])
        else:
            log.info("Zapytanie %s: VIN %s", inquiry_id, r["vin"])
    conn.commit()
    return new, len(touched)


def run_loop():
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    cfg = load_config()
    conn = open_db(cfg["db_path"])
    log.info("Start. Inbox: %s, interwał: %ss", cfg["inbox_dir"], cfg["interval_seconds"])
    while not stop.is_set():
        try:
            cfg = load_config()
            run_once(cfg, conn)
        except Exception:
            log.exception("Błąd w obiegu, próbuję dalej")
        stop.wait(cfg["interval_seconds"])
    conn.close()
    log.info("Zatrzymano")


def cmd_list(human_only, limit=50):
    conn = open_db(load_config()["db_path"])
    sql = "SELECT * FROM inquiries" + (" WHERE needs_human = 1" if human_only else "")
    rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        print("Brak zapytań.")
        return
    print(f"{'id':>4}  {'kontakt':<12}  {'human':<5}  {'vin':<17}  {'powód':<34}  tekst")
    for r in rows:
        text = " ".join(r["request_text"].split())[:40]
        print(f"{r['id']:>4}  {(r['contact'] or '-')[:12]:<12}  "
              f"{'TAK' if r['needs_human'] else 'nie':<5}  {(r['vin'] or '-'):<17}  "
              f"{(r['reason'] or '')[:34]:<34}  {text}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("once")
    sub.add_parser("run")
    p = sub.add_parser("list")
    p.add_argument("--human", action="store_true")
    p = sub.add_parser("extract")
    p.add_argument("text")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.cmd == "run":
        run_loop()
    elif args.cmd == "once":
        cfg = load_config()
        conn = open_db(cfg["db_path"])
        new, done = run_once(cfg, conn)
        print(f"Nowe wiadomości: {new}, zaktualizowane zapytania: {done}")
    elif args.cmd == "list":
        cmd_list(args.human)
    elif args.cmd == "extract":
        print(json.dumps(extract(args.text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
