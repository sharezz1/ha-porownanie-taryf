from datetime import datetime

import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.core.presety import Cennik
from custom_components.porownanie_taryf.core.sprzedaz import WynikSprzedazy, sprzedaz_cennik, sprzedaz_pstryk
from custom_components.porownanie_taryf.core.strefy import TANIE_G12_DOMYSLNE
from tests.dane import wrzesien


def test_sprzedaz_pstryk():
    w = sprzedaz_pstryk(wrzesien(), 0.23)
    assert w.brutto == pytest.approx(517.248) and w.netto == pytest.approx(421.2)


def test_sprzedaz_pstryk_null_jako_zero():
    r = HourlyReading(datetime(2025, 12, 10, 0, tzinfo=TZ), 1.0, None, None, None)
    assert sprzedaz_pstryk([r], 0.23) == WynikSprzedazy(0.0, 0.0)


def test_sprzedaz_cennik():
    c = Cennik("X", 10.0, 0.005, {"G12": {"dzien": 0.6, "noc": 0.4}})
    w = sprzedaz_cennik(wrzesien(), "G12", c, TANIE_G12_DOMYSLNE, 0.23)
    assert w.brutto == pytest.approx(474.288) and w.netto == pytest.approx(385.6)  # (382 + 3,6) · 1,23


def test_sprzedaz_cennik_akcyza_w_podstawie_vat():
    r = HourlyReading(datetime(2025, 12, 10, 0, tzinfo=TZ), 1.0, None, None, None)
    c = Cennik("X", 0.0, 0.005, {"G12": {"dzien": 0.5, "noc": 0.5}})
    assert sprzedaz_cennik([r], "G12", c, TANIE_G12_DOMYSLNE, 0.23).brutto == pytest.approx(0.62115)  # (0,5 + 0,005) · 1,23
