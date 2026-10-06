"""Sensory: suma brutto na scenariusz, różnica względem obecnej taryfy i kWh w tanich/drogich strefach (spec §7)."""

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TaryfyConfigEntry, TaryfyCoordinator
from .core.scenariusz import etykieta, grupa_scenariusza, klucze_scenariuszy, sprzedawca_scenariusza, taryfa_scenariusza
from .entity import TaryfyEntity

POWOD_BRAK_KONCA = "koniec_przed_data"


async def async_setup_entry(
    hass: HomeAssistant, entry: TaryfyConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    koord = entry.runtime_data
    obecny = f"pstryk_{koord.konf.obecna_taryfa}"
    sensory: list[TaryfyEntity] = [KwhSensor(koord, "kwh_tanie"), KwhSensor(koord, "kwh_drogie")]
    for klucz in klucze_scenariuszy(koord.konf):
        sensory.append(ScenariuszSensor(koord, klucz, "razem"))
        if klucz != obecny:
            sensory.append(ScenariuszSensor(koord, klucz, "roznica"))
    # encje po usuniętym cenniku lub zmienionej taryfie: wpisy rejestru nie znikają same
    aktualne = {s.unique_id for s in sensory}
    rejestr = er.async_get(hass)
    for wpis in er.async_entries_for_config_entry(rejestr, entry.entry_id):
        if wpis.domain == "sensor" and wpis.unique_id not in aktualne:
            rejestr.async_remove(wpis.entity_id)
    async_add_entities(sensory)


class _Sensor(TaryfyEntity, SensorEntity):
    """Przy zakresie z końcem przed datą wynik to None: stan `unknown` + `powod` (HA nie zapisuje atrybutów `unavailable`)."""

    def _atrybuty(self, wynik) -> dict[str, Any]:
        return {
            "okres_od": wynik.od.isoformat(),
            "okres_do": wynik.do.isoformat(),
            "pokrycie": round(wynik.pokrycie, 4),
            "dane_z": self.coordinator.dane_z.isoformat() if self.coordinator.dane_z else None,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        wynik = self.coordinator.data
        return {"powod": POWOD_BRAK_KONCA} if wynik is None else self._atrybuty(wynik)


class KwhSensor(_Sensor):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        wynik = self.coordinator.data
        return None if wynik is None else round(getattr(wynik, self._attr_translation_key), 2)


class ScenariuszSensor(_Sensor):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "PLN"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: TaryfyCoordinator, klucz: str, rodzaj: str) -> None:
        super().__init__(coordinator, f"{klucz}_{rodzaj}", rodzaj)
        self._klucz = klucz
        self._attr_translation_placeholders = {"scenariusz": etykieta(klucz, coordinator.konf)}

    @property
    def native_value(self) -> float | None:
        wynik = self.coordinator.data
        if wynik is None:
            return None
        razem = wynik.scenariusze[self._klucz].razem
        if self._attr_translation_key == "roznica":  # dodatnia = drożej niż obecna taryfa
            razem -= wynik.scenariusze[wynik.obecny].razem
        return round(razem, 2)

    def _atrybuty(self, wynik) -> dict[str, Any]:
        s = wynik.scenariusze[self._klucz]
        return super()._atrybuty(wynik) | {
            "scenariusz": self._klucz,
            "etykieta": etykieta(self._klucz, self.coordinator.konf),
            "grupa": grupa_scenariusza(self._klucz),
            "sprzedawca": sprzedawca_scenariusza(self._klucz, self.coordinator.konf),
            "taryfa": taryfa_scenariusza(self._klucz),
            "obecny": self._klucz == wynik.obecny,
            "sprzedaz_przed": round(s.sprzedaz_przed, 2),
            "tarcza": round(s.tarcza, 2),
            "sprzedaz_po": round(s.sprzedaz_po, 2),
            "dystrybucja": round(s.dystrybucja, 2),
            "netto": round(s.netto, 2),
            "szacunek": s.szacunek,
            "ostrzezenia": list(s.ostrzezenia),
            "kwh_na_strefe": {z: round(v, 2) for z, v in s.kwh_na_strefe.items()},
        }
