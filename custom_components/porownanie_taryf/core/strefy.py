"""Strefy czasowe taryf Enea Operator (G11, G12, G12w, G13active) wg zegara ściennego Europe/Warsaw."""

from datetime import date, datetime, timedelta, timezone
from functools import cache

from . import TZ

TANIE_G12_DOMYSLNE: frozenset[int] = frozenset({22, 23, 0, 1, 2, 3, 4, 5, 13, 14})

# G13active: strefy zależą od miesiąca (pkt 2.2.11 taryfy). Godziny lokalne,
# przedziały domknięte od lewej: (początek, koniec).
G13_STREFY = {
    1:  {"ograniczanie": [(7, 10), (15, 20)], "pobor": [(23, 24), (0, 6)]},
    2:  {"ograniczanie": [(7, 9), (16, 21)],  "pobor": [(23, 24), (0, 6)]},
    3:  {"ograniczanie": [(6, 9), (16, 23)],  "pobor": [(10, 16)]},
    4:  {"ograniczanie": [(6, 9), (18, 23)],  "pobor": [(10, 16)]},
    5:  {"ograniczanie": [(6, 9), (18, 23)],  "pobor": [(9, 17)]},
    6:  {"ograniczanie": [(6, 9), (18, 23)],  "pobor": [(9, 17)]},
    7:  {"ograniczanie": [(6, 9), (18, 23)],  "pobor": [(9, 17)]},
    8:  {"ograniczanie": [(6, 9), (18, 23)],  "pobor": [(9, 17)]},
    9:  {"ograniczanie": [(6, 9), (17, 23)],  "pobor": [(10, 16)]},
    10: {"ograniczanie": [(7, 9), (16, 23)],  "pobor": [(10, 16)]},
    11: {"ograniczanie": [(7, 9), (14, 21)],  "pobor": [(23, 24), (0, 6)]},
    12: {"ograniczanie": [(7, 10), (13, 20)], "pobor": [(23, 24), (0, 6)]},
}


def wielkanoc(rok: int) -> date:
    """Anonimowy algorytm Gaussa-Meeusa."""
    a, b, c = rok % 19, rok // 100, rok % 100
    d, e = b // 4, b % 4
    f, g, h = (b + 8) // 25, (b - (b + 8) // 25 + 1) // 3, (19 * a + b - d - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(rok, (h + l - 7 * m + 114) // 31, ((h + l - 7 * m + 114) % 31) + 1)


@cache
def swieta(rok: int) -> frozenset[date]:
    w = wielkanoc(rok)
    dni = {date(rok, 1, 1), date(rok, 1, 6), w, w + timedelta(days=1),
           date(rok, 5, 1), date(rok, 5, 3), w + timedelta(days=49), w + timedelta(days=60),
           date(rok, 8, 15), date(rok, 11, 1), date(rok, 11, 11),
           date(rok, 12, 25), date(rok, 12, 26)}
    if rok >= 2025:  # Wigilia dniem wolnym od 2025
        dni.add(date(rok, 12, 24))
    return frozenset(dni)


def strefa(taryfa: str, ts: datetime, tanie_g12: frozenset[int] = TANIE_G12_DOMYSLNE) -> str:
    ts = ts.astimezone(TZ)
    if taryfa == "G11":
        return "calodobowa"
    if taryfa == "G12":
        return "noc" if ts.hour in tanie_g12 else "dzien"
    if taryfa == "G12w":
        # szczyt tylko w dni robocze 6:00-21:00; weekendy i święta w całości pozaszczyt
        if ts.weekday() >= 5 or ts.date() in swieta(ts.year):
            return "pozaszczyt"
        return "szczyt" if 6 <= ts.hour < 21 else "pozaszczyt"
    if taryfa == "G13active":  # nie wyróżnia weekendów
        cfg = G13_STREFY[ts.month]
        for nazwa in ("ograniczanie", "pobor"):
            if any(start <= ts.hour < koniec for start, koniec in cfg[nazwa]):
                return nazwa
        return "pozostale"
    raise ValueError(f"nieznana taryfa: {taryfa}")


def godzin_w_miesiacu(rok: int, mies: int) -> int:
    """Prawdziwa liczba godzin w miesiącu (z DST): różnica UTC między 1. dniami."""
    # UTC jawnie: odejmowanie dwóch datetime z tym samym tzinfo liczy zegar ścienny, nie UTC
    pocz = datetime(rok, mies, 1, tzinfo=TZ).astimezone(timezone.utc)
    nast = datetime(rok + (mies == 12), mies % 12 + 1, 1, tzinfo=TZ).astimezone(timezone.utc)
    return int((nast - pocz).total_seconds() // 3600)
