"""Prywatny test PV na danych autora: REF_DB (energia.db) + REF_PV (katalog z gti.json, rce.json i oczekiwane.json).
Oczekiwane wartości i dane wejściowe żyją poza repozytorium; brak oczekiwane.json -> skip."""

import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.core.presety import zbuduj_konfiguracje
from custom_components.porownanie_taryf.core.pv import ParametryPV, Polac
from custom_components.porownanie_taryf.core.pv_wyniki import wyniki
from custom_components.porownanie_taryf.core.strefy import TANIE_G12_DOMYSLNE

pytestmark = pytest.mark.reference
_DB, _PV = os.environ.get("REF_DB"), os.environ.get("REF_PV")
if not _DB or not _PV:
    pytest.skip("brak REF_DB lub REF_PV", allow_module_level=True)


def _odczyty():
    with sqlite3.connect(_DB) as c:
        rows = c.execute("SELECT ts_utc, kwh_import, energy_cost_net, service_cost_net, excise FROM hourly WHERE kwh_import IS NOT NULL").fetchall()
    return [HourlyReading(datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(TZ), k, e, s, x) for t, k, e, s, x in rows]


def test_6_kwp_regresja_i_monotonicznosc():
    oczek_plik = Path(_PV) / "oczekiwane.json"
    if not oczek_plik.exists():
        pytest.skip("brak REF_PV/oczekiwane.json")
    oczek = json.loads(oczek_plik.read_text())
    gti = {k: tuple(v) for k, v in json.loads((Path(_PV) / "gti.json").read_text()).items()}
    rce = json.loads((Path(_PV) / "rce.json").read_text())
    konf = zbuduj_konfiguracje({"uklad": "3f", "preset": "enea_2026", "taryfa": "G12", "tanie_g12": sorted(TANIE_G12_DOMYSLNE)}, {})
    w = wyniki(_odczyty(), konf, [Polac(*oczek["polac"])], [gti], rce, 3000, 2000, ParametryPV(), date(2026, 10, 9))
    assert w["stan"] == "ok", w
    v = {(x["kwp"][0]["kwp"], x["magazyn_kwh"]): x for x in w["warianty"]}
    for k, x in v.items():
        print(k, {f: x[f] for f in ("oszczednosc_rok", "produkcja_kwh", "autokonsumpcja", "eksport_kwh", "depozyt_niewykorzystany", "zwrot_lata")})
    print("baza", w["baza"], "pokrycie", w["pokrycie"], "ostrzezenia", w["ostrzezenia"])
    assert v[(6.0, 0)]["oszczednosc_rok"] == pytest.approx(oczek["oszczednosc_6kwp"], rel=0.01)
    assert v[(8.0, 0)]["oszczednosc_rok"] > v[(6.0, 0)]["oszczednosc_rok"] > v[(4.0, 0)]["oszczednosc_rok"]
    assert oczek["uzysk_min"] <= v[(6.0, 0)]["produkcja_kwh"] / 6 <= oczek["uzysk_max"]
