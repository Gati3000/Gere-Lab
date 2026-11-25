
import re
import unicodedata

EXTRACTOR_VERSION = "0.2"

_TOKEN_17 = re.compile(r"(?<![A-Z0-9])[A-Z0-9]{17}(?![A-Z0-9])")
_TOKEN_LONG = re.compile(r"(?<![A-Z0-9])[A-Z0-9]{14,20}(?![A-Z0-9])")
_FORBIDDEN = set("IOQ")
_ALNUM = re.compile(r"[A-Z0-9]+")
_SEPARATOR = re.compile(r"[ \-.]{1,2}")   # between groups of a VIN: space, dash or dot

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


def _spaced_vins(upper):
    """VIN-y zapisane w grupach ("WVW ZZZ 3CZ 9E 123456", "WVW-ZZZ-..."): 2-6 grup dających razem 17 znaków."""
    tokens = list(_ALNUM.finditer(upper))
    found = []
    i = 0
    while i < len(tokens):
        if tokens[i].group().isalpha() and len(tokens[i].group()) > 3:
            i += 1
            continue
        joined, j = tokens[i].group(), i
        while j + 1 < len(tokens) and len(joined) < 17:
            if not _SEPARATOR.fullmatch(upper[tokens[j].end():tokens[j + 1].start()]):
                break
            if tokens[j + 1].group().isalpha() and len(tokens[j + 1].group()) > 3:
                break
            j += 1
            joined += tokens[j].group()
        if j > i and len(joined) == 17 and _looks_like_vin(joined):
            found.append(joined)
            i = j + 1
        else:
            i += 1
    return found


def _clean_request(text, vin):
    if vin:
        # każdy znak VIN-u może być oddzielony spacją, kreską lub kropką
        pattern = r"(?:\bvin\b\s*[:=\-]?\s*)?" + r"[ \-.]{0,2}".join(re.escape(c) for c in vin)
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = " ".join(text.split())
    return text.strip(" :;,.-")


_MAX_REF = 13

_BRANDS = [
    ("Ford", r"ford", None), ("Chevrolet", r"chevrolet|chevy", None), ("GMC", r"gmc", None),
    ("Cadillac", r"cadillac", None), ("Buick", r"buick", None), ("Chrysler", r"chrysler", None),
    ("Dodge", r"dodge", None), ("Jeep", r"jeep", None),
    ("Ram", r"ram(?=\s+(?:trucks?|promaster|1500|2500|3500))", None), ("Lincoln", r"lincoln", None),
    ("Tesla", r"tesla", None), ("Pontiac", r"pontiac", None), ("Oldsmobile", r"oldsmobile", None),
    ("Saturn", r"saturn", None), ("Hummer", r"hummer", None), ("Mercury", r"mercury", None),
    ("Plymouth", r"plymouth", None), ("Fiat", r"fiat", None), ("Alfa Romeo", r"alfa\s*romeo", None),
    ("Audi", r"audi", None), ("BMW", r"bmw", None), ("Mercedes-Benz", r"mercedes(?:[\s-]*benz)?", None),
    ("Volkswagen", r"volkswagen|vw", None), ("Opel", r"opel", None), ("Vauxhall", r"vauxhall", None),
    ("Porsche", r"porsche", None), ("Skoda", r"skoda", None),
    ("Seat", r"seat(?!\s+(?:belt|cover|cushion|motor|heater))", None), ("Cupra", r"cupra", None),
    ("Citroen", r"citroen", None), ("Peugeot", r"peugeot", None), ("Renault", r"renault", None),
    ("Dacia", r"dacia", None), ("Volvo", r"volvo", None), ("Saab", r"saab", None),
    ("Mini", r"mini(?=\s+(?:cooper|one|countryman|clubman|paceman|jcw))", None),
    ("Land Rover", r"land\s*rover", None), ("Land Rover", r"range\s*rover", "Range Rover"),
    ("Jaguar", r"jaguar", None), ("Bentley", r"bentley", None), ("Rolls-Royce", r"rolls[\s-]*royce", None),
    ("Maserati", r"maserati", None), ("Ferrari", r"ferrari", None), ("Lamborghini", r"lamborghini", None),
    ("Toyota", r"toyota", None), ("Lexus", r"lexus", None), ("Honda", r"honda", None),
    ("Acura", r"acura", None), ("Nissan", r"nissan", None), ("Infiniti", r"infiniti", None),
    ("Mazda", r"mazda", None), ("Mitsubishi", r"mitsubishi", None), ("Subaru", r"subaru", None),
    ("Suzuki", r"suzuki", None), ("Hyundai", r"hyundai", None), ("Kia", r"kia", None),
    ("Genesis", r"genesis", None), ("Isuzu", r"isuzu", None), ("Lancia", r"lancia", None),
    ("Lotus", r"lotus", None), ("Aston Martin", r"aston\s*martin", None),
]

_PARTS = [
    ("shock absorber", ["amortyzator", "amortiguador", "shock absorber", "shocks?$", "absorber$"]),
    ("strut", ["strut", "mcpherson"]),
    ("coil spring", ["sprezyn", "muelle", "coil spring", "springs?$"]),
    ("air spring", ["air spring", "air suspension", "pneumatyczn", "neumatic", "airmatic"]),
    ("airbag", ["airbag", "poduszk\\w* powietrzn"]),
    ("control arm", ["wahacz", "brazo", "control arm", "wishbone"]),
    ("ball joint", ["sworzen", "rotula", "ball joint"]),
    ("tie rod end", ["koncowk\\w* drazk", "koncowka", "tie rod", "rotula de direccion", "terminal de direccion"]),
    ("steering rack", ["maglownic", "listw\\w* kierown", "cremallera", "steering rack"]),
    ("power steering pump", ["pomp\\w* wspomag", "bomba de direccion", "bomba servo", "power steering pump"]),
    ("stabilizer link", ["lacznik\\w* stabilizator", "lacznik", "bieleta", "biela estabilizadora", "sway bar link", "stabilizer link", "end link"]),
    ("sway bar", ["stabilizator", "barra estabilizadora", "sway bar", "stabilizer bar", "anti-roll"]),
    ("wheel bearing", ["lozysk", "rodamiento", "wheel bearing"]),
    ("wheel hub", ["piast", "buje$", "wheel hub", "hub assembly"]),
    ("brake disc", ["tarcz\\w* hamulc", "tarcz", "disco de freno", "discos de freno", "brake rotor", "brake disc", "rotors?$"]),
    ("brake pads", ["klock\\w* hamulc", "pastilla\\w* de freno", "klock", "pastilla", "brake pad", "pads?$"]),
    ("brake caliper", ["zacisk", "pinza", "caliper"]),
    ("brake hose", ["przewod\\w* hamulc", "waz\\w* hamulc", "latiguillo", "brake hose", "brake line"]),
    ("brake master cylinder", ["pomp\\w* hamulc", "pompa glowna", "bomba de freno", "master cylinder"]),
    ("brake booster", ["serwo", "servofreno", "brake booster"]),
    ("abs sensor", ["czujnik\\w* abs", "sensor abs", "abs sensor", "wheel speed sensor", "czujnik\\w* predkosci"]),
    ("water pump", ["pomp\\w* wody", "bomba de agua", "water pump"]),
    ("radiator", ["chlodnic", "radiador", "radiator"]),
    ("intercooler", ["intercooler", "chlodnic\\w* powietrza"]),
    ("ac condenser", ["skraplacz", "condensador", "condenser"]),
    ("ac compressor", ["sprezark\\w* klim", "kompresor\\w* klim", "compresor", "ac compressor", "a/c compressor"]),
    ("thermostat", ["termostat"]),
    ("alternator", ["alternator", "alternador"]),
    ("starter", ["rozrusznik", "motor de arranque", "starter"]),
    ("battery", ["akumulator", "bateria", "battery"]),
    ("spark plug", ["swiec\\w* zaplon", "swieca", "bujia", "spark plug"]),
    ("ignition coil", ["cewk", "bobina", "ignition coil", "coil pack"]),
    ("fuel pump", ["pomp\\w* paliwa", "bomba de combustible", "bomba de gasolina", "fuel pump"]),
    ("fuel injector", ["wtryskiwacz", "inyector", "injector"]),
    ("oil filter", ["filtr\\w* oleju", "filtro de aceite", "oil filter"]),
    ("air filter", ["filtr\\w* powietrza", "filtro de aire", "air filter"]),
    ("cabin filter", ["filtr\\w* kabin", "filtr\\w* pylk", "filtro de habitaculo", "filtro de polen", "cabin filter", "pollen filter"]),
    ("fuel filter", ["filtr\\w* paliwa", "filtro de combustible", "fuel filter"]),
    ("oil pump", ["pomp\\w* oleju", "bomba de aceite", "oil pump"]),
    ("timing belt", ["pasek rozrzad", "correa de distribucion", "timing belt"]),
    ("timing chain", ["lancuch rozrzad", "cadena de distribucion", "timing chain"]),
    ("drive belt", ["pasek wieloklin", "pasek klinow", "pasek osprzet", "correa de accesorios", "serpentine belt", "drive belt"]),
    ("belt tensioner", ["napinacz", "tensor", "tensioner"]),
    ("clutch", ["sprzegl", "embrague", "clutch"]),
    ("flywheel", ["kolo zamachowe", "volante motor", "flywheel"]),
    ("gearbox", ["skrzyni\\w* bieg", "caja de cambios", "gearbox"]),
    ("driveshaft", ["wal\\w* napedow", "wal\\w* kardan", "polos$", "polosie", "driveshaft", "drive shaft", "propshaft"]),
    ("cv joint", ["przegub", "homocinetic", "cv joint", "cv axle"]),
    ("differential", ["dyferencjal", "mostek", "diferencial", "differential"]),
    ("turbocharger", ["turbosprezark", "turbina", "turbocompresor", "turbocharger"]),
    ("egr valve", ["zawor\\w* egr", "valvula egr", "egr$"]),
    ("catalytic converter", ["katalizator", "catalizador", "catalytic converter"]),
    ("dpf", ["dpf$", "filtr\\w* czastek", "filtro de particulas"]),
    ("muffler", ["tlumik", "silenciador", "muffler"]),
    ("exhaust", ["wydech", "tubo de escape", "sistema de escape", "exhaust", "kolektor\\w* wydech"]),
    ("oxygen sensor", ["sond\\w* lambda", "lambda$", "czujnik\\w* tlenu", "sensor de oxigeno", "o2 sensor", "oxygen sensor"]),
    ("maf sensor", ["przeplywomierz", "caudalimetro", "maf$", "mass air flow"]),
    ("crankshaft sensor", ["czujnik\\w* walu", "czujnik\\w* polozenia walu", "sensor de ciguenal", "crankshaft sensor", "crank sensor"]),
    ("camshaft sensor", ["czujnik\\w* rozrzad", "sensor de arbol de levas", "camshaft sensor", "cam sensor"]),
    ("throttle body", ["przepustnic", "cuerpo de mariposa", "throttle body"]),
    ("headlight", ["reflektor", "lampa przedni", "przednia lampa", "faros?$", "headlight", "headlamp", "head light"]),
    ("taillight", ["lampa tyln", "tylna lampa", "luz trasera", "piloto", "taillight", "tail light", "tail lamp", "rear light"]),
    ("fog light", ["halogen", "antiniebla", "fog light", "fog lamp"]),
    ("mirror", ["lusterk", "espejo", "retrovisor", "mirror"]),
    ("bumper", ["zderzak", "parachoques", "paragolpes", "bumper"]),
    ("fender", ["blotnik", "aleta$", "guardabarros", "fender"]),
    ("hood", ["maska$", "capo$", "hood$", "bonnet"]),
    ("door", ["drzwi$", "puertas?$", "doors?$"]),
    ("window regulator", ["podnosnik\\w* szyb", "mechanizm\\w* szyb", "elevalunas", "window regulator", "window motor"]),
    ("windshield", ["szyb\\w* czolow", "przedni\\w* szyb", "parabrisas", "windshield", "windscreen"]),
    ("wiper motor", ["silnik\\w* wycieraczek", "motor limpiaparabrisas", "wiper motor"]),
    ("wiper", ["wycieraczk", "piorko", "pioro", "limpiaparabrisas", "escobilla", "wiper"]),
    ("blower motor", ["dmuchaw", "blower"]),
    ("heater core", ["nagrzewnic", "heater core", "radiador de calefaccion"]),
    ("evaporator", ["parownik", "evaporador", "evaporator"]),
    ("engine mount", ["poduszk\\w* silnika", "lap\\w* silnika", "soporte de motor", "engine mount", "motor mount"]),
    ("head gasket", ["uszczelk\\w* pod glowic", "junta de culata", "head gasket"]),
    ("valve cover gasket", ["uszczelk\\w* pokryw\\w* zawor", "junta de tapa de valvulas", "valve cover gasket"]),
    ("gasket", ["uszczelk", "juntas?$", "gasket"]),
    ("ecu", ["sterownik", "komputer silnika", "centralita", "ecu$", "pcm$", "ecm$"]),
    ("fuse box", ["skrzynk\\w* bezpiecznik", "caja de fusibles", "fuse box"]),
    ("seat belt", ["pas\\w* bezpiecze", "cinturon", "seat belt", "seatbelt"]),
    ("grille", ["grill$", "atrapa", "rejilla", "grille"]),
    ("tailgate", ["klap\\w* bagaznik", "porton", "tailgate", "trunk lid"]),
    ("radiator fan", ["wentylator", "electroventilador", "radiator fan", "cooling fan"]),
    ("oil pan", ["misk\\w* olejow", "carter$", "oil pan"]),
    ("fuel tank", ["zbiornik\\w* paliwa", "deposito de combustible", "fuel tank"]),
    ("parking sensor", ["czujnik\\w* parkowania", "sensor de aparcamiento", "parking sensor", "pdc$"]),
    ("instrument cluster", ["licznik$", "zegary$", "cuadro de instrumentos", "instrument cluster"]),
]

_SIDES = [
    ("left", r"lew(?:y|a|e|ego|ej|ym|ych)\b|izquierd\w*|left\b|lh\b"),
    ("right", r"praw(?:y|a|e|ego|ej|ym|ych)\b|derech\w*|right\b|rh\b"),
    ("both", r"oba\b|obie\b|obydwa\b|ambos\b|ambas\b|both\b"),
]
_POSITIONS = [
    ("front", r"przod\w*|przedni\w*|delanter\w*|front\w*"),
    ("rear", r"tyl\b|tylu\b|tyln\w*|traser\w*|rear\b|back\b"),
]
_FUEL = [
    ("diesel", r"diesel|ropa\b|tdi|hdi|dci|cdi|crdi|tdci|jtd\w*|cdti|multijet"),
    ("gasoline", r"benzyn\w*|gasolina|petrol|gasoline|tsi|tfsi|fsi|gdi"),
    ("hybrid", r"hybryd\w*|hibrid\w*|hybrid"),
    ("electric", r"elektryczn\w*|electrico|electric|ev\b"),
    ("lpg", r"lpg|gnc|autogas"),
]
_TRANS = [
    ("automatic", r"automat\w*|cvt|dsg|tiptronic|steptronic|s-tronic|powershift"),
    ("manual", r"manual\w*|mecanic[ao]\b"),
]
_DRIVE = [
    ("AWD", r"awd|quattro|xdrive|4matic|4motion|all[\s-]*wheel"),
    ("4WD", r"4wd|4x4|four[\s-]*wheel"),
    ("FWD", r"fwd|front[\s-]*wheel"),
    ("RWD", r"rwd|rear[\s-]*wheel"),
]
_BODY = [
    ("sedan", r"sedan\w*|saloon|berlina"),
    ("wagon", r"kombi|wagon|estate|touring|avant|variant"),
    ("hatchback", r"hatchback|hatch\b|liftback"),
    ("coupe", r"coupe\b"),
    ("convertible", r"cabrio\w*|convertible|cabriolet|roadster|spyder|spider|descapotable"),
    ("suv", r"suv\b|crossover|todoterreno"),
    ("pickup", r"pickup|pick-up|pikap"),
    ("van", r"van\b|furgon\w*|minivan|mpv\b"),
]
_MARKET = [
    ("USA", r"usa\b|us[\s-]*spec|amerykansk\w*|american\w*|americano"),
    ("EU", r"eu[\s-]*spec|euro[\s-]*spec|europejsk\w*|europeo|european"),
]
_STEERING = [
    ("LHD", r"lhd\b|lewostronn\w*"),
    ("RHD", r"rhd\b|prawostronn\w*"),
]


def _compile(table):
    return [(name, re.compile(r"\b(?:" + pat + r")")) for name, pat in table]


def _frag(fragment):
    fragment = fragment.replace(" ", r"\s+")
    return fragment[:-1] + r"\b" if fragment.endswith("$") else fragment + r"\w*"


_BRAND_RES = [(name, re.compile(r"\b(?:" + pat + r")\b"), prefix) for name, pat, prefix in _BRANDS]
_PART_RES = [(name, re.compile(r"\b(?:" + "|".join(_frag(f) for f in frags) + r")")) for name, frags in _PARTS]
_SIDE_RES = _compile(_SIDES)
_POS_RES = _compile(_POSITIONS)
_FUEL_RES = _compile(_FUEL)
_TRANS_RES = _compile(_TRANS)
_DRIVE_RES = _compile(_DRIVE)
_BODY_RES = _compile(_BODY)
_MARKET_RES = _compile(_MARKET)
_STEERING_RES = _compile(_STEERING)
_VOCAB = [rx for table in (_SIDE_RES, _POS_RES, _FUEL_RES, _TRANS_RES, _DRIVE_RES, _BODY_RES,
                           _MARKET_RES, _STEERING_RES, _PART_RES) for _, rx in table]

_NOISE = set(
    "do na dla od z ze za po w i oraz lub a o u y e de del la el los las un una para por con sin en "
    "for the and or with from to of my me model rok roku r year ano vin silnik motor engine nr numer ref "
    "oem szt sztuk pcs uds x komplet set kit pair potrzebuje prosze szukam chce mam cena ile czy jest "
    "mozna kupic quiero necesito busco tengo precio cuanto hay need want looking price how much you "
    "have is there please pls thanks hello hi hola czesc dzien dobry witam dziekuje gracias buenos dias "
    "tardes pasuje fits fit es kod code".split()
)

_NEXT_TOKEN = re.compile(r"\s+([a-z0-9][a-z0-9\-]*)")
_SPLIT = re.compile(r"[\n;]+|(?<!\d),|,(?!\d)|\.\s+|\s[+&]\s")
_JOIN = re.compile(r"\s*(?:(?:and|y|i|oraz|e|or|lub)\s+)?")
_MOD = "|".join(pat for _, pat in _SIDES + _POSITIONS)
_QTY_BEFORE = re.compile(
    r"(?<![\w.,/-])(\d{1,2}|dwa|dwie|trzy|cztery|dos|tres|cuatro|two|three|four|pair)"
    r"\s*(?:[x\u00d7]|szt\.?|sztuk|pcs|uds?\.?)?\s*(?:(?:" + _MOD + r")\s+){0,2}\Z"
)
_QTY_AFTER = re.compile(r"\s*(?:[x\u00d7]\s*(\d{1,2})\b|(\d{1,2})\s*(?:szt|sztuk|pcs|uds|unidades)\b|(\d{1,2})\s*\Z)")
_QTY_WORDS = {"dwa": 2, "dwie": 2, "trzy": 3, "cztery": 4, "dos": 2, "tres": 3, "cuatro": 4,
              "two": 2, "three": 3, "four": 4, "pair": 2}

_YEAR_TOKEN = r"(?:19[5-9]\d|20[0-3]\d)"
_YEAR = re.compile(
    r"(?<![\w.,/-])(" + _YEAR_TOKEN + r")(?:\s*[-/]\s*(" + _YEAR_TOKEN + r"))?"
    r"(?!\d)(?![a-z]{2})(?!\s*(?:cc|ccm|cm3|kw|km|hp|cv|ps|bhp|nm|kg|zl|pln|eur|euro|szt|pcs)\b)"
)
_PROD = re.compile(r"(?<![\w.,/-])(0?[1-9]|1[0-2])\s*[/.]\s*(" + _YEAR_TOKEN + r")(?!\d)")
_DISP = re.compile(
    r"(?<![\w.,])([0-8])[.,](\d)(?![\d.,])"
    r"(?!\s*(?:szt|pcs|uds|mm|cm|kg|kw|km|hp|cv|ps|bar|nm|v\b|zl|pln|eur|x\b))"
)
_DISP_CC = re.compile(r"(?<![\w.,])(\d{3,4})\s*(?:cc|ccm|cm3)\b")
_POWER = re.compile(r"(?<![\w.,])(\d{2,3})\s*(kw|km|hp|ps|cv|bhp)(?![\w/])")
_LAYOUT = re.compile(r"(?<![\w.,])v(4|6|8|10|12)(?!\w)")
_DOORS = re.compile(r"(?<![\w.,])([2-5])\s*-?\s*(?:door|doors|drzwi\w*|puertas?|portes)\b")
_ENGINE_CODE = re.compile(
    r"(?:kod\s+silnika|silnik\s+kod|engine\s+code|motor\s+code|codigo\s+(?:de\s+)?motor|kod\s+motoru)"
    r"\s*[:=\-]?\s*([a-z0-9][a-z0-9\-]{1,9})"
)

_PHONE = re.compile(
    r"(?:\+\s*\d|\b00\d{2})[\d ()-]{7,}\d|(?:tel\w*|phone|movil|tlf|cel\w*)\W{0,3}[\d +()-]{7,}\d",
    re.IGNORECASE,
)
_REF_SPACED = re.compile(r"(?<![A-Z0-9])([0-9][0-9A-Z]{2})[ .-]?(\d{3})[ .-]?(\d{3})(?:[ .-]?([A-Z]{1,3}))?(?![A-Z0-9])")
_REF_TOKEN = re.compile(r"(?<![A-Z0-9])(?=[A-Z0-9./-]*\d)[A-Z0-9][A-Z0-9./-]{3,17}[A-Z0-9](?![A-Z0-9])")
_REF_SUFFIX_WORDS = set(
    "DO NA ZA PO OD ZE LUB I O U W Y DE LA EL UN AL LO ES EN TO MY OR IN ON IS IT ME AT BY NO SO FOR THE AND FIT".split()
)
_NOT_REF = re.compile(
    r"\d{2,4}(?:KW|HP|CV|PS|KM|CC|CCM|CM3|BHP|NM)"
    r"|\d{3}/\d{2}R?\d{2}"
    r"|\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
    r"|(?:19|20)\d\d[-/](?:19|20)\d\d"
    r"|\d{1,2}[./-](?:19|20)\d\d"
    r"|\d+\.\d{1,2}"
)


def _norm(text):
    out = []
    for ch in text.lower():
        if ch == "\u0142":
            out.append("l")
            continue
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        out.append(base[:1] if base else ch)
    return "".join(out)


def _strip_vins(text, vins):
    for vin in vins:
        pattern = r"(?:\bvin\b\s*[:=\-]?\s*)?" + r"[ \-.]{0,2}".join(re.escape(c) for c in vin)
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _first(table, n):
    hits = []
    for name, rx in table:
        m = rx.search(n)
        if m:
            hits.append((m.start(), name))
    return min(hits)[1] if hits else None


def _spans(sentence, table):
    return [(m.start(), m.end(), name) for name, rx in table for m in rx.finditer(sentence)]


def _vin_region(vin):
    if vin[0] in "12345":
        return "NA"
    if vin[0] in "STUVWXYZ":
        return "EU"
    return "OTHER"


def _is_noise(token, brand, n, end):
    if token in _NOISE or re.fullmatch(_YEAR_TOKEN, token):
        return True
    if re.match(r"[.,]\d", n[end:end + 2]):
        return True
    if token.isdigit() and len(token) <= 2 and brand != "Mazda":
        return True
    return any(rx.fullmatch(token) for rx in _VOCAB)


def _brand_model(n):
    best = None
    for name, rx, prefix in _BRAND_RES:
        m = rx.search(n)
        if m and (best is None or (m.start(), m.start() - m.end()) < best[0]):
            best = ((m.start(), m.start() - m.end()), name, m.end(), prefix)
    if best is None:
        return None, None
    _, brand, pos, prefix = best
    tokens = [prefix] if prefix else []
    for _ in range(3):
        m = _NEXT_TOKEN.match(n, pos)
        if not m or _is_noise(m.group(1), brand, n, m.end()):
            break
        tok = m.group(1)
        tokens.append(tok.upper() if len(tok) <= 3 or any(c.isdigit() for c in tok) else tok.title())
        pos = m.end()
    return brand, " ".join(tokens) or None


def _find_parts(sentence):
    found = []
    for name, rx in _PART_RES:
        for m in rx.finditer(sentence):
            if name == "door" and not m.group().startswith("drzwi") and re.search(r"\d\s*-?\s*\Z", sentence[:m.start()]):
                continue
            found.append((m.start(), m.end(), name))
    found.sort(key=lambda t: (-(t[1] - t[0]), t[0]))
    taken = []
    for s, e, name in found:
        if all(e <= ts or s >= te for ts, te, _ in taken):
            taken.append((s, e, name))
    return sorted(taken)


def _quantity(sentence, s, e):
    after = _QTY_AFTER.match(sentence, e)
    if after:
        return int(after.group(1) or after.group(2) or after.group(3))
    before = _QTY_BEFORE.search(sentence[:s])
    if before:
        value = before.group(1)
        return int(value) if value.isdigit() else _QTY_WORDS[value]
    return None


def _put(item, key, name):
    for value in (["left", "right"] if name == "both" else [name]):
        if value not in item[key]:
            item[key].append(value)


def _parts(n):
    out = []
    last = None
    for sentence in _SPLIT.split(n):
        found = _find_parts(sentence)
        mods = [("sides",) + t for t in _spans(sentence, _SIDE_RES)] + [("positions",) + t for t in _spans(sentence, _POS_RES)]
        if not found:
            if last is not None:
                for key, _, _, name in mods:
                    _put(last, key, name)
            continue
        items = [{"name": name, "raw": sentence[s:e].strip(), "sides": [], "positions": [],
                  "quantity": _quantity(sentence, s, e)} for s, e, name in found]
        mods.sort(key=lambda t: t[1])
        groups = []
        for mod in mods:
            if groups and _JOIN.fullmatch(sentence[groups[-1][-1][2]:mod[1]]):
                groups[-1].append(mod)
            else:
                groups.append([mod])
        for group in groups:
            gaps = [min(max(0, ms - e, s - me) for _, ms, me, _ in group) for s, e, _ in found]
            for key, _, _, name in group:
                _put(items[gaps.index(min(gaps))], key, name)
        out.extend(items)
        last = items[-1]
    seen = set()
    unique = []
    for item in out:
        sig = (item["name"], tuple(item["sides"]), tuple(item["positions"]), item["quantity"])
        if sig not in seen:
            seen.add(sig)
            unique.append(item)
    return unique


def _ref_ok(raw, clean):
    if not 6 <= len(clean) <= _MAX_REF or sum(c.isdigit() for c in clean) < 4:
        return False
    if _NOT_REF.fullmatch(raw) or re.fullmatch(r"[4-8]\d{8}", clean):
        return False
    return True


def _references(text):
    upper = text.upper()
    found = []
    for m in _REF_SPACED.finditer(upper):
        suffix = m.group(4) if m.group(4) and m.group(4) not in _REF_SUFFIX_WORDS else ""
        joined = m.group(1) + m.group(2) + m.group(3) + suffix
        if any(c.isalpha() for c in joined):
            found.append((m.start(), joined))
    blank = _REF_SPACED.sub(lambda m: " " * len(m.group()), upper)
    for m in _REF_TOKEN.finditer(blank):
        clean = re.sub(r"[./-]", "", m.group())
        if _ref_ok(m.group(), clean):
            found.append((m.start(), clean))
    refs = []
    for _, ref in sorted(found):
        if ref not in refs:
            refs.append(ref)
    return refs


def _details(text, vins):
    work = _PHONE.sub(" ", _strip_vins(text, vins))
    n = _norm(work)
    brand, model = _brand_model(n)
    year_m = _YEAR.search(n)
    prod_m = _PROD.search(n)
    year = int(year_m.group(1)) if year_m else (int(prod_m.group(2)) if prod_m else None)
    year_to = int(year_m.group(2)) if year_m and year_m.group(2) and int(year_m.group(2)) >= year else None
    displacement = None
    disp_m = _DISP.search(n)
    if disp_m:
        displacement = float(disp_m.group(1) + "." + disp_m.group(2))
    else:
        cc_m = _DISP_CC.search(n)
        if cc_m:
            displacement = round(int(cc_m.group(1)) / 1000, 1)
    power_kw = power_hp = None
    power_m = _POWER.search(n)
    if power_m:
        if power_m.group(2) == "kw":
            power_kw = int(power_m.group(1))
        else:
            power_hp = int(power_m.group(1))
    layout_m = _LAYOUT.search(n)
    code_m = _ENGINE_CODE.search(n)
    doors_m = _DOORS.search(n)
    return {
        "vin_region": None,
        "references": _references(work),
        "brand": brand,
        "model": model,
        "year": year,
        "year_to": year_to,
        "production_date": f"{prod_m.group(2)}-{int(prod_m.group(1)):02d}" if prod_m else None,
        "displacement_l": displacement,
        "power_kw": power_kw,
        "power_hp": power_hp,
        "engine_code": code_m.group(1).upper() if code_m else None,
        "engine_layout": "V" + layout_m.group(1) if layout_m else None,
        "fuel": _first(_FUEL_RES, n),
        "transmission": _first(_TRANS_RES, n),
        "drivetrain": _first(_DRIVE_RES, n),
        "body": _first(_BODY_RES, n),
        "doors": int(doors_m.group(1)) if doors_m else None,
        "market": _first(_MARKET_RES, n),
        "steering": _first(_STEERING_RES, n),
        "parts": _parts(n),
    }


def _no_vin_reason(result):
    refs = result["references"]
    if len(refs) == 1:
        return None
    if len(refs) > 1:
        return None if len(result["parts"]) >= len(refs) else "kilka referencji, nie wiadomo która"
    if result["brand"] and result["model"] and result["year"]:
        return None if result["parts"] else "brak części"
    if result["brand"] or result["model"] or result["year"]:
        return "brak VIN, za mało danych o aucie"
    return "brak VIN"


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

    vins = [t for t in dict.fromkeys(_TOKEN_17.findall(upper) + _spaced_vins(upper)) if _looks_like_vin(t)]
    result.update(_details(text, vins))

    if not vins:
        result["request_text"] = _clean_request(text, None)
        wrong = [
            t for t in _TOKEN_LONG.findall(upper)
            if len(t) != 17 and _looks_like_vin(t) and any(c.isalpha() for c in t)
        ]
        if not wrong:
            reason = _no_vin_reason(result)
            result["needs_human"] = reason is not None
            result["reason"] = reason
            return result
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
    result["vin_region"] = _vin_region(vin)
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
