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


# Katalog ofert kompleksowych. Ceny netto Z AKCYZĄ w cenie (stąd akcyza=0.0); wyjątek: PGE — cennik netto bez akcyzy (akcyza=0.005); VAT liczony od całości.
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
        "G13active": {"ograniczanie": 0.6435, "pozostale": 0.4950, "pobor": 0.2772},
    }, oferta="EneoPewność", uwagi=(
        "Cena energii i opłata handlowa stałe przez 36 miesięcy; opłata 15,94 zł/mies. netto przy e-fakturze "
        "(20,01 zł netto przy fakturze papierowej), obejmuje usługę „Elektryk”.",
        "Przy zmianie sprzedawcy grupa taryfowa musi być taka jak dotychczasowa — na inną grupę (np. G12sezON) najpierw zmiana grupy u operatora.",
        "Cennik dla umów zawieranych od 1.10 do 31.12.2026.",
    )),
    "tauron_extra_2026": Cennik("Tauron", 6.80, 0.0, {
        "G11": {"calodobowa": 0.5020},
        "G12": {"dzien": 0.5480, "noc": 0.4180},
        "G12w": {"szczyt": 0.6270, "pozaszczyt": 0.4180},
    }, oferta="Twój Extra Elektryk 24H", uwagi=(
        "Cennik „Prąd z Twoim Extra Elektrykiem 24H”: umowę trzeba zawrzeć do 31.10.2026; ceny i stawki stałe do 30.09.2027.",
        "Opłata handlowa obejmuje gwarancję stałej ceny i usługę „Elektryk 24H”; brak opłaty za wcześniejsze rozwiązanie.",
        "Ceny netto z cennika, z akcyzą; dostępna poza obszarem TAURON Dystrybucja (Enea, Energa, PGE, Stoen).",
    )),
    "tauron_natura_2026": Cennik("Tauron", 25.61, 0.0, {
        "G11": {"calodobowa": 0.4999},
        "G12": {"dzien": 0.5457, "noc": 0.4163},
        "G12w": {"szczyt": 0.6244, "pozaszczyt": 0.4163},
    }, oferta="Energia dla natury i pszczół", uwagi=(
        "Cennik „Energia dla natury i pszczół”: umowę trzeba zawrzeć do 31.10.2026; ceny i stawki stałe do 30.09.2029.",
        "Opłata handlowa: 0 zł/mies. do 31.12.2026, od 01.01.2027 — 25,61 zł/mies. netto; w obliczeniach przyjęto 25,61 (koszt docelowy — w 2026 r. realnie 0 zł).",
        "Ceny netto z cennika, z akcyzą; certyfikat pochodzenia energii z OZE; dostępna poza obszarem TAURON Dystrybucja.",
    )),
    "pge_taryfowy_gtpa": Cennik("PGE", 9.99, 0.005, {
        "G11": {"calodobowa": 0.6170},
        "G12": {"dzien": 0.6975, "noc": 0.4367},
        "G12w": {"szczyt": 0.7170, "pozaszczyt": 0.5027},
    }, oferta="cennik taryfowy", uwagi=(
        "„Cennik taryfowy dla Klientów z grup G korzystających z prawa wyboru Sprzedawcy” (GT-PA) — obowiązuje od 1.08.2025.",
        "Ceny netto BEZ akcyzy — akcyza 0,005 zł/kWh doliczana poza VAT; cennik bezterminowy, bez gwarancji stałości cen.",
        "Dla konsumentów w obszarach: Enea, Energa, TAURON (w obszarze PGE Dystrybucja PGE ma inne ceny).",
    )),
    "energa_podstawowa_2026": Cennik("Energa", 16.99, 0.0, {
        "G11": {"calodobowa": 0.5000},
        "G12": {"dzien": 0.6080, "noc": 0.4037},
        "G12w": {"szczyt": 0.6080, "pozaszczyt": 0.4037},
    }, oferta="Podstawowa 2 lata", uwagi=(
        "Oferta „Podstawowa 2 lata”: umowę można zawrzeć do 31.12.2026; stałe warunki przez 24 miesiące.",
        "Ceny netto wyliczone z brutto (÷ 1,23): 0,6150 / 0,7478 / 0,4966 zł/kWh brutto; jedna cena dla G12 i G12w.",
        "Opłata handlowa 20,90 zł/mies. z e-fakturą (25,90 zł z papierową); po okresie oferty — cennik standardowy.",
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
