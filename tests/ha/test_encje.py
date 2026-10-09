"""Encje sensor/select/date: wartości z magazynu, wybór okresu bez API, przywracanie (spec §7)."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from custom_components.porownanie_taryf.const import DOMAIN
from custom_components.porownanie_taryf.sources.pstryk import PstrykAuthError
from tests.dane import wrzesien

from .common import DATA_WPISU, zapisz_magazyn

POBIERZ = "custom_components.porownanie_taryf.sources.pstryk.PstrykClient.pobierz"


@pytest.fixture(autouse=True)
def _zegar(freezer):
    freezer.move_to(datetime(2026, 10, 5, 12, tzinfo=timezone.utc))


@pytest.fixture
def wpis(hass, hass_storage):
    e = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU, title="Porównanie taryf")
    e.add_to_hass(hass)
    zapisz_magazyn(hass_storage, e.entry_id, wrzesien())
    return e


@pytest.fixture
def pobierz():
    with patch(POBIERZ, new_callable=AsyncMock, return_value=[]) as m:
        yield m


async def _setup(hass, wpis):
    await hass.config_entries.async_setup(wpis.entry_id)
    await hass.async_block_till_done()


def _eid(hass, wpis, platforma, suffix):
    return er.async_get(hass).async_get_entity_id(platforma, DOMAIN, f"{wpis.entry_id}_{suffix}")


def _stan(hass, wpis, platforma, suffix):
    eid = _eid(hass, wpis, platforma, suffix)
    return eid and hass.states.get(eid)


async def test_sensory_wrzesien(hass, wpis, pobierz):
    await _setup(hass, wpis)

    razem = _stan(hass, wpis, "sensor", "pstryk_G12_razem")
    assert float(razem.state) == pytest.approx(710.79, abs=0.005)
    a = razem.attributes
    assert a["unit_of_measurement"] == "PLN"
    assert a["device_class"] == "monetary"
    assert "state_class" not in a
    assert a["sprzedaz_przed"] == 517.25
    assert a["tarcza"] == -74.45
    assert a["sprzedaz_po"] == 442.8
    assert a["dystrybucja"] == 267.99
    assert a["pokrycie"] == 1.0
    assert a["okres_od"] == "2026-09-01"
    assert a["okres_do"] == "2026-09-30"
    assert a["szacunek"] is False
    assert a["ostrzezenia"] == []
    assert a["dane_z"] == "2026-10-05T12:00:00+00:00"  # udane pobranie (pusta odpowiedź) ze startu
    assert "netto" in a and "kwh_na_strefe" in a

    roznica = _stan(hass, wpis, "sensor", "pstryk_G12w_roznica")
    assert float(roznica.state) == pytest.approx(-14.225, abs=0.006)
    assert _stan(hass, wpis, "sensor", "pstryk_G12_roznica") is None  # obecna taryfa nie ma różnicy z samą sobą

    tanie = _stan(hass, wpis, "sensor", "kwh_tanie")
    drogie = _stan(hass, wpis, "sensor", "kwh_drogie")
    assert float(tanie.state) == pytest.approx(300.0)
    assert float(drogie.state) == pytest.approx(420.0)
    for s in (tanie, drogie):
        assert s.attributes["device_class"] == "energy"
        assert s.attributes["unit_of_measurement"] == "kWh"
        assert "state_class" not in s.attributes


async def test_atrybuty_identyfikujace_scenariusz(hass, wpis, pobierz):
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "pstryk_G12_razem").attributes
    assert (a["scenariusz"], a["etykieta"], a["obecny"]) == ("pstryk_G12", "Pstryk + G12", True)
    b = _stan(hass, wpis, "sensor", "pstryk_G12w_razem").attributes
    assert (b["scenariusz"], b["obecny"]) == ("pstryk_G12w", False)
    c = _stan(hass, wpis, "sensor", "pstryk_G12w_roznica").attributes
    assert (c["scenariusz"], c["etykieta"], c["obecny"]) == ("pstryk_G12w", "Pstryk + G12w", False)


async def test_atrybuty_grup_scenariuszy(hass, wpis, pobierz):
    await _setup(hass, wpis)

    for suffix, oczekiwane in {
        "pstryk_G11_razem": ("pstryk", "Pstryk", "G11", "Pstryk + G11"),
        "pstryk_G12w_roznica": ("pstryk", "Pstryk", "G12w", "Pstryk + G12w"),
        "kompleksowa_enea_2026_wybor_G12_razem": ("kompleksowa", "Enea", "G12", "Enea prawo wyboru + G12"),
        "kompleksowa_enea_2026_wybor_G12w_roznica": ("kompleksowa", "Enea", "G12w", "Enea prawo wyboru + G12w"),
    }.items():
        a = _stan(hass, wpis, "sensor", suffix).attributes
        assert (a["grupa"], a["sprzedawca"], a["taryfa"], a["etykieta"]) == oczekiwane, suffix
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G13active_razem") is None  # Enea nie ma G13active
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G13active_roznica") is None


async def test_atrybuty_oferty_i_uwag(hass, wpis, pobierz):
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "kompleksowa_enea_eneopewnosc_2026_G12sezON_razem").attributes
    assert (a["grupa"], a["sprzedawca"], a["oferta"], a["taryfa"]) == ("kompleksowa", "Enea", "EneoPewność", "G12sezON")
    assert a["etykieta"] == "Enea EneoPewność + G12sezON"
    assert len(a["uwagi"]) == 3 and all(isinstance(u, str) and u for u in a["uwagi"])
    assert "36 miesięcy" in a["uwagi"][0] and "grupa taryfowa" in a["uwagi"][1] and "31.12.2026" in a["uwagi"][2]
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_eneopewnosc_2026_G12sezON_roznica").attributes["oferta"] == "EneoPewność"

    p = _stan(hass, wpis, "sensor", "pstryk_G12sezON_razem").attributes
    assert (p["oferta"], p["uwagi"]) == ("", [])
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G12sezON_razem") is None  # prawo wyboru nie ma G12sezON
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G12_razem").attributes["oferta"] == "prawo wyboru"
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_eneopewnosc_2026_G13active_razem").attributes["taryfa"] == "G13active"


async def test_atrybuty_cena_do_znaczniki_taryfy(hass, wpis, pobierz):
    await _setup(hass, wpis)

    pewnosc = _stan(hass, wpis, "sensor", "kompleksowa_enea_eneopewnosc_2026_G12_razem").attributes
    assert (pewnosc["cena_do"], pewnosc["znaczniki"]) == ("36 mies.", [])
    natura = _stan(hass, wpis, "sensor", "kompleksowa_tauron_natura_2026_G12_razem").attributes
    assert natura["cena_do"] == "do 09.2029"
    assert natura["znaczniki"] == [["realnie taniej", "W 2026 opłata handlowa realnie 0 zł — ok. 30 zł/rok mniej niż w tabeli"]]
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G12_roznica").attributes["cena_do"] == ""
    pstryk = _stan(hass, wpis, "sensor", "pstryk_G12_razem").attributes
    assert (pstryk["cena_do"], pstryk["znaczniki"]) == ("", [])
    assert pstryk["taryfy"] == ["G11", "G12", "G12w", "G12sezON", "G13active"]
    assert _stan(hass, wpis, "sensor", "pstryk_G12w_roznica").attributes["taryfy"] == pstryk["taryfy"]


async def test_uwagi_poza_rejestratorem(hass, wpis, pobierz):
    from custom_components.porownanie_taryf.sensor import ScenariuszSensor

    statyczne = {"uwagi", "stawki_dystrybucji", "oplaty_dystrybucji_mc", "ceny_energii", "oplata_handlowa_mc", "vat", "akcyza_kwh", "srednia_cena_energii", "cena_do", "znaczniki", "taryfy"}
    assert statyczne <= ScenariuszSensor._unrecorded_attributes
    assert statyczne <= ScenariuszSensor._Entity__combined_unrecorded_attributes  # HA faktycznie to uwzględnia


async def test_wlasny_cennik_bez_oferty_i_uwag(hass, wpis, pobierz):
    hass.config_entries.async_update_entry(
        wpis, options={"cennik": {"nazwa": "X", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}}
    )
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "cennik_G12_razem").attributes
    assert (a["oferta"], a["uwagi"]) == ("", [])


async def test_wlasny_cennik_to_grupa_kompleksowa(hass, wpis, pobierz):
    hass.config_entries.async_update_entry(
        wpis, options={"cennik": {"nazwa": "X", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}}
    )
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "cennik_G12_razem").attributes
    assert (a["grupa"], a["sprzedawca"], a["taryfa"], a["etykieta"]) == ("kompleksowa", "X", "G12", "X + G12")
    assert _stan(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G12_razem").attributes["sprzedawca"] == "Enea"  # oba naraz


async def test_select_przelicza_bez_api(hass, wpis, pobierz):
    await _setup(hass, wpis)
    przed = float(_stan(hass, wpis, "sensor", "pstryk_G12_razem").state)
    wywolania = pobierz.call_count

    await hass.services.async_call(
        "select", "select_option", {"entity_id": _eid(hass, wpis, "select", "okres"), "option": "dzien"}, blocking=True
    )
    await hass.async_block_till_done()

    razem = _stan(hass, wpis, "sensor", "pstryk_G12_razem")
    assert float(razem.state) < przed / 10
    assert razem.attributes["okres_od"] == razem.attributes["okres_do"] == "2026-09-01"
    assert pobierz.call_count == wywolania


async def test_zakres_koniec_przed_data(hass, wpis, pobierz):
    await _setup(hass, wpis)

    await hass.services.async_call(
        "select", "select_option", {"entity_id": _eid(hass, wpis, "select", "okres"), "option": "zakres"}, blocking=True
    )
    await hass.services.async_call(
        "date", "set_value", {"entity_id": _eid(hass, wpis, "date", "koniec"), "date": "2026-08-31"}, blocking=True
    )
    await hass.async_block_till_done()

    for suffix in ("pstryk_G12_razem", "pstryk_G12w_roznica", "kwh_tanie"):
        s = _stan(hass, wpis, "sensor", suffix)
        assert s.state == "unknown"
        assert s.attributes["powod"] == "koniec_przed_data"


async def test_restore_okresu(hass, wpis, pobierz):
    rejestr = er.async_get(hass)
    select = rejestr.async_get_or_create(
        "select", DOMAIN, f"{wpis.entry_id}_okres", suggested_object_id="okres", config_entry=wpis
    )
    data = rejestr.async_get_or_create(
        "date", DOMAIN, f"{wpis.entry_id}_data", suggested_object_id="data", config_entry=wpis
    )
    mock_restore_cache(hass, [State(select.entity_id, "rok"), State(data.entity_id, "2026-03-15")])

    await _setup(hass, wpis)

    koord = wpis.runtime_data
    assert koord.rodzaj == "rok"
    assert koord.dzien == date(2026, 3, 15)
    assert hass.states.get(select.entity_id).state == "rok"
    assert _stan(hass, wpis, "sensor", "pstryk_G12_razem").attributes["okres_od"] == "2026-01-01"


async def test_date_domyslna(hass, wpis, pobierz):
    await _setup(hass, wpis)

    assert _stan(hass, wpis, "date", "data").state == "2026-09-01"
    assert _stan(hass, wpis, "date", "koniec").state == "2026-09-01"
    assert _stan(hass, wpis, "select", "okres").state == "miesiac"


async def test_entity_id_bez_powtorzen_z_config_flow(hass, pobierz):
    """Tytuł wpisu z config flow jest nazwą urządzenia, więc nie może się powtarzać w nazwie encji."""
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"api_key": "sk-test"})
    await hass.async_block_till_done()

    ids = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), r["result"].entry_id)}
    assert ids  # harness ma język en: nazwy z en.json ("total"), użytkownik pl dostaje "razem"
    assert {i for i in ids if not i.split(".")[1].startswith("porownanie_taryf_")} == set()
    assert "sensor.porownanie_taryf_pstryk_g12_total" in ids
    assert "select.porownanie_taryf_period" in ids


async def test_sterowanie_dostepne_mimo_bledu_odswiezania(hass, wpis, pobierz):
    await _setup(hass, wpis)
    pobierz.side_effect = PstrykAuthError("Pstryk HTTP 401")

    await wpis.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert _stan(hass, wpis, "sensor", "pstryk_G12_razem").state == "unavailable"
    assert _stan(hass, wpis, "select", "okres").state == "miesiac"
    assert _stan(hass, wpis, "date", "data").state == "2026-09-01"
    assert _stan(hass, wpis, "date", "koniec").state == "2026-09-01"


async def test_osierocone_encje_cennika_znikaja(hass, hass_storage):
    cennik = {"nazwa": "Enea", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}
    wpis = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU, title="Porównanie taryf", options={"cennik": cennik})
    wpis.add_to_hass(hass)
    zapisz_magazyn(hass_storage, wpis.entry_id, wrzesien())
    rejestr = er.async_get(hass)
    with patch(POBIERZ, new_callable=AsyncMock, return_value=[]):
        await _setup(hass, wpis)
        assert _eid(hass, wpis, "sensor", "cennik_G12_razem") and _eid(hass, wpis, "sensor", "cennik_G12_roznica")

        hass.config_entries.async_update_entry(wpis, options={})
        await hass.config_entries.async_reload(wpis.entry_id)
        await hass.async_block_till_done()

    assert _eid(hass, wpis, "sensor", "cennik_G12_razem") is None
    assert _eid(hass, wpis, "sensor", "cennik_G12_roznica") is None
    assert _eid(hass, wpis, "sensor", "pstryk_G12_razem")  # reszta zostaje
    assert rejestr.async_get(_eid(hass, wpis, "select", "okres"))


async def test_encje_v03_oferty_kompleksowej_znikaja_po_aktualizacji(hass, hass_storage):
    """v0.3: klucz `kompleksowa_<T>`; v0.4: `kompleksowa_<id oferty>_<T>`. Stare wpisy rejestru sprząta async_setup_entry."""
    wpis = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU, title="Porównanie taryf")
    wpis.add_to_hass(hass)
    zapisz_magazyn(hass_storage, wpis.entry_id, wrzesien())
    rejestr = er.async_get(hass)
    stare = [f"{wpis.entry_id}_kompleksowa_G12_{r}" for r in ("razem", "roznica")]
    for uid in stare:
        rejestr.async_get_or_create("sensor", DOMAIN, uid, config_entry=wpis)
    with patch(POBIERZ, new_callable=AsyncMock, return_value=[]):
        await _setup(hass, wpis)

    assert all(rejestr.async_get_entity_id("sensor", DOMAIN, uid) is None for uid in stare)
    assert _eid(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G12_razem")
    assert _eid(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G12_roznica")
    assert not [e for e in rejestr.entities.values() if e.unique_id.endswith("_kompleksowa_G12_razem")]


OPCJE_CENNIKA = {"cennik": {"nazwa": "X", "oplata_mc": 10, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}}


async def test_atrybuty_cen_pstryk(hass, wpis, pobierz):
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "pstryk_G12_razem").attributes
    assert a["id_oferty"] == ""
    assert a["vat"] == 0.23
    assert a["stawki_dystrybucji"] == {"dzien": 0.3214, "noc": 0.1348}
    assert a["oplaty_dystrybucji_mc"] == {"sieciowa": 14.56, "abonament": 3.84, "mocowa": 24.05}
    assert a["srednia_cena_energii"] == {"przed_tarcza": 0.58, "po_tarczy": 0.4959}
    assert a["akcyza_kwh"] == 0.005
    assert "ceny_energii" not in a and "oplata_handlowa_mc" not in a
    # różnica nie niesie tabeli cen, ale ma id_oferty (panel filtruje po nim obie)
    r = _stan(hass, wpis, "sensor", "pstryk_G12w_roznica").attributes
    assert r["id_oferty"] == "" and "stawki_dystrybucji" not in r


async def test_atrybuty_cen_oferty_kompleksowej(hass, wpis, pobierz):
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "kompleksowa_enea_eneopewnosc_2026_G12sezON_razem").attributes
    assert a["id_oferty"] == "enea_eneopewnosc_2026"
    assert a["ceny_energii"] == {"pozostale": 0.5841, "zalecana": 0.3465}
    assert a["oplata_handlowa_mc"] == 15.94
    assert a["akcyza_kwh"] == 0.0
    assert a["stawki_dystrybucji"] == {"pozostale": 0.3214, "zalecana": 0.1348}
    assert a["oplaty_dystrybucji_mc"] == {"sieciowa": 14.56, "abonament": 3.84, "mocowa": 24.05}
    assert "srednia_cena_energii" not in a
    r = _stan(hass, wpis, "sensor", "kompleksowa_enea_2026_wybor_G12_roznica").attributes
    assert r["id_oferty"] == "enea_2026_wybor"


async def test_atrybuty_cen_wlasnego_cennika(hass, wpis, pobierz):
    hass.config_entries.async_update_entry(wpis, options=OPCJE_CENNIKA)
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "cennik_G12_razem").attributes
    assert a["id_oferty"] == "cennik"
    assert (a["ceny_energii"], a["oplata_handlowa_mc"], a["akcyza_kwh"]) == ({"dzien": 0.6, "noc": 0.4}, 10, 0.005)
    assert _stan(hass, wpis, "sensor", "cennik_G12_roznica").attributes["id_oferty"] == "cennik"


async def test_nadpisana_stawka_widoczna_w_atrybutach(hass, wpis, pobierz):
    hass.config_entries.async_update_entry(wpis, options={"stawki": {"G12_dzien": 0.30}})
    await _setup(hass, wpis)

    assert _stan(hass, wpis, "sensor", "pstryk_G12_razem").attributes["stawki_dystrybucji"]["dzien"] == 0.3435


async def test_srednia_pstryk_bez_odczytow_to_null(hass, hass_storage, pobierz):
    wpis = MockConfigEntry(domain=DOMAIN, data=DATA_WPISU, title="Porównanie taryf")
    wpis.add_to_hass(hass)  # pusty magazyn, ale udane pobranie: okres bez odczytów
    await _setup(hass, wpis)

    a = _stan(hass, wpis, "sensor", "pstryk_G12_razem").attributes
    assert a["srednia_cena_energii"] == {"przed_tarcza": None, "po_tarczy": None}
    assert a["akcyza_kwh"] is None


async def test_osierocony_select_sprzedawca_znika_po_aktualizacji(hass, wpis, pobierz):
    """v0.7 usunęła select „Sprzedawca”: wpis rejestru po nim sprząta async_setup_entry, okres zostaje."""
    rejestr = er.async_get(hass)
    rejestr.async_get_or_create("select", DOMAIN, f"{wpis.entry_id}_sprzedawca", suggested_object_id="sprzedawca", config_entry=wpis)
    await _setup(hass, wpis)

    assert _eid(hass, wpis, "select", "sprzedawca") is None
    assert not [e for e in rejestr.entities.values() if e.unique_id.endswith("_sprzedawca")]
    assert _eid(hass, wpis, "select", "okres")
    assert _eid(hass, wpis, "date", "data")
