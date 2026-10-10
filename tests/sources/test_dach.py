import asyncio
import json
import math
import random
from pathlib import Path

import pytest

from custom_components.porownanie_taryf.sources.dach import (
    UUG_URL,
    WCS_URL,
    Punkt,
    adres_z_lokalizacji,
    geokoduj,
    pobierz_nmpt,
    polacie,
    wczytaj_aaigrid,
)

FIX = Path(__file__).parent.parent / "fixtures"


def dach_dwuspadowy(kalenica=168.0, nachylenie=40.0, krok=0.5, r=16):
    """Sztuczny dach 16 × 9 m na gruncie 68 m; wiersz 0 = północ."""
    a = math.radians(kalenica)
    rnd = random.Random(1)
    n = int(2 * r / krok)
    z = []
    for i in range(n):
        wiersz = []
        for j in range(n):
            e, nn = -r + j * krok, r - i * krok
            wzdluz = e * math.sin(a) + nn * math.cos(a)
            poprz = e * math.cos(a) - nn * math.sin(a)
            h = 68.0
            if abs(wzdluz) < 8 and abs(poprz) < 4.5:
                h += 4 + (4.5 - abs(poprz)) * math.tan(math.radians(nachylenie))
            wiersz.append(h + rnd.gauss(0, 0.05))
        z.append(wiersz)
    return z


def test_sztuczny_dach():
    p = sorted(polacie(dach_dwuspadowy(), 0.5))
    assert len(p) == 2
    assert abs(p[0][0] - 78) <= 3 and abs(p[1][0] - 258) <= 3
    assert all(abs(x[1] - 40) <= 3 for x in p)


def test_plaskie_pole():
    assert polacie([[68.0] * 40 for _ in range(40)], 0.5) == []


def test_wiernosc_z_prototypem_na_prawdziwym_wycinku():
    z, krok = wczytaj_aaigrid((FIX / "nmpt_dach_testowy.asc").read_text(encoding="latin-1"))
    assert krok == 0.5 and len(z) == 80 and len(z[0]) == 80
    p = polacie(z, krok)
    # prototyp energia/dach.py (numpy): [(168, 50, 88), (350, 50, 66)] — port odtwarza go co do piksela
    assert len(p) == 2
    assert all(abs(x[0] - y[0]) <= 1 and abs(x[1] - y[1]) <= 1 for x, y in zip(p, [(168, 50), (350, 50)]))


def test_aaigrid_z_naglowkiem_mime():
    t = "--wcs\nContent-Type: image/x-aaigrid\n\nncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 0.5\n1 2\n3 4\n--wcs\nContent-Type: text/xml\n\n<gml/>\n--wcs--\n"
    assert wczytaj_aaigrid(t) == ([[1.0, 2.0], [3.0, 4.0]], 0.5)


@pytest.fixture
async def sesja(aioclient_mock):
    s = aioclient_mock.create_session(asyncio.get_running_loop())
    yield s
    await s.close()


async def test_geokoduj_dwa_uklady_i_polskie_znaki(aioclient_mock, sesja):
    pl = json.loads((FIX / "uug_adres.json").read_text())
    aioclient_mock.get(UUG_URL, json=pl)
    p = await geokoduj(sesja, "Warszawa, Marszałkowska 1")
    assert isinstance(p, Punkt) and aioclient_mock.call_count == 2
    assert "Marsza%C5%82kowska" in str(aioclient_mock.mock_calls[0][1]) or "Marszałkowska" in str(aioclient_mock.mock_calls[0][1])


async def test_geokoduj_brak(aioclient_mock, sesja):
    aioclient_mock.get(UUG_URL, json={"results": None, "returned objects": 0})
    assert await geokoduj(sesja, "Nieistniejąca 999, Xyz") is None


async def test_geokoduj_wspolrzedne_x_wschod(aioclient_mock, sesja):
    aioclient_mock.get(UUG_URL, json={"results": {"1": {"x": "638027.42", "y": "485064.76"}}})
    p = await geokoduj(sesja, "x")
    assert (p.e, p.n) == (638027.42, 485064.76) and (p.lon, p.lat) == (638027.42, 485064.76)  # mock zwraca to samo dla obu srid


async def test_adres_z_lokalizacji(aioclient_mock, sesja):
    aioclient_mock.get(UUG_URL, json={"results": {"1": {"city": "Warszawa", "street": "ulica Marszałkowska", "number": "1"}}})
    assert await adres_z_lokalizacji(sesja, 52.2, 21.0) == "Warszawa, ulica Marszałkowska 1"
    aioclient_mock.clear_requests()
    aioclient_mock.get(UUG_URL, json={"results": {"1": {"city": "Wólka", "street": None, "number": "5"}}})
    assert await adres_z_lokalizacji(sesja, 52.2, 21.0) == "Wólka 5"
    aioclient_mock.clear_requests()
    aioclient_mock.get(UUG_URL, json={"results": None})
    assert await adres_z_lokalizacji(sesja, 52.2, 21.0) is None


async def test_pobierz_nmpt_x_to_wschod(aioclient_mock, sesja):
    tekst = "--wcs\nContent-Type: image/x-aaigrid\n\nncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 0.5\n1 2\n3 4\n--wcs--\n"
    aioclient_mock.get(WCS_URL, text=tekst)
    assert await pobierz_nmpt(sesja, 500000.4, 300000.6) == ([[1.0, 2.0], [3.0, 4.0]], 0.5)
    url = str(aioclient_mock.mock_calls[0][1])
    assert "COVERAGEID=DSM_PL-KRON86-NH" in url
    assert "x%28499980%2C500020%29" in url or "x(499980,500020)" in url
    assert "y%28299981%2C300021%29" in url or "y(299981,300021)" in url


async def test_pobierz_nmpt_limit_czasu(aioclient_mock, sesja):
    assert await pobierz_nmpt(sesja, 1.0, 1.0, limit_s=0) is None
    assert aioclient_mock.call_count == 0
