"""Tłumaczenia pl/en: identyczna struktura kluczy i komplet kluczy używanych w kodzie."""

import json
from pathlib import Path
import re

import pytest
from homeassistant.helpers.selector import SelectSelector

from custom_components.porownanie_taryf import config_flow
from custom_components.porownanie_taryf.coordinator import ISSUE_ENDPOINT
from custom_components.porownanie_taryf.core.presety import TARCZA_DOMYSLNA, stawki_enea_2026, stawki_na_plasko
from custom_components.porownanie_taryf.core.scenariusz import RODZAJE_OKRESU

KOD = Path(config_flow.__file__).parent
TLUMACZENIA = {j: json.loads((KOD / "translations" / f"{j}.json").read_text(encoding="utf-8")) for j in ("pl", "en")}
ZRODLO_FLOW = Path(config_flow.__file__).read_text(encoding="utf-8")

# translation_key encji (sensor.py, select.py, date.py), kroki, błędy i aborty (config_flow.py), issue (coordinator.py)
WYMAGANE = [
    *(f"entity.sensor.{k}.name" for k in ("razem", "roznica", "kwh_tanie", "kwh_drogie")),
    "entity.select.okres.name",
    *(f"entity.select.okres.state.{s}" for s in RODZAJE_OKRESU),
    "entity.date.data.name",
    "entity.date.koniec.name",
    "config.step.user.title",
    "config.step.reauth_confirm.title",
    *(f"config.error.{k}" for k in ("invalid_auth", "cannot_connect", "endpoint_changed", "tanie_g12_puste")),
    *(f"config.abort.{k}" for k in ("already_configured", "reauth_successful")),
    *(f"options.step.init.menu_options.{k}" for k in ("stawki", "tarcza", "cennik")),
    *(f"options.step.{k}.title" for k in ("stawki", "tarcza", "cennik")),
    "options.error.cennik_niekompletny",
    f"issues.{ISSUE_ENDPOINT}.title",
    f"issues.{ISSUE_ENDPOINT}.description",
]

# SelectSelector z `translation_key` (config_flow.py) -> jego opcje
SELEKTORY = {"uklad": ("3f", "1f"), "preset": ("enea_2026",), "podstawa": ("brutto", "netto")}


def _klucze(d: dict, prefiks: str = "") -> set[str]:
    wynik = set()
    for k, v in d.items():
        wynik.add(prefiks + k)
        if isinstance(v, dict):
            wynik |= _klucze(v, f"{prefiks}{k}.")
    return wynik


def _pobierz(d: dict, sciezka: str):
    for k in sciezka.split("."):
        d = d[k]
    return d


def _pola(schema) -> set[str]:
    return {str(k) for k in schema.schema}


def test_ta_sama_struktura():
    pl, en = (_klucze(TLUMACZENIA[j]) for j in ("pl", "en"))
    assert pl == en, f"tylko pl: {sorted(pl - en)}, tylko en: {sorted(en - pl)}"


@pytest.mark.parametrize("jezyk", TLUMACZENIA)
def test_komplet_kluczy(jezyk):
    for sciezka in WYMAGANE:
        assert _pobierz(TLUMACZENIA[jezyk], sciezka).strip(), sciezka


@pytest.mark.parametrize("jezyk", TLUMACZENIA)
def test_placeholder_scenariusza(jezyk):
    for k in ("razem", "roznica"):
        assert "{scenariusz}" in TLUMACZENIA[jezyk]["entity"]["sensor"][k]["name"]


def test_kod_nie_ma_kluczy_spoza_tlumaczen():
    """Kroki, opcje menu i kody błędów z config_flow.py muszą istnieć w tłumaczeniach."""
    pl = TLUMACZENIA["pl"]
    kroki = set(pl["config"]["step"]) | set(pl["options"]["step"])
    bledy = set(pl["config"]["error"]) | set(pl["options"]["error"])
    assert set(re.findall(r'step_id="(\w+)"', ZRODLO_FLOW)) <= kroki
    assert set(re.findall(r'(?:errors\["base"\] = |return )"(\w+)"', ZRODLO_FLOW)) <= bledy
    menu = re.search(r"menu_options=\[(.*?)\]", ZRODLO_FLOW).group(1)
    assert set(re.findall(r'"(\w+)"', menu)) == set(pl["options"]["step"]["init"]["menu_options"])
    assert ISSUE_ENDPOINT in pl["issues"]


@pytest.mark.parametrize("jezyk", TLUMACZENIA)
def test_kazde_pole_ma_etykiete(jezyk):
    """Każde pole formularza ma `data`, a `data_description` dotyczy tylko istniejących pól."""
    pola = {
        ("config", "user"): _pola(config_flow._SCHEMA_USER),
        ("config", "reauth_confirm"): _pola(config_flow._SCHEMA_KLUCZ),
        ("options", "stawki"): {"vat", *stawki_na_plasko(stawki_enea_2026("3f"))},
        ("options", "tarcza"): {f"{r}_{p}" for r in TARCZA_DOMYSLNA for p in config_flow.POLA_TARCZY},
        ("options", "cennik"): _pola(config_flow._SCHEMA_CENNIK),
    }
    for (flow, krok), oczekiwane in pola.items():
        t = TLUMACZENIA[jezyk][flow]["step"][krok]
        assert set(t["data"]) == oczekiwane, (flow, krok)
        assert set(t.get("data_description", {})) <= set(t["data"]), (flow, krok)


@pytest.mark.parametrize("jezyk", TLUMACZENIA)
def test_opcje_selektorow_maja_etykiety(jezyk):
    for klucz, opcje in SELEKTORY.items():
        etykiety = TLUMACZENIA[jezyk]["selector"][klucz]["options"]
        assert set(etykiety) == set(opcje), klucz
        assert all(e.strip() for e in etykiety.values()), klucz


def test_selektory_formularza_user_maja_translation_key():
    selektory = {str(k): v for k, v in config_flow._SCHEMA_USER.schema.items() if isinstance(v, SelectSelector)}
    for pole in ("uklad", "preset"):
        assert selektory[pole].config["translation_key"] == pole
        assert tuple(selektory[pole].config["options"]) == SELEKTORY[pole]
    assert "translation_key" not in selektory["taryfa"].config  # nazwy taryf bez tłumaczenia
