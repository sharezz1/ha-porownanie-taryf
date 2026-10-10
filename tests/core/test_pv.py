from datetime import datetime

import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.core.pv import (
    ParametryPV, Polac, az_open_meteo, klucz_godziny, produkcja, siatka_wariantow,
    skaluj, symuluj, uzupelnij_koszty, wartosc_eksportu, zwrot,
)

P = ParametryPV()


def r(h, kwh, e=0.5, s=0.08, x=0.005, d=1):
    """Odczyt 2026-06-<d> <h>:00 lokalnie, koszty proporcjonalne do kWh."""
    k = lambda v: None if v is None else v * kwh
    return HourlyReading(datetime(2026, 6, d, h, tzinfo=TZ), kwh, k(e), k(s), k(x))


@pytest.mark.parametrize(("az_n", "om"), [(0, -180), (90, -90), (180, 0), (226, 46), (270, 90)])
def test_az_open_meteo(az_n, om):
    assert az_open_meteo(az_n) == om


def test_produkcja_temperatura_i_cien():
    assert produkcja(1000, 25 - 31, 1, 0, P) == pytest.approx(0.85)  # ogniwo dokładnie 25°C
    assert produkcja(1000, -6, 1, 0.5, P) == pytest.approx(0.425)
    assert produkcja(0, 10, 6, 0, P) == 0.0


def test_bilans_energii_i_magazyn_przenosi_na_wieczor():
    odczyty = [r(12, 1.0), r(20, 2.0)]
    pogoda = [{klucz_godziny(odczyty[0]): (900.0, 25.0), klucz_godziny(odczyty[1]): (0.0, 15.0)}]
    s = symuluj(odczyty, pogoda, [Polac(180, 40, 6)], 10, P)
    k0, k1 = (klucz_godziny(o) for o in odczyty)
    po = {klucz_godziny(o): o for o in s.godziny_po}
    for k, o in zip((k0, k1), odczyty):
        assert po[k].kwh + s.autokonsumpcja[k] == pytest.approx(o.kwh)  # pobór + autokonsumpcja = zużycie
        assert s.eksport[k] >= 0
    assert po[k1].kwh < 2.0  # wieczór częściowo z magazynu
    bez = symuluj(odczyty, pogoda, [Polac(180, 40, 6)], 0, P)
    assert {klucz_godziny(o): o.kwh for o in bez.godziny_po}[k1] == 2.0


def test_godzina_bez_gti_zostaje_bez_zmian_i_bez_produkcji():
    o = r(12, 1.0)
    s = symuluj([o], [{}], [Polac(180, 40, 6)], 0, P)
    assert s.godziny_po == [o] and s.produkcja == {}


def test_produkcja_bierze_serie_swojej_polaci():
    o = r(12, 0.0)
    k = klucz_godziny(o)
    sw = {k: (800.0, 20.0)}
    ne = {k: (100.0, 20.0)}
    a = symuluj([o], [sw, ne], [Polac(226, 40, 6), Polac(46, 40, 0)], 0, P).produkcja[k]
    b = symuluj([o], [sw, ne], [Polac(226, 40, 0), Polac(46, 40, 6)], 0, P).produkcja[k]
    assert a > 5 * b  # odwrócenie połaci zmienia wynik


def test_skaluj_kwh_zero_bez_zmian_i_proporcja():
    z = r(3, 0.0)
    assert skaluj(z, 0.0) == z
    o = skaluj(r(12, 2.0), 0.5)
    assert (o.kwh, o.energy_net, o.service_net, o.excise) == pytest.approx((0.5, 0.25, 0.04, 0.0025))


def test_uzupelnij_koszty_srednia_miesiaca():
    odczyty = [r(10, 1.0), r(11, 2.0, e=None)]
    out, flaga = uzupelnij_koszty(odczyty)
    assert flaga and out[1].energy_net == pytest.approx(1.0)  # 0,5 zł/kWh × 2 kWh
    assert uzupelnij_koszty([r(10, 1.0)]) == ([r(10, 1.0)], False)


@pytest.mark.parametrize(("kmax", "rozmiary"), [(8, [4, 6, 8]), (9.5, [5, 7, 9.5]), (6, [3, 4.5, 6]), (3, [2.5, 3]), (2, [2])])
def test_siatka(kmax, rozmiary):
    w = siatka_wariantow([Polac(226, 40, kmax)])
    assert sorted({sum(p.kwp for p in pol) for pol, _ in w}) == pytest.approx(rozmiary)
    assert {m for _, m in w} == {0, 5, 10}


def test_siatka_dzieli_proporcjonalnie_i_pusta():
    (pol, _), *_ = [x for x in siatka_wariantow([Polac(226, 40, 6), Polac(46, 40, 2)]) if sum(p.kwp for p in x[0]) == 8]
    assert [p.kwp for p in pol] == pytest.approx([6, 2])
    assert siatka_wariantow([Polac(226, 40, 0)]) == []


def test_wartosc_eksportu_godzinowo():
    k1, k2 = "2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"
    w, brak = wartosc_eksportu({k1: 10, k2: 10}, {k1: 0.2, k2: -0.1})
    assert w["2026-06"] == pytest.approx(10 * 0.2 * 1.23) and not brak  # ujemna cena godziny -> 0
    w, _ = wartosc_eksportu({k1: 10}, {k1: -0.3})
    assert w["2026-06"] == 0.0
    _, brak = wartosc_eksportu({k1: 10}, {})
    assert brak


def test_zwrot_i_wymiany():
    lata, bilans = zwrot(18000, 0, 3000, ParametryPV(wzrost_cen=0, degradacja=0))
    assert lata == 6 and bilans == pytest.approx(20 * 3000 - 18000 - 0.10 * 18000)
    lata, _ = zwrot(18000, 10000, 500, ParametryPV(wzrost_cen=0, degradacja=0))
    assert lata is None
