from datetime import date, datetime, timezone

import pytest

from custom_components.porownanie_taryf.core import TZ
from custom_components.porownanie_taryf.core.strefy import godzin_w_miesiacu, strefa, swieta, wielkanoc


def test_wielkanoc():
    assert wielkanoc(2026) == date(2026, 4, 5) and wielkanoc(2027) == date(2027, 3, 28)


def test_swieta_2026_z_wigilia():
    s = swieta(2026)
    assert {date(2026, 4, 6), date(2026, 6, 4), date(2026, 11, 11), date(2026, 12, 24)} <= s  # Pon. Wielkanocny, Boże Ciało, Wigilia (wolna od 2025)
    assert len(s) == 14


@pytest.mark.parametrize("ts", [datetime(2026, 9, 15, 12, tzinfo=TZ), datetime(2026, 9, 20, 3, tzinfo=TZ)])
def test_g11_calodobowa(ts):  # dzień roboczy 12:00, niedziela 03:00
    assert strefa("G11", ts) == "calodobowa"


@pytest.mark.parametrize("h,exp", [(5, "noc"), (6, "dzien"), (13, "noc"), (15, "dzien"), (22, "noc")])
def test_g12_domyslne(h, exp):
    assert strefa("G12", datetime(2026, 9, 15, h, tzinfo=TZ)) == exp


def test_g12_wlasne_tanie():
    assert strefa("G12", datetime(2026, 9, 15, 13, tzinfo=TZ), frozenset(range(0, 7))) == "dzien"


@pytest.mark.parametrize("ts,exp", [
    (datetime(2026, 9, 15, 6, tzinfo=TZ), "szczyt"), (datetime(2026, 9, 15, 20, tzinfo=TZ), "szczyt"),
    (datetime(2026, 9, 15, 21, tzinfo=TZ), "pozaszczyt"), (datetime(2026, 9, 19, 12, tzinfo=TZ), "pozaszczyt"),
    (datetime(2026, 11, 11, 12, tzinfo=TZ), "pozaszczyt"), (datetime(2026, 4, 6, 12, tzinfo=TZ), "pozaszczyt"),
    (datetime(2026, 6, 4, 12, tzinfo=TZ), "pozaszczyt"), (datetime(2026, 12, 24, 12, tzinfo=TZ), "pozaszczyt")])
def test_g12w(ts, exp):
    assert strefa("G12w", ts) == exp


@pytest.mark.parametrize("ts,exp", [
    (datetime(2026, 9, 15, 7, tzinfo=TZ), "ograniczanie"), (datetime(2026, 9, 15, 12, tzinfo=TZ), "pobor"),
    (datetime(2026, 9, 15, 16, tzinfo=TZ), "pozostale"), (datetime(2026, 9, 15, 17, tzinfo=TZ), "ograniczanie"),
    (datetime(2026, 9, 19, 7, tzinfo=TZ), "ograniczanie"), (datetime(2027, 1, 12, 23, tzinfo=TZ), "pobor")])
def test_g13active(ts, exp):
    assert strefa("G13active", ts) == exp


def test_dst_wejscie_utc_liczone_wg_zegara_sciennego():
    assert strefa("G12", datetime(2026, 3, 29, 20, tzinfo=timezone.utc)) == "noc"   # 22:00 CEST
    assert strefa("G12", datetime(2026, 10, 25, 4, tzinfo=timezone.utc)) == "noc"   # 05:00 CET
    assert strefa("G12", datetime(2026, 10, 25, 5, tzinfo=timezone.utc)) == "dzien"  # 06:00 CET


def test_godzin_w_miesiacu():
    assert [godzin_w_miesiacu(2026, m) for m in (2, 3, 9, 10)] == [672, 743, 720, 745]
