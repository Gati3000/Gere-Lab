"""Klienci w Gere-Drive/Clients: folder z 6-cyfrowym ID, w nim Client.yml, Addresses.yml, Purchases.jsonl, Shipments.jsonl."""
import json
import os
import re
import threading
from datetime import date

import yaml

from Paths import DRIVE_CLIENTS

ID = re.compile(r"^\d{6}$")
LOCK = threading.Lock()
CLIENT_FIELDS = ("name", "surname", "company", "tax_id", "email", "language", "holded_contact_id", "notes", "status")
ADDRESS_FIELDS = ("label", "street", "number", "rest", "postal_code", "city", "province", "country", "contact_name", "contact_phone")
SHIPMENT_FIELDS = ("date", "purchase", "address_id", "carrier", "service", "tracking", "weight_kg", "packages", "cod", "status")


class Dumper(yaml.SafeDumper):
    pass


def _quote_digits(dumper, value):
    # liczby i telefony zawsze w cudzyslowie, zeby YAML nie obcial zer
    style = "'" if value.isdigit() or value[:1] == "+" else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


Dumper.add_representer(str, _quote_digits)


def normalize_phone(raw):
    """'+34 600 000 000' i '34600000000' dają '+34600000000'. Za krótki numer = ''."""
    digits = re.sub(r"\D", "", str(raw or ""))
    return "+" + digits if len(digits) >= 8 else ""


def valid_postal(code, country="ES"):
    """Dla ES: 5 cyfr, pierwsze dwie to prowincja 01-52. Dla innych krajów nie sprawdza."""
    if str(country).upper() != "ES":
        return bool(str(code).strip())
    return bool(re.fullmatch(r"(0[1-9]|[1-4]\d|5[0-2])\d{3}", str(code)))


def _dir(client_id):
    if not ID.match(str(client_id)):
        raise ValueError("bad client id")
    return DRIVE_CLIENTS / str(client_id)


def _write_yaml(path, data):
    part = path.with_name(path.name + ".part")
    with part.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=Dumper, allow_unicode=True, sort_keys=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(part, path)


def _read_yaml(path, default):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or default
    except (OSError, yaml.YAMLError):
        return default


def _append(path, row):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _read_lines(path):
    out = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def list_ids():
    """Posortowane ID folderów klientów. _Template i inne foldery są pomijane."""
    if not DRIVE_CLIENTS.is_dir():
        return []
    return sorted(p.name for p in DRIVE_CLIENTS.iterdir() if p.is_dir() and ID.match(p.name))


def read_client(client_id):
    data = _read_yaml(_dir(client_id) / "Client.yml", None)
    return data if isinstance(data, dict) else None


def read_addresses(client_id):
    data = _read_yaml(_dir(client_id) / "Addresses.yml", [])
    return [a for a in data if isinstance(a, dict)] if isinstance(data, list) else []


def read_purchases(client_id):
    return _read_lines(_dir(client_id) / "Purchases.jsonl")


def read_shipments(client_id):
    return _read_lines(_dir(client_id) / "Shipments.jsonl")


def find_by_phone(phone):
    """ID klienta o tym numerze (whatsapp lub phones) albo None."""
    wanted = normalize_phone(phone)
    if not wanted:
        return None
    for client_id in list_ids():
        client = read_client(client_id) or {}
        numbers = [client.get("whatsapp")] + list(client.get("phones") or [])
        if wanted in (normalize_phone(n) for n in numbers):
            return client_id
    return None


def create_client(whatsapp, name=""):
    """Zwraca (ID, True) dla nowego klienta albo (ID, False), gdy numer już jest w bazie."""
    phone = normalize_phone(whatsapp)
    if not phone:
        raise ValueError("bad phone")
    with LOCK:
        found = find_by_phone(phone)
        if found:
            return found, False
        DRIVE_CLIENTS.mkdir(parents=True, exist_ok=True)
        ids = list_ids()
        number = int(ids[-1]) + 1 if ids else 1
        while True:
            client_id = f"{number:06d}"
            try:
                # mkdir zajmuje ID atomowo, także gdy drugi proces tworzy klienta w tej samej chwili
                (DRIVE_CLIENTS / client_id).mkdir()
                break
            except FileExistsError:
                number += 1
        folder = DRIVE_CLIENTS / client_id
        _write_yaml(folder / "Client.yml", {
            "id": client_id, "name": str(name).strip(), "surname": "", "company": "", "tax_id": "",
            "whatsapp": phone, "phones": [phone], "email": "", "language": "",
            "created": date.today().isoformat(), "status": "incomplete", "holded_contact_id": "", "notes": "",
        })
        _write_yaml(folder / "Addresses.yml", [])
        (folder / "Purchases.jsonl").touch()
        (folder / "Shipments.jsonl").touch()
        return client_id, True


def update_client(client_id, **fields):
    """Zmienia tylko pola z CLIENT_FIELDS. Zwraca zapisany profil."""
    with LOCK:
        client = read_client(client_id)
        if client is None:
            raise ValueError("no such client")
        for key, value in fields.items():
            if key in CLIENT_FIELDS:
                client[key] = str(value).strip()
        _write_yaml(_dir(client_id) / "Client.yml", client)
        return client


def add_address(client_id, make_default=False, **fields):
    """Dopisuje adres. Pierwszy adres klienta jest domyślny. Zły kod pocztowy ES = ValueError."""
    address = {k: str(fields.get(k, "")).strip() for k in ADDRESS_FIELDS}
    address["country"] = address["country"].upper() or "ES"
    if not valid_postal(address["postal_code"], address["country"]):
        raise ValueError("bad postal code")
    with LOCK:
        if read_client(client_id) is None:
            raise ValueError("no such client")
        addresses = read_addresses(client_id)
        new_id = max([a.get("id", 0) for a in addresses] + [0]) + 1
        is_default = make_default or not addresses
        if is_default:
            for a in addresses:
                a["default"] = False
        label = address.pop("label")
        addresses.append({"id": new_id, "label": label, "default": is_default, **address})
        _write_yaml(_dir(client_id) / "Addresses.yml", addresses)
        return addresses[-1]


def add_purchase(client_id, document, items, source="holded", day=None):
    """Dopisuje zakup. Zwraca 1 = zapisano, 0 = ten dokument już jest."""
    with LOCK:
        if read_client(client_id) is None:
            raise ValueError("no such client")
        if any(p.get("document") == document for p in read_purchases(client_id)):
            return 0
        _append(_dir(client_id) / "Purchases.jsonl", {"date": day or date.today().isoformat(), "document": document, "source": source, "items": items})
        return 1


def add_shipment(client_id, **fields):
    """Dopisuje etykietę do historii. Pola z SHIPMENT_FIELDS, reszta jest pomijana."""
    with LOCK:
        if read_client(client_id) is None:
            raise ValueError("no such client")
        row = {k: fields.get(k, "") for k in SHIPMENT_FIELDS}
        row["date"] = row["date"] or date.today().isoformat()
        _append(_dir(client_id) / "Shipments.jsonl", row)
        return row
