"""Prywatne testy referencyjne: rdzeń vs prawdziwe dane godzinowe i faktury autora.

Wymagają dwóch plików spoza repo: bazy SQLite (`REF_DB`) i JSON-a z oczekiwanymi kwotami z faktur
(`REF_EXPECTED`, domyślnie `oczekiwane_referencja.json` obok `REF_DB`). Brak któregokolwiek = moduł pomijany.
Format JSON: {"tarcza": {"<miesiąc>": <rabat>, ...}, "wrzesien": {"razem": ..., "sprzedaz_przed": ...,
"tarcza": ..., "dystrybucja": ..., "g12w_minus_g12": ..., "kwh_tanie": ..., "kwh_drogie": ...}}
"""

import json
import os
from pathlib import Path
import sqlite3
from collections import defaultdict
from datetime import date, datetime

import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.core.dystrybucja import dystrybucja
from custom_components.porownanie_taryf.core.presety import (
    TARCZA_DOMYSLNA,
    stawki_enea_2026,
    zbuduj_konfiguracje,
)
from custom_components.porownanie_taryf.core.scenariusz import policz
from custom_components.porownanie_taryf.core.sprzedaz import sprzedaz_pstryk
from custom_components.porownanie_taryf.core.strefy import TANIE_G12_DOMYSLNE
from custom_components.porownanie_taryf.core.tarcza import tarcza

pytestmark = pytest.mark.reference

_DB = os.environ.get("REF_DB")
_JSON = Path(os.environ["REF_EXPECTED"]) if "REF_EXPECTED" in os.environ else (Path(_DB).parent / "oczekiwane_referencja.json" if _DB else None)
if not _DB or not _JSON or not _JSON.is_file():
    pytest.skip("brak REF_DB lub pliku z oczekiwanymi kwotami (REF_EXPECTED)", allow_module_level=True)
OCZEKIWANE = json.loads(_JSON.read_text())

VAT = 0.23
KONF = zbuduj_konfiguracje(
    {"uklad": "3f", "preset": "enea_2026", "taryfa": "G12", "tanie_g12": sorted(TANIE_G12_DOMYSLNE)}, {}
)


@pytest.fixture(scope="module")
def wiersze() -> list[dict]:
    """Wiersze 2026 (grudzień 2025 ma inne stawki i puste pola sprzedaży)."""
    db = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        wszystkie = db.execute("SELECT * FROM hourly WHERE kwh_import IS NOT NULL ORDER BY ts_utc").fetchall()
    finally:
        db.close()
    out = []
    for w in wszystkie:
        d = dict(w)
        d["start"] = datetime.fromisoformat(d["ts_local"]).astimezone(TZ)
        if d["start"].year == 2026:
            out.append(d)
    return out


def _odczyty(wiersze) -> list[HourlyReading]:
    return [
        HourlyReading(w["start"], w["kwh_import"], w["energy_cost_net"], w["service_cost_net"], w["excise"])
        for w in wiersze
    ]


def _wg_miesiecy(wiersze) -> dict[int, list[dict]]:
    m = defaultdict(list)
    for w in wiersze:
        m[w["start"].month].append(w)
    return m


def _z(v) -> float:
    return v or 0.0


def test_dystrybucja_g12_vs_api(wiersze):
    luty_wrzesien = [w for w in wiersze if 2 <= w["start"].month <= 9]
    model = dystrybucja(_odczyty(luty_wrzesien), "G12", stawki_enea_2026("3f"), TANIE_G12_DOMYSLNE, VAT).netto
    api = sum(_z(w["var_dist_cost_net"]) + _z(w["fix_dist_cost_net"]) for w in luty_wrzesien)
    assert abs(model - api) / api <= 0.005


def test_sprzedaz_plus_dystrybucja_api_rowna_importowi(wiersze):
    miesiace = _wg_miesiecy(wiersze)
    assert miesiace
    for mies, ws in miesiace.items():
        sprzedaz = sprzedaz_pstryk(_odczyty(ws), VAT).brutto
        dystr_api = sum(
            _z(w["var_dist_cost_net"]) + _z(w["fix_dist_cost_net"])
            + _z(w["var_dist_cost_vat"]) + _z(w["fix_dist_cost_vat"])
            for w in ws
        )
        import_api = sum(_z(w["energy_import_cost"]) for w in ws)
        assert abs(sprzedaz + dystr_api - import_api) <= 0.01, f"2026-{mies:02d}"


def test_tarcza_faktury(wiersze):
    wszystkie = _odczyty(wiersze)
    presety = list(TARCZA_DOMYSLNA.values())
    for mies, oczekiwany in ((int(m), v) for m, v in OCZEKIWANE["tarcza"].items()):
        okres = [r for r in wszystkie if r.start_local.month == mies]
        assert tarcza(okres, wszystkie, presety, VAT).rabat == pytest.approx(oczekiwany, abs=0.10), mies


def test_akceptacja_wrzesien(wiersze):
    ocz = OCZEKIWANE["wrzesien"]
    w = policz(_odczyty(wiersze), date(2026, 9, 1), date(2026, 9, 30), KONF)
    g12 = w.scenariusze["pstryk_G12"]
    assert g12.razem == pytest.approx(ocz["razem"], abs=0.50)
    assert g12.sprzedaz_przed == pytest.approx(ocz["sprzedaz_przed"], abs=0.01)
    assert g12.tarcza == pytest.approx(ocz["tarcza"], abs=0.10)
    assert g12.dystrybucja == pytest.approx(ocz["dystrybucja"], abs=0.50)
    assert w.scenariusze["pstryk_G12w"].razem - g12.razem == pytest.approx(ocz["g12w_minus_g12"], abs=0.30)
    assert w.kwh_tanie == pytest.approx(ocz["kwh_tanie"], abs=0.2)
    assert w.kwh_drogie == pytest.approx(ocz["kwh_drogie"], abs=0.2)
