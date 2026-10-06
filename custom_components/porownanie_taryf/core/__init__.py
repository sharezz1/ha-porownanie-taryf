"""Czysty rdzeń obliczeń (bez zależności od platformy HA)."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")


@dataclass(frozen=True, slots=True)
class HourlyReading:
    start_local: datetime  # aware, TZ
    kwh: float
    energy_net: float | None = None
    service_net: float | None = None
    excise: float | None = None
