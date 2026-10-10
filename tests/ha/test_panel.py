"""Panel „Porównanie taryf”: rejestracja w pasku bocznym, serwowanie panel.js i sprzątanie z ostatnim wpisem (spec §7a)."""

import hashlib
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.porownanie_taryf import PLIK
from custom_components.porownanie_taryf.const import DOMAIN
from tests.dane import wrzesien

from .common import DATA_WPISU, zapisz_magazyn

POBIERZ = "custom_components.porownanie_taryf.sources.pstryk.PstrykClient.pobierz"
PANELE = "frontend_panels"


@pytest.fixture(autouse=True)
def _zegar(freezer):
    freezer.move_to(datetime(2026, 10, 5, 12, tzinfo=timezone.utc))


@pytest.fixture(autouse=True)
def _pobierz():
    with patch(POBIERZ, new_callable=AsyncMock, return_value=[]):
        yield


def _wpis(hass, hass_storage, api_key="sk-test"):
    e = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU | {"api_key": api_key}, title="Porównanie taryf")
    e.add_to_hass(hass)
    zapisz_magazyn(hass_storage, e.entry_id, wrzesien())
    return e


async def _setup(hass, wpis):
    await hass.config_entries.async_setup(wpis.entry_id)
    await hass.async_block_till_done()


async def test_panel_zarejestrowany(hass, hass_storage):
    await _setup(hass, _wpis(hass, hass_storage))

    p = hass.data[PANELE]["taryfy-pradu"]
    assert p.sidebar_icon == "mdi:scale-balance" and p.require_admin is False
    assert p.config["_panel_custom"]["name"] == "porownanie-taryf-panel"
    url = p.config["_panel_custom"]["module_url"]
    assert re.fullmatch(r"/porownanie_taryf/panel\.js\?v=0\.8\.0-[0-9a-f]{8}", url)
    assert url.endswith(hashlib.sha256(PLIK.read_bytes()).hexdigest()[:8])


async def test_url_modulu_zmienia_sie_z_trescia_pliku(hass, hass_storage, tmp_path):
    inny = tmp_path / "panel.js"
    inny.write_bytes(PLIK.read_bytes() + b"\n// zmiana")
    with patch("custom_components.porownanie_taryf.PLIK", inny):
        await _setup(hass, _wpis(hass, hass_storage))

    url = hass.data[PANELE]["taryfy-pradu"].config["_panel_custom"]["module_url"]
    assert url.endswith(hashlib.sha256(inny.read_bytes()).hexdigest()[:8])
    assert "?v=0.8.0-" in url
    assert not url.endswith(hashlib.sha256(PLIK.read_bytes()).hexdigest()[:8])


@pytest.mark.parametrize("jezyk", ["pl", "pl-PL", "en", "de"])
async def test_tytul_wg_jezyka(hass, hass_storage, jezyk):
    hass.config.language = jezyk
    await _setup(hass, _wpis(hass, hass_storage))

    assert hass.data[PANELE]["taryfy-pradu"].sidebar_title == "Porównanie taryf"


async def test_plik_js_serwowany(hass, hass_client, hass_storage):
    await _setup(hass, _wpis(hass, hass_storage))

    r = await (await hass_client()).get("/porownanie_taryf/panel.js")
    assert r.status == 200 and "porownanie-taryf-panel" in await r.text()


async def test_reload_nie_rzuca_i_panel_zostaje(hass, hass_storage):
    wpis = _wpis(hass, hass_storage)
    await _setup(hass, wpis)

    assert await hass.config_entries.async_reload(wpis.entry_id)
    await hass.async_block_till_done()

    assert wpis.state is ConfigEntryState.LOADED
    assert "taryfy-pradu" in hass.data[PANELE]


async def test_wyladowanie_ostatniego_usuwa_panel(hass, hass_storage):
    wpis = _wpis(hass, hass_storage)
    await _setup(hass, wpis)
    assert "taryfy-pradu" in hass.data[PANELE]

    assert await hass.config_entries.async_unload(wpis.entry_id)

    assert "taryfy-pradu" not in hass.data[PANELE]


async def test_dwa_wpisy_panel_zostaje_po_wyladowaniu_jednego(hass, hass_storage):
    a, b = _wpis(hass, hass_storage, "sk-a"), _wpis(hass, hass_storage, "sk-b")
    await _setup(hass, a)  # setup domeny stawia od razu oba wpisy
    assert a.state is b.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(a.entry_id)
    assert "taryfy-pradu" in hass.data[PANELE]

    assert await hass.config_entries.async_unload(b.entry_id)
    assert "taryfy-pradu" not in hass.data[PANELE]
