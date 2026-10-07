"""Config flow: klucz Pstryk, reauth i opcje (spec §7). Bez sieci i bez coordinatora."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.porownanie_taryf.const import DOMAIN
from custom_components.porownanie_taryf.core.presety import zbuduj_konfiguracje
from custom_components.porownanie_taryf.sources.pstryk import (
    PstrykAuthError,
    PstrykConnectionError,
    PstrykEndpointError,
    PstrykError,
    PstrykRateLimitError,
)

from .common import DATA_WPISU

POBIERZ = "custom_components.porownanie_taryf.sources.pstryk.PstrykClient.pobierz"
SETUP = "custom_components.porownanie_taryf.async_setup_entry"
TERAZ = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _zegar(freezer):
    freezer.move_to(TERAZ)


@pytest.fixture(autouse=True)
def setup_entry():
    with patch(SETUP, return_value=True) as m:
        yield m


@pytest.fixture
def pobierz():
    with patch(POBIERZ, new_callable=AsyncMock, return_value=[]) as m:
        yield m


def _wpis(hass, **kw):
    e = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU, title="Porównanie taryf", **kw)
    e.add_to_hass(hass)
    return e


async def _user(hass, dane):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["type"] is FlowResultType.FORM and r["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(r["flow_id"], dane)


async def _opcje(hass, wpis, krok, dane):
    r = await hass.config_entries.options.async_init(wpis.entry_id)
    assert r["type"] is FlowResultType.MENU
    assert r["menu_options"] == ["stawki", "tarcza", "cennik"]
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": krok})
    assert r["type"] is FlowResultType.FORM and r["step_id"] == krok
    r = await hass.config_entries.options.async_configure(r["flow_id"], dane)
    # zapis opcji przeładowuje wpis, a przeładowanie w tle rozwiązuje zależności manifestu (http, panel_custom):
    # bez tego teardown anuluje je w trakcie ("Home Assistant is stopping")
    await hass.async_block_till_done()
    return r


def _domyslne(formularz) -> dict:
    return {str(k): k.default() for k in formularz["data_schema"].schema if callable(k.default)}


# --- krok user -------------------------------------------------------------------------


async def test_user_ok(hass, pobierz):
    r = await _user(hass, {"api_key": "sk-test"})  # reszta z domyślnych wartości formularza

    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["title"] == "Porównanie taryf"
    assert r["data"] == DATA_WPISU
    # walidacja: jedna doba, wczoraj 00:00 UTC -> dziś 00:00 UTC
    pobierz.assert_awaited_once_with(datetime(2026, 10, 4, tzinfo=timezone.utc), datetime(2026, 10, 5, tzinfo=timezone.utc))


async def test_user_wlasne_wartosci(hass, pobierz):
    r = await _user(hass, {"api_key": "sk-test", "uklad": "1f", "taryfa": "G12w", "tanie_g12": ["13", "2", "22"]})

    assert r["data"] == {**DATA_WPISU, "uklad": "1f", "taryfa": "G12w", "tanie_g12": [22, 2, 13]}


async def test_user_taryfa_g11(hass, pobierz):
    r = await _user(hass, {"api_key": "sk-test", "taryfa": "G11"})

    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["taryfa"] == "G11"


async def test_user_taryfa_g12sezon(hass, pobierz):
    r = await _user(hass, {"api_key": "sk-test", "taryfa": "G12sezON"})

    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["taryfa"] == "G12sezON"


async def test_user_puste_tanie_g12(hass, pobierz):
    r = await _user(hass, {"api_key": "sk-test", "tanie_g12": []})

    assert r["type"] is FlowResultType.FORM
    assert r["errors"] == {"tanie_g12": "tanie_g12_puste"}
    pobierz.assert_not_awaited()  # błąd pola wychwycony przed zapytaniem do API

    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"api_key": "sk-test", "tanie_g12": ["22"]})
    assert r["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("blad", "kod"),
    [
        (PstrykAuthError("Pstryk HTTP 401"), "invalid_auth"),
        (PstrykConnectionError("timeout"), "cannot_connect"),
        (PstrykEndpointError("Pstryk HTTP 404"), "endpoint_changed"),
        (PstrykRateLimitError(30), "cannot_connect"),
        (PstrykError("Pstryk HTTP 408"), "cannot_connect"),
    ],
)
async def test_user_bledy(hass, pobierz, blad, kod):
    pobierz.side_effect = blad
    r = await _user(hass, {"api_key": "sk-test"})

    assert r["type"] is FlowResultType.FORM
    assert r["errors"] == {"base": kod}

    pobierz.side_effect = None  # formularz nie utknął: ponowna próba przechodzi
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"api_key": "sk-test"})
    assert r["type"] is FlowResultType.CREATE_ENTRY


async def test_duplikat_klucza(hass, pobierz):
    _wpis(hass)
    r = await _user(hass, {"api_key": "sk-test"})

    assert r["type"] is FlowResultType.ABORT
    assert r["reason"] == "already_configured"
    pobierz.assert_not_awaited()


# --- reauth ------------------------------------------------------------------------------


async def test_reauth(hass, pobierz, setup_entry):
    wpis = _wpis(hass)
    r = await wpis.start_reauth_flow(hass)
    assert r["type"] is FlowResultType.FORM and r["step_id"] == "reauth_confirm"

    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"api_key": "sk-nowy"})
    await hass.async_block_till_done()

    assert r["type"] is FlowResultType.ABORT
    assert r["reason"] == "reauth_successful"
    assert wpis.data["api_key"] == "sk-nowy"
    assert wpis.data["taryfa"] == "G12"  # reszta danych nietknięta
    assert setup_entry.await_count == 1  # dokładnie jedno przeładowanie


async def test_reauth_zly_klucz(hass, pobierz):
    wpis = _wpis(hass)
    pobierz.side_effect = PstrykAuthError("Pstryk HTTP 401")
    r = await wpis.start_reauth_flow(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"api_key": "sk-zly"})

    assert r["type"] is FlowResultType.FORM
    assert r["errors"] == {"base": "invalid_auth"}
    assert wpis.data["api_key"] == "sk-test"


# --- opcje: stawki -------------------------------------------------------------------------


async def test_opcje_stawki(hass):
    wpis = _wpis(hass)
    r = await _opcje(hass, wpis, "stawki", {"G12_dzien": 0.30, "vat": 0.23})

    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert wpis.options["vat"] == 0.23
    assert wpis.options["stawki"]["G12_dzien"] == 0.30
    assert wpis.options["stawki"]["G12_noc"] == 0.0913  # reszta domyślna
    assert len(wpis.options["stawki"]) == 20
    assert {"G12sezON_pozostale", "G12sezON_zalecana", "ssv_G12sezON"} <= wpis.options["stawki"].keys()


async def test_opcje_stawki_g11(hass):
    wpis = _wpis(hass)
    r = await hass.config_entries.options.async_init(wpis.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "stawki"})
    domyslne = _domyslne(r)
    assert (domyslne["G11_calodobowa"], domyslne["ssv_G11"]) == (0.2456, 10.41)  # preset Enea 2026, układ 3f

    r = await hass.config_entries.options.async_configure(r["flow_id"], {"G11_calodobowa": 0.25})
    await hass.async_block_till_done()
    assert wpis.options["stawki"]["G11_calodobowa"] == 0.25
    assert wpis.options["stawki"]["ssv_G11"] == 10.41


async def test_opcje_stawki_vat_to_ulamek(hass):
    wpis = _wpis(hass)
    with pytest.raises(InvalidData):  # 23 zamiast 0,23: selektor ma max=1
        await _opcje(hass, wpis, "stawki", {"vat": 23})
    assert "vat" not in wpis.options


async def test_opcje_stawki_formularz_podpowiada_zapisane(hass):
    wpis = _wpis(hass, options={"vat": 0.08, "stawki": {"G12_dzien": 0.30}})
    r = await hass.config_entries.options.async_init(wpis.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "stawki"})

    domyslne = _domyslne(r)
    assert domyslne["vat"] == 0.08
    assert domyslne["G12_dzien"] == 0.30
    assert domyslne["G12_noc"] == 0.0913  # preset Enea 2026, układ 3f
    assert domyslne["ssv_G12"] == 14.56


async def test_opcje_stawki_uklad_1f(hass):
    wpis = MockConfigEntry(domain=DOMAIN, data={**DATA_WPISU, "uklad": "1f"}, title="Porównanie taryf")
    wpis.add_to_hass(hass)
    await _opcje(hass, wpis, "stawki", {})

    assert wpis.options["stawki"]["ssv_G12"] == 9.59


# --- opcje: Tarcza ----------------------------------------------------------------------------


async def test_opcje_tarcza(hass):
    wpis = _wpis(hass)
    r = await _opcje(hass, wpis, "tarcza", {"2026_limit": 0.65})

    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert wpis.options["tarcza"]["2026"]["limit"] == 0.65
    assert wpis.options["tarcza"]["2026"]["od"] == "2026-01-01"
    assert wpis.options["tarcza"] == {
        "2026": {"limit": 0.65, "podstawa": "brutto", "obejmuje_obsluge": True, "od": "2026-01-01", "do": "2026-12-31"},
        "2027": {"limit": 0.5, "podstawa": "netto", "obejmuje_obsluge": False, "od": "2027-01-01", "do": "2027-12-31"},
    }


async def test_opcje_tarcza_wlasne_pola(hass):
    wpis = _wpis(hass)
    await _opcje(
        hass, wpis, "tarcza",
        {"2027_podstawa": "brutto", "2027_obejmuje_obsluge": True, "2027_od": "2027-02-01", "2027_do": "2027-11-30"},
    )

    assert wpis.options["tarcza"]["2027"] == {
        "limit": 0.5, "podstawa": "brutto", "obejmuje_obsluge": True, "od": "2027-02-01", "do": "2027-11-30",
    }


async def test_opcje_tarcza_podstawa_ma_translation_key(hass):
    wpis = _wpis(hass)
    r = await hass.config_entries.options.async_init(wpis.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "tarcza"})

    selektor = next(v for k, v in r["data_schema"].schema.items() if str(k) == "2026_podstawa")
    assert selektor.config["translation_key"] == "podstawa"
    assert list(selektor.config["options"]) == ["brutto", "netto"]


async def test_opcje_tarcza_formularz_podpowiada_zapisane(hass):
    zapisane = {"limit": 0.7, "podstawa": "netto", "obejmuje_obsluge": False, "od": "2026-03-01", "do": "2026-09-30"}
    wpis = _wpis(hass, options={"tarcza": {"2026": zapisane}})
    r = await hass.config_entries.options.async_init(wpis.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "tarcza"})

    domyslne = _domyslne(r)
    assert {k: domyslne[f"2026_{k}"] for k in zapisane} == zapisane
    assert domyslne["2027_limit"] == 0.5  # rok bez zapisanych opcji: preset


# --- opcje: własny cennik -------------------------------------------------------------------


async def test_opcje_cennik_niekompletny(hass):
    wpis = _wpis(hass)
    r = await _opcje(hass, wpis, "cennik", {"G12_dzien": 0.6})

    assert r["type"] is FlowResultType.FORM
    assert r["errors"] == {"base": "cennik_niekompletny"}
    assert "cennik" not in wpis.options


async def test_opcje_cennik_nazwa_bez_cen(hass):
    wpis = _wpis(hass)
    r = await _opcje(hass, wpis, "cennik", {"nazwa": "Enea"})

    assert r["errors"] == {"base": "cennik_niekompletny"}
    assert "cennik" not in wpis.options


async def test_opcje_cennik_ok(hass):
    wpis = _wpis(hass)
    r = await _opcje(hass, wpis, "cennik", {"G12_dzien": 0.6, "G12_noc": 0.4, "nazwa": "Enea", "oplata_mc": 10})

    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert wpis.options["cennik"] == {
        "nazwa": "Enea", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}},
    }


async def test_opcje_cennik_kilka_taryf(hass):
    wpis = _wpis(hass)
    await _opcje(
        hass, wpis, "cennik",
        {"nazwa": "X", "G12_dzien": 0.6, "G12_noc": 0.4, "G13active_ograniczanie": 0.7, "G13active_pozostale": 0.6, "G13active_pobor": 0.3},
    )

    assert wpis.options["cennik"]["ceny"] == {
        "G12": {"dzien": 0.6, "noc": 0.4},
        "G13active": {"ograniczanie": 0.7, "pozostale": 0.6, "pobor": 0.3},
    }


async def test_opcje_cennik_pusta_nazwa_usuwa_cennik(hass):
    istniejacy = {"nazwa": "Enea", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}
    wpis = _wpis(hass, options={"vat": 0.08, "cennik": istniejacy})
    r = await _opcje(hass, wpis, "cennik", {"nazwa": ""})

    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert "cennik" not in wpis.options
    assert wpis.options["vat"] == 0.08


async def test_opcje_cennik_formularz_podpowiada_zapisany(hass):
    istniejacy = {"nazwa": "Enea", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}
    wpis = _wpis(hass, options={"cennik": istniejacy})
    r = await hass.config_entries.options.async_init(wpis.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "cennik"})

    sugestie = {str(k): k.description["suggested_value"] for k in r["data_schema"].schema if k.description}
    assert sugestie == {"nazwa": "Enea", "oplata_mc": 10, "akcyza": 0.005, "G12_dzien": 0.6, "G12_noc": 0.4}


# --- opcje: wspólne ------------------------------------------------------------------------


async def test_opcje_zachowuja_inne_sekcje(hass):
    istniejacy = {"nazwa": "Enea", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}
    wpis = _wpis(hass, options={"cennik": istniejacy})

    await _opcje(hass, wpis, "stawki", {"G12_dzien": 0.30})
    assert wpis.options["cennik"] == istniejacy
    await _opcje(hass, wpis, "tarcza", {"2026_limit": 0.65})
    assert wpis.options["cennik"] == istniejacy
    assert wpis.options["stawki"]["G12_dzien"] == 0.30  # i stawki po zapisie tarczy


async def test_opcje_ksztalt_czyta_zbuduj_konfiguracje(hass):
    wpis = _wpis(hass)
    await _opcje(hass, wpis, "stawki", {"G12_dzien": 0.30, "vat": 0.08})
    await _opcje(hass, wpis, "tarcza", {"2026_limit": 0.65, "2027_od": "2027-02-01"})
    await _opcje(hass, wpis, "cennik", {"nazwa": "Enea", "G12_dzien": 0.6, "G12_noc": 0.4})

    konf = zbuduj_konfiguracje(wpis.data, wpis.options)

    assert konf.vat == 0.08
    assert konf.stawki.zmienne["G12"]["dzien"] == 0.30
    assert konf.tarcza[0].limit == 0.65
    assert konf.tarcza[1].od == date(2027, 2, 1)
    assert konf.cennik.nazwa == "Enea"
    assert konf.cennik.ceny == {"G12": {"dzien": 0.6, "noc": 0.4}}


async def test_opcje_przeladowuja_wpis(hass, setup_entry):
    wpis = _wpis(hass)
    await hass.config_entries.async_setup(wpis.entry_id)
    assert setup_entry.await_count == 1

    await _opcje(hass, wpis, "stawki", {"vat": 0.08})
    await hass.async_block_till_done()

    assert setup_entry.await_count == 2  # OptionsFlowWithReload, bez update listenera
    assert not wpis.update_listeners
