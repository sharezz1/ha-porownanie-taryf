"""Config flow: klucz Pstryk i parametry instalacji, reauth oraz opcje (spec §7)."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .core.presety import (
    CONF_PRESET,
    CONF_TANIE_G12,
    CONF_TARYFA,
    CONF_UKLAD,
    OPT_CENNIK,
    OPT_STAWKI,
    OPT_TARCZA,
    OPT_VAT,
    STREFY,
    TARCZA_DOMYSLNA,
    TARYFY,
    stawki_enea_2026,
    stawki_na_plasko,
)
from .core.strefy import TANIE_G12_DOMYSLNE
from .sources.pstryk import (
    PstrykAuthError,
    PstrykClient,
    PstrykEndpointError,
    PstrykError,
)

AKCYZA_DOMYSLNA = 0.005
POLA_TARCZY = ("limit", "podstawa", "obejmuje_obsluge", "od", "do")

# HA odrzuca step < 0.001, a stawki mają 4 miejsca po przecinku; "any" nie zaokrągla wpisanej wartości
_LICZBA = NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step="any", min=0))
_VAT = NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step="any", min=0, max=1))  # ułamek: 0,23, nie 23


def _lista(*opcje: str, klucz: str | None = None) -> SelectSelector:
    """`klucz` = translation_key etykiet opcji (`selector.<klucz>.options` w tłumaczeniach)."""
    return SelectSelector(SelectSelectorConfig(options=list(opcje), **({"translation_key": klucz} if klucz else {})))


_KLUCZ = {vol.Required(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
_SCHEMA_KLUCZ = vol.Schema(_KLUCZ)
_SCHEMA_USER = vol.Schema(
    {
        **_KLUCZ,
        vol.Required(CONF_UKLAD, default="3f"): _lista("3f", "1f", klucz=CONF_UKLAD),
        vol.Required(CONF_PRESET, default="enea_2026"): _lista("enea_2026", klucz=CONF_PRESET),
        vol.Required(CONF_TARYFA, default="G12"): _lista(*TARYFY),
        vol.Required(CONF_TANIE_G12, default=[str(h) for h in sorted(TANIE_G12_DOMYSLNE)]): SelectSelector(
            SelectSelectorConfig(options=[str(h) for h in range(24)], multiple=True)
        ),
    }
)
_POLA_CENNIKA = [f"{t}_{z}" for t, strefy in STREFY.items() for z in strefy]
_SCHEMA_CENNIK = vol.Schema(
    {
        vol.Optional("nazwa"): TextSelector(),
        vol.Optional("oplata_mc", default=0.0): _LICZBA,
        vol.Optional("akcyza", default=AKCYZA_DOMYSLNA): _LICZBA,
        **{vol.Optional(pole): _LICZBA for pole in _POLA_CENNIKA},
    }
)


async def _waliduj_klucz(hass: HomeAssistant, klucz: str) -> str | None:
    """Kod błędu albo None. Zapytanie o jedną dobę: wczoraj 00:00 UTC -> dziś 00:00 UTC."""
    koniec = dt_util.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        await PstrykClient(async_get_clientsession(hass), klucz).pobierz(koniec - timedelta(days=1), koniec)
    except PstrykAuthError:
        return "invalid_auth"
    except PstrykEndpointError:
        return "endpoint_changed"
    except PstrykError:  # sieć, 5xx, 429 i nieobsłużone statusy
        return "cannot_connect"
    return None


class TaryfyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TaryfyOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            if not user_input[CONF_TANIE_G12]:
                errors[CONF_TANIE_G12] = "tanie_g12_puste"
            elif blad := await _waliduj_klucz(self.hass, user_input[CONF_API_KEY]):
                errors["base"] = blad
            else:
                godziny = sorted((int(h) for h in user_input[CONF_TANIE_G12]), key=lambda h: (h < 22, h))
                return self.async_create_entry(title="Porównanie taryf", data={**user_input, CONF_TANIE_G12: godziny})
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_SCHEMA_USER, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if blad := await _waliduj_klucz(self.hass, user_input[CONF_API_KEY]):
                errors["base"] = blad
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(step_id="reauth_confirm", data_schema=_SCHEMA_KLUCZ, errors=errors)


class TaryfyOptionsFlow(OptionsFlowWithReload):
    """Każdy krok zapisuje swoją sekcję opcji; zmiana przeładowuje wpis (bez update listenera)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(menu_options=["stawki", "tarcza", "cennik"])

    def _zapisz(self, sekcje: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **sekcje})

    async def async_step_stawki(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        opcje = self.config_entry.options
        if user_input is not None:
            return self._zapisz(
                {
                    OPT_VAT: user_input[OPT_VAT],
                    OPT_STAWKI: {k: v for k, v in user_input.items() if k != OPT_VAT},
                }
            )
        stawki = {
            **stawki_na_plasko(stawki_enea_2026(self.config_entry.data[CONF_UKLAD])),
            **opcje.get(OPT_STAWKI, {}),
        }
        schema = {vol.Required(OPT_VAT, default=opcje.get(OPT_VAT, 0.23)): _VAT}
        schema.update({vol.Required(klucz, default=wartosc): _LICZBA for klucz, wartosc in stawki.items()})
        return self.async_show_form(step_id="stawki", data_schema=vol.Schema(schema))

    async def async_step_tarcza(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._zapisz(
                {OPT_TARCZA: {rok: {p: user_input[f"{rok}_{p}"] for p in POLA_TARCZY} for rok in TARCZA_DOMYSLNA}}
            )
        zapisane = self.config_entry.options.get(OPT_TARCZA, {})
        schema: dict[Any, Any] = {}
        for rok, preset in TARCZA_DOMYSLNA.items():
            bazowe = {
                "limit": preset.limit,
                "podstawa": preset.podstawa,
                "obejmuje_obsluge": preset.obejmuje_obsluge,
                "od": preset.od.isoformat(),
                "do": preset.do.isoformat(),
                **zapisane.get(rok, {}),
            }
            typy = {
                "limit": _LICZBA,
                "podstawa": _lista("brutto", "netto", klucz="podstawa"),
                "obejmuje_obsluge": BooleanSelector(),
                "od": DateSelector(),
                "do": DateSelector(),
            }
            schema.update({vol.Required(f"{rok}_{p}", default=bazowe[p]): typy[p] for p in POLA_TARCZY})
        return self.async_show_form(step_id="tarcza", data_schema=vol.Schema(schema))

    async def async_step_cennik(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            ceny: dict[str, dict[str, float]] = {}
            for taryfa, strefy in STREFY.items():
                wpisane = {z: user_input[f"{taryfa}_{z}"] for z in strefy if user_input.get(f"{taryfa}_{z}") is not None}
                if len(wpisane) == len(strefy):
                    ceny[taryfa] = wpisane
                elif wpisane:  # taryfa wchodzi tylko z kompletem stref
                    errors["base"] = "cennik_niekompletny"
            nazwa = (user_input.get("nazwa") or "").strip()
            if nazwa and not ceny:
                errors["base"] = "cennik_niekompletny"
            if not errors:
                opcje = {k: v for k, v in self.config_entry.options.items() if k != OPT_CENNIK}
                if nazwa:
                    cennik = {
                        "nazwa": nazwa,
                        "oplata_mc": user_input.get("oplata_mc", 0.0),
                        "akcyza": user_input.get("akcyza", AKCYZA_DOMYSLNA),
                        "ceny": ceny,
                    }
                    opcje[OPT_CENNIK] = cennik
                return self.async_create_entry(data=opcje)
        zapisany = self.config_entry.options.get(OPT_CENNIK)
        sugestie = user_input or (
            {
                "nazwa": zapisany["nazwa"],
                "oplata_mc": zapisany["oplata_mc"],
                "akcyza": zapisany["akcyza"],
                **{f"{t}_{z}": c for t, strefy in zapisany["ceny"].items() for z, c in strefy.items()},
            }
            if zapisany
            else None
        )
        return self.async_show_form(
            step_id="cennik",
            data_schema=self.add_suggested_values_to_schema(_SCHEMA_CENNIK, sugestie),
            errors=errors,
        )
