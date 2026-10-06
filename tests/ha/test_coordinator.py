"""Coordinator: magazyn godzin, odświeżanie z API Pstryk i obsługa błędów (spec §6)."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.porownanie_taryf.const import DOMAIN
from custom_components.porownanie_taryf.coordinator import ODSWIEZANIE
from custom_components.porownanie_taryf.sources.pstryk import (
    PstrykAuthError,
    PstrykConnectionError,
    PstrykEndpointError,
    PstrykError,
    PstrykRateLimitError,
)
from tests.dane import godziny, wrzesien

from .common import DATA_WPISU, zapisz_magazyn

TERAZ = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
POBIERZ = "custom_components.porownanie_taryf.sources.pstryk.PstrykClient.pobierz"
KLUCZ = f"{DOMAIN}.{{}}.hourly"
RAZEM_WRZESIEN = 710.78994  # Pstryk + G12, pełny wrzesień z tests/dane.py


@pytest.fixture(autouse=True)
def _zegar(freezer):
    freezer.move_to(TERAZ)


@pytest.fixture
def wpis(hass):
    e = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU, title="Porównanie taryf")
    e.add_to_hass(hass)
    return e


@pytest.fixture
def pobierz():
    with patch(POBIERZ, new_callable=AsyncMock, return_value=[]) as m:
        yield m


async def _setup(hass, wpis):
    await hass.config_entries.async_setup(wpis.entry_id)
    await hass.async_block_till_done()


async def _za(hass, freezer, czas: timedelta):
    freezer.tick(czas)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_backfill_przy_pustym_magazynie(hass, hass_storage, wpis, pobierz):
    pobierz.return_value = godziny(datetime(2026, 10, 4, tzinfo=timezone.utc), 3)
    await _setup(hass, wpis)

    assert wpis.state is ConfigEntryState.LOADED
    pobierz.assert_awaited_once()
    assert pobierz.call_args.args == (datetime(2026, 10, 5, tzinfo=timezone.utc) - timedelta(days=730), TERAZ)
    dane = hass_storage[KLUCZ.format(wpis.entry_id)]["data"]
    assert sorted(dane["godziny"]) == [f"2026-10-04T0{h}:00:00Z" for h in range(3)]
    assert dane["dane_z"] == TERAZ.isoformat()
    assert wpis.runtime_data.dane_z == TERAZ


async def test_koniec_okna_wyrownany_do_pelnej_godziny(hass, wpis, pobierz, freezer):
    """API zwraca bieżącą, niepełną godzinę, gdy window_end ma minuty."""
    freezer.move_to(datetime(2026, 10, 5, 12, 34, 56, tzinfo=timezone.utc))
    await _setup(hass, wpis)

    assert pobierz.call_args.args[1] == TERAZ  # 12:00:00
    assert wpis.runtime_data.dane_z == datetime(2026, 10, 5, 12, 34, 56, tzinfo=timezone.utc)  # czas faktycznego pobrania


async def test_odswiezenie_od_ostatniej_minus_48h(hass, hass_storage, wpis, pobierz):
    zapisz_magazyn(hass_storage, wpis.entry_id, godziny(datetime(2026, 10, 4, 8, tzinfo=timezone.utc), 3))
    # API zwraca korektę 10:00, nową 11:00 i duplikat 11:00 ze styku okien
    pobierz.return_value = godziny(datetime(2026, 10, 4, 10, tzinfo=timezone.utc), 2, kwh=2.0) * 2
    await _setup(hass, wpis)

    assert pobierz.call_args.args[0] == datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    g = hass_storage[KLUCZ.format(wpis.entry_id)]["data"]["godziny"]
    assert {k: v[0] for k, v in g.items()} == {
        "2026-10-04T08:00:00Z": 1.0,
        "2026-10-04T09:00:00Z": 1.0,
        "2026-10-04T10:00:00Z": 2.0,
        "2026-10-04T11:00:00Z": 2.0,
    }
    assert len(wpis.runtime_data.odczyty) == 4


async def test_auth_uruchamia_reauth(hass, wpis, pobierz):
    pobierz.side_effect = PstrykAuthError("Pstryk HTTP 401")
    await _setup(hass, wpis)

    assert wpis.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [config_entries.SOURCE_REAUTH]


async def test_endpoint_tworzy_repair_i_liczy_z_magazynu(hass, hass_storage, wpis, pobierz):
    zapisz_magazyn(hass_storage, wpis.entry_id, wrzesien())
    pobierz.side_effect = PstrykEndpointError("Pstryk HTTP 404")
    await _setup(hass, wpis)

    assert wpis.state is ConfigEntryState.LOADED
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "endpoint_zmieniony") is not None
    koord = wpis.runtime_data
    assert koord.data.scenariusze["pstryk_G12"].razem == pytest.approx(RAZEM_WRZESIEN)

    pobierz.side_effect = None
    await koord.async_refresh()
    assert issues.async_get_issue(DOMAIN, "endpoint_zmieniony") is None


@pytest.mark.parametrize("blad", [PstrykConnectionError("timeout"), PstrykError("Pstryk HTTP 408")])
async def test_start_offline_z_magazynem(hass, hass_storage, wpis, pobierz, blad):
    zapisz_magazyn(hass_storage, wpis.entry_id, wrzesien(), dane_z="2026-10-01T06:00:00+00:00")
    pobierz.side_effect = blad
    await _setup(hass, wpis)

    assert wpis.state is ConfigEntryState.LOADED
    koord = wpis.runtime_data
    assert koord.data.scenariusze["pstryk_G12"].razem == pytest.approx(RAZEM_WRZESIEN)
    assert koord.dane_z == datetime(2026, 10, 1, 6, tzinfo=timezone.utc)


async def test_start_offline_bez_magazynu(hass, wpis, pobierz):
    pobierz.side_effect = PstrykConnectionError("timeout")
    await _setup(hass, wpis)

    assert wpis.state is ConfigEntryState.SETUP_RETRY


async def test_429_wstrzymuje_do_retry_after(hass, hass_storage, wpis, pobierz, freezer):
    zapisz_magazyn(hass_storage, wpis.entry_id, wrzesien())
    pobierz.side_effect = PstrykRateLimitError(retry_after=30000)
    await _setup(hass, wpis)

    assert wpis.state is ConfigEntryState.LOADED
    koord = wpis.runtime_data
    assert koord.data.scenariusze["pstryk_G12"].razem == pytest.approx(RAZEM_WRZESIEN)
    koord.async_add_listener(Mock())  # zastępuje encje (Task 8): bez słuchaczy coordinator nie planuje odświeżeń
    pobierz.side_effect = None

    await koord.async_refresh()  # ręczne odświeżenie też czeka na Retry-After
    assert pobierz.await_count == 1
    await _za(hass, freezer, timedelta(hours=6))
    assert pobierz.await_count == 1
    await _za(hass, freezer, timedelta(hours=3))
    assert pobierz.await_count == 2


async def test_zmiana_okresu_bez_api(hass, hass_storage, wpis, pobierz):
    zapisz_magazyn(hass_storage, wpis.entry_id, wrzesien())
    await _setup(hass, wpis)
    koord = wpis.runtime_data
    sluchacz = Mock()
    koord.async_add_listener(sluchacz)
    przed = pobierz.await_count

    koord.ustaw_okres(rodzaj="dzien", dzien=date(2026, 9, 2))
    assert pobierz.await_count == przed
    assert koord.data.od == koord.data.do == date(2026, 9, 2)

    koord.ustaw_okres(rodzaj="zakres", koniec=date(2026, 9, 1))
    assert koord.data is None
    assert sluchacz.call_count == 2
    await hass.async_block_till_done()
    assert pobierz.await_count == przed


async def test_zmiana_opcji_przeladowuje(hass, wpis, pobierz):
    await _setup(hass, wpis)
    stary = wpis.runtime_data

    # zmiana opcji przez options flow (OptionsFlowWithReload) przeładowuje wpis
    r = await hass.config_entries.options.async_init(wpis.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "stawki"})
    await hass.config_entries.options.async_configure(r["flow_id"], {"vat": 0.08})
    await hass.async_block_till_done()

    assert wpis.state is ConfigEntryState.LOADED
    assert wpis.runtime_data is not stary
    assert wpis.runtime_data.konf.vat == 0.08


async def test_interwal_wraca_do_normalnego_po_429_i_bledzie(hass, wpis, pobierz, freezer):
    pobierz.side_effect = PstrykRateLimitError(retry_after=100)
    await _setup(hass, wpis)
    koord = wpis.runtime_data
    assert koord.update_interval < ODSWIEZANIE  # krótka przerwa do Retry-After

    freezer.tick(timedelta(seconds=200))
    pobierz.side_effect = PstrykConnectionError("timeout")  # magazyn pusty: UpdateFailed przed ustawieniem interwału
    await koord.async_refresh()

    assert koord.update_interval == ODSWIEZANIE


async def test_usuniecie_wpisu_czysci_magazyn_i_repair(hass, hass_storage, wpis, pobierz):
    pobierz.return_value = godziny(datetime(2026, 10, 4, tzinfo=timezone.utc), 3)
    await _setup(hass, wpis)
    klucz = KLUCZ.format(wpis.entry_id)
    assert klucz in hass_storage
    pobierz.side_effect = PstrykEndpointError("Pstryk HTTP 404")
    await wpis.runtime_data.async_refresh()
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "endpoint_zmieniony") is not None

    await hass.config_entries.async_remove(wpis.entry_id)
    await hass.async_block_till_done()

    assert klucz not in hass_storage
    assert issues.async_get_issue(DOMAIN, "endpoint_zmieniony") is None
