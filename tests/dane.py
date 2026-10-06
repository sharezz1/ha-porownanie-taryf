"""Syntetyczne dane godzinowe dla testów."""

from datetime import datetime, timedelta, timezone

from custom_components.porownanie_taryf.core import TZ, HourlyReading


def godziny(
    start: datetime,
    n: int,
    kwh: float = 1.0,
    e: float = 0.50,
    s: float = 0.08,
    x: float = 0.005,
) -> list[HourlyReading]:
    """n kolejnych godzin od `start` (krok 1 h w UTC, więc dni DST mają 23/25 h)."""
    utc = start.astimezone(timezone.utc)
    return [
        HourlyReading(
            start_local=(utc + timedelta(hours=i)).astimezone(TZ),
            kwh=kwh,
            energy_net=e,
            service_net=s,
            excise=x,
        )
        for i in range(n)
    ]


def wrzesien(n: int = 720, **kw) -> list[HourlyReading]:
    return godziny(datetime(2026, 9, 1, tzinfo=TZ), n, **kw)
