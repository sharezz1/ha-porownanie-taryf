from datetime import date, datetime

import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.core.presety import SPRZEDAWCY, zbuduj_konfiguracje
from custom_components.porownanie_taryf.core.scenariusz import (
    cennik_scenariusza,
    domyslna_data,
    etykieta,
    godzin_w_okresie,
    grupa_scenariusza,
    id_oferty_scenariusza,
    klucze_scenariuszy,
    policz,
    rozwiaz_okres,
    sprzedawca_scenariusza,
    taryfa_scenariusza,
)
from tests.dane import wrzesien

K = zbuduj_konfiguracje({"uklad": "3f", "preset": "enea_2026", "taryfa": "G12", "tanie_g12": [22,23,0,1,2,3,4,5,13,14]},
                        {"cennik": {"nazwa": "Enea", "oplata_mc": 10.0, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}})
D = date(2026, 9, 15)


def test_rozwiaz_okres():
    assert rozwiaz_okres("dzien", D, None) == (D, D)
    assert rozwiaz_okres("miesiac", D, None) == (date(2026,9,1), date(2026,9,30))
    assert rozwiaz_okres("rok", D, None) == (date(2026,1,1), date(2026,12,31))
    assert rozwiaz_okres("zakres", D, date(2026,9,20)) == (D, date(2026,9,20))
    assert rozwiaz_okres("zakres", D, date(2026,9,14)) is None and rozwiaz_okres("zakres", D, None) is None


def test_godziny_i_domyslna_data():
    assert godzin_w_okresie(date(2026,10,25), date(2026,10,25)) == 25 and godzin_w_okresie(date(2026,3,29), date(2026,3,29)) == 23
    assert domyslna_data(date(2026,10,5)) == date(2026,9,1) and domyslna_data(date(2027,1,3)) == date(2026,12,1)


def test_klucze_i_etykiety():
    assert klucze_scenariuszy(K) == [
        "pstryk_G11", "pstryk_G12", "pstryk_G12w", "pstryk_G12sezON", "pstryk_G13active",
        "kompleksowa_enea_2026_wybor_G11", "kompleksowa_enea_2026_wybor_G12", "kompleksowa_enea_2026_wybor_G12w",
        "kompleksowa_enea_eneopewnosc_2026_G11", "kompleksowa_enea_eneopewnosc_2026_G12",
        "kompleksowa_enea_eneopewnosc_2026_G12w", "kompleksowa_enea_eneopewnosc_2026_G12sezON",
        "kompleksowa_enea_eneopewnosc_2026_G13active",
        "kompleksowa_tauron_extra_2026_G11", "kompleksowa_tauron_extra_2026_G12", "kompleksowa_tauron_extra_2026_G12w",
        "kompleksowa_tauron_natura_2026_G11", "kompleksowa_tauron_natura_2026_G12", "kompleksowa_tauron_natura_2026_G12w",
        "kompleksowa_pge_taryfowy_gtpa_G11", "kompleksowa_pge_taryfowy_gtpa_G12", "kompleksowa_pge_taryfowy_gtpa_G12w",
        "kompleksowa_energa_podstawowa_2026_G11", "kompleksowa_energa_podstawowa_2026_G12", "kompleksowa_energa_podstawowa_2026_G12w",
        "cennik_G12"]
    assert etykieta("pstryk_G12", K) == "Pstryk + G12"
    assert etykieta("kompleksowa_enea_2026_wybor_G12", K) == "Enea prawo wyboru + G12"
    assert etykieta("kompleksowa_enea_eneopewnosc_2026_G12sezON", K) == "Enea EneoPewność + G12sezON"
    assert etykieta("kompleksowa_tauron_extra_2026_G12", K) == "Tauron Twój Extra Elektryk 24H + G12"
    assert etykieta("kompleksowa_energa_podstawowa_2026_G11", K) == "Energa Podstawowa 2 lata + G11"
    assert etykieta("cennik_G12", K) == "Enea + G12"  # własny cennik "Enea" z K


def test_grupa_sprzedawca_taryfa():
    assert grupa_scenariusza("pstryk_G12") == "pstryk"
    assert grupa_scenariusza("kompleksowa_enea_2026_wybor_G12") == grupa_scenariusza("cennik_G12") == "kompleksowa"
    assert sprzedawca_scenariusza("pstryk_G12", K) == "Pstryk"
    assert sprzedawca_scenariusza("kompleksowa_enea_eneopewnosc_2026_G11", K) == "Enea"
    assert sprzedawca_scenariusza("cennik_G12", K) == "Enea"
    assert taryfa_scenariusza("pstryk_G13active") == "G13active" and taryfa_scenariusza("cennik_G12") == "G12"
    assert taryfa_scenariusza("kompleksowa_enea_eneopewnosc_2026_G12sezON") == "G12sezON"


def test_id_oferty_scenariusza():
    assert id_oferty_scenariusza("pstryk_G12") == ""
    assert id_oferty_scenariusza("kompleksowa_enea_2026_wybor_G12") == "enea_2026_wybor"
    assert id_oferty_scenariusza("kompleksowa_enea_eneopewnosc_2026_G12sezON") == "enea_eneopewnosc_2026"
    assert id_oferty_scenariusza("cennik_G12") == "cennik"


def test_policz_agregaty_pstryk():
    w = policz(wrzesien(), date(2026,9,1), date(2026,9,30), K)
    assert w.kwh == pytest.approx(720.0)
    assert w.pstryk_energia_netto == pytest.approx(720 * 0.58)  # Σ(energia + obsługa), bez akcyzy
    assert w.pstryk_akcyza == pytest.approx(720 * 0.005)
    assert w.rabat_netto == pytest.approx(74.45 / 1.23, abs=0.005)
    assert policz([], date(2026,1,1), date(2026,1,31), K).kwh == 0.0


def test_cennik_scenariusza():
    assert cennik_scenariusza("pstryk_G12", K) is None
    assert cennik_scenariusza("kompleksowa_enea_2026_wybor_G12", K) is SPRZEDAWCY["enea_2026_wybor"]
    assert cennik_scenariusza("kompleksowa_enea_eneopewnosc_2026_G12sezON", K) is SPRZEDAWCY["enea_eneopewnosc_2026"]
    assert cennik_scenariusza("cennik_G12", K) is K.cennik


def test_policz_wrzesien():
    w = policz(wrzesien(), date(2026,9,1), date(2026,9,30), K)
    g = w.scenariusze["pstryk_G12"]
    assert w.obecny == "pstryk_G12" and w.pokrycie == 1.0 and (w.kwh_tanie, w.kwh_drogie) == (300.0, 420.0)
    assert g.sprzedaz_przed == pytest.approx(517.248) and g.tarcza == pytest.approx(-74.448)
    assert g.dystrybucja == pytest.approx(267.98994) and g.razem == pytest.approx(710.78994) and g.netto == pytest.approx(578.55117)
    assert w.scenariusze["pstryk_G12w"].razem - g.razem == pytest.approx(-14.225, abs=1e-3)
    c = w.scenariusze["cennik_G12"]
    assert c.tarcza == 0.0 and c.sprzedaz_przed == pytest.approx(473.46) and c.razem == pytest.approx(473.46 + 267.98994)
    assert g.ostrzezenia == ()
    assert w.scenariusze["pstryk_G11"].razem == pytest.approx(745.93596)
    assert w.scenariusze["pstryk_G12sezON"].razem == pytest.approx(710.78994)
    kg12, kg11, kg12w = (w.scenariusze[f"kompleksowa_enea_2026_wybor_{t}"] for t in ("G12", "G11", "G12w"))
    assert kg12.razem == pytest.approx(714.32004) and kg12.tarcza == 0.0 and kg12.sprzedaz_przed == pytest.approx(446.3301)
    assert kg11.razem == pytest.approx(763.26666) and kg12w.razem == pytest.approx(713.89569)
    assert "kompleksowa_enea_2026_wybor_G12sezON" not in w.scenariusze
    assert "kompleksowa_enea_2026_wybor_G13active" not in w.scenariusze
    for t, brutto, razem in (("G11", 457.9782, 761.11416), ("G12", 440.09646, 708.0864),
                             ("G12w", 447.90819, 701.67318), ("G12sezON", 449.21076, 717.2007), ("G13active", 459.07413, 748.22991)):
        e = w.scenariusze[f"kompleksowa_enea_eneopewnosc_2026_{t}"]
        assert e.sprzedaz_przed == pytest.approx(brutto) and e.razem == pytest.approx(razem) and e.tarcza == 0.0, t
    for klucz, brutto, razem in (
        ("kompleksowa_tauron_extra_2026_G11", 452.93520, 756.07116),
        ("kompleksowa_tauron_extra_2026_G12", 445.70280, 713.69274),
        ("kompleksowa_tauron_extra_2026_G12w", 463.37790, 717.14289),
        ("kompleksowa_tauron_natura_2026_G11", 474.21174, 777.34770),
        ("kompleksowa_tauron_natura_2026_G12", 467.02362, 735.01356),
        ("kompleksowa_tauron_natura_2026_G12w", 484.64337, 738.40836),
        ("kompleksowa_pge_taryfowy_gtpa_G11", 563.13090, 866.26686),
        ("kompleksowa_pge_taryfowy_gtpa_G12", 538.18650, 806.17644),
        ("kompleksowa_pge_taryfowy_gtpa_G12w", 548.89119, 802.65618),
        ("kompleksowa_energa_podstawowa_2026_G11", 463.69770, 766.83366),
        ("kompleksowa_energa_podstawowa_2026_G12", 483.95580, 751.94574),
        ("kompleksowa_energa_podstawowa_2026_G12w", 461.33979, 715.10478),
    ):
        s = w.scenariusze[klucz]
        assert s.sprzedaz_przed == pytest.approx(brutto) and s.razem == pytest.approx(razem) and s.tarcza == 0.0, klucz


def test_policz_obecna_g12sezon():
    k = zbuduj_konfiguracje({"uklad": "3f", "preset": "enea_2026", "taryfa": "G12sezON"}, {})
    w = policz(wrzesien(), date(2026,9,1), date(2026,9,30), k)
    assert w.obecny == "pstryk_G12sezON" and (w.kwh_tanie, w.kwh_drogie) == (300.0, 420.0)


def test_policz_obecna_g11():
    k = zbuduj_konfiguracje({"uklad": "3f", "preset": "enea_2026", "taryfa": "G11", "tanie_g12": [22,23,0,1,2,3,4,5,13,14]}, {})
    w = policz(wrzesien(), date(2026,9,1), date(2026,9,30), k)
    assert w.obecny == "pstryk_G11" and (w.kwh_tanie, w.kwh_drogie) == (720.0, 0.0)

def test_policz_ostrzezenia():
    w = policz(wrzesien(600), date(2026,9,1), date(2026,9,30), K)
    assert "pokrycie_ponizej_95" in w.scenariusze["pstryk_G12"].ostrzezenia
    d = policz(wrzesien(), date(2026,9,2), date(2026,9,2), K)
    assert "okres_krotszy_niz_miesiac" in d.scenariusze["pstryk_G12"].ostrzezenia and d.pokrycie == 1.0


def test_policz_pusty_okres():
    w = policz([], date(2026,1,1), date(2026,1,31), K)
    assert w.pokrycie == 0.0 and w.scenariusze["pstryk_G12"].razem == 0.0


def test_stawki_spoza_roku():
    r = [HourlyReading(datetime(2025,12,10,0,tzinfo=TZ), 1.0, 0.5, 0.08, 0.005)]
    assert "stawki_spoza_roku:2026" in policz(r, date(2025,12,10), date(2025,12,10), K).scenariusze["pstryk_G12"].ostrzezenia
