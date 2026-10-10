import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from tests.dane import okno_potem_503
from custom_components.porownanie_taryf.sources.rce import API_URL, RceError, parsuj_rce, pobierz_rce

FIX = json.loads((Path(__file__).parent.parent / "fixtures" / "rce_2026-06-15.json").read_text())


def test_kwadranse_do_godzin_dtime_utc_to_koniec():
    g = parsuj_rce(FIX)
    assert len(g) == 24
    # doba 2026-06-15 lokalnie (CEST) = 2026-06-14T22:00Z .. 2026-06-15T21:00Z
    assert min(g) == "2026-06-14T22:00:00Z" and max(g) == "2026-06-15T21:00:00Z"
    pierwsze4 = [x["rce_pln"] for x in FIX["value"] if x["dtime_utc"] in (
        "2026-06-14 22:15:00", "2026-06-14 22:30:00", "2026-06-14 22:45:00", "2026-06-14 23:00:00")]
    assert len(pierwsze4) == 4
    assert g["2026-06-14T22:00:00Z"] == pytest.approx(sum(pierwsze4) / 4 / 1000)


def test_okres_godzinowy_sprzed_x_2025():
    p = {"value": [{"dtime_utc": "2025-06-14 23:00:00", "rce_pln": 400.0}]}
    assert parsuj_rce(p) == {"2025-06-14T22:00:00Z": 0.4}


def test_ujemne_zostaja():
    p = {"value": [{"dtime_utc": "2026-06-15 11:15:00", "rce_pln": -20.0}]}
    assert parsuj_rce(p)["2026-06-15T11:00:00Z"] == pytest.approx(-0.02)


@pytest.fixture
async def sesja(aioclient_mock):
    s = aioclient_mock.create_session(asyncio.get_running_loop())
    yield s
    await s.close()


async def test_okna_po_10_dni(aioclient_mock, sesja):
    aioclient_mock.get(API_URL, json=FIX)
    await pobierz_rce(sesja, date(2026, 6, 1), date(2026, 6, 25))  # 25 dni -> 3 okna
    assert aioclient_mock.call_count == 3


@pytest.mark.parametrize("cialo", [{"value": [{"dtime_utc": "2026-06-15 11:15:00", "rce_pln": None}]}, [1, 2], {"value": [{"dtime_utc": None, "rce_pln": 1}]}])
async def test_zle_cialo_to_blad_modulu(aioclient_mock, sesja, cialo):
    aioclient_mock.get(API_URL, json=cialo)
    with pytest.raises(RceError):
        await pobierz_rce(sesja, date(2026, 6, 1), date(2026, 6, 2))


async def test_udane_okna_zostaja_w_akumulatorze_gdy_pozniejsze_pada(aioclient_mock, sesja):
    aioclient_mock.get(API_URL, side_effect=okno_potem_503(FIX))
    zebrane: dict = {}
    with pytest.raises(RceError):
        await pobierz_rce(sesja, date(2026, 6, 1), date(2026, 6, 25), zebrane)
    assert zebrane == parsuj_rce(FIX)


async def test_blad_http(aioclient_mock, sesja):
    aioclient_mock.get(API_URL, status=503)
    with pytest.raises(RceError):
        await pobierz_rce(sesja, date(2026, 6, 1), date(2026, 6, 2))
