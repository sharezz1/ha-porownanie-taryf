"""Dach z adresu (spec v0.8 §4): geokoder GUGiK, NMPT 0,5 m z Geoportalu (WCS), połacie z gradientu. Bez importów HA, bez numpy."""

import asyncio
from dataclasses import dataclass
import math
import time

import aiohttp

UUG_URL = "https://services.gugik.gov.pl/uug/"
WCS_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMPT/GRID1/WCS/DigitalSurfaceModel"
POKRYCIA = ("DSM_PL-KRON86-NH", "DSM_PL-EVRF2007-NH")  # KRON86 odpowiadał częściej (pomiar 2026-10-09)
MIN_WYS, NACHYLENIE, MIN_UDZIAL, MAX_POLACI = 2.5, (12.0, 65.0), 0.15, 4


@dataclass(frozen=True, slots=True)
class Punkt:
    adres: str
    e: float
    n: float
    lat: float
    lon: float


async def _uug(session: aiohttp.ClientSession, params: dict) -> dict | None:
    async with session.get(UUG_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            return None
        dane = await resp.json(content_type=None)
    wyniki = dane.get("results") or {}
    return wyniki.get("1")


async def geokoduj(session: aiohttp.ClientSession, adres: str) -> Punkt | None:
    try:
        pl = await _uug(session, {"request": "GetAddress", "address": adres, "srid": "2180"})
        wgs = await _uug(session, {"request": "GetAddress", "address": adres, "srid": "4326"})
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return None
    if not pl or not wgs:
        return None
    return Punkt(adres, float(pl["x"]), float(pl["y"]), float(wgs["y"]), float(wgs["x"]))


async def adres_z_lokalizacji(session: aiohttp.ClientSession, lat: float, lon: float) -> str | None:
    try:
        r = await _uug(session, {"request": "GetAddressReverse", "location": f"POINT({lon} {lat})", "srid": "4326"})
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return None
    if not r:
        return None
    return f"{r['city']}, {r['street']} {r['number']}" if r.get("street") else f"{r['city']} {r['number']}"


def wczytaj_aaigrid(tekst: str) -> tuple[list[list[float]], float]:
    tekst = tekst[tekst.index("ncols"):]
    linie = tekst.splitlines()
    nag, i = {}, 0
    while linie[i].split()[0].lower() in ("ncols", "nrows", "xllcorner", "yllcorner", "cellsize", "nodata_value"):
        k, v = linie[i].split()[:2]
        nag[k.lower()] = float(v)
        i += 1
    dane = []
    for l in linie[i:]:
        if l.startswith("--"):  # koniec części MIME; dalej nagłówki kolejnej części
            break
        dane.append(l)
    wart = [float(x) for l in dane for x in l.split()]
    nc, nr = int(nag["ncols"]), int(nag["nrows"])
    nodata = nag.get("nodata_value")
    z = [[math.nan if wart[w * nc + k] == nodata else wart[w * nc + k] for k in range(nc)] for w in range(nr)]
    return z, nag["cellsize"]


async def pobierz_nmpt(session: aiohttp.ClientSession, e: float, n: float, limit_s: float = 360) -> tuple[list[list[float]], float] | None:
    """Wycinek ±20 m. WCS: oś x = WSCHÓD (odwrotna kolejność cicho zwraca teren z innego miejsca)."""
    koniec = time.monotonic() + limit_s
    while time.monotonic() < koniec:
        for cov in POKRYCIA:
            zostalo = koniec - time.monotonic()
            if zostalo <= 0:
                return None
            params = {
                "SERVICE": "WCS", "VERSION": "2.0.1", "REQUEST": "GetCoverage", "FORMAT": "image/x-aaigrid",
                "COVERAGEID": cov, "SUBSET": [f"x({e - 20:.0f},{e + 20:.0f})", f"y({n - 20:.0f},{n + 20:.0f})"],
            }
            try:
                async with session.get(WCS_URL, params=_lista(params), timeout=aiohttp.ClientTimeout(total=min(120, zostalo))) as resp:
                    tekst = (await resp.read()).decode("latin-1")
                if "ncols" in tekst:
                    return wczytaj_aaigrid(tekst)
            except (aiohttp.ClientError, TimeoutError, ValueError):
                pass
        await asyncio.sleep(5)
    return None


def _lista(params: dict) -> list[tuple[str, str]]:
    """aiohttp: powtórzony klucz SUBSET jako lista par."""
    return [(k, x) for k, v in params.items() for x in (v if isinstance(v, list) else [v])]


def _percentyl(wart: list[float], q: float) -> float:
    s = sorted(wart)
    poz = (len(s) - 1) * q / 100
    d = math.floor(poz)
    return s[d] + (s[min(d + 1, len(s) - 1)] - s[d]) * (poz - d)


def _pochodna(z: list[list[float]], i: int, j: int, krok: float) -> tuple[float, float]:
    """(dz/dwiersz, dz/dkolumna) jak np.gradient: centralnie w środku, jednostronnie na brzegu."""
    nr, nc = len(z), len(z[0])
    def d(a, b, odl):
        return (a - b) / (odl * krok)
    dw = d(z[i + 1][j], z[i - 1][j], 2) if 0 < i < nr - 1 else (d(z[1][j], z[0][j], 1) if i == 0 else d(z[i][j], z[i - 1][j], 1))
    dk = d(z[i][j + 1], z[i][j - 1], 2) if 0 < j < nc - 1 else (d(z[i][1], z[i][0], 1) if j == 0 else d(z[i][j], z[i][j - 1], 1))
    return dw, dk


def polacie(z: list[list[float]], krok: float) -> list[tuple[int, int, int]]:
    """[(azymut od N, nachylenie, powierzchnia m²)], największa pierwsza. Wiersz 0 = północ."""
    plaskie = [v for w in z for v in w if not math.isnan(v)]
    if not plaskie:
        return []
    grunt = _percentyl(plaskie, 5)
    kier, nach = [], []
    for i, w in enumerate(z):
        for j, v in enumerate(w):
            if math.isnan(v) or v - grunt <= MIN_WYS:
                continue
            dw, dk = _pochodna(z, i, j, krok)
            if math.isnan(dw) or math.isnan(dk):
                continue
            s = math.degrees(math.atan(math.hypot(dk, dw)))
            if NACHYLENIE[0] < s < NACHYLENIE[1]:
                kier.append(math.degrees(math.atan2(-dk, dw)) % 360)  # połać patrzy przeciwnie do wzrostu wysokości
                nach.append(s)
    if len(kier) < 20:
        return []
    wynik, wolne = [], [True] * len(kier)
    while sum(wolne) > MIN_UDZIAL * len(kier) and len(wynik) < MAX_POLACI:
        hist = [0] * 36
        for k, w in zip(kier, wolne):
            if w:
                hist[min(int(k // 10), 35)] += 1
        srodek = (hist.index(max(hist)) + 0.5) * 10
        grupa = [w and abs((k - srodek + 180) % 360 - 180) < 25 for k, w in zip(kier, wolne)]
        ile = sum(grupa)
        if ile < MIN_UDZIAL * len(kier):
            break
        sx = sum(math.sin(math.radians(k)) for k, g in zip(kier, grupa) if g) / ile
        cx = sum(math.cos(math.radians(k)) for k, g in zip(kier, grupa) if g) / ile
        az = math.degrees(math.atan2(sx, cx)) % 360
        med = sorted(s for s, g in zip(nach, grupa) if g)
        mediana = med[ile // 2] if ile % 2 else (med[ile // 2 - 1] + med[ile // 2]) / 2
        pow_ = ile * krok**2 / math.cos(math.radians(mediana))
        wynik.append((round(az), round(mediana), round(pow_)))
        wolne = [w and not g for w, g in zip(wolne, grupa)]
    return wynik
