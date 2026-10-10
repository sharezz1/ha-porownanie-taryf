"""Zakładka „Fotowoltaika” (spec v0.8 §6): komendy websocket, konfiguracja i cache w Store, NMPT w tle."""

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .core.pv import ParametryPV, Polac, az_open_meteo
from .core.pv_wyniki import okno, wyniki
from .sources.dach import adres_z_lokalizacji, geokoduj, pobierz_nmpt, polacie
from .sources.pogoda import PogodaError, pobierz_gti
from .sources.rce import RceError, pobierz_rce

_LOGGER = logging.getLogger(__name__)
KLUCZ_KOMEND = "pv_komendy"
KLUCZ_DANYCH = "pv"

DOMYSLNY: dict[str, Any] = {
    "schema": 1, "adres": None, "e": None, "n": None, "lat": None, "lon": None, "polacie": [],
    "koszt_kwp": 3000, "koszt_kwh_mag": 2000, "wzrost_cen": 0.03,
    "zaawansowane": {"pr": 0.85, "degradacja": 0.005, "sprawnosc_mag": 0.90, "dod": 0.90,
                     "zwrot_depozytu": 0.0, "falownik_rok": 12, "falownik_pct": 0.10, "magazyn_rok": 15, "magazyn_pct": 0.70},
}
_U = lambda lo, hi: vol.All(vol.Coerce(float), vol.Range(min=lo, max=hi))
_OPC = lambda lo, hi: vol.Any(None, _U(lo, hi))
_POLAC = vol.Schema({
    vol.Required("az"): _U(0, 359.999), vol.Required("nachylenie"): _U(0, 65), vol.Required("kwp_max"): _U(0, 30),
    vol.Required("cien"): _U(0, 0.5), vol.Required("panele"): bool,
})
KONFIG = vol.Schema({
    vol.Required("schema"): 1,
    vol.Required("adres"): vol.Any(None, vol.All(str, vol.Length(max=200))),
    vol.Required("e"): _OPC(0, 1_000_000), vol.Required("n"): _OPC(0, 1_000_000),
    vol.Required("lat"): _OPC(-90, 90), vol.Required("lon"): _OPC(-180, 180),
    vol.Required("polacie"): vol.All([_POLAC], vol.Length(max=4)),
    vol.Required("koszt_kwp"): _U(500, 8000), vol.Required("koszt_kwh_mag"): _U(0, 6000),
    vol.Required("wzrost_cen"): _U(-0.05, 0.15),
    vol.Required("zaawansowane"): vol.Schema({
        vol.Required("pr"): _U(0.5, 1),
        vol.Required("degradacja"): _U(0, 0.02), vol.Required("sprawnosc_mag"): _U(0.5, 1), vol.Required("dod"): _U(0.5, 1),
        vol.Required("zwrot_depozytu"): _U(0, 1),
        vol.Required("falownik_rok"): vol.All(vol.Coerce(int), vol.Range(1, 20)), vol.Required("falownik_pct"): _U(0, 1),
        vol.Required("magazyn_rok"): vol.All(vol.Coerce(int), vol.Range(1, 20)), vol.Required("magazyn_pct"): _U(0, 1),
    }),
})


def _konfig(surowy: Any) -> dict:
    nowy = KONFIG(surowy)
    if (nowy["lat"] is None) != (nowy["lon"] is None):
        raise vol.Invalid("lat i lon muszą być podane razem")
    return nowy


@dataclass
class _Pv:
    konfig_store: Store
    cache_store: Store
    konfig: dict | None = None
    cache: dict = field(default_factory=lambda: {"gti": {}, "gti_pobrano": {}, "rce": {}, "nmpt": {}})
    wynik: tuple[Any, dict] | None = None  # (klucz ważności, wynik)
    blokada: asyncio.Lock = field(default_factory=asyncio.Lock)


def _punkt(e: float, n: float) -> str:
    return f"{round(e)},{round(n)}"


async def _pv(hass: HomeAssistant, entry_id: str) -> _Pv:
    dane = hass.data[DOMAIN].setdefault(KLUCZ_DANYCH, {})
    if entry_id not in dane:
        pv = _Pv(Store(hass, 1, f"{DOMAIN}.{entry_id}.pv"), Store(hass, 1, f"{DOMAIN}.{entry_id}.pv_cache"))
        pv.konfig = await pv.konfig_store.async_load()
        pv.cache |= await pv.cache_store.async_load() or {}
        # „trwa” nie przeżywa restartu: zadanie tła już nie istnieje
        pv.cache["nmpt"] = {k: v for k, v in pv.cache["nmpt"].items() if v is not None}
        return dane.setdefault(entry_id, pv)  # równoległe pierwsze wywołania dostają ten sam obiekt
    return dane[entry_id]


def _wpis(hass: HomeAssistant, connection, msg) -> ConfigEntry | None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(msg["id"], "not_loaded", "Wpis integracji nie jest załadowany")
        return None
    return entry


@websocket_api.websocket_command({vol.Required("type"): "porownanie_taryf/pv/konfig", vol.Required("entry_id"): str, vol.Optional("konfig"): dict})
@websocket_api.async_response
async def ws_konfig(hass, connection, msg):
    if not (entry := _wpis(hass, connection, msg)):
        return
    pv = await _pv(hass, entry.entry_id)
    if "konfig" in msg:
        if not connection.user.is_admin:
            connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Zapis wymaga administratora")
            return
        try:
            nowy = _konfig(msg["konfig"])
        except vol.Invalid as err:
            connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
            return
        if nowy["e"] is None:
            pv.cache["nmpt"].clear()  # „Usuń lokalizację”
        _przytnij_gti(pv, nowy)
        pv.konfig, pv.wynik = nowy, None
        await pv.konfig_store.async_save(nowy)
        await pv.cache_store.async_save(pv.cache)
    connection.send_result(msg["id"], pv.konfig or DOMYSLNY)


def _klucz_gti(lat: float, lon: float, pl: dict) -> str:
    return f"{lat:.3f},{lon:.3f},{round(pl['nachylenie'])},{round(pl['az'])}"


def _przytnij_gti(pv: _Pv, konfig: dict) -> None:
    if konfig["lat"] is None:
        pv.cache["gti"].clear()
        pv.cache["gti_pobrano"].clear()
        return
    potrzebne = {_klucz_gti(konfig["lat"], konfig["lon"], pl) for pl in konfig["polacie"]}
    for k in set(pv.cache["gti"]) | set(pv.cache["gti_pobrano"]):
        if k not in potrzebne:
            pv.cache["gti"].pop(k, None)
            pv.cache["gti_pobrano"].pop(k, None)


@websocket_api.websocket_command({
    vol.Required("type"): "porownanie_taryf/pv/dach", vol.Required("entry_id"): str,
    vol.Exclusive("adres", "gdzie"): vol.All(str, vol.Length(min=3, max=200)),
    vol.Inclusive("lat", "wsp"): _U(-90, 90), vol.Inclusive("lon", "wsp"): _U(-180, 180),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_dach(hass, connection, msg):
    if not (entry := _wpis(hass, connection, msg)):
        return
    if "adres" not in msg and "lat" not in msg:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Podaj adres albo lat i lon")
        return
    pv = await _pv(hass, entry.entry_id)
    sesja = async_get_clientsession(hass)
    adres = msg.get("adres")
    if adres is None:
        adres = await adres_z_lokalizacji(sesja, msg["lat"], msg["lon"])
    punkt = await geokoduj(sesja, adres) if adres else None
    if punkt is None:
        connection.send_error(msg["id"], "adres_nieznaleziony", "Nie znaleziono adresu")
        return
    k = _punkt(punkt.e, punkt.n)
    if k not in pv.cache["nmpt"]:
        pv.cache["nmpt"][k] = None  # trwa
        # zadanie może ruszyć od razu i skończyć przed odpowiedzią; wynik i tak odbierze pv/dach_status
        entry.async_create_background_task(hass, _nmpt(hass, pv, punkt.e, punkt.n), f"{DOMAIN}_nmpt_{k}")
        stan = {"polacie_nmpt": None, "nmpt_blad": None}
    else:
        stan = _stan_nmpt(pv, k)
    connection.send_result(msg["id"], {"adres": punkt.adres, "e": punkt.e, "n": punkt.n, "lat": punkt.lat, "lon": punkt.lon} | stan)


async def _nmpt(hass: HomeAssistant, pv: _Pv, e: float, n: float) -> None:
    k = _punkt(e, n)
    try:
        siatka = await pobierz_nmpt(async_get_clientsession(hass), e, n)
        if k not in pv.cache["nmpt"]:
            return  # w międzyczasie usunięto lokalizację
        if siatka is None:
            pv.cache["nmpt"][k] = {"blad": "niedostepny"}
            return  # nie zapisujemy porażki na stałe — kolejne „Szukaj” spróbuje ponownie
        lista = await hass.async_add_executor_job(polacie, *siatka)
        if k not in pv.cache["nmpt"]:
            return
        pv.cache["nmpt"][k] = {"polacie": [{"az": a, "nachylenie": s, "powierzchnia_m2": p} for a, s, p in lista]}
        await pv.cache_store.async_save(pv.cache)
    except Exception:  # noqa: BLE001 — zadanie tła nie może zostawić punktu na zawsze jako „trwa”
        _LOGGER.exception("Pobieranie NMPT nie powiodło się")
        if k in pv.cache["nmpt"]:
            pv.cache["nmpt"][k] = {"blad": "niedostepny"}
    finally:
        if k in pv.cache["nmpt"] and pv.cache["nmpt"][k] is None:  # np. CancelledError
            pv.cache["nmpt"].pop(k)


def _stan_nmpt(pv: _Pv, k: str) -> dict:
    if k not in pv.cache["nmpt"]:  # nieznany punkt (np. po restarcie albo „Usuń lokalizację”): nic nie trwa
        return {"polacie_nmpt": [], "nmpt_blad": "niedostepny"}
    v = pv.cache["nmpt"][k]
    if v is None:  # klucz z wartością None = zadanie tła trwa
        return {"polacie_nmpt": None, "nmpt_blad": None}
    if "blad" in v:
        pv.cache["nmpt"].pop(k)  # pokazane raz; następne „Szukaj” ponawia
        return {"polacie_nmpt": [], "nmpt_blad": v["blad"]}
    return {"polacie_nmpt": v["polacie"], "nmpt_blad": None}


@websocket_api.websocket_command({vol.Required("type"): "porownanie_taryf/pv/dach_status", vol.Required("entry_id"): str,
                                  vol.Required("e"): vol.Coerce(float), vol.Required("n"): vol.Coerce(float)})
@websocket_api.async_response
async def ws_dach_status(hass, connection, msg):
    if not (entry := _wpis(hass, connection, msg)):
        return
    pv = await _pv(hass, entry.entry_id)
    connection.send_result(msg["id"], _stan_nmpt(pv, _punkt(msg["e"], msg["n"])))


@websocket_api.websocket_command({vol.Required("type"): "porownanie_taryf/pv/wyniki", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_wyniki(hass, connection, msg):
    if not (entry := _wpis(hass, connection, msg)):
        return
    pv = await _pv(hass, entry.entry_id)
    k = pv.konfig
    polacie_max = [Polac(p["az"], p["nachylenie"], p["kwp_max"], p["cien"]) for p in (k or {}).get("polacie", []) if p["panele"]]
    if not k or k["lat"] is None or not polacie_max:
        connection.send_result(msg["id"], {"schema": 1, "stan": "brak_konfigu"})
        return
    koord = entry.runtime_data
    dzis = dt_util.now().date()
    klucz = (repr(k), koord.dane_z, repr(koord.konf), dzis)
    if pv.wynik and pv.wynik[0] == klucz:
        connection.send_result(msg["id"], pv.wynik[1])
        return
    async with pv.blokada:  # równoległe wywołania nie pobierają dwa razy
        if not (pv.wynik and pv.wynik[0] == klucz):
            wynik = await _licz(hass, pv, koord, k, polacie_max, dzis)
            if wynik["stan"] in ("ok", "za_malo_danych"):  # brak_pogody/brak_rce mają ponawiać
                pv.wynik = (klucz, wynik)
            connection.send_result(msg["id"], wynik)
            return
    connection.send_result(msg["id"], pv.wynik[1])


async def _licz(hass: HomeAssistant, pv: _Pv, koord, k: dict, polacie_max: list[Polac], dzis: date) -> dict:
    mies = okno(dzis)
    od = date.fromisoformat(mies[0] + "-01") - timedelta(days=1)  # zapas na przesunięcie UTC/lokalny
    do = min(dzis - timedelta(days=1), date.fromisoformat(mies[-1] + "-28") + timedelta(days=4))
    sesja = async_get_clientsession(hass)
    pogoda = []
    for pl in [p for p in k["polacie"] if p["panele"]]:
        kg = _klucz_gti(k["lat"], k["lon"], pl)
        # ponytail: dociąganie całego okna raz na dobę na połać; przyrostowo po dniach, gdy limity Open-Meteo zaczną boleć
        if pv.cache["gti_pobrano"].get(kg) != dzis.isoformat():
            try:
                nowe = await pobierz_gti(sesja, k["lat"], k["lon"], pl["nachylenie"], az_open_meteo(pl["az"]), od, do)
                pv.cache["gti"][kg] = {g: list(v) for g, v in nowe.items()}
                pv.cache["gti_pobrano"][kg] = dzis.isoformat()
            except PogodaError as err:
                _LOGGER.warning("Open-Meteo niedostępne (%s); liczę z cache", err)
        pogoda.append({g: tuple(v) for g, v in pv.cache["gti"].get(kg, {}).items()})
    pv.cache["rce"] = {g: v for g, v in pv.cache["rce"].items() if g[:10] >= od.isoformat()}  # tylko okno
    mam = {g[:10] for g in pv.cache["rce"]}
    brakuje_rce = [d for d in _dni(od, do) if d.isoformat() not in mam]
    if brakuje_rce:
        try:
            pv.cache["rce"] |= await pobierz_rce(sesja, min(brakuje_rce), max(brakuje_rce), pv.cache["rce"])  # okna zapisują się na bieżąco
        except RceError as err:
            _LOGGER.warning("PSE niedostępne (%s); liczę z cache", err)
    await pv.cache_store.async_save(pv.cache)
    z = k["zaawansowane"]
    p = ParametryPV(pr=z["pr"], degradacja=z["degradacja"], sprawnosc_mag=z["sprawnosc_mag"], dod=z["dod"],
                    wzrost_cen=k["wzrost_cen"], zwrot_depozytu=z["zwrot_depozytu"],
                    falownik_rok=z["falownik_rok"], falownik_pct=z["falownik_pct"], magazyn_rok=z["magazyn_rok"], magazyn_pct=z["magazyn_pct"])
    return await hass.async_add_executor_job(
        wyniki, list(koord.odczyty), koord.konf, polacie_max, pogoda, dict(pv.cache["rce"]), k["koszt_kwp"], k["koszt_kwh_mag"], p, dzis)


def _dni(od: date, do: date):
    d = od
    while d <= do:
        yield d
        d += timedelta(days=1)


@callback
def async_setup(hass: HomeAssistant) -> None:
    stan = hass.data.setdefault(DOMAIN, {})
    if stan.get(KLUCZ_KOMEND):
        return
    for komenda in (ws_konfig, ws_dach, ws_dach_status, ws_wyniki):
        websocket_api.async_register_command(hass, komenda)
    stan[KLUCZ_KOMEND] = True


async def async_remove(hass: HomeAssistant, entry: ConfigEntry) -> None:
    hass.data.get(DOMAIN, {}).get(KLUCZ_DANYCH, {}).pop(entry.entry_id, None)
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.pv").async_remove()
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.pv_cache").async_remove()
