"""Open-Meteo Archive: nasłonecznienie na płaszczyznę połaci (GTI) i temperatura. Bez importów HA."""

from datetime import date, datetime, timedelta

import aiohttp

API_URL = "https://archive-api.open-meteo.com/v1/archive"
_TIMEOUT = aiohttp.ClientTimeout(total=60)


class PogodaError(Exception):
    """Błąd sieci lub HTTP Open-Meteo."""


def parsuj_gti(payload: dict) -> dict[str, tuple[float, float]]:
    """Promieniowanie Open-Meteo = średnia z POPRZEDZAJĄCEJ godziny: etykieta t -> godzina startująca t − 1 h."""
    h = payload["hourly"]
    out = {}
    for t, gti, temp in zip(h["time"], h["global_tilted_irradiance"], h["temperature_2m"]):
        if gti is None:
            continue
        start = datetime.fromisoformat(t) - timedelta(hours=1)
        out[start.strftime("%Y-%m-%dT%H:00:00Z")] = (float(gti), float(temp) if temp is not None else 10.0)
    return out


async def pobierz_gti(
    session: aiohttp.ClientSession, lat: float, lon: float, nachylenie: float, az_om: float, od: date, do: date
) -> dict[str, tuple[float, float]]:
    params = {
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
        "start_date": od.isoformat(), "end_date": do.isoformat(),
        "hourly": "global_tilted_irradiance,temperature_2m",
        "tilt": str(round(nachylenie)), "azimuth": str(round(az_om)), "timezone": "GMT",
    }
    try:
        async with session.get(API_URL, params=params, timeout=_TIMEOUT) as resp:
            if resp.status != 200:
                raise PogodaError(f"Open-Meteo HTTP {resp.status}")
            return parsuj_gti(await resp.json(content_type=None))
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, TypeError, AttributeError) as err:
        raise PogodaError(str(err) or type(err).__name__) from err
