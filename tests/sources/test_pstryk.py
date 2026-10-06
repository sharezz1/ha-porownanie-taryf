import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.sources.pstryk import (
    API_URL,
    PstrykAuthError,
    PstrykClient,
    PstrykConnectionError,
    PstrykEndpointError,
    PstrykRateLimitError,
    do_magazynu,
    parse_frames,
    z_magazynu,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "pstryk_frames.json"
DZIEN = (datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 2, tzinfo=timezone.utc))


@pytest.fixture
async def klient(aioclient_mock):
    session = aioclient_mock.create_session(asyncio.get_running_loop())
    yield PstrykClient(session, "sk-test")
    await session.close()


def test_parse_frames():
    r = parse_frames(json.loads(FIXTURE.read_text()))
    assert len(r) == 2
    assert r[0] == HourlyReading(datetime(2026, 9, 1, 2, tzinfo=TZ), 1.5, 0.75, 0.12, 0.0075)  # 00:00Z = 02:00 CEST
    assert r[1].kwh == 0.5 and r[1].energy_net is None


def test_magazyn_w_obie_strony():
    r = parse_frames(json.loads(FIXTURE.read_text()))
    d = do_magazynu(r)
    assert list(d) == ["2026-09-01T00:00:00Z", "2026-09-01T01:00:00Z"]
    assert z_magazynu(json.loads(json.dumps(d))) == r


async def test_naglowek_bez_bearer_i_okna_90_dni(aioclient_mock, klient):
    aioclient_mock.get(API_URL, json={"frames": []})
    await klient.pobierz(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 7, 20, tzinfo=timezone.utc))  # 200 dni
    assert aioclient_mock.call_count == 3
    _, url, _, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == "sk-test" and "for_tz" not in str(url) and "resolution=hour" in str(url)


async def test_pobierz_parsuje_ramki(aioclient_mock, klient):
    aioclient_mock.get(API_URL, json=json.loads(FIXTURE.read_text()))
    assert len(await klient.pobierz(*DZIEN)) == 2


@pytest.mark.parametrize(
    "status,exc",
    [
        (401, PstrykAuthError),
        (403, PstrykAuthError),
        (400, PstrykEndpointError),
        (404, PstrykEndpointError),
        (500, PstrykConnectionError),
    ],
)
async def test_mapowanie_bledow(aioclient_mock, klient, status, exc):
    aioclient_mock.get(API_URL, status=status)
    with pytest.raises(exc):
        await klient.pobierz(*DZIEN)


@pytest.mark.parametrize("blad", [aiohttp.ClientError(), TimeoutError()])
async def test_blad_sieci(aioclient_mock, klient, blad):
    aioclient_mock.get(API_URL, exc=blad)
    with pytest.raises(PstrykConnectionError):
        await klient.pobierz(*DZIEN)


async def test_429_retry_after(aioclient_mock, klient):
    aioclient_mock.get(API_URL, status=429, headers={"Retry-After": "120"})
    with pytest.raises(PstrykRateLimitError) as e:
        await klient.pobierz(*DZIEN)
    assert e.value.retry_after == 120


async def test_429_domyslny_retry_after(aioclient_mock, klient):
    aioclient_mock.get(API_URL, status=429)
    with pytest.raises(PstrykRateLimitError) as e:
        await klient.pobierz(*DZIEN)
    assert e.value.retry_after == 60


@pytest.mark.parametrize(
    "tresc",
    [
        {},  # brak "frames"
        [],  # nie obiekt
        {"frames": [{"metrics": {"meter_values": {"energy_active_import_register": 1.0}}}]},  # ramka bez "start"
        {"frames": [{"start": "nie-data", "metrics": {"meter_values": {"energy_active_import_register": 1.0}}}]},
        {"frames": ["x"]},  # ramka nie jest obiektem
    ],
)
async def test_zmieniony_ksztalt_odpowiedzi_to_blad_endpointu(aioclient_mock, klient, tresc):
    aioclient_mock.get(API_URL, json=tresc)
    with pytest.raises(PstrykEndpointError):
        await klient.pobierz(*DZIEN)
