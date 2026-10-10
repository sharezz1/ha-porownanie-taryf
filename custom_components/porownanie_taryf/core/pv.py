"""Wirtualna fotowoltaika (spec v0.8 §3): produkcja połaci, symulacja godzinowa z magazynem,
wycena eksportu (net-billing), zwrot i siatka wariantów. Bez importów HA."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math

from . import TZ, HourlyReading

MNOZNIK_DEPOZYTU = 1.23  # ustawa OZE, od 2025 (W0)
_FMT = "%Y-%m-%dT%H:00:00Z"

Pogoda = Mapping[str, tuple[float, float]]  # klucz godziny UTC -> (GTI W/m², temperatura °C)


@dataclass(frozen=True, slots=True)
class Polac:
    az: float  # od północy: 0 = N, 90 = E
    nachylenie: float
    kwp: float
    cien: float = 0.0  # 0–0,5


@dataclass(frozen=True, slots=True)
class ParametryPV:
    pr: float = 0.85
    gamma: float = -0.0037
    sprawnosc_mag: float = 0.90
    dod: float = 0.90
    degradacja: float = 0.005
    wzrost_cen: float = 0.03
    zwrot_depozytu: float = 0.0
    falownik_rok: int = 12
    falownik_pct: float = 0.10
    magazyn_rok: int = 15
    magazyn_pct: float = 0.70


@dataclass(frozen=True, slots=True)
class Symulacja:
    godziny_po: list[HourlyReading]
    eksport: dict[str, float]
    produkcja: dict[str, float]
    autokonsumpcja: dict[str, float]


def az_open_meteo(az_n: float) -> float:
    """Azymut od północy -> konwencja Open-Meteo (0 = S, −90 = E, 90 = W)."""
    return (az_n % 360) - 180


def klucz_godziny(r: HourlyReading) -> str:
    return r.start_local.astimezone(timezone.utc).strftime(_FMT)


def miesiac_godziny(klucz: str) -> str:
    return datetime.fromisoformat(klucz.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m")


def produkcja(gti: float, temp: float, kwp: float, cien: float, p: ParametryPV) -> float:
    t_ogniwa = temp + 0.031 * gti  # przybliżenie NOCT
    return max(0.0, gti / 1000 * kwp * p.pr * (1 - cien) * (1 + p.gamma * (t_ogniwa - 25)))


def _miesiac(r: HourlyReading) -> str:
    return r.start_local.astimezone(TZ).strftime("%Y-%m")


def uzupelnij_koszty(odczyty: Sequence[HourlyReading]) -> tuple[list[HourlyReading], bool]:
    """`None` w kosztach godziny z poborem -> koszt jednostkowy miesiąca × kWh (bez tego oszczędność na energii znika)."""
    pola = ("energy_net", "service_net", "excise")
    suma: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in odczyty:
        for pole in pola:
            v = getattr(r, pole)
            if v is not None and r.kwh > 0:
                s = suma[(_miesiac(r), pole)]
                s[0] += v
                s[1] += r.kwh
    out, flaga = [], False
    for r in odczyty:
        zmiany = {}
        for pole in pola:
            s = suma.get((_miesiac(r), pole))
            if getattr(r, pole) is None and r.kwh > 0 and s and s[1] > 0:
                zmiany[pole] = s[0] / s[1] * r.kwh
        if zmiany:
            flaga = True
            r = replace(r, **zmiany)
        out.append(r)
    return out, flaga


def skaluj(r: HourlyReading, kwh: float) -> HourlyReading:
    """Pobór po PV; koszty godziny skalowane tym samym współczynnikiem (ceny Pstryka są per kWh)."""
    if r.kwh == 0:
        return r
    f = kwh / r.kwh
    m = lambda v: None if v is None else v * f
    return replace(r, kwh=kwh, energy_net=m(r.energy_net), service_net=m(r.service_net), excise=m(r.excise))


def symuluj(
    odczyty: Sequence[HourlyReading], pogoda: Sequence[Pogoda], polacie: Sequence[Polac], magazyn_kwh: float, p: ParametryPV
) -> Symulacja:
    """`pogoda[i]` należy do `polacie[i]`. Godzina bez GTI którejkolwiek połaci zostaje bez PV.
    Magazyn: tylko nadwyżka PV, start pusty, moc 0,5 C, sprawność √ na kierunek."""
    poj = magazyn_kwh * p.dod
    moc = magazyn_kwh * 0.5
    eta = math.sqrt(p.sprawnosc_mag)
    soc = 0.0
    po, eksport, prod, auto_ = [], {}, {}, {}
    for r in sorted(odczyty, key=lambda x: x.start_local):
        k = klucz_godziny(r)
        if any(k not in pg for pg in pogoda):
            po.append(r)
            continue
        pv = sum(produkcja(*pg[k], pl.kwp, pl.cien, p) for pg, pl in zip(pogoda, polacie))
        auto = min(pv, r.kwh)
        nadwyzka, deficyt = pv - auto, r.kwh - auto
        lad = min(nadwyzka, moc, (poj - soc) / eta) if magazyn_kwh else 0.0
        soc += lad * eta
        roz = min(deficyt, moc, soc * eta) if magazyn_kwh else 0.0
        soc -= roz / eta
        po.append(skaluj(r, deficyt - roz))
        eksport[k], prod[k], auto_[k] = nadwyzka - lad, pv, auto + roz
    return Symulacja(po, eksport, prod, auto_)


def _pol_kwp(x: float) -> float:
    return math.floor(x * 2 + 0.5) / 2  # do 0,5 kWp; nie round() (half-to-even)


def siatka_wariantow(polacie: Sequence[Polac]) -> list[tuple[tuple[Polac, ...], float]]:
    """Rozmiary {50, 75, 100}% sumy maks. kWp (≥ 2 kWp), rozdzielone proporcjonalnie; magazyn {0, 5, 10} kWh."""
    kmax = sum(pl.kwp for pl in polacie)
    if kmax <= 0:
        return []
    rozmiary = sorted({k for k in (_pol_kwp(kmax * u) for u in (0.5, 0.75, 1.0)) if k >= 2})
    return [
        (tuple(replace(pl, kwp=k * pl.kwp / kmax) for pl in polacie), mag)
        for k in rozmiary
        for mag in (0, 5, 10)
    ]


def wartosc_eksportu(eksport: Mapping[str, float], rce: Mapping[str, float]) -> tuple[dict[str, float], bool]:
    """Miesiąc lokalny -> wartość depozytu (zł, × MNOZNIK_DEPOZYTU): godzinowo max(RCE, 0) × eksport (W0, Ruling 8).
    Godzina eksportu bez ceny RCE jest pomijana, a flaga (drugi element) = True."""
    brak = False
    wynik: dict[str, float] = defaultdict(float)
    for k, e in eksport.items():
        if k not in rce:
            brak = True
            continue
        wynik[miesiac_godziny(k)] += max(rce[k], 0.0) * e
    return {m: v * MNOZNIK_DEPOZYTU for m, v in wynik.items()}, brak


def zwrot(koszt_pv: float, koszt_mag: float, oszczednosc: float, p: ParametryPV, lata: int = 20) -> tuple[int | None, float]:
    """(pierwszy rok z bilansem ≥ 0 albo None, bilans nominalny po `lata` latach), z wymianą falownika i magazynu."""
    bilans, pierwszy = -(koszt_pv + koszt_mag), None
    for rok in range(1, lata + 1):
        bilans += oszczednosc * (1 + p.wzrost_cen) ** (rok - 1) * (1 - p.degradacja) ** (rok - 1)
        if rok == p.falownik_rok:
            bilans -= p.falownik_pct * koszt_pv
        if koszt_mag and rok == p.magazyn_rok:
            bilans -= p.magazyn_pct * koszt_mag
        if pierwszy is None and bilans >= 0:
            pierwszy = rok
    return pierwszy, bilans
