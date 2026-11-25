"""Dzienne pliki wiadomości w Gere-Drive/Messeges (YYYY-MM-DD.jsonl, jeden JSON na linię)."""
import json
import os
import re
import shutil
import threading
from datetime import date, datetime, timedelta

import yaml

from Paths import DRIVE_MESSAGES, DRIVE_PHOTOS, WEB_CONFIG

NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.jsonl$")
LOCK = threading.Lock()
LIMIT = 200


def retention_days(cfg=None):
    """0, brak wartości albo wartość błędna = trzymaj zawsze, nic nie usuwaj."""
    if cfg is None:
        try:
            cfg = yaml.safe_load(WEB_CONFIG.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return 0
    try:
        days = int((cfg.get("messages") or {}).get("retention_days", 0))
    except (TypeError, ValueError, AttributeError):
        return 0
    return max(0, days)


def _files():
    """[(data, ścieżka)] tylko dla plików o nazwie YYYY-MM-DD.jsonl, najnowsze pierwsze."""
    if not DRIVE_MESSAGES.is_dir():
        return []
    found = []
    for path in DRIVE_MESSAGES.glob("*.jsonl"):
        if not NAME.match(path.name):
            continue
        try:
            found.append((date.fromisoformat(path.stem), path))
        except ValueError:
            continue
    return sorted(found, reverse=True)


def prune(days=None):
    """Usuwa pliki dzienne starsze niż okno. days <= 0 = nie rusza niczego."""
    if days is None:
        days = retention_days()
    if days <= 0:
        return []
    cutoff = date.today() - timedelta(days=days - 1)
    removed = []
    for day, path in _files():
        if day < cutoff:
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                continue
    prune_photos(cutoff)
    return removed


def save_message(sender, msg_id, text, sent_at=None, photos=None, media_missing=None):
    """Dopisuje wiadomość do pliku z jej dnia. Zwraca 1 = zapisano, 0 = duplikat."""
    when = datetime.fromtimestamp(sent_at) if sent_at else datetime.now()
    path = DRIVE_MESSAGES / f"{when:%Y-%m-%d}.jsonl"
    record = {"id": msg_id, "from": sender,
              "time": when.isoformat(timespec="seconds"), "text": text}
    if photos:
        record["photos"] = list(photos)
    if media_missing:
        record["media_missing"] = list(media_missing)
    line = json.dumps(record, ensure_ascii=False)
    with LOCK:
        DRIVE_MESSAGES.mkdir(parents=True, exist_ok=True)
        if path.exists():
            for old in path.read_text(encoding="utf-8").splitlines():
                try:
                    if json.loads(old).get("id") == msg_id:
                        return 0
                except (ValueError, AttributeError):
                    continue
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
    prune()
    return 1


def read_messages(days, limit=LIMIT):
    """Najnowsze pierwsze. days > 0 = dzisiaj i days-1 dni wstecz, 0 = wszystkie pliki."""
    cutoff = date.today() - timedelta(days=days - 1) if days > 0 else None
    out = []
    for day, path in _files():
        if cutoff and day < cutoff:
            break
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        items = []
        for line in lines:
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if isinstance(m, dict):
                items.append(m)
        out.extend(reversed(items))
        if len(out) >= limit:
            break
    return out[:limit]


def photo_target(sender, msg_id, index, ext, sent_at=None):
    when = datetime.fromtimestamp(sent_at) if sent_at else datetime.now()
    folder = DRIVE_PHOTOS / f"{when:%Y-%m-%d}"
    name = f"{sender}__{msg_id}__{index}{ext}"
    return folder / name, f"Photos/{when:%Y-%m-%d}/{name}"


def prune_photos(cutoff):
    if not DRIVE_PHOTOS.is_dir():
        return
    for folder in DRIVE_PHOTOS.iterdir():
        try:
            day = date.fromisoformat(folder.name)
        except ValueError:
            continue
        if folder.is_dir() and day < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
