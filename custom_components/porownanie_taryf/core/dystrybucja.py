"""Koszt dystrybucji (spec §5.2) i wspólny udział opłat miesięcznych."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from . import TZ, HourlyReading
from .presety import STREFY, StawkiDystrybucji
from .strefy import godzin_w_miesiacu, strefa


@dataclass(frozen=True, slots=True)
class WynikDystrybucji:
    brutto: float
    netto: float
    kwh_na_strefe: dict[str, float]


def udzial_miesiecy(odczyty: Sequence[HourlyReading]) -> float:
    """Σ_m (zmierzone godziny m / wszystkie godziny m) — mnożnik opłat zł/mc."""
    # ponytail: godzina z odczytem niesie 1/N opłaty swojego miesiąca (jak w energia/taryfy.py)
    mies = Counter((t.year, t.month) for t in (r.start_local.astimezone(TZ) for r in odczyty))
    return sum(n / godzin_w_miesiacu(rok, m) for (rok, m), n in mies.items())


def dystrybucja(
    odczyty: Sequence[HourlyReading],
    taryfa: str,
    stawki: StawkiDystrybucji,
    tanie_g12: frozenset[int],
    vat: float,
) -> WynikDystrybucji:
    kwh_na_strefe = dict.fromkeys(STREFY[taryfa], 0.0)
    for r in odczyty:
        kwh_na_strefe[strefa(taryfa, r.start_local, tanie_g12)] += r.kwh
    wspolne = stawki.sosj + stawki.oze + stawki.kog
    zmienny = sum(kwh * (stawki.zmienne[taryfa][s] + wspolne) for s, kwh in kwh_na_strefe.items())
    staly = (stawki.stale[taryfa] + stawki.abonament + stawki.moc) * udzial_miesiecy(odczyty)
    netto = zmienny + staly
    return WynikDystrybucji(netto * (1 + vat), netto, kwh_na_strefe)
