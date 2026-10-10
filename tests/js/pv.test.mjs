// Czyste funkcje zakładki „Fotowoltaika” (spec v0.8 §4.4, §5). Uruchomienie: node --test tests/js/*.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ZAAWANSOWANE, azymutKalenicy, entryIdPv, htmlKartyDachu, htmlKartyKosztow, htmlWynikowPv, kierunekSlownie, koniecStrzalki, pikselNaPuwg, polacieZKalenicy, tekstPv, urlOrto,
} from "../../custom_components/porownanie_taryf/frontend/panel.js";

test("piksel ↔ PUWG-92: lewy górny róg to (E_min, N_max), oś Y w dół", () => {
  assert.deepEqual(pikselNaPuwg(0, 0, 600, 600, 1000, 2000), { e: 970, n: 2030 });
  assert.deepEqual(pikselNaPuwg(600, 600, 600, 600, 1000, 2000), { e: 1030, n: 1970 });
  assert.deepEqual(pikselNaPuwg(150, 150, 300, 300, 1000, 2000), { e: 1000, n: 2000 }); // obraz przeskalowany
});

test("kalenica po przekątnej NW→SE: 135°, połacie 225°/45°", () => {
  const p1 = pikselNaPuwg(100, 100, 600, 600, 0, 0); // NW
  const p2 = pikselNaPuwg(500, 500, 600, 600, 0, 0); // SE
  assert.equal(Math.round(azymutKalenicy(p1, p2)), 135);
  assert.equal(Math.round(azymutKalenicy(p2, p1)), 135); // kolejność kliknięć bez znaczenia
  assert.deepEqual(polacieZKalenicy(135), [225, 45]);
  assert.deepEqual(polacieZKalenicy(0), [90, 270]); // kalenica N–S: połacie E/W
  assert.deepEqual(polacieZKalenicy(89.6), [180, 0]); // zaokrąglenie przed modulo: nigdy 360
  assert.deepEqual(polacieZKalenicy(89.4), [179, 359]);
});

test("kierunek słownie i strzałka", () => {
  assert.equal(kierunekSlownie(226), "SW");
  assert.equal(kierunekSlownie(46), "NE");
  assert.equal(kierunekSlownie(359), "N");
  const k = koniecStrzalki(90, 100); // na wschód: x rośnie, y bez zmian (środek 300,300)
  assert.equal(Math.round(k.x), 400);
  assert.equal(Math.round(k.y), 300);
});

test("URL ortofoto: kwadratowy BBOX 60 m i obraz 600 px", () => {
  const u = urlOrto(638027, 485065);
  assert.match(u, /BBOX=637997,485035,638057,485095/);
  assert.match(u, /WIDTH=600&HEIGHT=600/);
  assert.match(u, /SRS=EPSG:2180/);
});

test("entry_id z urządzenia wybieranego przez panel", () => {
  const hass = {
    entities: { "sensor.b": { entity_id: "sensor.b", device_id: "d2", platform: "porownanie_taryf", translation_key: "razem" },
      "sensor.a": { entity_id: "sensor.a", device_id: "d1", platform: "porownanie_taryf", translation_key: "razem" } },
    devices: { d1: { config_entries: ["E1"] }, d2: { config_entries: ["E2"] } },
  };
  assert.equal(entryIdPv(hass), "E1");
  assert.equal(entryIdPv({ entities: {}, devices: {} }), null);
});

const W = {
  schema: 1, stan: "ok", od: "2025-10-01", do: "2026-09-30", pokrycie: { "2025-10": 0, "2025-11": 0.79, "2025-12": 0.8, "2026-01": 0.9, "2026-02": 1, "2026-03": 1, "2026-04": 1, "2026-05": 1, "2026-06": 1, "2026-07": 1, "2026-08": 1, "2026-09": 1 },
  baza: { etykieta: "Pstryk + G12", razem_rok: 6775.77 },
  warianty: [
    { id: "4.0-0", kwp: [{ az: 226, kwp: 4 }], magazyn_kwh: 0, koszt: 12000, produkcja_kwh: 3812, autokonsumpcja: 0.51,
      pobor_vs_dzis: 0.78, eksport_kwh: 1900, oszczednosc_rok: 2400, zwrot_lata: 5, bilans_20_lat: 50000, depozyt_niewykorzystany: 0 },
    { id: "8.0-10", kwp: [{ az: 226, kwp: 8 }], magazyn_kwh: 10, koszt: 44000, produkcja_kwh: 7624, autokonsumpcja: 0.6,
      pobor_vs_dzis: 0.49, eksport_kwh: 3000, oszczednosc_rok: -50, zwrot_lata: null, bilans_20_lat: -45000, depozyt_niewykorzystany: 12.5 },
  ],
  ostrzezenia: ["pv_miesiac_uzupelniony:2026-01"],
};

test("tabela wyników: najkrótszy zwrot wyróżniony, ujemna oszczędność i brak zwrotu", () => {
  const h = htmlWynikowPv(W);
  assert.match(h, /class="najlepszy"[^]*4 kWp/);
  assert.match(h, /nie zwraca się w 20 l\./);
  assert.match(h, /class="ujemna"/);
  assert.match(h, /Pstryk \+ G12/);
  assert.match(h, /styczeń 2026/);
});

test("stany bez tabeli", () => {
  assert.match(htmlWynikowPv({ schema: 1, stan: "brak_konfigu" }), /Skonfiguruj dach/);
  assert.match(htmlWynikowPv({ schema: 1, stan: "za_malo_danych", miesiace_danych: 4 }), /4/);
  assert.match(htmlWynikowPv({ schema: 1, stan: "brak_pogody" }), /spróbuj później/);
  assert.match(htmlWynikowPv({ blad: "not_loaded" }), /niedostępna/);
  assert.equal(tekstPv("nieznany_kod"), "nieznany_kod");
});

test("tekstPv: kod uzupełnienia miesiąca z błędnym argumentem nie rzuca", () => {
  assert.equal(tekstPv("pv_miesiac_uzupelniony"), "pv_miesiac_uzupelniony");
  assert.equal(tekstPv("pv_miesiac_uzupelniony:xyz"), "pv_miesiac_uzupelniony:xyz");
  assert.equal(tekstPv("pv_miesiac_uzupelniony:2026-13"), "pv_miesiac_uzupelniony:2026-13");
  assert.doesNotMatch(tekstPv("pv_miesiac_uzupelniony:2026-"), /undefined/);
});

test("karta dachu: zdjęcie, propozycja NMPT z ostrzeżeniem, lista połaci", () => {
  const h = htmlKartyDachu({
    konfig: { adres: "Warszawa, Marszałkowska 1", polacie: [{ az: 226, nachylenie: 40, kwp_max: 8, cien: 0, panele: true }] },
    punkt: { e: 638027, n: 485065 }, nmpt: [{ az: 168, nachylenie: 50, powierzchnia_m2: 88 }], tryb: null,
  });
  assert.match(h, /BBOX=637997,485035,638057,485095/);
  assert.match(h, /może być starszy niż dom/);
  assert.match(h, /data-akcja="zgadza"/);
  assert.match(h, /SW 226°/);
  assert.match(h, /GUGiK/); // informacja o przesyłanych danych
  assert.match(h, /data-akcja="usun-lokalizacje"/);
});

test("karta dachu: błąd zdjęcia usuwa mapę z nakładką i kalenicę, daje ponowienie; tekst prywatności", () => {
  const ok = htmlKartyDachu({ konfig: { polacie: [] }, punkt: { e: 638027, n: 485065 }, nmpt: [] });
  assert.match(ok, /<img[^>]*data-url="[^"]*BBOX=/);
  assert.match(ok, /data-akcja="kalenica"/);
  assert.match(ok, /Pstryk i PSE nie dostają adresu ani współrzędnych\./);
  assert.doesNotMatch(ok, /Nic więcej nie opuszcza/);
  const blad = htmlKartyDachu({ konfig: { polacie: [{ az: 180, nachylenie: 35, kwp_max: 6, cien: 0, panele: true }] }, punkt: { e: 638027, n: 485065 }, nmpt: [], zdjecieBlad: true, tryb: "kalenica" });
  assert.doesNotMatch(blad, /<img|<svg|class="mapa[ "]/);
  assert.doesNotMatch(blad, /data-akcja="kalenica"/);
  assert.match(blad, /Geoportal nie odpowiada/);
  assert.match(blad, /data-akcja="zdjecie-ponow"/);
});

test("karta dachu: przycisk „Z lokalizacji HA” obok „Szukaj”, bez automatu", () => {
  const h = htmlKartyDachu({ konfig: { polacie: [] }, punkt: null });
  assert.match(h, /data-akcja="z-lokalizacji"[^>]*>Z lokalizacji HA</);
  assert.match(h, /data-akcja="szukaj"/);
  assert.doesNotMatch(h, /<img/);
});

test("karta dachu: trwa szukanie, błąd NMPT, tryb kalenicy, zapisany punkt bez szukania", () => {
  assert.match(htmlKartyDachu({ konfig: { polacie: [] }, punkt: { e: 1, n: 2 }, nmpt: null, tryb: null }), /Szukam połaci/);
  assert.match(htmlKartyDachu({ konfig: { polacie: [] }, punkt: { e: 1, n: 2 }, nmpt: [], nmptBlad: "niedostepny" }), /wskaż kalenicę/i);
  assert.match(htmlKartyDachu({ konfig: { polacie: [] }, punkt: { e: 1, n: 2 }, nmpt: [], tryb: "kalenica" }), /Kliknij pierwszy koniec kalenicy/);
  assert.match(htmlKartyDachu({ konfig: { polacie: [] }, punkt: { e: 1, n: 2 }, nmpt: [], tryb: "kalenica", klik1: { x: 5, y: 6 } }), /Kliknij drugi koniec kalenicy/);
  const zapisany = htmlKartyDachu({ konfig: { polacie: [] }, punkt: { e: 1, n: 2 } }); // nmpt === undefined: nic nie szukano
  assert.doesNotMatch(zapisany, /Szukam|nie pokazuje tu budynku/);
});

test("karta dachu: adres z konfiguracji jest escapowany", () => {
  assert.doesNotMatch(htmlKartyDachu({ konfig: { adres: '"><script>', polacie: [] }, punkt: null }), /<script>/);
});

test("karta kosztów: pasek szacunku przy domyślnych", () => {
  const z = { pr: 0.85, degradacja: 0.005, sprawnosc_mag: 0.9, dod: 0.9, zwrot_depozytu: 0, falownik_rok: 12, falownik_pct: 0.1, magazyn_rok: 15, magazyn_pct: 0.7 };
  assert.match(htmlKartyKosztow({ koszt_kwp: 3000, koszt_kwh_mag: 2000, wzrost_cen: 0.03, zaawansowane: z }), /szacunkowe/);
  const h = htmlKartyKosztow({ koszt_kwp: 2800, koszt_kwh_mag: 2000, wzrost_cen: 0.03, zaawansowane: z });
  assert.doesNotMatch(h, /szacunkowe/);
  assert.match(h, /value="3" data-pv-pole="wzrost_cen"/);
  assert.match(h, /data-pv-zaaw="magazyn_pct"/);
  assert.doesNotMatch(h, /wycena_eksportu/);
});

test("wyniki: etykieta „Z N miesięcy pomiaru, M uzupełnionych” i pokrycie per miesiąc w zwiniętym details", () => {
  const h = htmlWynikowPv(W);
  assert.match(h, /Z 10 miesięcy pomiaru, 2 uzupełnione\./); // 0 i 0,79 poniżej progu 0,8; 0,8 już się liczy
  assert.match(h, /<details data-id="pv-pokrycie"><summary>Pokrycie danymi po miesiącach<\/summary>/);
  assert.doesNotMatch(h, /<details data-id="pv-pokrycie" open/);
  assert.match(h, /<li>październik 2025: 0%<\/li>/);
  assert.match(h, /<li>listopad 2025: 79%<\/li>/);
  assert.match(htmlWynikowPv({ ...W, pokrycie: Object.fromEntries(Object.keys(W.pokrycie).map((m, i) => [m, i < 11 ? 1 : 0])) }), /Z 11 miesięcy pomiaru, 1 uzupełniony\./);
});

test("Zaawansowane: polskie etykiety, pola procentowe w %, PR jako ułamek z opisem", () => {
  const z = { pr: 0.85, degradacja: 0.005, sprawnosc_mag: 0.9, dod: 0.9, zwrot_depozytu: 0.1, falownik_rok: 12, falownik_pct: 0.1, magazyn_rok: 15, magazyn_pct: 0.7 };
  const h = htmlKartyKosztow({ koszt_kwp: 3000, koszt_kwh_mag: 2000, wzrost_cen: 0.03, zaawansowane: z });
  for (const e of ["PR — współczynnik wydajności", "Degradacja paneli", "Sprawność magazynu", "Głębokość rozładowania", "Zwrot niewykorzystanego depozytu",
    "Rok wymiany falownika", "Koszt wymiany falownika", "Rok wymiany magazynu", "Koszt wymiany magazynu"]) assert.ok(h.includes(e), e);
  assert.doesNotMatch(h, /<label>(pr|degradacja|sprawnosc_mag|dod|zwrot_depozytu|falownik_pct|magazyn_pct) /);
  assert.match(h, /value="0\.5" data-pv-zaaw="degradacja"> %\/rok/); // 0,005 -> 0,5 %/rok
  assert.match(h, /value="90" data-pv-zaaw="dod"/);
  assert.match(h, /value="10" data-pv-zaaw="zwrot_depozytu"/);
  assert.match(h, /value="70" data-pv-zaaw="magazyn_pct"> % ceny magazynu/);
  assert.match(h, /value="0\.85" data-pv-zaaw="pr"[^]*ułamek 0,5–1/);
  assert.match(h, /value="12" data-pv-zaaw="falownik_rok"/);
  assert.deepEqual(Object.entries(ZAAWANSOWANE).filter(([, v]) => v[2]).map(([n]) => n),
    ["degradacja", "sprawnosc_mag", "dod", "zwrot_depozytu", "falownik_pct", "magazyn_pct"]);
  assert.match(tekstPv("invalid_format"), /Sprawdź wartości pól — któreś jest poza zakresem/);
});
