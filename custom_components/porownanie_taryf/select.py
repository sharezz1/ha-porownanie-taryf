"""Selecty „Okres” (dzień/miesiąc/rok/zakres własny) i „Sprzedawca” (filtr panelu), przywracane po restarcie (spec §7, §7a)."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import TaryfyConfigEntry, TaryfyCoordinator
from .core.scenariusz import RODZAJE_OKRESU
from .entity import SterowanieEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: TaryfyConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([OkresSelect(entry.runtime_data), SprzedawcaSelect(entry.runtime_data)])


class OkresSelect(SterowanieEntity, SelectEntity, RestoreEntity):
    _attr_options = list(RODZAJE_OKRESU)

    def __init__(self, coordinator: TaryfyCoordinator) -> None:
        super().__init__(coordinator, "okres")

    @property
    def current_option(self) -> str:
        return self.coordinator.rodzaj

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (ostatni := await self.async_get_last_state()) and ostatni.state in self.options:
            self.coordinator.ustaw_okres(rodzaj=ostatni.state)

    async def async_select_option(self, option: str) -> None:
        self.coordinator.ustaw_okres(rodzaj=option)


class SprzedawcaSelect(SterowanieEntity, SelectEntity, RestoreEntity):
    """Oferta pokazywana w sekcji 2 panelu. Tylko do filtrowania widoku: liczb nie zmienia."""

    _attr_current_option = "wszystkie"

    def __init__(self, coordinator: TaryfyCoordinator) -> None:
        super().__init__(coordinator, "sprzedawca")
        k = coordinator.konf
        self._attr_options = ["wszystkie", *k.kompleksowe, *(["cennik"] if k.cennik else [])]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # wybór spoza listy (zmieniony katalog, usunięty cennik) zostaje przy "wszystkie"
        if (ostatni := await self.async_get_last_state()) and ostatni.state in self.options:
            self._attr_current_option = ostatni.state

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
