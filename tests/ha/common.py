"""Wspólne pomocniki testów nakładki HA."""

from typing import Any

from custom_components.porownanie_taryf.const import DOMAIN
from custom_components.porownanie_taryf.core import HourlyReading
from custom_components.porownanie_taryf.sources.pstryk import do_magazynu

DATA_WPISU = {
    "api_key": "sk-test",
    "uklad": "3f",
    "preset": "enea_2026",
    "taryfa": "G12",
    "tanie_g12": [22, 23, 0, 1, 2, 3, 4, 5, 13, 14],
}


def zapisz_magazyn(
    hass_storage: dict[str, Any],
    entry_id: str,
    odczyty: list[HourlyReading],
    dane_z: str | None = None,
) -> None:
    """Magazyn godzin wpisu w kształcie, w jakim zapisuje go coordinator."""
    klucz = f"{DOMAIN}.{entry_id}.hourly"
    hass_storage[klucz] = {
        "version": 1,
        "minor_version": 1,
        "key": klucz,
        "data": {"godziny": do_magazynu(odczyty), "dane_z": dane_z},
    }
