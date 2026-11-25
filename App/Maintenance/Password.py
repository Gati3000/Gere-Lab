import ctypes
import hmac
import os
import sys

SHADOW = os.environ.get("GERE_SHADOW") or "/etc/shadow"
USER = "root"


def stored_hash():
    with open(SHADOW, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split(":")
            if parts[0] == USER and len(parts) > 1:
                return parts[1]
    return None


def main():
    password = sys.stdin.read().rstrip("\n")
    try:
        stored = stored_hash()
    except OSError:
        return 3
    if not stored or stored[0] in "!*":
        return 4
    try:
        lib = ctypes.CDLL("libcrypt.so.1")
        lib.crypt.restype = ctypes.c_char_p
        lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        result = lib.crypt(password.encode(), stored.encode())
    except (OSError, AttributeError):
        return 5
    if result is None:
        return 5
    return 0 if hmac.compare_digest(result, stored.encode()) else 1


if __name__ == "__main__":
    sys.exit(main())
