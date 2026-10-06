"""Tarcza Pstryk (spec §5.4): średnia z całego miesiąca, rabat przypisany do okresu wg kWh."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from . import TZ, HourlyReading
from .presety import ParametryTarczy
from .strefy import godzin_w_miesiacu


@dataclass(frozen=True, slots=True)
class WynikTarczy:
    rabat: float  # brutto, >= 0
    rabat_netto: float
    szacunek: bool  # któryś miesiąc okresu jest w magazynie niepełny
    ostrzezenia: tuple[str, ...]


def _miesiac(r: HourlyReading) -> tuple[int, int]:
    t = r.start_local.astimezone(TZ)
    return t.year, t.month


def tarcza(
    okres: Sequence[HourlyReading],
    wszystkie: Sequence[HourlyReading],
    presety: Sequence[ParametryTarczy],
    vat: float,
) -> WynikTarczy:
    miesiace: dict[tuple[int, int], list[HourlyReading]] = defaultdict(list)
    for r in wszystkie:
        miesiace[_miesiac(r)].append(r)
    kwh_okresu: dict[tuple[int, int], float] = defaultdict(float)
    for r in okres:
        kwh_okresu[_miesiac(r)] += r.kwh

    rabat, szacunek, ostrzezenia = 0.0, False, set()
    for (rok, mies), kwh_w_okresie in kwh_okresu.items():
        p = next((p for p in presety if p.od <= date(rok, mies, 1) <= p.do), None)
        if p is None:  # rabat 0 jest pewny, więc bez flagi szacunku
            ostrzezenia.add(f"brak_tarczy:{rok}-{mies:02d}")
            continue
        if not p.zweryfikowany:
            ostrzezenia.add(f"tarcza_niezweryfikowana:{p.od.year}")
        m = miesiace[(rok, mies)]
        szacunek |= len(m) < godzin_w_miesiacu(rok, mies)
        kwh = sum(r.kwh for r in m)
        if kwh <= 0:
            continue
        baza = sum(
            (r.energy_net or 0.0) + ((r.service_net or 0.0) if p.obejmuje_obsluge else 0.0)
            for r in m
        )
        brutto = p.podstawa == "brutto"
        avg = (1 + vat if brutto else 1.0) * baza / kwh
        rabat_m = max(0.0, avg - p.limit) * kwh * (1.0 if brutto else 1 + vat)
        rabat += rabat_m * kwh_w_okresie / kwh

    return WynikTarczy(rabat, rabat / (1 + vat), szacunek, tuple(sorted(ostrzezenia)))
