"""Wspólna baza encji: jedno urządzenie usługi na wpis, nazwy z tłumaczeń."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaryfyCoordinator


class TaryfyEntity(CoordinatorEntity[TaryfyCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TaryfyCoordinator, suffix: str, translation_key: str | None = None) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_translation_key = translation_key or suffix
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, entry_type=DeviceEntryType.SERVICE, name=entry.title
        )


class SterowanieEntity(TaryfyEntity):
    """Encje sterujące okresem: działają bez API, więc błąd odświeżania ich nie wyłącza."""

    @property
    def available(self) -> bool:
        return True
