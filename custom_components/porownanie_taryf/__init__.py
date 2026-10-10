"""Porównanie taryf energii elektrycznej."""

import asyncio
import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from . import pv
from .const import DOMAIN, PANEL_JS, PANEL_KOMPONENT, PANEL_URL
from .coordinator import ISSUE_ENDPOINT, TaryfyConfigEntry, TaryfyCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.DATE]
KLUCZ_STATYK = "panel_statyczny"
KLUCZ_BLOKADY = "panel_blokada"
PLIK = Path(__file__).parent / "frontend" / "panel.js"


async def _zarejestruj_panel(hass: HomeAssistant) -> None:
    """Panel w pasku bocznym; idempotentna: reload i drugi wpis nie rejestrują go ponownie."""
    stan = hass.data.setdefault(DOMAIN, {})
    # wpisy startują równolegle, a poniżej są awaity: bez blokady oba przeszłyby sprawdzenie przed rejestracją
    async with stan.setdefault(KLUCZ_BLOKADY, asyncio.Lock()):
        if PANEL_URL in hass.data.get(frontend.DATA_PANELS, {}):
            return
        if not stan.get(KLUCZ_STATYK):  # trasy aiohttp nie da się wyrejestrować, a reload woła setup ponownie
            await hass.http.async_register_static_paths([StaticPathConfig(PANEL_JS, str(PLIK), cache_headers=False)])
            stan[KLUCZ_STATYK] = True
        wersja = (await async_get_integration(hass, DOMAIN)).version
        # skrót treści pliku: przeglądarka pobiera panel.js ponownie po każdej zmianie, także bez podbicia wersji
        skrot = await hass.async_add_executor_job(lambda: hashlib.sha256(PLIK.read_bytes()).hexdigest()[:8])
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL,
            webcomponent_name=PANEL_KOMPONENT,
            sidebar_title="Porównanie taryf",
            sidebar_icon="mdi:scale-balance",
            module_url=f"{PANEL_JS}?v={wersja}-{skrot}",
            require_admin=False,
        )


async def async_setup_entry(hass: HomeAssistant, entry: TaryfyConfigEntry) -> bool:
    coordinator = TaryfyCoordinator(hass, entry)
    await coordinator.wczytaj_magazyn()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _zarejestruj_panel(hass)
    pv.async_setup(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TaryfyConfigEntry) -> bool:
    wyladowano = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    inne_zaladowane = any(
        e.state is ConfigEntryState.LOADED for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id
    )
    if wyladowano and not inne_zaladowane:
        frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
    return wyladowano


async def async_remove_entry(hass: HomeAssistant, entry: TaryfyConfigEntry) -> None:
    """Sprząta po usuniętym wpisie: magazyn godzin (klucz jak w coordinatorze) i Repair o endpoincie."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.hourly").async_remove()
    await pv.async_remove(hass, entry)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_ENDPOINT)
