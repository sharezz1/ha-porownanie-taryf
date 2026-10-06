from datetime import datetime

import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.core.presety import TARCZA_DOMYSLNA
from custom_components.porownanie_taryf.core.tarcza import tarcza
from tests.dane import godziny, wrzesien

P = tuple(TARCZA_DOMYSLNA.values())


def test_pelny_miesiac_2026():
    w = wrzesien(); t = tarcza(w, w, P, 0.23)
    assert t.rabat == pytest.approx(74.448) and t.rabat_netto == pytest.approx(74.448 / 1.23)
    assert t.szacunek is False and t.ostrzezenia == ()


def test_avg_rowne_limitowi():
    w = wrzesien(e=0.61 / 1.23 - 0.08)
    assert tarcza(w, w, P, 0.23).rabat == pytest.approx(0.0, abs=1e-9)


def test_avg_ponizej_limitu():
    w = wrzesien(e=0.30); assert tarcza(w, w, P, 0.23).rabat == 0.0


def test_dzien_bierze_srednia_z_calego_miesiaca():
    w = wrzesien(); t = tarcza(w[:24], w, P, 0.23)
    assert t.rabat == pytest.approx(2.4816) and t.szacunek is False


def test_niepelny_miesiac_w_magazynie_to_szacunek():
    w = wrzesien(360); t = tarcza(w, w, P, 0.23)
    assert t.rabat == pytest.approx(37.224) and t.szacunek is True


def test_2027_netto_bez_oplaty_i_niezweryfikowany():
    sty = godziny(datetime(2027, 1, 1, tzinfo=TZ), 744, e=0.60)
    t = tarcza(sty, sty, P, 0.23)
    assert t.rabat == pytest.approx(91.512) and "tarcza_niezweryfikowana:2027" in t.ostrzezenia


def test_poza_presetem():
    r = [HourlyReading(datetime(2025, 12, 10, 0, tzinfo=TZ), 1.0, 0.9, 0.08, 0.005)]
    t = tarcza(r, r, P, 0.23)
    assert t.rabat == 0.0 and t.ostrzezenia == ("brak_tarczy:2025-12",)


def test_zakres_przez_dwa_miesiace_z_dst():
    pazdz = godziny(datetime(2026, 10, 1, tzinfo=TZ), 745)  # 25.10: zmiana czasu, 745 h
    w = wrzesien()
    t = tarcza(w[-24:] + pazdz[:24], w + pazdz, P, 0.23)
    assert t.rabat == pytest.approx(2 * 2.4816) and t.szacunek is False


def test_miesiac_bez_kwh():
    r = [HourlyReading(datetime(2026, 9, 1, 0, tzinfo=TZ), 0.0, 0.0, 0.0, 0.0)]
    assert tarcza(r, r, P, 0.23).rabat == 0.0
