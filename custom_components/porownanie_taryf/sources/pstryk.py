"""Klient API Pstryk (unified-metrics) — godzinowe zużycie i koszty. Bez importów HA."""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone

import aiohttp

from ..core import TZ, HourlyReading

API_URL = "https://api.pstryk.pl/integrations/meter-data/unified-metrics/"
OKNO_DNI = 90
_TIMEOUT = aiohttp.ClientTimeout(total=180)
_FMT = "%Y-%m-%dT%H:%M:%SZ"


class PstrykError(Exception):
    """Bazowy błąd klienta Pstryk."""


class PstrykAuthError(PstrykError):
    """401/403 — zły lub cofnięty klucz."""


class PstrykEndpointError(PstrykError):
    """400/404 — endpoint lub parametry nieobsługiwane."""


class PstrykRateLimitError(PstrykError):
    """429 — `retry_after` w sekundach."""

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(f"Pstryk 429, ponów za {retry_after}s")
        self.retry_after = retry_after


class PstrykConnectionError(PstrykError):
    """5xx, błąd sieci lub timeout."""


def parse_frames(payload: dict) -> list[HourlyReading]:
    """Ramki API -> odczyty. Ramki bez odczytu (dziury po stronie OSD) są pomijane,
    `null` w kosztach zostaje `None`."""
    out = []
    for fr in payload.get("frames") or []:
        metrics = fr.get("metrics") or {}
        kwh = (metrics.get("meter_values") or {}).get("energy_active_import_register")
        if kwh is None:
            continue
        cost = metrics.get("cost") or {}
        out.append(
            HourlyReading(
                datetime.fromisoformat(fr["start"]).astimezone(TZ),
                kwh,
                cost.get("energy_cost_net"),
                cost.get("service_cost_net"),
                cost.get("excise"),
            )
        )
    return out


class PstrykClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._key = api_key

    async def pobierz(self, start: datetime, end: datetime) -> list[HourlyReading]:
        """Odczyty z [start, end) (aware); zakres dzielony na okna po OKNO_DNI dni."""
        out: list[HourlyReading] = []
        cursor, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=OKNO_DNI), end)
            # ponytail: 429 w trakcie backfillu gubi już pobrane okna; dołącz częściowy wynik do PstrykRateLimitError,
            # jeśli limit Pstryk wypadnie poniżej ~9 zapytań na Retry-After
            payload = await self._okno(cursor, chunk_end)
            try:
                out += parse_frames(payload)
            except (KeyError, TypeError, ValueError, AttributeError) as err:  # ramka o innym kształcie niż znany
                raise PstrykEndpointError(f"Pstryk: nieoczekiwany kształt ramki ({type(err).__name__})") from err
            cursor = chunk_end
        return out

    async def _okno(self, start: datetime, end: datetime) -> dict:
        # ponytail: bez ponowień — o ponowieniu decyduje coordinator.
        params = {
            "metrics": "meter_values,cost",
            "resolution": "hour",  # for_tz przy hour daje 400
            "window_start": start.strftime(_FMT),
            "window_end": end.strftime(_FMT),
        }
        headers = {"Authorization": self._key, "Accept": "application/json"}  # goły klucz, bez Bearer
        try:
            async with self._session.get(API_URL, params=params, headers=headers, timeout=_TIMEOUT) as resp:
                status = resp.status
                if status == 429:
                    ra = resp.headers.get("Retry-After", "")
                    raise PstrykRateLimitError(int(ra) if ra.isdigit() else 60)
                if status in (401, 403):
                    raise PstrykAuthError(f"Pstryk HTTP {status}")
                if status in (400, 404):
                    raise PstrykEndpointError(f"Pstryk HTTP {status}")
                if status >= 500:
                    raise PstrykConnectionError(f"Pstryk HTTP {status}")
                if status != 200:
                    raise PstrykError(f"Pstryk HTTP {status}")
                payload = await resp.json(content_type=None)
                if not isinstance(payload, dict) or "frames" not in payload:
                    raise PstrykEndpointError("Pstryk: odpowiedź bez pola frames")
                return payload
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise PstrykConnectionError(str(err) or type(err).__name__) from err


def do_magazynu(odczyty: Iterable[HourlyReading]) -> dict[str, list[float | None]]:
    """Odczyty -> JSON-owalny słownik: klucz godziny UTC -> [kwh, energy_net, service_net, excise]."""
    return {
        r.start_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z"): [
            r.kwh,
            r.energy_net,
            r.service_net,
            r.excise,
        ]
        for r in odczyty
    }


def z_magazynu(d: Mapping[str, list]) -> list[HourlyReading]:
    """Odwrotność do_magazynu; posortowane po czasie."""
    return [
        HourlyReading(datetime.fromisoformat(k).astimezone(TZ), *v) for k, v in sorted(d.items())
    ]
