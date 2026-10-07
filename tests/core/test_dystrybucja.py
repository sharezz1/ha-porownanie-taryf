from datetime import datetime

import pytest

from custom_components.porownanie_taryf.core import TZ
from custom_components.porownanie_taryf.core.dystrybucja import WynikDystrybucji, dystrybucja, udzial_miesiecy
from custom_components.porownanie_taryf.core.presety import stawki_enea_2026
from custom_components.porownanie_taryf.core.strefy import TANIE_G12_DOMYSLNE
from tests.dane import godziny, wrzesien

S = stawki_enea_2026("3f")


@pytest.mark.parametrize("taryfa,strefy,netto,brutto", [
    ("G11", {"calodobowa": 720}, 246.452, 303.13596),
    ("G12", {"noc": 300, "dzien": 420}, 217.878, 267.98994),
    ("G12w", {"pozaszczyt": 390, "szczyt": 330}, 206.313, 253.76499),
    ("G12sezON", {"pozostale": 420, "zalecana": 300}, 217.878, 267.98994),
    ("G13active", {"pozostale": 270, "ograniczanie": 270, "pobor": 180}, 235.086, 289.15578)])
def test_pelny_wrzesien(taryfa, strefy, netto, brutto):
    w = dystrybucja(wrzesien(), taryfa, S, TANIE_G12_DOMYSLNE, 0.23)
    assert w.kwh_na_strefe == pytest.approx(strefy) and w.netto == pytest.approx(netto) and w.brutto == pytest.approx(brutto)


def test_pol_miesiaca_polowa_oplat_stalych():
    assert dystrybucja(wrzesien(360), "G12", S, TANIE_G12_DOMYSLNE, 0.23).netto == pytest.approx(108.939)


def test_pusta_lista():
    assert dystrybucja([], "G12", S, TANIE_G12_DOMYSLNE, 0.23) == WynikDystrybucji(0.0, 0.0, {"dzien": 0.0, "noc": 0.0})


@pytest.mark.parametrize("mies,godzin", [(3, 743), (10, 745)])
def test_udzial_stalych_dokladnie_1_w_miesiacu_z_dst(mies, godzin):
    assert udzial_miesiecy(godziny(datetime(2026, mies, 1, tzinfo=TZ), godzin)) == pytest.approx(1.0)
