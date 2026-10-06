"""Encje dat okresu: „Data” i „Koniec zakresu” (używany tylko w trybie zakres), przywracane po restarcie (spec §7)."""

from contextlib import suppress
from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import TaryfyConfigEntry, TaryfyCoordinator
from .entity import SterowanieEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: TaryfyConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    koord = entry.runtime_data
    async_add_entities([DataOkresu(koord, "data", "dzien"), DataOkresu(koord, "koniec", "koniec")])


class DataOkresu(SterowanieEntity, DateEntity, RestoreEntity):
    def __init__(self, coordinator: TaryfyCoordinator, klucz: str, pole: str) -> None:
        super().__init__(coordinator, klucz)
        self._pole = pole  # atrybut coordinatora i nazwa argumentu `ustaw_okres`

    @property
    def native_value(self) -> date | None:
        return getattr(self.coordinator, self._pole)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        wartosc = None
        if ostatni := await self.async_get_last_state():
            with suppress(ValueError):  # "unknown"/"unavailable"
                wartosc = date.fromisoformat(ostatni.state)
        if wartosc is None and self._pole == "koniec":
            wartosc = self.coordinator.dzien  # domyślnie koniec = data; bez tego encja pokazuje datę, a sensory liczą z None
        if wartosc is not None:
            self.coordinator.ustaw_okres(**{self._pole: wartosc})

    async def async_set_value(self, value: date) -> None:
        self.coordinator.ustaw_okres(**{self._pole: value})
