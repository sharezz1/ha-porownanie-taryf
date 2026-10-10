import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from custom_components.porownanie_taryf.sources.pogoda import API_URL, PogodaError, parsuj_gti, pobierz_gti

FIX = json.loads((Path(__file__).parent.parent / "fixtures" / "openmeteo_warszawa.json").read_text())


def test_przesuniecie_minus_godzina():
    g = parsuj_gti(FIX)
    h = FIX["hourly"]
    i = h["time"].index("2026-06-15T12:00")
    # etykieta 12:00 = średnia 11:00–12:00 -> godzina startująca 11:00
    assert g["2026-06-15T11:00:00Z"] == (h["global_tilted_irradiance"][i], h["temperature_2m"][i])
    assert "2026-06-14T23:00:00Z" in g  # etykieta 00:00 pierwszego dnia


def test_null_pomijany():
    p = {"hourly": {"time": ["2026-10-08T12:00"], "global_tilted_irradiance": [None], "temperature_2m": [10.0]}}
    assert parsuj_gti(p) == {}


@pytest.fixture
async def sesja(aioclient_mock):
    s = aioclient_mock.create_session(asyncio.get_running_loop())
    yield s
    await s.close()


async def test_parametry_zapytania(aioclient_mock, sesja):
    aioclient_mock.get(API_URL, json=FIX)
    await pobierz_gti(sesja, 52.23, 21.01, 40, 46, date(2026, 6, 15), date(2026, 6, 16))
    _, url, _, _ = aioclient_mock.mock_calls[0]
    q = str(url)
    assert "tilt=40" in q and "azimuth=46" in q and "timezone=GMT" in q and "global_tilted_irradiance" in q


@pytest.mark.parametrize("cialo", [[1], {"hourly": {"time": ["2026-06-15T10:00"], "global_tilted_irradiance": None, "temperature_2m": [1]}}])
async def test_zle_cialo_to_blad_modulu(aioclient_mock, sesja, cialo):
    aioclient_mock.get(API_URL, json=cialo)
    with pytest.raises(PogodaError):
        await pobierz_gti(sesja, 52.23, 21.01, 40, 0, date(2026, 6, 15), date(2026, 6, 16))


async def test_blad(aioclient_mock, sesja):
    aioclient_mock.get(API_URL, status=429)
    with pytest.raises(PogodaError):
        await pobierz_gti(sesja, 52.23, 21.01, 40, 0, date(2026, 6, 15), date(2026, 6, 16))
