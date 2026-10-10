"""Wynik zakładki PV (spec v0.8 §3.1, kontrakt §6.1 `pv/wyniki`): okno 12 miesięcy, syntetyczne godziny zużycia
w miejsce braków (Ruling 12), rachunek miesięczny przez `policz()`, depozyt i zwrot. Bez importów HA."""

from calendar import monthrange
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone

from . import TZ, HourlyReading
from .presety import Konfiguracja
from .pv import (
    ParametryPV, Pogoda, Polac, klucz_godziny, miesiac_godziny, siatka_wariantow, symuluj, uzupelnij_koszty,
    wartosc_eksportu, zwrot,
)
from .scenariusz import etykieta, godzin_w_okresie, policz

PROG_POKRYCIA = 0.80
MIN_PELNYCH = 6
MIN_POLROCZE = 2
PROG_SYNTETYCZNYCH = 0.20  # udział godzin syntetycznych w miesiącu, powyżej którego ostrzegamy
_LATO = range(4, 10)  # IV–IX
_FMT = "%Y-%m-%dT%H:00:00Z"
_KOSZTY = ("energy_net", "service_net", "excise")
_POMIJANE = ("okres_krotszy_niz_miesiac", "pokrycie_ponizej_95")  # PV ma własne pokrycie


def okno(dzis: date) -> list[str]:
    r, m = dzis.year, dzis.month
    out = []
    for _ in range(12):
        r, m = (r - 1, 12) if m == 1 else (r, m - 1)
        out.append(f"{r}-{m:02d}")
    return out[::-1]


def _zakres(m: str) -> tuple[date, date]:
    r, mm = map(int, m.split("-"))
    return date(r, mm, 1), date(r, mm, monthrange(r, mm)[1])


def _mies(r: HourlyReading) -> str:
    return r.start_local.astimezone(TZ).strftime("%Y-%m")


def _godziny_utc(m: str) -> list[datetime]:
    """Wszystkie prawdziwe godziny miesiąca lokalnego (z DST) jako UTC."""
    od, do = _zakres(m)
    t = datetime(od.year, od.month, od.day, tzinfo=TZ).astimezone(timezone.utc)
    return [t + timedelta(hours=i) for i in range(godzin_w_okresie(od, do))]


def pokrycie_miesiecy(odczyty: Sequence[HourlyReading], pogoda: Sequence[Pogoda], miesiace: Sequence[str]) -> dict[str, float]:
    """Odsetek godzin miesiąca (prawdziwych, z DST) z odczytem Pstryka i GTI wszystkich połaci."""
    n: dict[str, int] = defaultdict(int)
    zb = set(miesiace)
    for r in odczyty:
        m = _mies(r)
        if m in zb and all(klucz_godziny(r) in pg for pg in pogoda):
            n[m] += 1
    return {m: n[m] / godzin_w_okresie(*_zakres(m)) for m in miesiace}


def reprezentatywne(pokrycie: Mapping[str, float]) -> tuple[bool, set[str]]:
    pelne = {m for m, p in pokrycie.items() if p >= PROG_POKRYCIA - 1e-9}
    lato = sum(int(m[5:]) in _LATO for m in pelne)
    return len(pelne) >= MIN_PELNYCH and lato >= MIN_POLROCZE and len(pelne) - lato >= MIN_POLROCZE, pelne


def _jednostkowy(rs: Sequence[HourlyReading], pole: str) -> float | None:
    s = k = 0.0
    for r in rs:
        v = getattr(r, pole)
        if v is not None:
            s, k = s + v, k + r.kwh
    return s / k if k > 0 else None


def syntetyzuj(
    odczyty: Sequence[HourlyReading], pogoda: Sequence[Pogoda], miesiace: Sequence[str], pelne: set[str]
) -> list[HourlyReading]:
    """Odczyty syntetyczne dla godzin okna z GTI wszystkich połaci, a bez odczytu Pstryka (Ruling 12).
    Wzorzec: najbliższy pełny miesiąc wstecz i naprzód (cyklicznie w oknie); kWh = średnia godzin wzorca o tej samej
    lokalnej godzinie doby i typie dnia (roboczy / weekend), koszty = koszt jednostkowy tej grupy × kWh
    (grupa bez kWh: koszt jednostkowy całych miesięcy wzorcowych). Prawdziwe godziny zostają, zwracamy tylko nowe."""
    istniejace = {klucz_godziny(r) for r in odczyty}
    wg_miesiaca: dict[str, list[HourlyReading]] = defaultdict(list)
    for r in odczyty:
        wg_miesiaca[_mies(r)].append(r)
    n, out = len(miesiace), []
    for i, m in enumerate(miesiace):
        brak = [t for t in _godziny_utc(m) if (k := t.strftime(_FMT)) not in istniejace and all(k in pg for pg in pogoda)]
        if not brak:
            continue
        wzorce = {next(miesiace[(i + krok * d) % n] for d in range(1, n) if miesiace[(i + krok * d) % n] in pelne) for krok in (-1, 1)}
        pula = [r for w in wzorce for r in wg_miesiaca[w]]
        grupy: dict[tuple[int, bool], list[HourlyReading]] = defaultdict(list)
        for r in pula:
            lok = r.start_local.astimezone(TZ)
            grupy[(lok.hour, lok.weekday() >= 5)].append(r)
        srednia = sum(r.kwh for r in pula) / len(pula)
        jedn_puli = {pole: _jednostkowy(pula, pole) for pole in _KOSZTY}
        for t in brak:
            lok = t.astimezone(TZ)
            g = grupy.get((lok.hour, lok.weekday() >= 5), [])
            kwh = sum(r.kwh for r in g) / len(g) if g else srednia
            koszty = {}
            for pole in _KOSZTY:
                u = _jednostkowy(g, pole)
                u = jedn_puli[pole] if u is None else u
                koszty[pole] = None if u is None else u * kwh
            out.append(HourlyReading(lok, kwh, **koszty))
    return out


def wyniki(
    wszystkie: Sequence[HourlyReading], konf: Konfiguracja, polacie_max: Sequence[Polac], pogoda: Sequence[Pogoda],
    rce: Mapping[str, float], koszt_kwp: float, koszt_kwh_mag: float, p: ParametryPV, dzis: date,
) -> dict:
    warianty_def = siatka_wariantow(polacie_max)
    if not warianty_def:
        return {"schema": 1, "stan": "brak_konfigu"}
    if not all(pogoda):
        return {"schema": 1, "stan": "brak_pogody"}
    if not rce:
        return {"schema": 1, "stan": "brak_rce"}
    uzup, szacowane = uzupelnij_koszty(wszystkie)
    mies = okno(dzis)
    zb_mies = set(mies)
    # Godziny okna bez GTI którejkolwiek połaci wypadają: rachunek przed/po i skalowanie ×1/pokrycie liczą ten sam zbiór.
    uzup = [r for r in uzup if _mies(r) not in zb_mies or all(klucz_godziny(r) in pg for pg in pogoda)]
    pokr = pokrycie_miesiecy(uzup, pogoda, mies)  # prawdziwe pokrycie Pstryka: próg reprezentatywności i pole wyniku
    ok, pelne = reprezentatywne(pokr)
    if not ok:
        return {"schema": 1, "stan": "za_malo_danych", "miesiace_danych": len(pelne)}

    przed_m: dict[str, list[HourlyReading]] = defaultdict(list)
    for r in uzup:
        if _mies(r) in zb_mies:
            przed_m[_mies(r)].append(r)
    syn: dict[str, int] = defaultdict(int)
    for r in syntetyzuj([r for m in mies for r in przed_m[m]], pogoda, mies, pelne):
        przed_m[_mies(r)].append(r)
        syn[_mies(r)] += 1
    # Pokrycie po syntezie = godziny z GTI / godziny miesiąca; skalujemy ×1/pokrycie tylko za ogon bez GTI.
    skala = {m: godzin_w_okresie(*_zakres(m)) / len(przed_m[m]) if przed_m[m] else 0.0 for m in mies}
    if not all(skala.values()):
        return {"schema": 1, "stan": "brak_pogody"}
    ostrz: set[str] = set()
    if szacowane:
        ostrz.add("pv_koszt_szacowany")
    ostrz |= {f"pv_miesiac_uzupelniony:{m}" for m in mies if syn[m] / len(przed_m[m]) > PROG_SYNTETYCZNYCH}

    # `policz` dostaje tylko godziny danego miesiąca: Tarcza bierze z `wszystkie` wyłącznie miesiące okresu, wynik ten sam.
    przed: dict[str, float] = {}
    pobor_przed: dict[str, float] = {}
    for m in mies:
        wyn = policz(przed_m[m], *_zakres(m), konf)
        s = wyn.scenariusze[wyn.obecny]
        ostrz |= {o for o in s.ostrzezenia if not o.startswith(_POMIJANE)}
        przed[m] = s.razem * skala[m]
        pobor_przed[m] = sum(r.kwh for r in przed_m[m]) * skala[m]
    obecny = f"pstryk_{konf.obecna_taryfa}"
    w_oknie = [r for m in mies for r in przed_m[m]]

    warianty = []
    for polacie, mag in warianty_def:
        sym = symuluj(w_oknie, pogoda, polacie, mag, p)
        po = {klucz_godziny(r): r for r in sym.godziny_po}
        wart, brak_rce = wartosc_eksportu(sym.eksport, rce)
        if brak_rce:
            ostrz.add("pv_brak_rce")
        sumy = defaultdict(lambda: defaultdict(float))
        for k, v in sym.eksport.items():
            sumy[miesiac_godziny(k)]["eksport"] += v
        for k, v in sym.produkcja.items():
            sumy[miesiac_godziny(k)]["produkcja"] += v
        for k, v in sym.autokonsumpcja.items():
            sumy[miesiac_godziny(k)]["auto"] += v
        ag: dict[str, dict[str, float]] = {}
        for m in mies:
            od, do = _zakres(m)
            godz_po = [po[klucz_godziny(r)] for r in przed_m[m]]
            s_po = policz(godz_po, od, do, konf).scenariusze[obecny]
            f = skala[m]
            ag[m] = {
                "roznica": przed[m] - s_po.razem * f,
                "limit": max(0.0, s_po.razem) * f,  # W0, Ruling 9: depozyt i Bonus pokrywają całą fakturę miesiąca (energia, dystrybucja, opłaty)
                "wartosc": wart.get(m, 0.0) * f,
                "eksport": sumy[m]["eksport"] * f,
                "produkcja": sumy[m]["produkcja"] * f,
                "auto": sumy[m]["auto"] * f,
                "pobor_po": sum(r.kwh for r in godz_po) * f,
            }
        suma = lambda k: sum(ag[m][k] for m in mies)
        # Ruling 18: depozyt/Bonus u Pstryka nie wygasa, więc bilans długookresowy (wynik niezależny od miesiąca startu okna)
        zuzyty, reszta = min(suma("wartosc"), suma("limit")), max(0.0, suma("wartosc") - suma("limit"))
        oszcz = suma("roznica") + zuzyty + p.zwrot_depozytu * reszta
        kwp = sum(pl.kwp for pl in polacie)
        koszt_pv, koszt_mag = koszt_kwp * kwp, koszt_kwh_mag * mag
        lata, bilans = zwrot(koszt_pv, koszt_mag, oszcz, p)
        prod = suma("produkcja")
        pobor0 = sum(pobor_przed.values())
        warianty.append({
            "id": f"{kwp:.1f}-{mag:g}",
            "kwp": [{"az": pl.az, "kwp": round(pl.kwp, 2)} for pl in polacie],
            "magazyn_kwh": mag,
            "koszt": round(koszt_pv + koszt_mag, 2),
            "produkcja_kwh": round(prod, 1),
            "autokonsumpcja": round(suma("auto") / prod, 4) if prod else 0.0,
            "pobor_vs_dzis": round(suma("pobor_po") / pobor0, 4) if pobor0 else 1.0,
            "eksport_kwh": round(suma("eksport"), 1),
            "oszczednosc_rok": round(oszcz, 2),
            "zwrot_lata": lata,
            "bilans_20_lat": round(bilans, 2),
            "depozyt_niewykorzystany": round(reszta, 2),
        })

    od0, do0 = _zakres(mies[0])[0], _zakres(mies[-1])[1]
    return {
        "schema": 1, "stan": "ok", "od": od0.isoformat(), "do": do0.isoformat(),
        "pokrycie": {m: round(pokr[m], 4) for m in mies},
        "baza": {"etykieta": etykieta(obecny, konf), "razem_rok": round(sum(przed.values()), 2)},
        "warianty": warianty,
        "ostrzezenia": sorted(ostrz),
    }
