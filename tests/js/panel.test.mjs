// Testy czystych funkcji panelu „Porównanie taryf” (spec v0.7). Uruchomienie: node --test tests/js/*.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  htmlOdpowiedzi, htmlTabeli, kluczRenderu, komorkaCeny, kwota, nazwaOkresu, nazwaStrefy, odpowiedz, przesun, tekst, tekstOstrzezenia, udzialy, wierszeTabeli, zbierzDane,
} from "../../custom_components/porownanie_taryf/frontend/panel.js";

const NBSP = "\u00a0";
const WSP = { okres_od: "2026-09-01", okres_do: "2026-09-30", pokrycie: 1.0 };
const TARYFY5 = ["G11", "G12", "G12w", "G12sezON", "G13active"];

// Fałszywy `hass`: entity_id celowo bez znaczenia (panel ma szukać po platform + translation_key).
function hassZ({ scenariusze, roznice = {}, kwh = [570, 430], okres = ["miesiac", "2026-09-01", "2026-09-01"],
  wspolne = WSP, urzadzenie = "dev1", prefiks = "a", hass = { entities: {}, states: {}, language: "pl" } }) {
  let n = 0;
  const dodaj = (domena, tk, state, attributes = {}) => {
    const eid = `${domena}.${prefiks}${n++}`;
    hass.entities[eid] = { entity_id: eid, device_id: urzadzenie, platform: "porownanie_taryf", translation_key: tk };
    hass.states[eid] = { entity_id: eid, state: String(state), attributes };
  };
  for (const [klucz, etykieta, razem, po, dystr, tarcza, obecny, extra = {}] of scenariusze) {
    const a = { ...wspolne, scenariusz: klucz, etykieta, obecny, sprzedaz_po: po, dystrybucja: dystr, tarcza, ostrzezenia: [], ...extra };
    dodaj("sensor", "razem", razem, a);
    if (klucz in roznice) dodaj("sensor", "roznica", roznice[klucz], a);
  }
  dodaj("sensor", "kwh_tanie", kwh[0], wspolne);
  dodaj("sensor", "kwh_drogie", kwh[1], wspolne);
  dodaj("select", "okres", okres[0]);
  dodaj("date", "data", okres[1]);
  dodaj("date", "koniec", okres[2]);
  hass.entities["light.kuchnia"] = { entity_id: "light.kuchnia", device_id: "x", platform: "hue", translation_key: "razem" };
  hass.states["light.kuchnia"] = { entity_id: "light.kuchnia", state: "on", attributes: {} };
  return hass;
}

// liczby syntetyczne; roznica G12w (20.01) celowo różni się o grosz od 820 − 800: panel ma brać stan sensora `roznica`
const G12 = ["pstryk_G12", "Pstryk + G12", 800, 500, 300, -100, true];
const G12W = ["pstryk_G12w", "Pstryk + G12w", 820, 500, 320, -100, false];
const G13 = ["pstryk_G13active", "Pstryk + G13active", 810, 500, 310, -100, false];
const ROZNICE = { pstryk_G12w: 20.01, pstryk_G13active: 10 };

const meta = (grupa, sprzedawca, taryfa, oferta = "", uwagi = []) => ({ grupa, sprzedawca, taryfa, oferta, uwagi });
const pstryk = (s) => [...s, meta("pstryk", "Pstryk", s[0].split("_")[1])];
const PG11 = ["pstryk_G11", "Pstryk + G11", 830, 500, 330, -100, false, meta("pstryk", "Pstryk", "G11")];
const hassWrzesien = () => hassZ({ scenariusze: [G12, G12W, G13], roznice: ROZNICE });
function hassBezWyniku() {
  const h = hassZ({ scenariusze: [G12, G12W, G13], roznice: ROZNICE, okres: ["zakres", "2026-09-10", "2026-09-01"] });
  for (const [eid, e] of Object.entries(h.entities)) {
    if (e.platform === "porownanie_taryf" && e.entity_id.startsWith("sensor.")) {
      h.states[eid] = { entity_id: eid, state: "unknown", attributes: { powod: "koniec_przed_data" } };
    }
  }
  return h;
}

// oferta katalogu / własny cennik jako scenariusz; `razem` w zł, obecna umowa = Pstryk + G12 (800 zł)
const komp = (id, sprzedawca, oferta, t, razem, extra = {}) =>
  [`kompleksowa_${id}_${t}`, `${sprzedawca} ${oferta} + ${t}`.trim(), razem, 0, 0, 0, false, { ...meta("kompleksowa", sprzedawca, t, oferta), id_oferty: id, ...extra }];
const PEW = (t, razem) => komp("enea_eneopewnosc_2026", "Enea", "EneoPewność", t, razem, { cena_do: "36 mies.", znaczniki: [["cena stała", "Cena stała 36 miesięcy."]] });
const WYB = (t, razem) => komp("enea_2026_wybor", "Enea", "prawo wyboru", t, razem);
const TAU = (t, razem) => komp("tauron_extra_2026", "Tauron", "Twój Extra Elektryk 24H", t, razem, { cena_do: "do 09.2027" });
const WLASNY = (t, razem) => komp("cennik", "Moja", "", t, razem);
const hassTabela = (scenariusze, wspolne = { ...WSP, taryfy: TARYFY5 }, reszta = {}) => hassZ({ scenariusze, wspolne, ...reszta });
const hassGlowny = () => hassTabela([
  pstryk(G12), pstryk(G12W), pstryk(G13), PG11,
  PEW("G11", 900), PEW("G12", 760), PEW("G12w", 850), PEW("G12sezON", 770), PEW("G13active", 750),
  WYB("G12", 795), WYB("G12w", 805), TAU("G12", 800), WLASNY("G12", 900),
]);
const tabela = (h) => wierszeTabeli(zbierzDane(h));
const komorka = (t, wiersz, taryfa) => t.wiersze.find((w) => w.etykieta === wiersz).komorki[taryfa];

// --- zbierzDane ---

test("ranking rosnąco, obecny oznaczony, różnice", () => {
  const d = zbierzDane(hassWrzesien());
  assert.deepEqual(d.ranking.map(s => s.klucz), ["pstryk_G12", "pstryk_G13active", "pstryk_G12w"]);
  assert.equal(d.obecny.klucz, "pstryk_G12");
  assert.equal(d.ranking[2].roznica, 20.01);  // ze stanu sensora roznica, nie 820 − 800
  assert.deepEqual(d.kwh, { tanie: 570, drogie: 430 });
});
test("cennik (grupa kompleksowa) trafia do kompleksowych, nie do rankingu Pstryk", () => {
  const d = zbierzDane(hassTabela([pstryk(G12), ["cennik_G12", "Enea + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Enea", "G12")]]));
  assert.ok(d.kompleksowa.some(s => s.klucz === "cennik_G12" && s.etykieta === "Enea + G12"));
  assert.ok(!d.ranking.some(s => s.klucz === "cennik_G12"));
});
test("brak wyniku (unknown + powod)", () => { assert.equal(zbierzDane(hassBezWyniku()).brakWyniku, true); });
test("brak encji integracji (rejestr zapełniony, ale cudzy)", () => {
  const hass = { entities: { "light.kuchnia": { entity_id: "light.kuchnia", platform: "hue" } }, states: {}, language: "pl" };
  assert.equal(zbierzDane(hass), null);
});
test("rejestr encji jeszcze pusty: undefined (panel nic nie pokazuje), nie komunikat „Dodaj integrację”", () => {
  assert.equal(zbierzDane({ entities: {}, states: {}, language: "pl" }), undefined);
  assert.equal(zbierzDane({ states: {}, language: "pl" }), undefined);
});
test("kluczRenderu odróżnia pusty rejestr od zapełnionego cudzymi encjami (inaczej komunikat nigdy by się nie pojawił)", () => {
  const pusty = { entities: {}, states: {}, language: "pl" };
  const cudzy = { ...pusty, entities: { "light.kuchnia": { entity_id: "light.kuchnia", platform: "hue" } } };
  assert.notEqual(kluczRenderu(pusty), kluczRenderu(cudzy));
});
test("kluczRenderu stały gdy zmienia się encja spoza integracji", () => {
  const h = hassWrzesien(); const k = kluczRenderu(h);
  h.states["sensor.inna"] = { state: "1", attributes: {} };
  assert.equal(kluczRenderu(h), k);
});
test("kluczRenderu zmienia się ze stanem encji integracji, ale nie z językiem HA", () => {
  const h = hassWrzesien(); const k = kluczRenderu(h);
  const eid = Object.keys(h.entities).find(e => h.entities[e].translation_key === "data");
  h.states[eid] = { ...h.states[eid], state: "2026-10-01" };
  assert.notEqual(kluczRenderu(h), k);
  assert.equal(kluczRenderu({ ...h, language: "en" }), kluczRenderu(h));   // panel tylko po polsku: język HA nie wymusza renderu
});
test("kilka wpisów: urządzenie pierwszego (po entity_id) sensora razem", () => {
  const h = hassZ({ scenariusze: [G12], urzadzenie: "dev_b", prefiks: "b" });
  hassZ({ scenariusze: [["pstryk_G12w", "Pstryk + G12w", 1, 1, 0, 0, true]], urzadzenie: "dev_a", prefiks: "a", hass: h });
  const d = zbierzDane(h);
  assert.deepEqual(d.ranking.map(s => s.klucz), ["pstryk_G12w"]);
  assert.equal(h.entities[d.okres.encje.okres].device_id, "dev_a");
});
test("okres bez odczytów (pokrycie 0) to brak wyniku, nie ranking zer", () => {
  const d = zbierzDane(hassZ({ scenariusze: [G12], wspolne: { okres_od: "2026-11-01", okres_do: "2026-11-30", pokrycie: 0 } }));
  assert.equal(d.brakWyniku, true);
});
test("dwie grupy: ranking Pstryk i kompleksowa posortowane rosnąco; brak atrybutu grupa → grupa pstryk", () => {
  const d = zbierzDane(hassGlowny());
  assert.deepEqual(d.ranking.map(s => s.klucz), ["pstryk_G12", "pstryk_G13active", "pstryk_G12w", "pstryk_G11"]);
  assert.equal(d.kompleksowa[0].klucz, "kompleksowa_enea_eneopewnosc_2026_G13active");
  assert.equal(d.kompleksowa.at(-1).razem, 900);
  const stare = zbierzDane(hassWrzesien());
  assert.equal(stare.ranking.length, 3);
  assert.deepEqual(stare.kompleksowa, []);
});
test("obecna G11: całe zużycie tanie, drogie 0; odpowiedź bez błędu", () => {
  const h = hassZ({
    scenariusze: [["pstryk_G11", "Pstryk + G11", 830, 500, 330, -100, true, meta("pstryk", "Pstryk", "G11")], pstryk(["pstryk_G12", "Pstryk + G12", 800, 500, 300, -100, false])],
    roznice: { pstryk_G12: -30 }, kwh: [900, 0],
  });
  const d = zbierzDane(h);
  assert.equal(d.obecny.klucz, "pstryk_G11");
  assert.deepEqual(udzialy(d.kwh.tanie, d.kwh.drogie), [100, 0]);
  assert.equal(odpowiedz(d).oferta, "Pstryk");
});
test("brak atrybutu taryfa: taryfa = ostatni człon klucza (nowe klucze kompleksowa_<id>_<T>)", () => {
  const h = hassZ({ scenariusze: [G12, ["kompleksowa_enea_eneopewnosc_2026_G12", "Enea EneoPewność + G12", 700, 400, 300, 0, false, { grupa: "kompleksowa", sprzedawca: "Enea" }]] });
  assert.equal(zbierzDane(h).kompleksowa[0].taryfa, "G12");
});
test("nowe atrybuty: cena_do, znaczniki, taryfy; starsza integracja bez nich → puste / null", () => {
  const d = zbierzDane(hassGlowny());
  const pew = d.kompleksowa.find((s) => s.idOferty === "enea_eneopewnosc_2026");
  assert.equal(pew.cenaDo, "36 mies.");
  assert.deepEqual(pew.znaczniki, [["cena stała", "Cena stała 36 miesięcy."]]);
  assert.deepEqual(d.taryfy, TARYFY5);
  const stare = zbierzDane(hassWrzesien());
  assert.equal(stare.taryfy, null);
  assert.deepEqual(stare.ranking.map((s) => [s.cenaDo, s.znaczniki]), [["", []], ["", []], ["", []]]);
  const zle = zbierzDane(hassTabela([pstryk(G12), komp("x", "X", "Y", "G12", 700, { cena_do: 5, znaczniki: [null, "a", ["ok", "dymek"]] })]));
  assert.deepEqual([zle.kompleksowa[0].cenaDo, zle.kompleksowa[0].znaczniki], ["", [["ok", "dymek"]]]);
});

// --- drobne funkcje ---

test("udzialy: tanie i drogie zawsze dają razem 100%", () => {
  assert.deepEqual(udzialy(50.5, 49.5), [51, 49]);  // niezależne zaokrąglenie dałoby 51 + 50
  assert.deepEqual(udzialy(570, 430), [57, 43]);
  assert.deepEqual(udzialy(100, 0), [100, 0]);
  assert.deepEqual(udzialy(null, 5), [null, 100]);
  assert.deepEqual(udzialy(null, null), [null, null]);
  assert.deepEqual(udzialy(0, 0), [null, null]);
});
test("przesun", () => {
  assert.equal(przesun("dzien", "2026-12-31", 1), "2027-01-01");
  assert.equal(przesun("miesiac", "2026-01-31", 1), "2026-02-01");
  assert.equal(przesun("miesiac", "2026-01-15", -1), "2025-12-01");
  assert.equal(przesun("rok", "2028-02-29", -1), "2027-01-01");
});
test("nazwaOkresu", () => {
  assert.equal(nazwaOkresu("miesiac", "2026-09-01", "2026-09-30"), "wrzesień 2026");
  assert.equal(nazwaOkresu("rok", "2026-01-01", "2026-12-31"), "rok 2026");
  assert.equal(nazwaOkresu("dzien", "2026-09-15", "2026-09-15"), "15 września 2026");
});
test("ostrzeżenia jako zdania", () => {
  assert.match(tekstOstrzezenia("pokrycie_ponizej_95"), /niepełne|brakuje/i);
  assert.match(tekstOstrzezenia("brak_tarczy:2025-12"), /12\.2025|grud/i);
  assert.equal(tekstOstrzezenia("nieznany_kod"), "nieznany_kod");
});
test("kwota: separator tysięcy także dla 4 cyfr, znak minus, bez „-0”, zawsze w zł", () => {
  assert.equal(kwota(7123.45), `7${NBSP}123,45 zł`);
  assert.equal(kwota(-100.5), "−100,50 zł");
  assert.equal(kwota(-0), "0,00 zł");
  assert.equal(kwota(25.86, true), "+25,86 zł");
  assert.equal(kwota(-25.86, true), "−25,86 zł");
});
test("tytuł panelu po polsku", () => { assert.equal(tekst("tytul"), "Porównanie taryf"); });
test("komorkaCeny: brutto = netto × (1 + vat), pod spodem netto; null → „brak danych”", () => {
  const k = komorkaCeny(0.3214, 0.23);
  assert.ok(k.includes("0,3953 zł/kWh"));
  assert.match(k, /<small>netto 0,3214<\/small>/);
  assert.ok(komorkaCeny(10, 0.23, "zł/mies.", 2).includes("12,30 zł/mies."));
  for (const k2 of [komorkaCeny(null, 0.23), komorkaCeny(undefined, 0.23), komorkaCeny(0.3, null)]) { assert.match(k2, /brak danych/); assert.doesNotMatch(k2, /netto/); }
});
test("polskie nazwy stref; nieznane zwracane jak są", () => {
  assert.equal(nazwaStrefy("dzien"), "dzień"); assert.equal(nazwaStrefy("pozaszczyt"), "pozaszczyt"); assert.equal(nazwaStrefy("calodobowa"), "całodobowo");
  assert.equal(nazwaStrefy("nowa"), "nowa");
});

// --- wierszeTabeli ---

test("tabela: kolumny z atrybutu `taryfy`, obecna taryfa, próg 1% obecnej umowy", () => {
  const t = tabela(hassGlowny());
  assert.deepEqual(t.kolumny, TARYFY5);
  assert.equal(t.obecnaTaryfa, "G12");
  assert.equal(t.prog, 8);
});
test("tabela: bez atrybutu `taryfy` kolumny w kolejności pierwszego wystąpienia (bez G12sezON, bo nikt go nie ma)", () => {
  const t = tabela(hassTabela([pstryk(G12), pstryk(G12W), pstryk(G13)], WSP));
  assert.deepEqual(t.kolumny, ["G12", "G13active", "G12w"]);   // kolejność wg ceny (ranking), nie wg listy taryf
});
test("tabela: wiersze rosnąco po najmniejszej różnicy; remis → wiersz z obecną umową, potem etykieta; etykiety", () => {
  const t = tabela(hassGlowny());
  assert.deepEqual(t.wiersze.map((w) => [w.etykieta, w.min]), [
    ["Enea EneoPewność", -50], ["Enea prawo wyboru", -5], ["Pstryk", 0], ["Tauron Twój Extra Elektryk 24H", 0], ["Własny cennik", 100],
  ]);
  assert.equal(t.wiersze[2].obecny, true);
});
test("tabela: brak scenariusza = null w komórce; komórki w kolejności kolumn", () => {
  const t = tabela(hassGlowny());
  const wyb = t.wiersze.find((w) => w.etykieta === "Enea prawo wyboru");
  assert.deepEqual(Object.keys(wyb.komorki), TARYFY5);
  assert.deepEqual([wyb.komorki.G11, wyb.komorki.G12sezON, wyb.komorki.G13active], [null, null, null]);
  assert.deepEqual(komorka(t, "Enea prawo wyboru", "G12w"), { wiersz: "Enea prawo wyboru", taryfa: "G12w", roznica: 5, razem: 805, obecny: false, klasa: "rowne", sila: 0 });
  assert.ok(Object.values(t.wiersze[0].komorki).every(Boolean));   // EneoPewność ma wszystkie 5
});
test("tabela: klasy komórek i nasycenie (∝ |różnica| / największa w tabeli, obecna bez koloru)", () => {
  const t = tabela(hassGlowny());
  const pew = (taryfa) => komorka(t, "Enea EneoPewność", taryfa);
  assert.deepEqual([pew("G11").klasa, pew("G12").klasa, pew("G13active").klasa], ["drozej", "taniej", "taniej"]);
  assert.deepEqual([pew("G11").sila, pew("G12").sila, pew("G13active").sila], [1, 0.4, 0.5]);   // maksimum = +100 (G11 i Własny cennik)
  const obecna = komorka(t, "Pstryk", "G12");
  assert.deepEqual([obecna.obecny, obecna.roznica, obecna.klasa, obecna.sila], [true, 0, "rowne", 0]);
  assert.equal(komorka(t, "Tauron Twój Extra Elektryk 24H", "G12").klasa, "rowne");   // 0 zł bez bycia obecną umową
});
test("tabela: próg „≈ tyle samo” na granicy — dokładnie 1% (−8 zł z 800) jest już różnicą, −7,99 jeszcze nie", () => {
  const t = tabela(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12w", 792), komp("b", "B", "Bb", "G12w", 792.01)]));
  assert.equal(komorka(t, "A Aa", "G12w").klasa, "taniej");
  assert.equal(komorka(t, "B Bb", "G12w").klasa, "rowne");
  assert.equal(komorka(t, "A Aa", "G12w").najtansza, true);
  assert.equal(komorka(t, "B Bb", "G12w").najtansza, undefined);
});
test("tabela: naj = najtańsza komórka (bez obecnej), najBez = najtańsza w kolumnie obecnej taryfy; flagi wyróżnień", () => {
  const t = tabela(hassGlowny());
  assert.deepEqual([t.naj.wiersz, t.naj.taryfa, t.naj.roznica, t.naj.razem], ["Enea EneoPewność", "G13active", -50, 750]);
  assert.deepEqual([t.najBez.wiersz, t.najBez.taryfa, t.najBez.roznica], ["Enea EneoPewność", "G12", -40]);
  assert.equal(t.naj, komorka(t, "Enea EneoPewność", "G13active"));
  assert.equal(komorka(t, "Enea EneoPewność", "G13active").najtansza, true);
  assert.equal(komorka(t, "Enea EneoPewność", "G12").najtanszaBez, true);
  assert.equal(komorka(t, "Enea EneoPewność", "G12").najtansza, undefined);
});
test("tabela: najtańsza w obecnej taryfie = najtańsza ogółem → jedna ramka (bez przerywanej)", () => {
  const t = tabela(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12", 700), komp("a", "A", "Aa", "G12w", 790)]));
  assert.equal(t.naj, t.najBez);
  assert.equal(t.naj.najtansza, true);
  assert.equal(t.naj.najtanszaBez, undefined);
});
test("tabela: Pstryk dostaje znacznik Tarcza (z tarczy obecnej umowy); oferty — znaczniki i cena_do z katalogu", () => {
  const t = tabela(hassGlowny());
  const w = (e) => t.wiersze.find((x) => x.etykieta === e);
  assert.deepEqual(w("Pstryk").znaczniki, [["Tarcza −100 zł", "Tarcza Pstryk (−100,00 zł w tym okresie) jest już odjęta od kosztu."]]);
  assert.equal(w("Pstryk").cenaDo, "");
  assert.deepEqual(w("Enea EneoPewność").znaczniki, [["cena stała", "Cena stała 36 miesięcy."]]);
  assert.equal(w("Enea EneoPewność").cenaDo, "36 mies.");
  assert.equal(w("Tauron Twój Extra Elektryk 24H").cenaDo, "do 09.2027");
  const bez = tabela(hassTabela([pstryk(["pstryk_G12", "Pstryk + G12", 800, 500, 300, 0, true]), komp("a", "A", "Aa", "G12", 700)]));
  assert.deepEqual(bez.wiersze.find((x) => x.etykieta === "Pstryk").znaczniki, []);   // tarcza 0 → brak znacznika
});

// --- odpowiedz (spec §4) ---

test("odpowiedź: najtańsza komórka wymaga zmiany taryfy, ale w obecnej taryfie też jest istotna oszczędność", () => {
  assert.deepEqual(odpowiedz(zbierzDane(hassGlowny())), {
    typ: "najtaniej", oferta: "Enea EneoPewność", taryfa: "G12", mniej: 40, bezZmiany: true, zmianaTaryfy: false,
    obok: "ze zmianą na G13active: −50,00 zł", pod: "760,00 zł zamiast 800,00 zł (Pstryk + G12)",
  });
});
test("odpowiedź: najtańsza w obecnej taryfie → bez dopisków", () => {
  const o = odpowiedz(zbierzDane(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12", 700), komp("a", "A", "Aa", "G12w", 790)])));
  assert.deepEqual(o, { typ: "najtaniej", oferta: "A Aa", taryfa: "G12", mniej: 100, bezZmiany: false, zmianaTaryfy: false, obok: "", pod: "700,00 zł zamiast 800,00 zł (Pstryk + G12)" });
});
test("odpowiedź: oszczędność tylko po zmianie taryfy, w obecnej taryfie nieistotna → znacznik „zmiana taryfy”", () => {
  const o = odpowiedz(zbierzDane(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12", 799), komp("a", "A", "Aa", "G12w", 700)])));
  assert.deepEqual(o, { typ: "najtaniej", oferta: "A Aa", taryfa: "G12w", mniej: 100, bezZmiany: false, zmianaTaryfy: true, obok: "", pod: "700,00 zł zamiast 800,00 zł (Pstryk + G12)" });
});
test("odpowiedź: wszystkie różnice poniżej 1% → „Twoja umowa jest najtańsza”", () => {
  const o = odpowiedz(zbierzDane(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12", 795), komp("a", "A", "Aa", "G12w", 805)])));
  assert.deepEqual(o, { typ: "obecna", pod: "800,00 zł (Pstryk + G12)" });
});
test("odpowiedź: granica progu — −8,00 zł z 800 to już oszczędność, −7,99 jeszcze nie", () => {
  assert.equal(odpowiedz(zbierzDane(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12w", 792)]))).typ, "najtaniej");
  assert.equal(odpowiedz(zbierzDane(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12w", 792.01)]))).typ, "obecna");
});
test("odpowiedź: brak obecnej umowy albo wyniku → null (panel pokaże komunikat)", () => {
  assert.equal(odpowiedz(zbierzDane(hassBezWyniku())), null);
  assert.equal(odpowiedz(null), null);
  assert.equal(odpowiedz(undefined), null);
});

// --- Review Focus: stany brzegowe ---

test("tabela: sam Pstryk (brak ofert kompleksowych, starsza integracja) → jeden wiersz, odpowiedź bez błędu", () => {
  const d = zbierzDane(hassWrzesien());
  const t = wierszeTabeli(d);
  assert.deepEqual(t.wiersze.map((w) => w.etykieta), ["Pstryk"]);
  assert.deepEqual(t.kolumny, ["G12", "G13active", "G12w"]);
  assert.equal(odpowiedz(d).typ, "obecna");   // pozostałe taryfy Pstryka są droższe od obecnej
});
test("tabela: zerowe koszty (prog 0) nie dają dzielenia przez zero ani NaN", () => {
  const zero = (k, e, ob) => [k, e, 0, 0, 0, 0, ob, meta("pstryk", "Pstryk", k.split("_")[1])];
  const t = tabela(hassTabela([zero("pstryk_G12", "Pstryk + G12", true), zero("pstryk_G12w", "Pstryk + G12w", false)]));
  assert.equal(t.prog, 0);
  const c = komorka(t, "Pstryk", "G12w");
  assert.deepEqual([c.klasa, c.sila], ["rowne", 0]);
  assert.ok(t.wiersze.flatMap((w) => Object.values(w.komorki)).filter(Boolean).every((k) => Number.isFinite(k.sila) && !k.najtansza));
  assert.equal(odpowiedz(zbierzDane(hassTabela([zero("pstryk_G12", "Pstryk + G12", true), zero("pstryk_G12w", "Pstryk + G12w", false)]))).typ, "obecna");
});
test("tabela: oferta bez obecnej taryfy (null w kolumnie obecnej) i wiersz bez żadnej komórki nie psują najBez ani sortowania", () => {
  const h = hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12w", 700), komp("b", "B", "Bb", "G12", 790)]);
  const t = tabela(h);
  assert.equal(komorka(t, "A Aa", "G12"), null);
  assert.deepEqual([t.najBez.wiersz, t.najBez.roznica], ["B Bb", -10]);
  assert.deepEqual(t.wiersze.map((w) => w.etykieta), ["A Aa", "B Bb", "Pstryk"]);
  const sam = tabela(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12w", 700)]));
  assert.equal(sam.najBez, null);   // w kolumnie obecnej taryfy jest tylko obecna umowa
});

// --- HTML tabeli i linijki odpowiedzi ---

const htmlT = (h) => htmlTabeli(tabela(h));
test("HTML tabeli: nagłówki — obecna taryfa z podpisem, pozostałe z dymkiem o wniosku, ostatnia kolumna „cena stała”", () => {
  const html = htmlT(hassGlowny());
  assert.match(html, /<th scope="col" class="obecna">G12<small>obecna<\/small><\/th>/);
  assert.match(html, /<th scope="col" title="Wymaga zmiany taryfy u operatora \(wniosek\)">G11<\/th>/);
  assert.equal((html.match(/title="Wymaga zmiany taryfy/g) ?? []).length, 4);
  assert.match(html, /<th scope="col">cena stała<\/th><\/tr><\/thead>/);
  assert.match(html, /<th><span class="ukryte">Oferta<\/span><\/th>/);
});
test("HTML tabeli: wiersze w kolejności, znaczniki jako pigułki z dymkiem, cena stała lub „—”", () => {
  const html = htmlT(hassGlowny());
  const nazwy = [...html.matchAll(/<tr><th scope="row">([^<]*)/g)].map((m) => m[1]);
  assert.deepEqual(nazwy, ["Enea EneoPewność", "Enea prawo wyboru", "Pstryk", "Tauron Twój Extra Elektryk 24H", "Własny cennik"]);
  assert.match(html, /Enea EneoPewność<span class="znacznik" title="Cena stała 36 miesięcy\.">cena stała<\/span>/);
  assert.match(html, /Pstryk<span class="znacznik" title="Tarcza Pstryk \(−100,00 zł w tym okresie\) jest już odjęta od kosztu\.">Tarcza −100 zł<\/span>/);
  assert.match(html, /<td class="stala">36 mies\.<\/td>/);
  assert.match(html, /<td class="stala">do 09\.2027<\/td>/);
  assert.match(html, /<td class="stala">—<\/td>/);
});
test("HTML tabeli: komórki — kwota ze znakiem, kolor ∝ różnicy, „≈”, „teraz”, „—”, title z pełnym kosztem", () => {
  const html = htmlT(hassGlowny());
  assert.match(html, /<td class="taniej kol-obecna najtansza-bez" style="--a:40%" title="Enea EneoPewność \+ G12: 760,00 zł">−40,00 zł<\/td>/);
  assert.match(html, /<td class="taniej najtansza" style="--a:45%" title="Enea EneoPewność \+ G13active: 750,00 zł">−50,00 zł<\/td>/);
  assert.match(html, /<td class="drozej" style="--a:70%" title="Enea EneoPewność \+ G11: 900,00 zł">\+100,00 zł<\/td>/);
  assert.match(html, /<td class="rowne" title="Enea prawo wyboru \+ G12w: 805,00 zł">≈ \+5,00 zł<\/td>/);
  assert.match(html, /<td class="rowne kol-obecna" title="Pstryk \+ G12: 800,00 zł"><i class="teraz">teraz<\/i>0,00 zł<\/td>/);
  assert.match(html, /<td class="brak">—<\/td>/);
});
test("HTML tabeli: nazwy ofert, znaczniki, dymki i cena stała z atrybutów są escapowane", () => {
  const zla = komp("x", "<b>S</b>", "<i>O</i>", "G12", 700, { cena_do: "<u>1</u>", znaczniki: [["<s>z</s>", "\"><img onerror=1>"]] });
  const html = htmlT(hassTabela([pstryk(G12), zla]));
  assert.doesNotMatch(html, /<img|<b>S|<i>O|<u>1|<s>z/);
  assert.ok(html.includes("&#60;b&#62;S&#60;/b&#62; &#60;i&#62;O&#60;/i&#62;"));
  assert.ok(html.includes('title="&#34;&#62;&#60;img onerror=1&#62;">&#60;s&#62;z&#60;/s&#62;'));
});
test("HTML odpowiedzi: cztery przypadki ze spec §4", () => {
  const html = (h) => htmlOdpowiedzi(odpowiedz(zbierzDane(h)));
  assert.equal(html(hassGlowny()),
    '<div class="odpowiedz"><div class="glowna">Najtaniej: <b>Enea EneoPewność + G12</b> — <b class="taniej">40,00 zł mniej</b> niż teraz <span class="przygaszone">(bez zmiany taryfy)</span></div>'
    + '<div class="obok">ze zmianą na G13active: −50,00 zł</div><div class="pod">760,00 zł zamiast 800,00 zł (Pstryk + G12)</div></div>');
  const wGlownej = html(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12", 700), komp("a", "A", "Aa", "G12w", 790)]));
  assert.match(wGlownej, /Najtaniej: <b>A Aa \+ G12<\/b> — <b class="taniej">100,00 zł mniej<\/b> niż teraz<\/div><div class="pod">/);
  const zmiana = html(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12", 799), komp("a", "A", "Aa", "G12w", 700)]));
  assert.match(zmiana, /<b class="taniej">100,00 zł mniej<\/b> <span class="znacznik ostrzezenie" title="Wymaga zmiany taryfy u operatora \(wniosek\)">zmiana taryfy<\/span><\/div>/);
  assert.doesNotMatch(zmiana, /niż teraz/);
  assert.equal(html(hassTabela([pstryk(G12), komp("a", "A", "Aa", "G12", 795)])),
    '<div class="odpowiedz"><div class="glowna">Twoja umowa jest najtańsza <span class="przygaszone">(różnice poniżej 1%)</span></div><div class="pod">800,00 zł (Pstryk + G12)</div></div>');
  assert.equal(htmlOdpowiedzi(null), "");
});
test("HTML odpowiedzi: nazwa oferty z atrybutów jest escapowana", () => {
  const html = htmlOdpowiedzi(odpowiedz(zbierzDane(hassTabela([pstryk(G12), komp("x", "<b>S</b>", "O", "G12", 700)]))));
  assert.doesNotMatch(html, /<b>S/);
  assert.ok(html.includes("&#60;b&#62;S&#60;/b&#62; O + G12"));
});
