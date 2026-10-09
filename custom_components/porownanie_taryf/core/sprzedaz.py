"""Koszt sprzedaży energii: rzeczywisty z API Pstryk (§5.3) i z własnego cennika (§5.5)."""

from collections.abc import Sequence
from dataclasses import dataclass

from . import HourlyReading
from .dystrybucja import udzial_miesiecy
from .presety import Cennik
from .strefy import strefa


@dataclass(frozen=True, slots=True)
class WynikSprzedazy:
    brutto: float
    netto: float


def sprzedaz_pstryk(odczyty: Sequence[HourlyReading], vat: float) -> WynikSprzedazy:
    """Akcyza poza podstawą VAT; `None` w kosztach liczony jako 0."""
    podstawa = sum((r.energy_net or 0.0) + (r.service_net or 0.0) for r in odczyty)
    akcyza = sum(r.excise or 0.0 for r in odczyty)
    return WynikSprzedazy(podstawa * (1 + vat) + akcyza, podstawa + akcyza)


def sprzedaz_cennik(
    odczyty: Sequence[HourlyReading],
    taryfa: str,
    cennik: Cennik,
    tanie_g12: frozenset[int],
    vat: float,
) -> WynikSprzedazy:
    ceny = cennik.ceny[taryfa]
    podstawa = sum(r.kwh * ceny[strefa(taryfa, r.start_local, tanie_g12)] for r in odczyty)
    podstawa += cennik.oplata_mc * udzial_miesiecy(odczyty)
    akcyza = cennik.akcyza * sum(r.kwh for r in odczyty)
    # akcyza netto wchodzi do podstawy VAT (art. 29a ust. 6 ustawy o VAT)
    return WynikSprzedazy((podstawa + akcyza) * (1 + vat), podstawa + akcyza)
