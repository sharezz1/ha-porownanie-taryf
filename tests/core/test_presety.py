from datetime import date

from custom_components.porownanie_taryf.core.presety import (
    SPRZEDAWCY, Cennik, stawki_enea_2026, stawki_na_plasko, stawki_z_plaskich, zbuduj_konfiguracje,
)
from custom_components.porownanie_taryf.core.strefy import TANIE_G12_DOMYSLNE


def test_enea_2026_3f_i_1f():
    s3, s1 = stawki_enea_2026("3f"), stawki_enea_2026("1f")
    assert s3.zmienne["G12w"] == {"szczyt": 0.2702, "pozaszczyt": 0.0813}
    assert s3.zmienne["G11"] == {"calodobowa": 0.2456}
    assert s3.stale == {"G11": 10.41, "G12": 14.56, "G12w": 26.23, "G13active": 14.56}
    assert s1.stale == {"G11": 7.45, "G12": 9.59, "G12w": 16.85, "G13active": 9.59}
    assert (s3.sosj, s3.oze, s3.kog, s3.abonament, s3.moc, s3.rok) == (0.0332, 0.0073, 0.0030, 3.84, 24.05, 2026)


def test_plasko_w_obie_strony():
    s = stawki_enea_2026("3f")
    assert stawki_z_plaskich(stawki_na_plasko(s), 2026) == s
    assert len(stawki_na_plasko(s)) == 17


def test_zbuduj_konfiguracje_domyslna():
    k = zbuduj_konfiguracje({"uklad": "3f", "preset": "enea_2026", "taryfa": "G12", "tanie_g12": [22, 23, 0, 1, 2, 3, 4, 5, 13, 14]}, {})
    assert k.vat == 0.23 and k.cennik is None and k.tanie_g12 == TANIE_G12_DOMYSLNE
    assert [(p.limit, p.podstawa, p.obejmuje_obsluge, p.zweryfikowany) for p in k.tarcza] == [(0.61, "brutto", True, True), (0.50, "netto", False, False)]
    assert (k.tarcza[0].od, k.tarcza[0].do) == (date(2026, 1, 1), date(2026, 12, 31))


def test_sprzedawca_z_katalogu_i_nieznany():
    d = {"uklad": "3f", "preset": "enea_2026", "taryfa": "G12", "tanie_g12": [0]}
    assert zbuduj_konfiguracje(d, {}).kompleksowa == SPRZEDAWCY["enea_2026_wybor"]
    assert zbuduj_konfiguracje(d, {"sprzedawca": "nieznany"}).kompleksowa == SPRZEDAWCY["enea_2026_wybor"]
    assert SPRZEDAWCY["enea_2026_wybor"].nazwa == "Enea"


def test_zbuduj_konfiguracje_nadpisania():
    opt = {"vat": 0.08, "stawki": {"G12_dzien": 0.30}, "tarcza": {"2026": {"limit": 0.65, "od": "2026-03-01"}},
           "cennik": {"nazwa": "Enea", "oplata_mc": 10.0, "akcyza": 0.005, "ceny": {"G12": {"dzien": 0.6, "noc": 0.4}}}}
    k = zbuduj_konfiguracje({"uklad": "3f", "preset": "enea_2026", "taryfa": "G12w", "tanie_g12": [0]}, opt)
    assert k.vat == 0.08 and k.stawki.zmienne["G12"]["dzien"] == 0.30 and k.stawki.zmienne["G12"]["noc"] == 0.0913
    assert k.tarcza[0].limit == 0.65 and k.tarcza[0].od == date(2026, 3, 1) and k.tarcza[0].do == date(2026, 12, 31)
    assert k.cennik == Cennik("Enea", 10.0, 0.005, {"G12": {"dzien": 0.6, "noc": 0.4}}) and k.obecna_taryfa == "G12w"
