"""Faktury do akceptacji w Gere-Drive/Invoices: jeden plik JSON na fakturę (INV-000001.json).

Statusy: pending (czeka na Gere), approved, rejected. Decyzja jest ostateczna.
Kwoty trzymamy jako tekst z dwoma miejscami po przecinku (Decimal, nigdy float).

Z linii poleceń (z katalogu Gere-Lab):
    python3 App/Invoices.py demo     dwie przykładowe faktury do obejrzenia na stronie głównej
    python3 App/Invoices.py list     lista faktur
"""
import argparse
import json
import os
import re
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import Clients
from Paths import DRIVE_INVOICES

ID = re.compile(r"^INV-\d{6}$")
STATUSES = ("pending", "approved", "rejected")
CURRENCY = "EUR"
MAX_ITEMS = 50
CENT = Decimal("0.01")
LOCK = threading.Lock()


class NotFound(Exception):
    pass


class AlreadyDecided(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(invoice_id):
    if not ID.match(str(invoice_id)):
        raise ValueError("bad invoice id")
    return DRIVE_INVOICES / f"{invoice_id}.json"


def _write(path, data):
    part = path.with_name(path.name + ".part")
    with part.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(part, path)


def _read(path):
    """Słownik z pliku albo None (brak pliku, pusty plik w trakcie tworzenia, uszkodzony JSON)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _money(value):
    try:
        amount = Decimal(str(value).replace(",", ".").strip())
    except InvalidOperation:
        raise ValueError("bad amount")
    if not amount.is_finite() or amount < 0 or amount > Decimal("1000000"):
        raise ValueError("bad amount")
    return amount.quantize(CENT, ROUND_HALF_UP)


def clean_items(items):
    """[{name, qty, price}] -> lista z oczyszczonymi polami. Zły wpis = ValueError."""
    if not isinstance(items, list) or not items or len(items) > MAX_ITEMS:
        raise ValueError("bad items")
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("bad item")
        name = str(item.get("name", "")).strip()[:200]
        try:
            qty = int(str(item.get("qty", 1)).strip())
        except ValueError:
            raise ValueError("bad qty")
        if not name or not 1 <= qty <= 999:
            raise ValueError("bad item")
        out.append({"name": name, "qty": qty, "price": str(_money(item.get("price", 0)))})
    return out


def total_of(items):
    return str(sum((Decimal(i["price"]) * i["qty"] for i in items), Decimal("0.00")).quantize(CENT))


def _client_label(client):
    full = " ".join(p for p in (str(client.get(k) or "").strip() for k in ("name", "surname")) if p)
    return full or str(client.get("company") or "").strip()


def create_invoice(items, client_id=None, contact="", inquiry_id=None, note="", source="manual"):
    """Tworzy fakturę w statusie pending i zwraca ją. Zły input = ValueError.

    Klienta można podać po ID albo po numerze (contact), wtedy szukamy go po telefonie.
    """
    items = clean_items(items)
    contact = str(contact or "").strip()[:40]
    if client_id is None and contact:
        client_id = Clients.find_by_phone(contact)
    client_name = ""
    if client_id is not None:
        client = Clients.read_client(client_id)
        if client is None:
            raise ValueError("no such client")
        client_name = _client_label(client)
    if inquiry_id is not None:
        inquiry_id = int(inquiry_id)
    data = {
        "id": "",
        "status": "pending",
        "source": str(source)[:20],
        "client_id": client_id,
        "client_name": client_name,
        "contact": contact,
        "inquiry_id": inquiry_id,
        "currency": CURRENCY,
        "items": items,
        "total": total_of(items),
        "note": str(note or "").strip()[:500],
        "created": _now(),
        "decided": None,
        "reject_reason": "",
    }
    with LOCK:
        DRIVE_INVOICES.mkdir(parents=True, exist_ok=True)
        numbers = [int(p.stem[4:]) for p in DRIVE_INVOICES.glob("INV-*.json") if ID.match(p.stem)]
        number = max(numbers + [0]) + 1
        while True:
            invoice_id = f"INV-{number:06d}"
            try:
                # O_EXCL zajmuje numer atomowo, także gdy drugi proces tworzy fakturę w tej samej chwili
                fd = os.open(_path(invoice_id), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                number += 1
                continue
            os.close(fd)
            break
        data["id"] = invoice_id
        _write(_path(invoice_id), data)
    return data


def read_invoice(invoice_id):
    return _read(_path(invoice_id))


def list_invoices(status=None):
    """Najnowsze pierwsze. status=None = wszystkie."""
    if not DRIVE_INVOICES.is_dir():
        return []
    out = []
    for path in DRIVE_INVOICES.glob("INV-*.json"):
        if not ID.match(path.stem):
            continue
        invoice = _read(path)
        if invoice is not None and (status is None or invoice.get("status") == status):
            out.append(invoice)
    return sorted(out, key=lambda i: str(i.get("id", "")), reverse=True)


def decide(invoice_id, status, reason=""):
    """pending -> approved albo rejected. Drugiej decyzji nie ma: AlreadyDecided."""
    if status not in ("approved", "rejected"):
        raise ValueError("bad status")
    with LOCK:
        path = _path(invoice_id)
        invoice = _read(path)
        if invoice is None:
            raise NotFound(invoice_id)
        if invoice.get("status") != "pending":
            raise AlreadyDecided(invoice_id)
        invoice["status"] = status
        invoice["decided"] = _now()
        invoice["reject_reason"] = str(reason or "").strip()[:500] if status == "rejected" else ""
        _write(path, invoice)
        return invoice


def _demo():
    ids = Clients.list_ids()
    first = create_invoice(
        [{"name": "Alternador VW Passat B6", "qty": 1, "price": "148.50"},
         {"name": "Correa de accesorios", "qty": 1, "price": "22.90"}],
        client_id=ids[0] if ids else None, contact="" if ids else "+34600000000",
        note="DEMO: wygenerowane poleceniem demo", source="demo")
    second = create_invoice(
        [{"name": "Amortiguador delantero", "qty": 2, "price": "64.00"}],
        client_id=ids[-1] if ids else None, note="DEMO: wygenerowane poleceniem demo", source="demo")
    print("Utworzono:", first["id"], second["id"])


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    sub.add_parser("list")
    args = parser.parse_args()
    if args.cmd == "demo":
        _demo()
    else:
        rows = list_invoices()
        if not rows:
            print("Brak faktur.")
        for i in rows:
            print(f"{i['id']}  {i['status']:<9}  {i['total']:>9} {i['currency']}  {i.get('client_name') or i.get('contact') or '-'}")


if __name__ == "__main__":
    main()
