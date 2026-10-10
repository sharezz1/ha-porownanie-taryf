"""Ceny RCE z PSE (api.raporty.pse.pl) — zł/kWh na godzinę UTC. Bez importów HA."""

from collections import defaultdict
from datetime import date, datetime, timedelta

import aiohttp

API_URL = "https://api.raporty.pse.pl/api/rce-pln"
OKNO_DNI = 10
_TIMEOUT = aiohttp.ClientTimeout(total=60)


class RceError(Exception):
    """Błąd sieci lub HTTP przy pobieraniu RCE."""


def parsuj_rce(payload: dict) -> dict[str, float]:
    """Okresy (15 min od 30.09.2025, wcześniej 1 h) -> średnia na godzinę. `dtime_utc` = KONIEC okresu."""
    suma: dict[str, float] = defaultdict(float)
    n: dict[str, int] = defaultdict(int)
    for rek in payload.get("value") or []:
        koniec = datetime.fromisoformat(rek["dtime_utc"])
        k = (koniec - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:00:00Z")
        suma[k] += rek["rce_pln"] / 1000
        n[k] += 1
    return {k: suma[k] / n[k] for k in suma}


async def pobierz_rce(session: aiohttp.ClientSession, od: date, do: date, wynik: dict[str, float] | None = None) -> dict[str, float]:
    """Okno po oknie (OKNO_DNI dni). Gdy podano `wynik`, każde udane okno trafia do niego od razu, więc błąd
    późniejszego okna (RceError) nie gubi już pobranych."""
    wynik = {} if wynik is None else wynik
    d = od
    while d <= do:
        koniec = min(d + timedelta(days=OKNO_DNI - 1), do)
        params = {"$filter": f"business_date ge '{d}' and business_date le '{koniec}'", "$first": "20000"}
        try:
            async with session.get(API_URL, params=params, timeout=_TIMEOUT) as resp:
                if resp.status != 200:
                    raise RceError(f"PSE HTTP {resp.status}")
                wynik |= parsuj_rce(await resp.json(content_type=None))
        except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, TypeError, AttributeError) as err:
            raise RceError(str(err) or type(err).__name__) from err
        d = koniec + timedelta(days=1)
    return wynik
