
import re

EXTRACTOR_VERSION = "0.1"

_TOKEN_17 = re.compile(r"(?<![A-Z0-9])[A-Z0-9]{17}(?![A-Z0-9])")
_TOKEN_LONG = re.compile(r"(?<![A-Z0-9])[A-Z0-9]{14,20}(?![A-Z0-9])")
_FORBIDDEN = set("IOQ")

_TRANSLIT = {str(d): d for d in range(10)}
_TRANSLIT.update(
    {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
     "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
     "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9}
)
_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def check_digit_ok(vin):
    """Sprawdza 9. znak VIN (cyfra kontrolna). Zakłada 17 znaków bez I, O, Q."""
    total = sum(_TRANSLIT[c] * w for c, w in zip(vin, _WEIGHTS))
    rest = total % 11
    return vin[8] == ("X" if rest == 10 else str(rest))


def _looks_like_vin(token):
    return sum(c.isdigit() for c in token) >= 4


def _clean_request(text, vin):
    if vin:
        pattern = r"(?:\bvin\b\s*[:=\-]?\s*)?" + re.escape(vin)
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = " ".join(text.split())
    return text.strip(" :;,.-")


def extract(text):
    """Zwraca słownik z wynikiem. Format zostaje na kolejne wersje (dojdą pola)."""
    upper = text.upper()
    result = {
        "vin": None,
        "vin_valid": False,
        "request_text": "",
        "needs_human": False,
        "reason": None,
        "extractor_version": EXTRACTOR_VERSION,
    }

    vins = [t for t in dict.fromkeys(_TOKEN_17.findall(upper)) if _looks_like_vin(t)]

    if not vins:
        result["request_text"] = _clean_request(text, None)
        wrong = [
            t for t in _TOKEN_LONG.findall(upper)
            if len(t) != 17 and _looks_like_vin(t) and any(c.isalpha() for c in t)
        ]
        result["needs_human"] = True
        result["reason"] = "VIN ma złą długość" if wrong else "brak VIN"
        return result

    if len(vins) > 1:
        result["request_text"] = _clean_request(text, None)
        result["needs_human"] = True
        result["reason"] = "kilka różnych VIN-ów"
        return result

    vin = vins[0]
    result["vin"] = vin
    result["request_text"] = _clean_request(text, vin)

    if _FORBIDDEN & set(vin):
        result["needs_human"] = True
        result["reason"] = "VIN ma niedozwolone znaki (I, O, Q)"
        return result

    # Powalona logika Amerykańskich samochodow zajrzec jeszcze i rozszerzyc o inne panstwa
    if vin[0] in "12345" and not check_digit_ok(vin):
        result["needs_human"] = True
        result["reason"] = "cyfra kontrolna VIN się nie zgadza"
        return result

    result["vin_valid"] = True
    if sum(c.isalpha() for c in result["request_text"]) < 3:
        result["needs_human"] = True
        result["reason"] = "VIN bez części"
    return result
