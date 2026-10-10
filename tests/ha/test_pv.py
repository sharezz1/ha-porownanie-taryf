import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.porownanie_taryf.const import DOMAIN
from custom_components.porownanie_taryf.sources.dach import Punkt
from custom_components.porownanie_taryf.sources.rce import API_URL as RCE_API, parsuj_rce
from tests.dane import okno_potem_503, wrzesien

from .common import DATA_WPISU, zapisz_magazyn

POBIERZ = "custom_components.porownanie_taryf.sources.pstryk.PstrykClient.pobierz"


@pytest.fixture(autouse=True)
def _zegar(freezer):
    freezer.move_to(datetime(2026, 10, 9, 12, tzinfo=timezone.utc))


@pytest.fixture(autouse=True)
def _pobierz():
    with patch(POBIERZ, new_callable=AsyncMock, return_value=[]):
        yield


async def _wpis(hass, hass_storage, cache=None):
    e = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU, title="Porównanie taryf")
    e.add_to_hass(hass)
    zapisz_magazyn(hass_storage, e.entry_id, wrzesien())
    if cache is not None:
        klucz = f"{DOMAIN}.{e.entry_id}.pv_cache"
        hass_storage[klucz] = {"version": 1, "minor_version": 1, "key": klucz, "data": cache}
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    return e


async def test_konfig_domyslny_i_zapis(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id})
    r = await ws.receive_json()
    assert r["success"] and r["result"]["schema"] == 1 and r["result"]["koszt_kwp"] == 3000
    k = r["result"] | {"polacie": [{"az": 226, "nachylenie": 40, "kwp_max": 8, "cien": 0, "panele": True}]}
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id, "konfig": k})
    r = await ws.receive_json()
    assert r["success"] and r["result"]["polacie"][0]["az"] == 226
    assert hass_storage[f"{DOMAIN}.{e.entry_id}.pv"]["data"]["polacie"][0]["kwp_max"] == 8


async def test_walidacja(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id})
    k = (await ws.receive_json())["result"] | {"polacie": [{"az": 226, "nachylenie": 80, "kwp_max": 8, "cien": 0, "panele": True}]}
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id, "konfig": k})
    r = await ws.receive_json()
    assert not r["success"] and r["error"]["code"] == "invalid_format"


async def test_not_loaded(hass, hass_storage, hass_ws_client):
    await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": "nie-ma"})
    r = await ws.receive_json()
    assert not r["success"] and r["error"]["code"] == "not_loaded"


async def test_zapis_tylko_admin(hass, hass_storage, hass_ws_client, hass_read_only_access_token):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass, hass_read_only_access_token)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id})
    assert (await ws.receive_json())["success"]  # odczyt wolno
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id, "konfig": {}})
    assert (await ws.receive_json())["error"]["code"] == "unauthorized"
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach", "entry_id": e.entry_id, "adres": "Xyz 1"})
    assert (await ws.receive_json())["error"]["code"] == "unauthorized"


async def test_dach_adres_nieznaleziony_i_ok(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    with patch("custom_components.porownanie_taryf.pv.geokoduj", AsyncMock(return_value=None)):
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach", "entry_id": e.entry_id, "adres": "Xyz 999"})
        assert (await ws.receive_json())["error"]["code"] == "adres_nieznaleziony"
    p = Punkt("Warszawa, Marszałkowska 1", 638027.0, 485065.0, 52.23, 21.01)
    with patch("custom_components.porownanie_taryf.pv.geokoduj", AsyncMock(return_value=p)), \
         patch("custom_components.porownanie_taryf.pv.pobierz_nmpt", AsyncMock(return_value=None)):
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach", "entry_id": e.entry_id, "adres": p.adres})
        r = await ws.receive_json()
        assert r["success"] and r["result"]["e"] == 638027.0 and r["result"]["polacie_nmpt"] is None
        await hass.async_block_till_done()
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach_status", "entry_id": e.entry_id, "e": p.e, "n": p.n})
        r = await ws.receive_json()
        assert r["result"] == {"polacie_nmpt": [], "nmpt_blad": "niedostepny"}


async def test_wyniki_brak_konfigu(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": e.entry_id})
    r = await ws.receive_json()
    assert r["success"] and r["result"] == {"schema": 1, "stan": "brak_konfigu"}


async def test_remove_czysci_store(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id})
    k = (await ws.receive_json())["result"]
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id, "konfig": k})
    await ws.receive_json()
    assert f"{DOMAIN}.{e.entry_id}.pv_cache" in hass_storage
    await hass.config_entries.async_remove(e.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{e.entry_id}.pv" not in hass_storage
    assert f"{DOMAIN}.{e.entry_id}.pv_cache" not in hass_storage


async def test_wyniki_wynik_i_pogoda_z_cache(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id})
    k = (await ws.receive_json())["result"] | {
        "lat": 52.23, "lon": 21.01,
        "polacie": [{"az": 226, "nachylenie": 40, "kwp_max": 8, "cien": 0, "panele": True}]}
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id, "konfig": k})
    assert (await ws.receive_json())["success"]
    gti = AsyncMock(return_value={"2026-09-15T10:00:00Z": (500.0, 15.0)})
    rce = AsyncMock(return_value={"2026-09-15T10:00:00Z": 300.0})
    with patch("custom_components.porownanie_taryf.pv.pobierz_gti", gti), patch("custom_components.porownanie_taryf.pv.pobierz_rce", rce):
        for _ in range(2):
            await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": e.entry_id})
            r = await ws.receive_json()
            assert r["success"] and r["result"]["schema"] == 1
    assert gti.await_count == 1 and rce.await_count == 1
    # zapis konfigu unieważnia wynik, ale GTI z tego samego dnia zostaje w cache (gti_pobrano)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id, "konfig": k | {"koszt_kwp": 3500}})
    assert (await ws.receive_json())["success"]
    with patch("custom_components.porownanie_taryf.pv.pobierz_gti", gti), patch("custom_components.porownanie_taryf.pv.pobierz_rce", rce):
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": e.entry_id})
        assert (await ws.receive_json())["success"]
    assert gti.await_count == 1


GTI = "custom_components.porownanie_taryf.pv.pobierz_gti"
RCE = "custom_components.porownanie_taryf.pv.pobierz_rce"
NMPT = "custom_components.porownanie_taryf.pv.pobierz_nmpt"
GEO = "custom_components.porownanie_taryf.pv.geokoduj"
PUNKT = Punkt("Warszawa, Marszałkowska 1", 638027.0, 485065.0, 52.23, 21.01)
POLAC = {"az": 226, "nachylenie": 40, "kwp_max": 8, "cien": 0, "panele": True}


async def _konfig(ws, wpis, **zmiany):
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": wpis.entry_id})
    k = (await ws.receive_json())["result"] | zmiany
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": wpis.entry_id, "konfig": k})
    r = await ws.receive_json()
    assert r["success"], r
    return k


async def _wyniki(ws, e):
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": e.entry_id})
    return (await ws.receive_json())["result"]


async def test_rce_blad_drugiego_okna_zachowuje_pierwsze(hass, hass_storage, hass_ws_client, aioclient_mock):
    fix = json.loads((Path(__file__).parent.parent / "fixtures" / "rce_2026-06-15.json").read_text())
    aioclient_mock.get(RCE_API, side_effect=okno_potem_503(fix))
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await _konfig(ws, e, lat=52.23, lon=21.01, polacie=[POLAC])
    with patch(GTI, AsyncMock(return_value={"2026-09-15T10:00:00Z": (500.0, 15.0)})):
        await _wyniki(ws, e)
    assert aioclient_mock.call_count == 2  # drugie okno 503 przerywa
    assert set(hass_storage[f"{DOMAIN}.{e.entry_id}.pv_cache"]["data"]["rce"]) == set(parsuj_rce(fix))


async def test_nmpt_wyjatek_nie_zostawia_trwa(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    with patch(GEO, AsyncMock(return_value=PUNKT)), patch(NMPT, AsyncMock(side_effect=IndexError)):
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach", "entry_id": e.entry_id, "adres": PUNKT.adres})
        assert (await ws.receive_json())["success"]
        await hass.async_block_till_done()
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach_status", "entry_id": e.entry_id, "e": PUNKT.e, "n": PUNKT.n})
        assert (await ws.receive_json())["result"] == {"polacie_nmpt": [], "nmpt_blad": "niedostepny"}


async def test_dach_status_nieznany_punkt_to_niedostepny_a_trwajace_zadanie_to_trwa(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    status = {"type": "porownanie_taryf/pv/dach_status", "entry_id": e.entry_id, "e": PUNKT.e, "n": PUNKT.n}
    await ws.send_json_auto_id(status)
    assert (await ws.receive_json())["result"] == {"polacie_nmpt": [], "nmpt_blad": "niedostepny"}
    koniec = asyncio.Event()

    async def wolno(*_):
        await koniec.wait()

    with patch(GEO, AsyncMock(return_value=PUNKT)), patch(NMPT, wolno):
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach", "entry_id": e.entry_id, "adres": PUNKT.adres})
        assert (await ws.receive_json())["success"]
        await ws.send_json_auto_id(status)
        assert (await ws.receive_json())["result"] == {"polacie_nmpt": None, "nmpt_blad": None}
        koniec.set()
        await hass.async_block_till_done()


async def test_nmpt_trwa_z_dysku_jest_porzucane(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage, cache={"gti": {}, "gti_pobrano": {}, "rce": {}, "nmpt": {"638027,485065": None}})
    ws = await hass_ws_client(hass)
    nmpt = AsyncMock(return_value=None)
    with patch(GEO, AsyncMock(return_value=PUNKT)), patch(NMPT, nmpt):
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach", "entry_id": e.entry_id, "adres": PUNKT.adres})
        assert (await ws.receive_json())["success"]
        await hass.async_block_till_done()
    assert nmpt.await_count == 1


async def test_usun_lokalizacje_czysci_wspolrzedne(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    k = await _konfig(ws, e, lat=52.23, lon=21.01, e=638027.0, n=485065.0, polacie=[POLAC])
    with patch(GTI, AsyncMock(return_value={"2026-09-15T10:00:00Z": (500.0, 15.0)})), patch(RCE, AsyncMock(return_value={})):
        await _wyniki(ws, e)
    assert hass_storage[f"{DOMAIN}.{e.entry_id}.pv_cache"]["data"]["gti_pobrano"]
    await _konfig(ws, e, lat=None, lon=None, e=None, n=None, polacie=[], adres=None)
    c = hass_storage[f"{DOMAIN}.{e.entry_id}.pv_cache"]["data"]
    assert c["gti"] == {} and c["gti_pobrano"] == {} and c["nmpt"] == {}


async def test_rce_poza_oknem_przycinane(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage, cache={"gti": {}, "gti_pobrano": {}, "nmpt": {},
                                               "rce": {"2020-01-01T10:00:00Z": 100.0}})
    ws = await hass_ws_client(hass)
    await _konfig(ws, e, lat=52.23, lon=21.01, polacie=[POLAC])
    with patch(GTI, AsyncMock(return_value={"2026-09-15T10:00:00Z": (500.0, 15.0)})), \
         patch(RCE, AsyncMock(return_value={"2026-09-15T10:00:00Z": 300.0})):
        await _wyniki(ws, e)
    assert list(hass_storage[f"{DOMAIN}.{e.entry_id}.pv_cache"]["data"]["rce"]) == ["2026-09-15T10:00:00Z"]


async def test_brak_pogody_nie_jest_cache_owany(hass, hass_storage, hass_ws_client):
    from custom_components.porownanie_taryf.sources.pogoda import PogodaError

    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await _konfig(ws, e, lat=52.23, lon=21.01, polacie=[POLAC])
    gti = AsyncMock(side_effect=[PogodaError("x"), {"2026-09-15T10:00:00Z": (500.0, 15.0)}])
    with patch(GTI, gti), patch(RCE, AsyncMock(return_value={"2026-09-15T10:00:00Z": 300.0})):
        assert (await _wyniki(ws, e))["stan"] == "brak_pogody"
        assert (await _wyniki(ws, e))["stan"] != "brak_pogody"
    assert gti.await_count == 2


async def test_rownolegle_wyniki_jedno_pobranie(hass, hass_storage, hass_ws_client):
    import asyncio

    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await _konfig(ws, e, lat=52.23, lon=21.01, polacie=[POLAC])

    async def wolne(*a, **kw):
        for _ in range(20):  # sleep(t) wisi przy zamrożonym zegarze
            await asyncio.sleep(0)
        return {"2026-09-15T10:00:00Z": (500.0, 15.0)}

    gti = AsyncMock(side_effect=wolne)
    with patch(GTI, gti), patch(RCE, AsyncMock(return_value={"2026-09-15T10:00:00Z": 300.0})):
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": e.entry_id})
        await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": e.entry_id})
        assert (await ws.receive_json())["success"] and (await ws.receive_json())["success"]
    assert gti.await_count == 1


@pytest.mark.parametrize("zmiany", [
    {"lat": 91.0, "lon": 10.0}, {"lat": 53.0, "lon": None}, {"lat": None, "lon": 17.0}, {"e": 2_000_000.0},
])
async def test_walidacja_wspolrzednych(hass, hass_storage, hass_ws_client, zmiany):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id})
    k = (await ws.receive_json())["result"] | zmiany
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/konfig", "entry_id": e.entry_id, "konfig": k})
    r = await ws.receive_json()
    assert not r["success"] and r["error"]["code"] == "invalid_format"


@pytest.mark.parametrize("msg", [{}, {"lat": 53.0}, {"lat": 53.0, "lon": 200.0}])
async def test_dach_wymaga_adresu_lub_pary(hass, hass_storage, hass_ws_client, msg):
    e = await _wpis(hass, hass_storage)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/dach", "entry_id": e.entry_id} | msg)
    assert (await ws.receive_json())["error"]["code"] == "invalid_format"


async def test_not_loaded_wpis_istnieje(hass, hass_storage, hass_ws_client):
    e = await _wpis(hass, hass_storage)
    await hass.config_entries.async_unload(e.entry_id)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "porownanie_taryf/pv/wyniki", "entry_id": e.entry_id})
    assert (await ws.receive_json())["error"]["code"] == "not_loaded"
