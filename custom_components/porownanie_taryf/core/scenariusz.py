"""Rozwiązanie okresu i złożenie wyniku scenariuszy (sprzedawca × taryfa dystrybucyjna), spec §5.6 i §7."""

from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from . import TZ, HourlyReading
from .dystrybucja import dystrybucja
from .presety import TANIA_STREFA, TARYFY, Konfiguracja
from .sprzedaz import sprzedaz_cennik, sprzedaz_pstryk
from .tarcza import tarcza

RODZAJE_OKRESU = ("dzien", "miesiac", "rok", "zakres")


@dataclass(frozen=True, slots=True)
class WynikScenariusza:
    sprzedaz_przed: float
    tarcza: float  # <= 0
    sprzedaz_po: float
    dystrybucja: float
    razem: float
    netto: float
    kwh_na_strefe: dict[str, float]
    szacunek: bool
    ostrzezenia: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Wynik:
    od: date
    do: date
    pokrycie: float
    kwh_tanie: float  # w tanich strefach obecnej taryfy
    kwh_drogie: float
    obecny: str  # klucz scenariusza
    scenariusze: dict[str, WynikScenariusza]


def rozwiaz_okres(rodzaj: str, d: date, koniec: date | None) -> tuple[date, date] | None:
    """None = zakres bez poprawnego końca (koniec brak lub przed datą)."""
    if rodzaj == "dzien":
        return d, d
    if rodzaj == "miesiac":
        return d.replace(day=1), d.replace(day=monthrange(d.year, d.month)[1])
    if rodzaj == "rok":
        return date(d.year, 1, 1), date(d.year, 12, 31)
    if rodzaj == "zakres":
        return (d, koniec) if koniec is not None and koniec >= d else None
    raise ValueError(f"nieznany rodzaj okresu: {rodzaj}")


def godzin_w_okresie(od: date, do: date) -> int:
    """Prawdziwa liczba godzin (z DST): różnica UTC, nie zegara ściennego."""
    pocz = datetime(od.year, od.month, od.day, tzinfo=TZ).astimezone(timezone.utc)
    kon = datetime.combine(do + timedelta(days=1), datetime.min.time(), tzinfo=TZ).astimezone(timezone.utc)
    return int((kon - pocz).total_seconds() // 3600)


def domyslna_data(dzis: date) -> date:
    """1. dzień poprzedniego miesiąca."""
    return (dzis.replace(day=1) - timedelta(days=1)).replace(day=1)


def klucze_scenariuszy(k: Konfiguracja) -> list[str]:
    klucze = [f"pstryk_{t}" for t in TARYFY]
    klucze += [f"kompleksowa_{t}" for t in TARYFY if t in k.kompleksowa.ceny]
    if k.cennik:
        klucze += [f"cennik_{t}" for t in TARYFY if t in k.cennik.ceny]
    return klucze


def taryfa_scenariusza(klucz: str) -> str:
    return klucz.split("_", 1)[1]


def grupa_scenariusza(klucz: str) -> str:
    """"pstryk" | "kompleksowa" (także własny cennik)."""
    return "pstryk" if klucz.startswith("pstryk_") else "kompleksowa"


def sprzedawca_scenariusza(klucz: str, k: Konfiguracja) -> str:
    rodzaj = klucz.split("_", 1)[0]
    return {"pstryk": "Pstryk", "kompleksowa": k.kompleksowa.nazwa}.get(rodzaj) or k.cennik.nazwa


def etykieta(klucz: str, k: Konfiguracja) -> str:
    return f"{sprzedawca_scenariusza(klucz, k)} + {taryfa_scenariusza(klucz)}"


def policz(wszystkie: Sequence[HourlyReading], od: date, do: date, k: Konfiguracja) -> Wynik:
    odczyty = [r for r in wszystkie if od <= r.start_local.astimezone(TZ).date() <= do]
    pokrycie = len(odczyty) / godzin_w_okresie(od, do)
    wspolne = set()
    if pokrycie < 0.95:
        wspolne.add("pokrycie_ponizej_95")
    if (do - od).days + 1 < 28:
        wspolne.add("okres_krotszy_niz_miesiac")
    if any(r.start_local.astimezone(TZ).year != k.stawki.rok for r in odczyty):
        wspolne.add(f"stawki_spoza_roku:{k.stawki.rok}")

    pstryk = sprzedaz_pstryk(odczyty, k.vat)
    rabat = tarcza(odczyty, wszystkie, k.tarcza, k.vat)  # wspólna dla wszystkich scenariuszy pstryk_*
    dystr = {t: dystrybucja(odczyty, t, k.stawki, k.tanie_g12, k.vat) for t in TARYFY}

    scenariusze: dict[str, WynikScenariusza] = {}
    for klucz in klucze_scenariuszy(k):
        rodzaj, t = klucz.split("_", 1)
        if rodzaj == "pstryk":
            s, r_brutto, r_netto, szacunek = pstryk, rabat.rabat, rabat.rabat_netto, rabat.szacunek
            ostrzezenia = wspolne.union(rabat.ostrzezenia)
        else:
            cennik = k.kompleksowa if rodzaj == "kompleksowa" else k.cennik
            s, r_brutto, r_netto, szacunek = sprzedaz_cennik(odczyty, t, cennik, k.tanie_g12, k.vat), 0.0, 0.0, False
            ostrzezenia = wspolne
        d = dystr[t]
        po = s.brutto - r_brutto
        scenariusze[klucz] = WynikScenariusza(
            sprzedaz_przed=s.brutto,
            tarcza=-r_brutto + 0.0,  # + 0.0: unika "-0.0" przy zerowym rabacie
            sprzedaz_po=po,
            dystrybucja=d.brutto,
            razem=po + d.brutto,
            netto=s.netto - r_netto + d.netto,
            kwh_na_strefe=d.kwh_na_strefe,
            szacunek=szacunek,
            ostrzezenia=tuple(sorted(ostrzezenia)),
        )

    obecna = k.obecna_taryfa
    tania = TANIA_STREFA[obecna]
    kwh = dystr[obecna].kwh_na_strefe
    return Wynik(
        od=od, do=do, pokrycie=pokrycie,
        kwh_tanie=kwh[tania],
        kwh_drogie=sum(v for z, v in kwh.items() if z != tania),
        obecny=f"pstryk_{obecna}",
        scenariusze=scenariusze,
    )
