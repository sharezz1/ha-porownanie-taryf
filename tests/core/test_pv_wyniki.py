from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

import pytest

from custom_components.porownanie_taryf.core import TZ, HourlyReading
from custom_components.porownanie_taryf.core.presety import zbuduj_konfiguracje
from custom_components.porownanie_taryf.core.pv import ParametryPV, Polac, klucz_godziny, produkcja, siatka_wariantow, symuluj, wartosc_eksportu
from custom_components.porownanie_taryf.core.pv_wyniki import okno, pokrycie_miesiecy, reprezentatywne, syntetyzuj, wyniki
from custom_components.porownanie_taryf.core.scenariusz import policz
from custom_components.porownanie_taryf.core.strefy import TANIE_G12_DOMYSLNE

KONF = zbuduj_konfiguracje({"uklad": "3f", "preset": "enea_2026", "taryfa": "G12", "tanie_g12": sorted(TANIE_G12_DOMYSLNE)}, {})


def rok_syntetyczny(od=datetime(2025, 9, 30, 22, tzinfo=timezone.utc), do=datetime(2026, 9, 30, 22, tzinfo=timezone.utc), pomin=()):
    """Godziny: 1 kWh/h, energia 0,50 zł/kWh netto, obsługa 0,08, akcyza 0,005. GTI: 600 W/m² w 10–14 UTC."""
    odczyty, gti, rce = [], {}, {}
    t = od
    while t < do:
        lok = t.astimezone(TZ)
        if lok.strftime("%Y-%m") not in pomin:
            odczyty.append(HourlyReading(lok, 1.0, 0.5, 0.08, 0.005))
        k = t.strftime("%Y-%m-%dT%H:00:00Z")
        gti[k] = (600.0 if 10 <= t.hour < 14 else 0.0, 15.0)
        rce[k] = 0.30
        t += timedelta(hours=1)
    return odczyty, gti, rce


def test_okno():
    assert okno(date(2026, 10, 9)) == [f"2025-{m}" for m in ("10", "11", "12")] + [f"2026-{m:02d}" for m in range(1, 10)]


def test_pokrycie_zmiana_czasu_marzec_kompletny():
    o, g, _ = rok_syntetyczny()
    p = pokrycie_miesiecy(o, [g], okno(date(2026, 10, 9)))
    assert p["2026-03"] == pytest.approx(1.0) and p["2025-10"] == pytest.approx(1.0)


def test_pokrycie_spada_gdy_brak_gti_na_koncu():
    o, g, _ = rok_syntetyczny()
    g = {k: v for k, v in g.items() if k < "2026-09-26"}
    p = pokrycie_miesiecy(o, [g], okno(date(2026, 10, 9)))
    assert p["2026-09"] == pytest.approx(25 / 30, abs=0.01)


def test_prog_reprezentatywnosci():
    pelne = {m: 1.0 for m in ("2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07")}
    ok, zb = reprezentatywne(pelne | {"2025-12": 0.69})
    assert ok and "2025-12" not in zb
    ok, _ = reprezentatywne({m: 1.0 for m in ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09")})
    assert not ok  # brak X–III
    ok, _ = reprezentatywne({"2026-03": 0.8, "2026-02": 0.799} | {m: 1.0 for m in ("2025-12", "2026-06", "2026-07", "2026-08", "2026-09")})
    assert ok  # 0,8 liczy się, 0,799 nie: 6 pełnych


def test_brak_konfigu():
    o, g, r = rok_syntetyczny()
    w = wyniki(o, KONF, [Polac(180, 35, 0)], [g], r, 3000, 2000, ParametryPV(), date(2026, 10, 9))
    assert w == {"schema": 1, "stan": "brak_konfigu"}


def test_za_malo_danych():
    o, g, r = rok_syntetyczny(od=datetime(2026, 5, 31, 22, tzinfo=timezone.utc))
    w = wyniki(o, KONF, [Polac(180, 35, 6)], [g], r, 3000, 2000, ParametryPV(), date(2026, 10, 9))
    assert w["stan"] == "za_malo_danych" and w["miesiace_danych"] == 4


def test_wynik_ok_spojny():
    o, g, r = rok_syntetyczny(pomin=("2026-01",))
    w = wyniki(o, KONF, [Polac(180, 35, 6)], [g], r, 3000, 2000, ParametryPV(), date(2026, 10, 9))
    assert w["stan"] == "ok" and w["schema"] == 1 and len(w["warianty"]) == 9
    assert "pv_miesiac_uzupelniony:2026-01" in w["ostrzezenia"]
    bez_mag = {v["kwp"][0]["kwp"]: v for v in w["warianty"] if v["magazyn_kwh"] == 0}
    assert bez_mag[6.0]["oszczednosc_rok"] > bez_mag[3.0]["oszczednosc_rok"] > 0
    for v in w["warianty"]:
        assert 0 <= v["autokonsumpcja"] <= 1 and 0 <= v["pobor_vs_dzis"] <= 1
        assert v["koszt"] == pytest.approx(3000 * sum(x["kwp"] for x in v["kwp"]) + 2000 * v["magazyn_kwh"])
    z_mag = [v for v in w["warianty"] if v["kwp"][0]["kwp"] == 6.0 and v["magazyn_kwh"] == 10][0]
    assert z_mag["autokonsumpcja"] > bez_mag[6.0]["autokonsumpcja"]


def _wyniki_6kwp(o, g, r):
    return wyniki(o, KONF, [Polac(180, 35, 6)], [g], r, 3000, 2000, ParametryPV(), date(2026, 10, 9))


def test_ogon_gti_nie_zmienia_wyniku():
    """Godziny Pstryka bez GTI wypadają z rachunku, więc skalowanie ×1/pokrycie nie liczy ich podwójnie."""
    o, g, r = rok_syntetyczny()
    pelne = _wyniki_6kwp(o, g, r)
    obciete = _wyniki_6kwp(o, {k: v for k, v in g.items() if k < "2026-09-26"}, r)
    assert obciete["pokrycie"]["2026-09"] == pytest.approx(25 / 30, abs=0.01)
    assert obciete["baza"]["razem_rok"] == pytest.approx(pelne["baza"]["razem_rok"], abs=1.0)
    wariant = lambda w: next(v for v in w["warianty"] if v["magazyn_kwh"] == 0 and v["kwp"][0]["kwp"] == 6.0)
    assert wariant(obciete)["oszczednosc_rok"] == pytest.approx(wariant(pelne)["oszczednosc_rok"], abs=1.0)


def test_baza_rok_to_suma_miesiecy():
    o, g, r = rok_syntetyczny()
    w = _wyniki_6kwp(o, g, r)
    assert set(w["pokrycie"].values()) == {1.0}
    oczekiwane = 0.0
    for m in okno(date(2026, 10, 9)):
        r_, mm = map(int, m.split("-"))
        wyn = policz(o, date(r_, mm, 1), date(r_, mm, monthrange(r_, mm)[1]), KONF)
        oczekiwane += wyn.scenariusze[wyn.obecny].razem
    assert w["baza"]["razem_rok"] == pytest.approx(oczekiwane, abs=0.01)


def test_depozyt_dlugookresowy_reszta_to_nadwyzka_wartosci_nad_rachunkami():
    """Ruling 18: reszta = max(0, Σ wartość − Σ limit), limit miesiąca = max(0, razem_po); przewymiarowana instalacja ją zostawia."""
    o, g, r = rok_syntetyczny()
    w = wyniki(o, KONF, [Polac(180, 35, 30)], [g], r, 3000, 2000, ParametryPV(), date(2026, 10, 9))
    assert w["warianty"][-1]["depozyt_niewykorzystany"] > 0
    # niezależnie: ostatni wariant (największy)
    polacie, mag = siatka_wariantow([Polac(180, 35, 30)])[-1]
    sym = symuluj(o, [g], polacie, mag, ParametryPV())
    po = {klucz_godziny(x): x for x in sym.godziny_po}
    razem = 0.0
    for m in okno(date(2026, 10, 9)):
        r_, mm = map(int, m.split("-"))
        godz = [x for x in o if x.start_local.strftime("%Y-%m") == m]
        wyn = policz([po[klucz_godziny(x)] for x in godz], date(r_, mm, 1), date(r_, mm, monthrange(r_, mm)[1]), KONF)
        razem += max(0.0, wyn.scenariusze[wyn.obecny].razem)
    wartosc = sum(wartosc_eksportu(sym.eksport, r)[0].values())
    assert w["warianty"][-1]["depozyt_niewykorzystany"] == pytest.approx(max(0.0, wartosc - razem), abs=0.02)


def test_oszczednosc_nie_zalezy_od_miesiaca_startu_okna():
    """Ruling 18: depozyt nie wygasa, więc przesunięcie okna o pół roku (sezonowość!) nie zmienia oszczędności."""
    od = datetime(2025, 3, 31, 22, tzinfo=timezone.utc)
    o, g, r = rok_syntetyczny(od=od, do=datetime(2026, 9, 30, 22, tzinfo=timezone.utc))
    o = [HourlyReading(x.start_local, 0.3, 0.40 * 0.3, 0.08 * 0.3, 0.005 * 0.3) for x in o]  # mały odbiorca; cena poniżej limitu Tarczy, więc rabat nie zaburza porównania
    zimowe = {1, 2, 3, 10, 11, 12}
    g = {k: ((v[0] * 0.15 if int(k[5:7]) in zimowe else v[0]), v[1]) for k, v in g.items()}
    oszcz = lambda dzis: next(
        v for v in wyniki(o, KONF, [Polac(180, 35, 15)], [g], r, 3000, 2000, ParametryPV(), dzis)["warianty"]
        if v["magazyn_kwh"] == 0 and v["kwp"][0]["kwp"] == 15.0)["oszczednosc_rok"]
    assert oszcz(date(2026, 4, 9)) == pytest.approx(oszcz(date(2026, 10, 9)), abs=1.0)


def test_pusta_seria_jednej_polaci_to_brak_pogody():
    o, g, r = rok_syntetyczny()
    w = wyniki(o, KONF, [Polac(180, 35, 3), Polac(90, 35, 3)], [g, {}], r, 3000, 2000, ParametryPV(), date(2026, 10, 9))
    assert w == {"schema": 1, "stan": "brak_pogody"}


def _godziny(m_od, m_do, kwh, koszt, dni=None):
    """Odczyty miesięcy m_od..m_do (włącznie); kwh = kwh(lok), koszt energii jednostkowy stały."""
    out, t = [], datetime(2026, m_od, 1, tzinfo=TZ).astimezone(timezone.utc)
    koniec = datetime(2026, m_do + 1, 1, tzinfo=TZ).astimezone(timezone.utc)
    while t < koniec:
        lok = t.astimezone(TZ)
        if dni is None or lok.day <= dni:
            k = kwh(lok)
            out.append(HourlyReading(lok, k, koszt * k, 0.08 * k, 0.005 * k))
        t += timedelta(hours=1)
    return out


def _gti(m_od, m_do):
    t, koniec = datetime(2026, m_od, 1, tzinfo=TZ).astimezone(timezone.utc), datetime(2026, m_do + 1, 1, tzinfo=TZ).astimezone(timezone.utc)
    g = {}
    while t < koniec:
        g[t.strftime("%Y-%m-%dT%H:00:00Z")] = (100.0, 10.0)
        t += timedelta(hours=1)
    return g


def test_syntetyzuj_wzorzec_godzina_i_typ_dnia():
    """Kwiecień: prawdziwe tylko dni 1–10; reszta z marca i maja (ta sama godzina doby i typ dnia)."""
    marzec = _godziny(3, 3, lambda l: (1 + l.hour / 10) * (2 if l.weekday() >= 5 else 1), 0.5)
    maj = _godziny(5, 5, lambda l: 3 * (1 + l.hour / 10) * (2 if l.weekday() >= 5 else 1), 1.0)
    kwiecien = _godziny(4, 4, lambda l: 9.0, 0.7, dni=10)
    o = marzec + kwiecien + maj
    syn = syntetyzuj(o, [_gti(3, 5)], ["2026-03", "2026-04", "2026-05"], {"2026-03", "2026-05"})
    assert all(r.start_local.month == 4 and r.start_local.day > 10 for r in syn)
    assert len(syn) + len(kwiecien) == 30 * 24  # prawdziwe zostają, brakujące uzupełnione, bez duplikatów
    assert len({klucz_godziny(r) for r in syn + kwiecien}) == 30 * 24

    def wzorzec(lok):
        g = [r for r in marzec + maj if r.start_local.hour == lok.hour and (r.start_local.weekday() >= 5) == (lok.weekday() >= 5)]
        return g

    for dzien, godz in ((20, 10), (25, 3)):  # 20.04.2026 poniedziałek, 25.04.2026 sobota
        r = next(x for x in syn if x.start_local.day == dzien and x.start_local.hour == godz)
        g = wzorzec(r.start_local)
        assert r.kwh == pytest.approx(sum(x.kwh for x in g) / len(g))
        assert r.energy_net == pytest.approx(sum(x.energy_net for x in g) / sum(x.kwh for x in g) * r.kwh)
        assert r.service_net == pytest.approx(0.08 * r.kwh) and r.excise == pytest.approx(0.005 * r.kwh)
    pon = next(x for x in syn if x.start_local.day == 20 and x.start_local.hour == 10)
    sob = next(x for x in syn if x.start_local.day == 25 and x.start_local.hour == 10)
    assert sob.kwh > 1.5 * pon.kwh  # typ dnia: weekend ≈ 2× dzień roboczy


def test_syntetyzuj_pomija_godziny_bez_gti():
    marzec = _godziny(3, 3, lambda l: 1.0, 0.5)
    maj = _godziny(5, 5, lambda l: 1.0, 0.5)
    g = _gti(3, 5)
    g = {k: v for k, v in g.items() if k < "2026-04-16"}
    syn = syntetyzuj(marzec + maj, [g], ["2026-03", "2026-04", "2026-05"], {"2026-03", "2026-05"})
    assert syn and all(r.start_local.month == 4 and r.start_local.day <= 16 for r in syn)
    assert len(syn) == 15 * 24 + 2  # do 16.04 02:00 lokalnie (16.04 00:00 UTC)


def test_produkcja_brakujacych_miesiecy_z_wlasnego_gti():
    """Regresja Task 9: zimowe miesiące bez Pstryka nie dostają produkcji z września."""
    o, g, r = rok_syntetyczny(pomin=("2025-10", "2025-11", "2025-12", "2026-01"))
    zimowe = {1, 2, 3, 10, 11, 12}
    g = {k: ((v[0] * 0.15 if int(k[5:7]) in zimowe else v[0]), v[1]) for k, v in g.items()}
    w = _wyniki_6kwp(o, g, r)
    assert w["stan"] == "ok"
    wariant = next(v for v in w["warianty"] if v["magazyn_kwh"] == 0 and v["kwp"][0]["kwp"] == 6.0)
    oczekiwane = sum(produkcja(gti, t, 6.0, 0.0, ParametryPV()) for gti, t in g.values())
    assert wariant["produkcja_kwh"] == pytest.approx(oczekiwane, rel=0.01)
    for m in ("2025-10", "2025-11", "2025-12", "2026-01"):
        assert f"pv_miesiac_uzupelniony:{m}" in w["ostrzezenia"]
        assert w["pokrycie"][m] == 0.0  # pole `pokrycie` = prawdziwy Pstryk


def test_baza_rok_z_syntetycznymi_godzinami_zachowuje_poziom():
    """Jednorodne zużycie: syntetyczne miesiące kosztują tyle samo co prawdziwe."""
    o, g, r = rok_syntetyczny()
    pelny = _wyniki_6kwp(o, g, r)
    o2, g2, r2 = rok_syntetyczny(pomin=("2025-10", "2025-11", "2026-01"))
    brak = _wyniki_6kwp(o2, g2, r2)
    assert brak["baza"]["razem_rok"] == pytest.approx(pelny["baza"]["razem_rok"], rel=0.02)
