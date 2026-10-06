// Testy czystych funkcji panelu „Taryfy prądu” (spec §7a). Uruchomienie: node --test tests/js/*.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  htmlWynikow, kluczRenderu, kwota, naTaryfy, nazwaOkresu, podsumowanie, przesun, tekst, tekstOstrzezenia, udzialy,
  werdyktKompleksowa, werdyktPstryk, zbierzDane,
} from "../../custom_components/porownanie_taryf/frontend/panel.js";

// Fałszywy `hass`: entity_id celowo bez znaczenia (panel ma szukać po platform + translation_key).
function hassZ({ scenariusze, roznice = {}, kwh = [570, 430], okres = ["miesiac", "2026-09-01", "2026-09-01"],
  wspolne = { okres_od: "2026-09-01", okres_do: "2026-09-30", pokrycie: 1.0 }, urzadzenie = "dev1", prefiks = "a",
  hass = { entities: {}, states: {}, language: "pl" } }) {
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

const meta = (grupa, sprzedawca, taryfa) => ({ grupa, sprzedawca, taryfa });
const pstryk = (s) => [...s, meta("pstryk", "Pstryk", s[0].split("_")[1])];
const PG11 = ["pstryk_G11", "Pstryk + G11", 830, 500, 330, -100, false, meta("pstryk", "Pstryk", "G11")];
const enea = (t, razem, po, dystr) => [`kompleksowa_${t}`, `Enea + ${t}`, razem, po, dystr, 0, false, meta("kompleksowa", "Enea", t)];
const ENEA = [enea("G11", 1000, 450, 550), enea("G12", 850, 450, 400), enea("G12w", 900, 450, 450)];
const ROZNICE_ENEA = { pstryk_G11: 30, kompleksowa_G11: 200, kompleksowa_G12: 50, kompleksowa_G12w: 100 };
const hassEnea = (opcje = {}) => hassZ({
  scenariusze: [pstryk(G12), pstryk(G12W), pstryk(G13), PG11, ...ENEA], roznice: { ...ROZNICE, ...ROZNICE_ENEA }, ...opcje,
});
const hassEneaG12 = (razem, roznica) => {   // podmienia sumę i różnicę Enea + G12 (reszta jak w hassEnea)
  const h = hassEnea();
  const eid = (tk, k) => Object.keys(h.entities).find(e => h.entities[e].translation_key === tk && h.states[e].attributes.scenariusz === k);
  h.states[eid("razem", "kompleksowa_G12")].state = razem;
  h.states[eid("roznica", "kompleksowa_G12")].state = roznica;
  return h;
};
const hassEneaTansza = () => hassEneaG12("770", "-30");
const hassWrzesien = () => hassZ({ scenariusze: [G12, G12W, G13], roznice: ROZNICE });
const hassGdzieG12wTansza = () => hassZ({
  scenariusze: [G12, ["pstryk_G12w", "Pstryk + G12w", 785, 500, 285, -100, false], G13],
  roznice: { pstryk_G12w: -15, pstryk_G13active: 10 },
});
const hassZCennikiem = () => hassZ({
  scenariusze: [G12, G12W, G13, ["cennik_G12", "Enea + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Enea", "G12")]],
  roznice: { ...ROZNICE, cennik_G12: 80 },
});
function hassBezWyniku() {
  const h = hassZ({ scenariusze: [G12, G12W, G13], roznice: ROZNICE, okres: ["zakres", "2026-09-10", "2026-09-01"] });
  for (const [eid, e] of Object.entries(h.entities)) {
    if (e.platform === "porownanie_taryf" && e.entity_id.startsWith("sensor.")) {
      h.states[eid] = { entity_id: eid, state: "unknown", attributes: { powod: "koniec_przed_data" } };
    }
  }
  return h;
}

test("ranking rosnąco, obecny oznaczony, różnice", () => {
  const d = zbierzDane(hassWrzesien());
  assert.deepEqual(d.ranking.map(s => s.klucz), ["pstryk_G12", "pstryk_G13active", "pstryk_G12w"]);
  assert.equal(d.obecny.klucz, "pstryk_G12");
  assert.equal(d.ranking[2].roznica, 20.01);  // ze stanu sensora roznica, nie 820 − 800
  assert.deepEqual(d.kwh, { tanie: 570, drogie: 430 });
});
test("cennik (grupa kompleksowa) trafia do drugiego wykresu, nie do rankingu Pstryk", () => {
  const d = zbierzDane(hassZCennikiem());
  assert.ok(d.kompleksowa.some(s => s.klucz === "cennik_G12" && s.etykieta === "Enea + G12"));
  assert.ok(!d.ranking.some(s => s.klucz === "cennik_G12"));
  assert.deepEqual(d.brakujace, []);  // własny cennik pomijany w adnotacji
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
test("kluczRenderu stały gdy zmienia się encja spoza integracji", () => {
  const h = hassWrzesien(); const k = kluczRenderu(h);
  h.states["sensor.inna"] = { state: "1", attributes: {} };
  assert.equal(kluczRenderu(h), k);
});

// --- poza briefem: stany brzegowe z Review Focus ---

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
test("dwie grupy: ranking Pstryk (4 wiersze), kompleksowa posortowana, brakujące taryfy", () => {
  const d = zbierzDane(hassEnea());
  assert.deepEqual(d.ranking.map(s => s.klucz), ["pstryk_G12", "pstryk_G13active", "pstryk_G12w", "pstryk_G11"]);
  assert.deepEqual(d.kompleksowa.map(s => s.klucz), ["kompleksowa_G12", "kompleksowa_G12w", "kompleksowa_G11"]);
  assert.equal(d.kompleksowa[0].roznica, 50);
  assert.deepEqual(d.brakujace, [{ sprzedawca: "Enea", taryfy: ["G13active"] }]);
});
test("brak atrybutu grupa (stare sensory) → grupa pstryk; brak kompleksowej → pusta lista", () => {
  const d = zbierzDane(hassWrzesien());
  assert.equal(d.ranking.length, 3);
  assert.deepEqual(d.kompleksowa, []);
  assert.deepEqual(d.brakujace, []);
});
test("obecna G11: całe zużycie tanie, drogie 0, werdykt i HTML bez błędów", () => {
  const h = hassZ({
    scenariusze: [["pstryk_G11", "Pstryk + G11", 830, 500, 330, -100, true, meta("pstryk", "Pstryk", "G11")], pstryk(["pstryk_G12", "Pstryk + G12", 800, 500, 300, -100, false])],
    roznice: { pstryk_G12: -30 }, kwh: [900, 0],
  });
  const d = zbierzDane(h);
  assert.equal(d.obecny.klucz, "pstryk_G11");
  assert.deepEqual(udzialy(d.kwh.tanie, d.kwh.drogie), [100, 0]);
  assert.match(werdyktPstryk(d).tekst, /Najtańsza taryfa dystrybucyjna: G12 /);
  assert.doesNotThrow(() => htmlWynikow(d));
});
test("brakujące taryfy: kolejność G11, G12, G12w, G13active (nie wg ceny), spójnik „ani”", () => {
  const h = hassZ({
    scenariusze: [pstryk(G12), pstryk(G12W), pstryk(G13), PG11, enea("G12", 850, 450, 400), enea("G12w", 900, 450, 450)],
    roznice: { ...ROZNICE, pstryk_G11: 30, kompleksowa_G12: 50, kompleksowa_G12w: 100 },
  });
  const d = zbierzDane(h);   // w rankingu cenowo G13active przed G11; w nocie ma być G11 pierwsze
  assert.deepEqual(d.brakujace, [{ sprzedawca: "Enea", taryfy: ["G11", "G13active"] }]);
  assert.match(htmlWynikow(d), /Enea nie oferuje G11 ani G13active gospodarstwom domowym\./);
});

// --- v0.3.1: dwie sekcje, linijka podsumowania, osobne werdykty, tylko po polsku ---

const NBSP = "\u00a0";
const hassMieszany = () => {   // obecny G12, G12w tańsza o 25,86 w sekcji 1, Enea + G12 tańsza o 202,21 w sekcji 2
  const h = hassEnea();
  const ustaw = (tk, k, v) => { h.states[Object.keys(h.entities).find(e => h.entities[e].translation_key === tk && h.states[e].attributes.scenariusz === k)].state = v; };
  ustaw("razem", "pstryk_G12w", "774.14"); ustaw("roznica", "pstryk_G12w", "-25.86");
  ustaw("razem", "kompleksowa_G12", "597.79"); ustaw("roznica", "kompleksowa_G12", "-202.21");
  return h;
};

test("kwota: separator tysięcy także dla 4 cyfr, znak minus, bez „-0”, zawsze w zł", () => {
  assert.equal(kwota(7123.45), `7${NBSP}123,45 zł`);
  assert.equal(kwota(-100.5), "−100,50 zł");
  assert.equal(kwota(-0), "0,00 zł");
  assert.equal(kwota(25.86, true), "+25,86 zł");
  assert.equal(kwota(-25.86, true), "−25,86 zł");
});
test("tytuł panelu po polsku", () => { assert.equal(tekst("tytul"), "Porównanie taryf"); });
test("podsumowanie: obecna + najtańsza opcja ogółem z obu sekcji", () => {
  assert.equal(podsumowanie(zbierzDane(hassMieszany())), `Twoja umowa (Pstryk + G12): 800,00 zł · najtańsza opcja ogółem: Enea + G12, o 202,21 zł mniej`);
});
test("podsumowanie: obecna najtańsza ogółem; remis → „równie tania”; bez ofert kompleksowych i bez „zapłaciłeś”", () => {
  assert.equal(podsumowanie(zbierzDane(hassEnea())), "Twoja umowa (Pstryk + G12): 800,00 zł · to najtańsza opcja ogółem");
  assert.equal(podsumowanie(zbierzDane(hassEneaG12("800", "0"))), "Twoja umowa (Pstryk + G12): 800,00 zł · równie tania jak Enea + G12");
  assert.equal(podsumowanie(zbierzDane(hassWrzesien())), "Twoja umowa (Pstryk + G12): 800,00 zł · to najtańsza opcja ogółem");
  assert.doesNotMatch(podsumowanie(zbierzDane(hassMieszany())), /zapłaci/i);
  assert.equal(podsumowanie(zbierzDane(hassBezWyniku())), "");
});
test("werdykt sekcji 1: najtańsza taryfa dystrybucyjna (sama taryfa w nazwie) albo obecna najtańsza", () => {
  assert.deepEqual(werdyktPstryk(zbierzDane(hassMieszany())), { lepsza: true, tekst: "Najtańsza taryfa dystrybucyjna: G12w — o 25,86 zł mniej niż obecna G12" });
  assert.deepEqual(werdyktPstryk(zbierzDane(hassWrzesien())), { lepsza: false, tekst: "Obecna taryfa G12 jest najtańsza" });
  const remis = hassZ({ scenariusze: [G12, ["pstryk_G12w", "Pstryk + G12w", 800, 500, 300, -100, false]], roznice: { pstryk_G12w: 0 } });
  assert.equal(werdyktPstryk(zbierzDane(remis)).tekst, "Obecna taryfa G12 jest równie tania jak G12w");
  assert.equal(werdyktPstryk(zbierzDane(hassBezWyniku())), null);
});
test("remis po zaokrągleniu (−0,004) to remis w werdykcie sekcji 1 i w podsumowaniu; ranking <2 taryf → brak werdyktu", () => {
  const h = hassZ({ scenariusze: [G12, ["pstryk_G12w", "Pstryk + G12w", 799.996, 500, 300, -100, false]], roznice: { pstryk_G12w: -0.004 } });
  assert.equal(werdyktPstryk(zbierzDane(h)).tekst, "Obecna taryfa G12 jest równie tania jak G12w");
  assert.equal(werdyktPstryk(zbierzDane(h)).lepsza, false);
  assert.equal(podsumowanie(zbierzDane(h)), "Twoja umowa (Pstryk + G12): 800,00 zł · równie tania jak Pstryk + G12w");
  assert.equal(werdyktPstryk(zbierzDane(hassZ({ scenariusze: [G12] }))), null);
});
test("werdykt sekcji 2: najtańsza oferta kompleksowa vs obecna umowa z Pstrykiem", () => {
  assert.deepEqual(werdyktKompleksowa(zbierzDane(hassMieszany())), { lepsza: true, tekst: "Najtańsza: Enea + G12 — o 202,21 zł mniej niż obecna umowa z Pstrykiem" });
  assert.deepEqual(werdyktKompleksowa(zbierzDane(hassEnea())), { lepsza: false, tekst: "Najtańsza: Enea + G12 — o 50,00 zł więcej niż obecna umowa z Pstrykiem" });
  assert.equal(werdyktKompleksowa(zbierzDane(hassEneaG12("800", "0"))).tekst, "Najtańsza: Enea + G12 — tyle samo co obecna umowa z Pstrykiem");
  assert.equal(werdyktKompleksowa(zbierzDane(hassWrzesien())), null);   // brak ofert kompleksowych
});
test("naTaryfy: skracanie etykiet tylko dla jednego (katalogowego) sprzedawcy i unikalnych taryf", () => {
  const d = zbierzDane(hassEnea());
  assert.equal(naTaryfy(d.ranking), true);
  assert.equal(naTaryfy(d.kompleksowa, true), true);
  assert.equal(naTaryfy(d.kompleksowa, false), false);
  const zly = zbierzDane(hassZ({ scenariusze: [pstryk(G12), ["cennik_G12", "Moja + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Moja", "G12")], enea("G12", 850, 450, 400)], roznice: { cennik_G12: 80, kompleksowa_G12: 50 } }));
  assert.equal(naTaryfy(zly.kompleksowa, true), false);   // dwóch sprzedawców
  assert.equal(naTaryfy([]), false);
});
test("HTML: podsumowanie, dwie ponumerowane sekcje, kafelki w sekcji 1, odstęp, inny kolor „prądu” w sekcji 2", () => {
  const html = htmlWynikow(zbierzDane(hassMieszany()));
  assert.match(html, /<p class="podsumowanie">Twoja umowa \(Pstryk \+ G12\): 800,00 zł · najtańsza opcja ogółem: Enea \+ G12, o 202,21 zł mniej<\/p>/);
  const [przed, po] = html.split('<h3>2. ');
  assert.match(przed, /<h3>1\. Prąd z Pstryka \+ dystrybucja Enea Operator<\/h3>/);
  assert.match(po, /^Umowa kompleksowa Enea \(prąd i dystrybucja od Enei\)<\/h3>/);
  assert.match(przed, /class="werdykt lepsza">Najtańsza taryfa dystrybucyjna: G12w — o 25,86 zł mniej niż obecna G12</);
  assert.match(po, /class="werdykt lepsza">Najtańsza: Enea \+ G12 — o 202,21 zł mniej niż obecna umowa z Pstrykiem</);
  // kafelki Pstryk tylko w sekcji 1, etykiety wierszy = sama taryfa, odznaka „obecna” tylko w sekcji 1
  for (const k of ["Tarcza Pstryk", "Zużycie", "Tanie godziny", "Drogie godziny", "Dane"]) { assert.ok(przed.includes(`<dt>${k}</dt>`)); assert.ok(!po.includes(`<dt>${k}</dt>`)); }
  assert.match(przed, /<span class="etykieta">G12<span class="odznaka">obecna<\/span>/);
  assert.match(przed, /<span class="etykieta">G12w<\/span>/);
  assert.match(po, /<span class="etykieta">G12<\/span>/);
  assert.equal((html.match(/class="odznaka"/g) ?? []).length, 1);
  // kolory „prądu”: sekcja 1 = prad, sekcja 2 = prad2; legendy „prąd po tarczy” / „prąd”
  assert.ok(przed.includes('class="prad"') && !przed.includes("prad2"));
  assert.ok(po.includes('class="prad2"') && !po.includes('class="prad"'));
  assert.match(przed, /<i class="prad"><\/i>prąd po tarczy/); assert.match(po, /<i class="prad2"><\/i>prąd<\/span>/);
  // wspólna skala: 500 / 1000 (najdroższy z obu sekcji), nie / 830
  assert.match(html, /width:50\.00%/); assert.doesNotMatch(html, /width:60\.24%/);
  // adnotacje pod wykresem sekcji 2, ostrzeżenia i rada na dole
  assert.match(po, /Enea nie oferuje G13active gospodarstwom domowym\./);
  assert.match(po, /<p class="adnotacja">Ceny Enei z cennika 2026 dla klientów, którzy zmieniali sprzedawcę — przed decyzją potwierdź ofertę w Enei\.<\/p>/);
  assert.ok(html.indexOf("O zmianie taryfy decyduj") > html.indexOf("Ceny Enei"));
  assert.doesNotMatch(html, /Comprehensive|Tariff|current|cheapest/);
});
test("HTML: obecna najtańsza → werdykt sekcji 1 bez koloru sukcesu; sekcja 2 „więcej”", () => {
  const html = htmlWynikow(zbierzDane(hassEnea()));
  assert.match(html, /class="werdykt">Obecna taryfa G12 jest najtańsza</);
  assert.match(html, /class="werdykt">Najtańsza: Enea \+ G12 — o 50,00 zł więcej niż obecna umowa z Pstrykiem</);
});
test("HTML: bez ofert kompleksowych nie ma sekcji 2 ani adnotacji", () => {
  const html = htmlWynikow(zbierzDane(hassWrzesien()));
  assert.doesNotMatch(html, /<h3>2\.|kompleksow|nie oferuje|z cennika 2026/);
  assert.match(html, /<h3>1\. /);
});
test("HTML: samotny własny cennik o nazwie „Enea”: nagłówek z Enią, ale bez noty o cenniku 2026", () => {
  const wlasny = hassZ({ scenariusze: [pstryk(G12), ["cennik_G12", "Enea + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Enea", "G12")]], roznice: { cennik_G12: 80 } });
  const html = htmlWynikow(zbierzDane(wlasny));
  assert.match(html, /<h3>2\. Umowa kompleksowa Enea \(prąd i dystrybucja od Enei\)<\/h3>/);
  assert.doesNotMatch(html, /z cennika 2026/);
});
test("HTML: własny cennik innego sprzedawcy / kilku sprzedawców → nagłówek ogólny, etykiety z nazwą, nazwa escapowana", () => {
  const zly = ["cennik_G12", "<img src=x> + G12", 900, 600, 300, 0, false, meta("kompleksowa", "<img src=x>", "G12")];
  const h = hassZ({ scenariusze: [pstryk(G12), pstryk(G13), ...ENEA, zly], roznice: ROZNICE_ENEA });
  const html = htmlWynikow(zbierzDane(h));
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /<h3>2\. Umowa kompleksowa<\/h3>/);
  assert.match(html, /<span class="etykieta">Enea \+ G12<\/span>/);   // pełna etykieta, gdy sprzedawcy się różnią
  assert.doesNotMatch(html, /od Enei/);
  const sam = hassZ({ scenariusze: [pstryk(G12), ["cennik_G12", "Moja + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Moja", "G12")]], roznice: { cennik_G12: 80 } });
  const h2 = htmlWynikow(zbierzDane(sam));
  assert.match(h2, /<h3>2\. Umowa kompleksowa<\/h3>/); assert.match(h2, /<span class="etykieta">Moja \+ G12<\/span>/);
});
