"""Presety stawek dystrybucyjnych i budowa konfiguracji z wpisu HA (dane + opcje)."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from .strefy import TANIE_G12_DOMYSLNE

TARYFY = ("G11", "G12", "G12w", "G12sezON", "G13active")
STREFY: dict[str, tuple[str, ...]] = {
    "G11": ("calodobowa",),
    "G12": ("dzien", "noc"),
    "G12w": ("szczyt", "pozaszczyt"),
    "G12sezON": ("pozostale", "zalecana"),
    "G13active": ("ograniczanie", "pozostale", "pobor"),
}
TANIA_STREFA: dict[str, str] = {"G11": "calodobowa", "G12": "noc", "G12w": "pozaszczyt", "G12sezON": "zalecana", "G13active": "pobor"}

CONF_UKLAD = "uklad"  # "3f" | "1f"
CONF_PRESET = "preset"  # "enea_2026"
CONF_TARYFA = "taryfa"
CONF_TANIE_G12 = "tanie_g12"  # list[int]
OPT_VAT = "vat"
OPT_STAWKI = "stawki"
OPT_TARCZA = "tarcza"
OPT_CENNIK = "cennik"

_STALE_ENEA_2026 = {
    "3f": {"G11": 10.41, "G12": 14.56, "G12w": 26.23, "G12sezON": 14.56, "G13active": 14.56},
    "1f": {"G11": 7.45, "G12": 9.59, "G12w": 16.85, "G12sezON": 9.59, "G13active": 9.59},
}


@dataclass(frozen=True, slots=True)
class StawkiDystrybucji:
    zmienne: dict[str, dict[str, float]]  # taryfa -> strefa -> zł/kWh netto
    stale: dict[str, float]  # taryfa -> składnik stały zł/mc
    sosj: float  # opłata jakościowa zł/kWh
    oze: float
    kog: float
    abonament: float  # zł/mc
    moc: float  # opłata mocowa zł/mc
    rok: int


@dataclass(frozen=True, slots=True)
class ParametryTarczy:
    limit: float
    podstawa: str  # "brutto" | "netto"
    obejmuje_obsluge: bool
    od: date
    do: date
    zweryfikowany: bool


@dataclass(frozen=True, slots=True)
class Cennik:
    nazwa: str
    oplata_mc: float
    akcyza: float
    ceny: dict[str, dict[str, float]]  # taryfa -> strefa -> zł/kWh netto
    oferta: str = ""  # nazwa oferty w katalogu; własny cennik jej nie ma
    uwagi: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Konfiguracja:
    obecna_taryfa: str
    tanie_g12: frozenset[int]
    vat: float
    stawki: StawkiDystrybucji
    tarcza: tuple[ParametryTarczy, ...]
    cennik: Cennik | None
    kompleksowe: dict[str, Cennik]  # wszystkie oferty z katalogu, liczone równolegle


# Katalog ofert kompleksowych. Ceny netto Z AKCYZĄ (stąd akcyza=0.0), VAT liczony od całości.
# Oferta bez danej taryfy = brak scenariusza. Kolejność wpisów = kolejność w panelu przy remisie.
SPRZEDAWCY: dict[str, Cennik] = {
    "enea_2026_wybor": Cennik("Enea", 10.49, 0.0, {
        "G11": {"calodobowa": 0.5050},
        "G12": {"dzien": 0.5900, "noc": 0.3486},
        "G12w": {"szczyt": 0.5050, "pozaszczyt": 0.5050},
    }, oferta="prawo wyboru", uwagi=(
        "Cennik dla klientów, którzy zmieniali sprzedawcę — przed decyzją potwierdź ofertę w Enei.",
    )),
    "enea_eneopewnosc_2026": Cennik("Enea", 15.94, 0.0, {
        "G11": {"calodobowa": 0.4950},
        "G12": {"dzien": 0.5736, "noc": 0.3365},
        "G12w": {"szczyt": 0.6464, "pozaszczyt": 0.3459},
        "G12sezON": {"pozostale": 0.5841, "zalecana": 0.3465},
    }, oferta="EneoPewność", uwagi=(
        "Cena energii i opłata handlowa stałe przez 36 miesięcy; opłata 15,94 zł/mies. przy e-fakturze "
        "(20,01 zł przy fakturze papierowej), obejmuje usługę „Elektryk”.",
        "Przy zmianie sprzedawcy grupa taryfowa musi być taka jak dotychczasowa — na G12sezON najpierw zmiana grupy u operatora.",
        "Cennik dla umów zawieranych od 1.10 do 31.12.2026.",
    )),
}

TARCZA_DOMYSLNA: dict[str, ParametryTarczy] = {
    "2026": ParametryTarczy(0.61, "brutto", True, date(2026, 1, 1), date(2026, 12, 31), True),
    "2027": ParametryTarczy(0.50, "netto", False, date(2027, 1, 1), date(2027, 12, 31), False),
}


def stawki_enea_2026(uklad: str) -> StawkiDystrybucji:
    return StawkiDystrybucji(
        zmienne={
            "G11": {"calodobowa": 0.2456},
            "G12": {"dzien": 0.2779, "noc": 0.0913},
            "G12w": {"szczyt": 0.2702, "pozaszczyt": 0.0813},
            "G12sezON": {"pozostale": 0.2779, "zalecana": 0.0913},
            "G13active": {"ograniczanie": 0.3032, "pozostale": 0.2456, "pobor": 0.0730},
        },
        stale=dict(_STALE_ENEA_2026[uklad]),
        sosj=0.0332, oze=0.0073, kog=0.0030, abonament=3.84, moc=24.05, rok=2026,
    )


def stawki_na_plasko(s: StawkiDystrybucji) -> dict[str, float]:
    plasko = {f"{t}_{z}": v for t, strefy in s.zmienne.items() for z, v in strefy.items()}
    plasko.update({f"ssv_{t}": v for t, v in s.stale.items()})
    plasko.update(sosj=s.sosj, oze=s.oze, kog=s.kog, abonament=s.abonament, moc=s.moc)
    return plasko


def stawki_z_plaskich(d: Mapping[str, float], rok: int) -> StawkiDystrybucji:
    return StawkiDystrybucji(
        zmienne={t: {z: d[f"{t}_{z}"] for z in zs} for t, zs in STREFY.items()},
        stale={t: d[f"ssv_{t}"] for t in TARYFY},
        sosj=d["sosj"], oze=d["oze"], kog=d["kog"], abonament=d["abonament"], moc=d["moc"], rok=rok,
    )


def zbuduj_konfiguracje(data: Mapping[str, Any], options: Mapping[str, Any]) -> Konfiguracja:
    # ponytail: jedyny preset to enea_2026; CONF_PRESET dopiero wybierze stawki, gdy pojawi się drugi
    baza = stawki_enea_2026(data[CONF_UKLAD])
    stawki = stawki_z_plaskich({**stawki_na_plasko(baza), **options.get(OPT_STAWKI, {})}, baza.rok)
    nadpisania = options.get(OPT_TARCZA, {})
    tarcza = tuple(
        replace(p, **{k: date.fromisoformat(v) if k in ("od", "do") else v
                      for k, v in nadpisania.get(rok, {}).items()})
        for rok, p in TARCZA_DOMYSLNA.items()
    )
    c = options.get(OPT_CENNIK)
    return Konfiguracja(
        obecna_taryfa=data[CONF_TARYFA],
        tanie_g12=frozenset(data.get(CONF_TANIE_G12, TANIE_G12_DOMYSLNE)),
        vat=options.get(OPT_VAT, 0.23),
        stawki=stawki,
        tarcza=tarcza,
        cennik=Cennik(c["nazwa"], c["oplata_mc"], c["akcyza"], c["ceny"]) if c else None,
        kompleksowe=SPRZEDAWCY,
    )
