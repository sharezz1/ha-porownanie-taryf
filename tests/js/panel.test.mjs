// Testy czystych funkcji panelu „Taryfy prądu” (spec §7a). Uruchomienie: node --test tests/js/*.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  etykietaOferty, grupyOpcji, htmlOpcji, synchronizujListe, htmlCenSekcji1, htmlCenSekcji2, htmlWynikow, kluczRenderu, komorkaCeny, kwota, nazwaStrefy, widokSekcji2, naTaryfy, nazwaOkresu, podsumowanie, przesun, tekst, tekstOstrzezenia, udzialy,
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

const meta = (grupa, sprzedawca, taryfa, oferta = "", uwagi = []) => ({ grupa, sprzedawca, taryfa, oferta, uwagi });
const UWAGA_WYBOR = "Uwaga testowa A: potwierdź ofertę.";
const pstryk = (s) => [...s, meta("pstryk", "Pstryk", s[0].split("_")[1])];
const PG11 = ["pstryk_G11", "Pstryk + G11", 830, 500, 330, -100, false, meta("pstryk", "Pstryk", "G11")];
const enea = (t, razem, po, dystr) => [`kompleksowa_enea_2026_wybor_${t}`, `Enea prawo wyboru + ${t}`, razem, po, dystr, 0, false, meta("kompleksowa", "Enea", t, "prawo wyboru", [UWAGA_WYBOR])];
const ENEA = [enea("G11", 1000, 450, 550), enea("G12", 850, 450, 400), enea("G12w", 900, 450, 450)];
const ROZNICE_ENEA = { pstryk_G11: 30, kompleksowa_enea_2026_wybor_G11: 200, kompleksowa_enea_2026_wybor_G12: 50, kompleksowa_enea_2026_wybor_G12w: 100 };
const hassEnea = (opcje = {}) => hassZ({
  scenariusze: [pstryk(G12), pstryk(G12W), pstryk(G13), PG11, ...ENEA], roznice: { ...ROZNICE, ...ROZNICE_ENEA }, ...opcje,
});
const hassEneaG12 = (razem, roznica) => {   // podmienia sumę i różnicę Enea + G12 (reszta jak w hassEnea)
  const h = hassEnea();
  const eid = (tk, k) => Object.keys(h.entities).find(e => h.entities[e].translation_key === tk && h.states[e].attributes.scenariusz === k);
  h.states[eid("razem", "kompleksowa_enea_2026_wybor_G12")].state = razem;
  h.states[eid("roznica", "kompleksowa_enea_2026_wybor_G12")].state = roznica;
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
  assert.deepEqual(d.kompleksowa.map(s => s.klucz), ["kompleksowa_enea_2026_wybor_G12", "kompleksowa_enea_2026_wybor_G12w", "kompleksowa_enea_2026_wybor_G11"]);
  assert.equal(d.kompleksowa[0].roznica, 50);
  assert.deepEqual(d.brakujace, [{ sprzedawca: "Enea", oferta: "prawo wyboru", taryfy: ["G13active"] }]);
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
    roznice: { ...ROZNICE, pstryk_G11: 30, kompleksowa_enea_2026_wybor_G12: 50, kompleksowa_enea_2026_wybor_G12w: 100 },
  });
  const d = zbierzDane(h);   // w rankingu cenowo G13active przed G11; w nocie ma być G11 pierwsze
  assert.deepEqual(d.brakujace, [{ sprzedawca: "Enea", oferta: "prawo wyboru", taryfy: ["G11", "G13active"] }]);
  assert.match(htmlWynikow(d), /Oferta „prawo wyboru” nie obejmuje G11 ani G13active\./);
});

// --- v0.3.1: dwie sekcje, linijka podsumowania, osobne werdykty, tylko po polsku ---

const NBSP = "\u00a0";
const hassMieszany = () => {   // obecny G12, G12w tańsza o 25,86 w sekcji 1, Enea + G12 tańsza o 202,21 w sekcji 2
  const h = hassEnea();
  const ustaw = (tk, k, v) => { h.states[Object.keys(h.entities).find(e => h.entities[e].translation_key === tk && h.states[e].attributes.scenariusz === k)].state = v; };
  ustaw("razem", "pstryk_G12w", "774.14"); ustaw("roznica", "pstryk_G12w", "-25.86");
  ustaw("razem", "kompleksowa_enea_2026_wybor_G12", "597.79"); ustaw("roznica", "kompleksowa_enea_2026_wybor_G12", "-202.21");
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
  assert.equal(podsumowanie(zbierzDane(hassMieszany())), `Twoja umowa (Pstryk + G12): 800,00 zł · najtańsza opcja ogółem: Enea prawo wyboru + G12, o 202,21 zł mniej`);
});
test("podsumowanie: obecna najtańsza ogółem; remis → „równie tania”; bez ofert kompleksowych i bez „zapłaciłeś”", () => {
  assert.equal(podsumowanie(zbierzDane(hassEnea())), "Twoja umowa (Pstryk + G12): 800,00 zł · to najtańsza opcja ogółem");
  assert.equal(podsumowanie(zbierzDane(hassEneaG12("800", "0"))), "Twoja umowa (Pstryk + G12): 800,00 zł · równie tania jak Enea prawo wyboru + G12");
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
  assert.deepEqual(werdyktKompleksowa(zbierzDane(hassMieszany())), { lepsza: true, tekst: "Najtańsza: Enea prawo wyboru + G12 — o 202,21 zł mniej niż obecna umowa z Pstrykiem" });
  assert.deepEqual(werdyktKompleksowa(zbierzDane(hassEnea())), { lepsza: false, tekst: "Najtańsza: Enea prawo wyboru + G12 — o 50,00 zł więcej niż obecna umowa z Pstrykiem" });
  assert.equal(werdyktKompleksowa(zbierzDane(hassEneaG12("800", "0"))).tekst, "Najtańsza: Enea prawo wyboru + G12 — tyle samo co obecna umowa z Pstrykiem");
  assert.equal(werdyktKompleksowa(zbierzDane(hassWrzesien())), null);   // brak ofert kompleksowych
});
test("naTaryfy: skracanie etykiet tylko dla jednego (katalogowego) sprzedawcy i unikalnych taryf", () => {
  const d = zbierzDane(hassEnea());
  assert.equal(naTaryfy(d.ranking), true);
  assert.equal(naTaryfy(d.kompleksowa, true), true);
  assert.equal(naTaryfy(d.kompleksowa, false), false);
  const zly = zbierzDane(hassZ({ scenariusze: [pstryk(G12), ["cennik_G12", "Moja + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Moja", "G12")], enea("G12", 850, 450, 400)], roznice: { cennik_G12: 80, kompleksowa_enea_2026_wybor_G12: 50 } }));
  assert.equal(naTaryfy(zly.kompleksowa, true), false);   // dwóch sprzedawców
  assert.equal(naTaryfy([]), false);
});
test("HTML: podsumowanie, dwie ponumerowane sekcje, kafelki w sekcji 1, odstęp, inny kolor „prądu” w sekcji 2", () => {
  const html = htmlWynikow(zbierzDane(hassMieszany()));
  assert.match(html, /<p class="podsumowanie">Twoja umowa \(Pstryk \+ G12\): 800,00 zł · najtańsza opcja ogółem: Enea prawo wyboru \+ G12, o 202,21 zł mniej<\/p>/);
  const [przed, po] = html.split('<h3>2. ');
  assert.match(przed, /<h3>1\. Prąd z Pstryka \+ dystrybucja Enea Operator<\/h3>/);
  assert.match(po, /^Umowa kompleksowa Enea \(prąd i dystrybucja od Enei\)<\/h3>/);
  assert.match(przed, /class="werdykt lepsza">Najtańsza taryfa dystrybucyjna: G12w — o 25,86 zł mniej niż obecna G12</);
  assert.match(po, /class="werdykt lepsza">Najtańsza: Enea prawo wyboru \+ G12 — o 202,21 zł mniej niż obecna umowa z Pstrykiem</);
  // kafelki Pstryk tylko w sekcji 1, etykiety wierszy = sama taryfa, odznaka „obecna” tylko w sekcji 1
  for (const k of ["Tarcza Pstryk", "Zużycie", "Tanie godziny", "Drogie godziny", "Dane"]) { assert.ok(przed.includes(`<dt>${k}</dt>`)); assert.ok(!po.includes(`<dt>${k}</dt>`)); }
  assert.match(przed, /<span class="etykieta">G12<span class="odznaka">obecna<\/span>/);
  assert.match(przed, /<span class="etykieta">G12w<\/span>/);
  assert.match(po, /<span class="etykieta">prawo wyboru · G12<\/span>/);
  assert.equal((html.match(/class="odznaka"/g) ?? []).length, 1);
  // kolory „prądu”: sekcja 1 = prad, sekcja 2 = prad2; legendy „prąd po tarczy” / „prąd”
  assert.ok(przed.includes('class="prad"') && !przed.includes("prad2"));
  assert.ok(po.includes('class="prad2"') && !po.includes('class="prad"'));
  assert.match(przed, /<i class="prad"><\/i>prąd po tarczy/); assert.match(po, /<i class="prad2"><\/i>prąd<\/span>/);
  // wspólna skala: 500 / 1000 (najdroższy z obu sekcji), nie / 830
  assert.match(html, /width:50\.00%/); assert.doesNotMatch(html, /width:60\.24%/);
  // adnotacje pod wykresem sekcji 2, ostrzeżenia i rada na dole
  assert.match(po, /Oferta „prawo wyboru” nie obejmuje G13active\./);
  assert.match(po, new RegExp(`<p class="adnotacja"><strong>prawo wyboru:</strong> ${UWAGA_WYBOR}</p>`));
  assert.ok(html.indexOf("O zmianie taryfy decyduj") > html.indexOf(UWAGA_WYBOR));
  assert.doesNotMatch(html, /Comprehensive|Tariff|current|cheapest/);
});
test("HTML: obecna najtańsza → werdykt sekcji 1 bez koloru sukcesu; sekcja 2 „więcej”", () => {
  const html = htmlWynikow(zbierzDane(hassEnea()));
  assert.match(html, /class="werdykt">Obecna taryfa G12 jest najtańsza</);
  assert.match(html, /class="werdykt">Najtańsza: Enea prawo wyboru \+ G12 — o 50,00 zł więcej niż obecna umowa z Pstrykiem</);
});
test("HTML: bez ofert kompleksowych nie ma sekcji 2 ani adnotacji", () => {
  const html = htmlWynikow(zbierzDane(hassWrzesien()));
  assert.doesNotMatch(html, /<h3>2\.|kompleksow|nie obejmuje|Uwaga testowa/);
  assert.match(html, /<h3>1\. /);
});
test("HTML: samotny własny cennik o nazwie „Enea”: nagłówek z Enią, ale bez noty o cenniku 2026", () => {
  const wlasny = hassZ({ scenariusze: [pstryk(G12), ["cennik_G12", "Enea + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Enea", "G12")]], roznice: { cennik_G12: 80 } });
  const html = htmlWynikow(zbierzDane(wlasny));
  assert.match(html, /<h3>2\. Umowa kompleksowa Enea \(prąd i dystrybucja od Enei\)<\/h3>/);
  assert.doesNotMatch(html, /adnotacja/);
});
test("HTML: własny cennik innego sprzedawcy / kilku sprzedawców → nagłówek ogólny, etykiety z nazwą, nazwa escapowana", () => {
  const zly = ["cennik_G12", "<img src=x> + G12", 900, 600, 300, 0, false, meta("kompleksowa", "<img src=x>", "G12")];
  const h = hassZ({ scenariusze: [pstryk(G12), pstryk(G13), ...ENEA, zly], roznice: ROZNICE_ENEA });
  const html = htmlWynikow(zbierzDane(h));
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /<h3>2\. Umowa kompleksowa<\/h3>/);
  assert.match(html, /<span class="etykieta">Enea prawo wyboru \+ G12<\/span>/);   // pełna etykieta, gdy sprzedawcy się różnią
  assert.doesNotMatch(html, /od Enei/);
  const sam = hassZ({ scenariusze: [pstryk(G12), ["cennik_G12", "Moja + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Moja", "G12")]], roznice: { cennik_G12: 80 } });
  const h2 = htmlWynikow(zbierzDane(sam));
  assert.match(h2, /<h3>2\. Umowa kompleksowa<\/h3>/); assert.match(h2, /<span class="etykieta">Moja \+ G12<\/span>/);
});

// --- v0.4.0: G12sezON w sekcji 1, wiele ofert katalogu w sekcji 2, uwagi z atrybutów ---

const UWAGI_PEWNOSC = ["Cena stała przez 36 miesięcy.", "Zmiana grupy u operatora <img src=x onerror=1>."];
const oferta = (id, of, uwagi, t, razem, po, dystr) => [`kompleksowa_${id}_${t}`, `Enea ${of} + ${t}`, razem, po, dystr, 0, false, meta("kompleksowa", "Enea", t, of, uwagi)];
const WYBOR = (t, r, po, d) => oferta("enea_2026_wybor", "prawo wyboru", [UWAGA_WYBOR], t, r, po, d);
const PEWNOSC = (t, r, po, d) => oferta("enea_eneopewnosc_2026", "EneoPewność", UWAGI_PEWNOSC, t, r, po, d);
const PSEZ = ["pstryk_G12sezON", "Pstryk + G12sezON", 805, 500, 305, -100, false, meta("pstryk", "Pstryk", "G12sezON")];
const hassDwieOferty = (extra = [], roznice = {}) => hassZ({
  scenariusze: [pstryk(G12), pstryk(G12W), PSEZ, pstryk(G13), PG11,
    WYBOR("G11", 1000, 450, 550), WYBOR("G12", 850, 450, 400), WYBOR("G12w", 900, 450, 450),
    PEWNOSC("G11", 960, 440, 520), PEWNOSC("G12", 700, 400, 300), PEWNOSC("G12w", 750, 410, 340), PEWNOSC("G12sezON", 780, 420, 360), PEWNOSC("G13active", 790, 430, 360), ...extra],
  roznice: { ...ROZNICE, pstryk_G11: 30, pstryk_G12sezON: 5, kompleksowa_enea_2026_wybor_G11: 200, kompleksowa_enea_2026_wybor_G12: 50, kompleksowa_enea_2026_wybor_G12w: 100,
    kompleksowa_enea_eneopewnosc_2026_G11: 160, kompleksowa_enea_eneopewnosc_2026_G12: -100, kompleksowa_enea_eneopewnosc_2026_G12w: -50, kompleksowa_enea_eneopewnosc_2026_G12sezON: -20, kompleksowa_enea_eneopewnosc_2026_G13active: -10, ...roznice },
});

test("sekcja 1: G12sezON jako piąty wiersz, kolejność wg ceny", () => {
  const d = zbierzDane(hassDwieOferty());
  assert.equal(d.ranking.length, 5);
  assert.deepEqual(d.ranking.map(s => s.taryfa), ["G12", "G12sezON", "G13active", "G12w", "G11"]);
  const html = htmlWynikow(d);
  assert.match(html.split('<h3>2. ')[0], /<span class="etykieta">G12sezON<\/span>/);
});
test("sekcja 2: dwie oferty Enei w jednym rankingu rosnąco, etykiety „oferta · taryfa”, nagłówek sprzedawcy", () => {
  const d = zbierzDane(hassDwieOferty());
  assert.deepEqual(d.kompleksowa.map(s => s.taryfa), ["G12", "G12w", "G12sezON", "G13active", "G12", "G12w", "G11", "G11"]);
  assert.deepEqual(d.kompleksowa.map(s => s.oferta), ["EneoPewność", "EneoPewność", "EneoPewność", "EneoPewność", "prawo wyboru", "prawo wyboru", "EneoPewność", "prawo wyboru"]);
  const po = htmlWynikow(d).split('<h3>2. ')[1];
  assert.match(po, /^Umowa kompleksowa Enea \(prąd i dystrybucja od Enei\)<\/h3>/);
  assert.match(po, /<span class="etykieta">EneoPewność · G12<\/span>/);
  assert.match(po, /<span class="etykieta">prawo wyboru · G11<\/span>/);
  assert.ok(po.indexOf("EneoPewność · G12<") < po.indexOf("prawo wyboru · G12<"));
});
test("brakujące taryfy osobno dla każdej oferty (kolejność TARYFY), tekst „Oferta „…” nie obejmuje …” (bez nazwy sprzedawcy)", () => {
  const d = zbierzDane(hassDwieOferty());
  assert.deepEqual(d.brakujace, [
    { sprzedawca: "Enea", oferta: "prawo wyboru", taryfy: ["G12sezON", "G13active"] },
  ]);   // EneoPewność oferuje wszystkie taryfy: brak wpisu
  const html = htmlWynikow(d);
  assert.match(html, /Oferta „prawo wyboru” nie obejmuje G12sezON ani G13active\./);
  assert.doesNotMatch(html, /Oferta „EneoPewność”/);
});
test("uwagi z atrybutu: każde zdanie raz na ofertę, escapowane, bez zdania wpisanego w panel", () => {
  const d = zbierzDane(hassDwieOferty());
  assert.deepEqual(d.uwagi, [
    { sprzedawca: "Enea", oferta: "prawo wyboru", uwagi: [UWAGA_WYBOR] },
    { sprzedawca: "Enea", oferta: "EneoPewność", uwagi: UWAGI_PEWNOSC },
  ]);
  const html = htmlWynikow(d);
  assert.equal(html.split(UWAGA_WYBOR).length - 1, 1);
  assert.equal(html.split("Cena stała przez 36 miesięcy.").length - 1, 1);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /Zmiana grupy u operatora &#60;img src=x onerror=1&#62;\./);
  assert.doesNotMatch(html, /z cennika 2026|Ceny Enei/);
});
test("uwagi: jeden akapit na ofertę, nazwa oferty pogrubiona, zdania połączone spacją, wszystko escapowane", () => {
  const html = htmlWynikow(zbierzDane(hassDwieOferty()));
  assert.ok(html.includes(`<p class="adnotacja"><strong>prawo wyboru:</strong> ${UWAGA_WYBOR}</p>`));
  assert.ok(html.includes('<p class="adnotacja"><strong>EneoPewność:</strong> Cena stała przez 36 miesięcy. Zmiana grupy u operatora &#60;img src=x onerror=1&#62;.</p>'));
  const zla = oferta("x", "<b>oferta</b>", ["a & b"], "G12", 700, 400, 300);
  const h = htmlWynikow(zbierzDane(hassZ({ scenariusze: [pstryk(G12), zla], roznice: { kompleksowa_x_G12: -100 } })));
  assert.ok(h.includes("<strong>&#60;b&#62;oferta&#60;/b&#62;:</strong> a &#38; b</p>"));
});
test("własny cennik „Enea” obok katalogu: etykieta z nazwą, bez uwag i brakujących taryf katalogu", () => {
  const wlasny = ["cennik_G12", "Enea + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Enea", "G12")];
  const d = zbierzDane(hassDwieOferty([wlasny], { cennik_G12: 80 }));
  assert.deepEqual(d.brakujace.map(b => b.oferta), ["prawo wyboru"]);
  assert.deepEqual(d.uwagi.map(u => u.oferta), ["prawo wyboru", "EneoPewność"]);
  const po = htmlWynikow(d).split('<h3>2. ')[1];
  assert.match(po, /<span class="etykieta">Enea \+ G12<\/span>/);
  assert.equal(po.split(UWAGA_WYBOR).length - 1, 1);
});
test("werdykt i podsumowanie wskazują najtańszą ofertę z etykietą oferty", () => {
  const d = zbierzDane(hassDwieOferty());
  assert.equal(werdyktKompleksowa(d).tekst, "Najtańsza: Enea EneoPewność + G12 — o 100,00 zł mniej niż obecna umowa z Pstrykiem");
  assert.equal(podsumowanie(d), "Twoja umowa (Pstryk + G12): 800,00 zł · najtańsza opcja ogółem: Enea EneoPewność + G12, o 100,00 zł mniej");
});
test("własny cennik nie dostaje uwag katalogu także samotnie", () => {
  const wlasny = ["cennik_G12", "Enea + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Enea", "G12")];
  const d = zbierzDane(hassZ({ scenariusze: [pstryk(G12), pstryk(G13), wlasny], roznice: { ...ROZNICE, cennik_G12: 80 } }));
  assert.deepEqual(d.brakujace, []);
  assert.deepEqual(d.uwagi, []);
});
test("brak atrybutu taryfa: taryfa = ostatni człon klucza (nowe klucze kompleksowa_<id>_<T>)", () => {
  const h = hassZ({ scenariusze: [G12, ["kompleksowa_enea_eneopewnosc_2026_G12", "Enea EneoPewność + G12", 700, 400, 300, 0, false, { grupa: "kompleksowa", sprzedawca: "Enea" }]] });
  assert.equal(zbierzDane(h).kompleksowa[0].taryfa, "G12");
});

// --- v0.5.0: lista „Sprzedawca” filtruje sekcję 2, rozwijane tabele cen (brutto, pod spodem netto) ---

const WYBOR_OPCJE = ["wszystkie", "enea_2026_wybor", "enea_eneopewnosc_2026", "tauron_extra_2026", "tauron_natura_2026", "pge_taryfowy_gtpa", "energa_podstawowa_2026", "cennik"];
// syntetyczne ceny netto: stawki dystrybucji G12 dzien 0,3214 / noc 0,1348, vat 0,23
const CENY_DYSTR = { vat: 0.23, stawki_dystrybucji: { dzien: 0.3214, noc: 0.1348 }, oplaty_dystrybucji_mc: { sieciowa: 10, abonament: 3.84, mocowa: 24.05 } };
const idOf = (id, extra = {}) => ({ id_oferty: id, ...CENY_DYSTR, ceny_energii: { dzien: 0.6, noc: 0.4 }, oplata_handlowa_mc: 5, akcyza_kwh: 0, ...extra });
const hassWybor = (stan = "wszystkie", { opcje = WYBOR_OPCJE, extraScen = [], ...r } = {}) => {
  const kopia = (sc, id) => [...sc.slice(0, 7), { ...sc[7], ...idOf(id) }];
  const h = hassZ({
    scenariusze: [
      ["pstryk_G12", "Pstryk + G12", 800, 500, 300, -100, true, { ...meta("pstryk", "Pstryk", "G12"), ...CENY_DYSTR, id_oferty: "", srednia_cena_energii: { przed_tarcza: 0.6, po_tarczy: 0.5 }, akcyza_kwh: 0.005 }],
      ["pstryk_G12w", "Pstryk + G12w", 820, 500, 320, -100, false, { ...meta("pstryk", "Pstryk", "G12w"), ...CENY_DYSTR, vat: 0.23, stawki_dystrybucji: { szczyt: 0.4, pozaszczyt: 0.2 }, id_oferty: "" }],
      ["pstryk_G13active", "Pstryk + G13active", 810, 500, 310, -100, false, { ...meta("pstryk", "Pstryk", "G13active"), ...CENY_DYSTR, stawki_dystrybucji: { szczyt: 0.5, pobor: 0.1 }, id_oferty: "" }],
      kopia(WYBOR("G12", 850, 450, 400), "enea_2026_wybor"), kopia(WYBOR("G12w", 900, 450, 450), "enea_2026_wybor"),
      kopia(PEWNOSC("G12", 700, 400, 300), "enea_eneopewnosc_2026"),
      kopia(["cennik_G12", "Własny + G12", 880, 580, 300, 0, false, meta("kompleksowa", "Własny", "G12")], "cennik"),
      ...extraScen,
    ],
    roznice: { pstryk_G12w: 20, pstryk_G13active: 10, kompleksowa_enea_2026_wybor_G12: 50, kompleksowa_enea_2026_wybor_G12w: 100, kompleksowa_enea_eneopewnosc_2026_G12: -100, cennik_G12: 80 },
    ...r,
  });
  const eid = "select.sprzedawca";
  h.entities[eid] = { entity_id: eid, device_id: "dev1", platform: "porownanie_taryf", translation_key: "sprzedawca" };
  h.states[eid] = { entity_id: eid, state: stan, attributes: { options: opcje } };
  return h;
};
const sekcja2 = (html) => html.split("<h3>2. ")[1];

test("komorkaCeny: brutto = netto × (1 + vat), pod spodem netto; null → „brak danych”", () => {
  const k = komorkaCeny(0.3214, 0.23);
  assert.ok(k.includes("0,3953 zł/kWh"));
  assert.match(k, /<small>netto 0,3214<\/small>/);
  assert.ok(komorkaCeny(10, 0.23, "zł/mies.", 2).includes("12,30 zł/mies."));
  for (const k2 of [komorkaCeny(null, 0.23), komorkaCeny(undefined, 0.23), komorkaCeny(0.3, null)]) { assert.match(k2, /brak danych/); assert.doesNotMatch(k2, /netto/); }
});
test("polskie nazwy stref i etykiety opcji; nieznane zwracane jak są", () => {
  assert.equal(nazwaStrefy("dzien"), "dzień"); assert.equal(nazwaStrefy("pozaszczyt"), "pozaszczyt"); assert.equal(nazwaStrefy("calodobowa"), "całodobowo");
  assert.equal(nazwaStrefy("nowa"), "nowa");
  assert.deepEqual(WYBOR_OPCJE.map((o) => etykietaOferty(o)), ["Wszystkie oferty", "Enea — prawo wyboru", "Enea — EneoPewność", "Tauron — Twój Extra Elektryk 24H", "Tauron — Energia dla natury i pszczół", "PGE — cennik taryfowy", "Energa — Podstawowa 2 lata", "Własny cennik"]);
  assert.equal(etykietaOferty("inny_id"), "inny_id");
});
test("wybór „wszystkie”: sekcja 2 pokazuje wszystkie oferty; select ma opcje z polskimi etykietami i zaznaczoną wybraną", () => {
  const d = zbierzDane(hassWybor("wszystkie"));
  assert.deepEqual(d.wybor, { encja: "select.sprzedawca", stan: "wszystkie", opcje: WYBOR_OPCJE });
  assert.equal(widokSekcji2(d).kompleksowa.length, 4);
  const html = htmlWynikow(d);
  const po = sekcja2(html);
  assert.match(po, /<select data-sprzedawca>/);
  assert.match(po, /<option value="wszystkie" selected>Wszystkie oferty<\/option>/);
  assert.match(po, /<option value="enea_2026_wybor">Enea — prawo wyboru<\/option>/);
  assert.match(po, /<option value="enea_eneopewnosc_2026">Enea — EneoPewność<\/option>/);
  assert.match(po, /<option value="cennik">Własny cennik: Własny<\/option>/);
  assert.equal((html.match(/<select/g) ?? []).length, 1);   // lista tylko w nagłówku sekcji 2
  assert.ok(html.indexOf("<select") > html.indexOf("<h3>2. ") && html.indexOf("<select") < html.indexOf("</h3>", html.indexOf("<h3>2. ")) + 400);
});
test("wybór jednej oferty: wykres, werdykt, brakujące taryfy i uwagi tylko tej oferty; podsumowanie dalej ze wszystkich", () => {
  const wszystkie = htmlWynikow(zbierzDane(hassWybor("wszystkie")));
  const html = htmlWynikow(zbierzDane(hassWybor("enea_2026_wybor")));
  const po = sekcja2(html);
  assert.match(po, /<option value="enea_2026_wybor" selected>/);
  assert.deepEqual([...po.matchAll(/<span class="etykieta">([^<]*)</g)].map((m) => m[1]), ["prawo wyboru · G12", "prawo wyboru · G12w"]);
  assert.match(po, /class="werdykt">Najtańsza: Enea prawo wyboru \+ G12 — o 50,00 zł więcej niż obecna umowa z Pstrykiem</);
  assert.doesNotMatch(po, /EneoPewność · |Własny \+ G12<\/span>/);
  assert.match(po, /Oferta „prawo wyboru” nie obejmuje G13active\./);
  assert.doesNotMatch(po, /Oferta „EneoPewność”/);
  assert.match(po, new RegExp(UWAGA_WYBOR));
  // podsumowanie na górze identyczne i nadal wskazuje najtańszą ofertę ogółem (EneoPewność), choć filtr jej nie pokazuje
  const gora = (h) => h.match(/<p class="podsumowanie">[^]*?<\/p>/)[0];
  assert.equal(gora(html), gora(wszystkie));
  assert.match(gora(html), /najtańsza opcja ogółem: Enea EneoPewność \+ G12, o 100,00 zł mniej/);
  // sekcja 1 bez zmian
  assert.equal(html.split("<h3>2. ")[0], wszystkie.split("<h3>2. ")[0]);
});
test("wybór „cennik”: tylko własny cennik; brak uwag katalogu", () => {
  const po = sekcja2(htmlWynikow(zbierzDane(hassWybor("cennik"))));
  assert.deepEqual([...po.matchAll(/<span class="etykieta">([^<]*)</g)].map((m) => m[1]), ["Własny + G12"]);
  assert.doesNotMatch(po, /nie obejmuje|Uwaga testowa/);
  assert.match(po, /Najtańsza: Własny \+ G12 — o 80,00 zł więcej/);
});
test("wybór spoza listy (po zmianie katalogu) → „wszystkie”, bez błędu; opcja bez pasujących wierszy też", () => {
  for (const stan of ["usunieta_oferta", "unknown"]) {
    const d = zbierzDane(hassWybor(stan));
    assert.equal(widokSekcji2(d).id, "wszystkie");
    assert.equal(widokSekcji2(d).kompleksowa.length, 4);
    assert.match(htmlWynikow(d), /<option value="wszystkie" selected>/);
  }
  const h = hassWybor("puste", { opcje: [...WYBOR_OPCJE, "puste"] });
  assert.equal(widokSekcji2(zbierzDane(h)).id, "wszystkie");   // opcja z listy, ale żaden sensor jej nie ma
  assert.match(htmlWynikow(zbierzDane(h)), /<option value="puste">puste<\/option>/);
});
test("bez encji Sprzedawca (starsza integracja): brak listy, sekcja 2 jak dotąd", () => {
  const h = hassWybor(); delete h.entities["select.sprzedawca"];
  const d = zbierzDane(h);
  assert.equal(d.wybor, null);
  const html = htmlWynikow(d);
  assert.doesNotMatch(html, /<select/);
  assert.equal(widokSekcji2(d).kompleksowa.length, 4);
});
test("etykiety nieznanych opcji z atrybutów sensorów: „sprzedawca — oferta”; cennik z nazwą sprzedawcy", () => {
  const nowa = ["kompleksowa_inna_2027_G12", "Inna Nowa + G12", 860, 450, 410, 0, false, { ...meta("kompleksowa", "Inna", "G12", "Nowa"), ...CENY_DYSTR, id_oferty: "inna_2027" }];
  const h = hassWybor("wszystkie", { opcje: [...WYBOR_OPCJE, "inna_2027", "bez_wierszy"], extraScen: [nowa] });
  const d = zbierzDane(h);
  const html = htmlWynikow(d);
  assert.match(html, /<option value="inna_2027">Inna — Nowa<\/option>/);
  assert.match(html, /<option value="bez_wierszy">bez_wierszy<\/option>/);
  assert.match(html, /<option value="cennik">Własny cennik: Własny<\/option>/);   // meta cennika: sprzedawca „Własny”
  assert.match(html, /<option value="enea_2026_wybor">Enea — prawo wyboru<\/option>/);   // wbudowane etykiety bez zmian
  assert.equal(etykietaOferty("cennik", d.kompleksowa), "Własny cennik: Własny");
  assert.equal(etykietaOferty("cennik", []), "Własny cennik");
  const bez = hassWybor("wszystkie"); for (const e of Object.keys(bez.states)) if (bez.states[e].attributes.scenariusz === "cennik_G12") bez.states[e].attributes.sprzedawca = "";
  assert.match(htmlWynikow(zbierzDane(bez)), /<option value="cennik">Własny cennik<\/option>/);
  const zly = ["kompleksowa_x_G12", "X", 860, 450, 410, 0, false, { ...meta("kompleksowa", "<i>Ex</i>", "G12", "Of"), id_oferty: "x" }];
  assert.ok(htmlWynikow(zbierzDane(hassWybor("wszystkie", { opcje: [...WYBOR_OPCJE, "x"], extraScen: [zly] }))).includes(">&#60;i&#62;Ex&#60;/i&#62; — Of</option>"));
});
test("synchronizujListe: lista pokazuje widok efektywny (opcja bez wierszy → wszystkie), nawet gdy HTML się nie zmienił", () => {
  const lista = { value: "bez_wierszy" };   // przeglądarka ustawiła wybór użytkownika
  const korzen = { querySelector: (s) => (s === "select[data-sprzedawca]" ? lista : null) };
  synchronizujListe(korzen, zbierzDane(hassWybor("bez_wierszy", { opcje: [...WYBOR_OPCJE, "bez_wierszy"] })));
  assert.equal(lista.value, "wszystkie");
  synchronizujListe(korzen, zbierzDane(hassWybor("cennik")));
  assert.equal(lista.value, "cennik");
  synchronizujListe({ querySelector: () => null }, zbierzDane(hassWybor("cennik")));   // brak listy: bez błędu
  synchronizujListe(korzen, zbierzDane(hassWrzesien()));   // brak encji Sprzedawca: lista nietknięta
  assert.equal(lista.value, "cennik");
});
test("a11y: pusty nagłówek kolumny tabeli średniej Pstryk ma ukrytą etykietę, podpis wspomina opłatę handlową Pstryka", () => {
  const html = htmlCenSekcji1(zbierzDane(hassWybor("wszystkie")));
  assert.doesNotMatch(html, /<th scope="col"><\/th>/);
  assert.match(html, /<th scope="col"><span class="ukryte">Pozycja<\/span><\/th>/);
  assert.match(html, /<caption>Pstryk: średnia cena energii w okresie \(z opłatą handlową Pstryka\)<\/caption>/);
});
test("nieznany id oferty na liście → sam id, escapowany", () => {
  const html = htmlWynikow(zbierzDane(hassWybor("wszystkie", { opcje: [...WYBOR_OPCJE, "<b>x</b>"] })));
  assert.match(html, /<option value="&#60;b&#62;x&#60;\/b&#62;">&#60;b&#62;x&#60;\/b&#62;<\/option>/);
  assert.doesNotMatch(html, /<b>x/);
});
test("kluczRenderu zmienia się z wyborem Sprzedawcy", () => {
  assert.notEqual(kluczRenderu(hassWybor("wszystkie")), kluczRenderu(hassWybor("cennik")));
});
test("dwa <details>: sekcja 1 i sekcja 2, otwarte tylko te zapamiętane", () => {
  const d = zbierzDane(hassWybor("wszystkie"));
  const html = htmlWynikow(d);
  assert.equal((html.match(/<details/g) ?? []).length, 2);
  assert.ok(html.split("<h3>2. ")[0].includes('<details class="ceny" data-id="s1">'));
  assert.ok(sekcja2(html).includes('<details class="ceny" data-id="s2">'));
  assert.equal((html.match(/<summary>Ceny w tej sekcji<\/summary>/g) ?? []).length, 2);
  assert.doesNotMatch(html, / open>/);
  const otw = htmlWynikow(d, { otwarte: new Set(["s2"]) });
  assert.ok(otw.includes('data-id="s2" open>') && otw.includes('data-id="s1">'));
});
test("bez ofert kompleksowych jest tylko <details> sekcji 1", () => {
  assert.equal((htmlWynikow(zbierzDane(hassWrzesien())).match(/<details/g) ?? []).length, 1);
});
test("ceny sekcji 1: stawki każdej taryfy per strefa (brutto + netto), opłaty stałe, średnia Pstryk przed/po Tarczy", () => {
  const html = htmlCenSekcji1(zbierzDane(hassWybor("wszystkie")));
  assert.match(html, /<th scope="row" rowspan="2">G12<\/th><td>dzień<\/td><td class="cena"><span class="brutto">0,3953 zł\/kWh<\/span><small>netto 0,3214<\/small>/);
  assert.match(html, /<td>noc<\/td><td class="cena"><span class="brutto">0,1658 zł\/kWh<\/span><small>netto 0,1348<\/small>/);   // 0,1348 × 1,23
  assert.match(html, /<td>szczyt<\/td>[^]*?0,4920 zł\/kWh<\/span><small>netto 0,4000/);
  assert.ok(html.indexOf(">G12<") < html.indexOf(">G12w<"));
  for (const t of ["Opłata sieciowa stała", "Abonament", "Opłata mocowa"]) assert.ok(html.includes(t));
  assert.ok(html.includes("4,72 zł/mies.") && html.includes("<small>netto 3,84</small>") && html.includes("29,58 zł/mies."));
  assert.match(html, /przed Tarczą<\/th><td class="cena"><span class="brutto">0,7380 zł\/kWh<\/span><small>netto 0,6000/);
  assert.match(html, /po Tarczy<\/th><td class="cena"><span class="brutto">0,6150 zł\/kWh<\/span><small>netto 0,5000/);
  assert.ok(html.includes("Akcyza (bez VAT)") && html.includes("0,0050 zł/kWh"));
  assert.ok(!/Dzien|dzien|pozaszczyt_/.test(html));
});
test("ceny sekcji 1: okres bez odczytów (średnia null) i brak atrybutów → „brak danych”", () => {
  const h = hassWybor("wszystkie");
  const eid = Object.keys(h.entities).find((e) => h.states[e].attributes.scenariusz === "pstryk_G12" && h.entities[e].translation_key === "razem");
  h.states[eid].attributes.srednia_cena_energii = { przed_tarcza: null, po_tarczy: null };
  const html = htmlCenSekcji1(zbierzDane(h));
  assert.equal((html.match(/przed Tarczą<\/th><td class="cena brak">brak danych/g) ?? []).length, 1);
  assert.match(html, /po Tarczy<\/th><td class="cena brak">brak danych/);
  const goly = htmlCenSekcji1(zbierzDane(hassWrzesien()));   // sensory bez atrybutów cen
  assert.ok(goly.includes("brak danych") && !goly.includes("NaN") && !goly.includes("undefined"));
});
test("ceny sekcji 2: ceny pokazanej oferty per strefa + opłata handlowa; filtr zawęża tabelę", () => {
  const d = zbierzDane(hassWybor("enea_eneopewnosc_2026"));
  const html = htmlCenSekcji2(d, widokSekcji2(d));
  assert.match(html, /Enea — EneoPewność · G12<\/th><td>dzień<\/td><td class="cena"><span class="brutto">0,7380 zł\/kWh<\/span><small>netto 0,6000/);
  assert.match(html, /<td>noc<\/td><td class="cena"><span class="brutto">0,4920 zł\/kWh<\/span><small>netto 0,4000/);
  assert.ok(html.includes("Opłata handlowa") && html.includes("6,15 zł/mies.") && html.includes("<small>netto 5,00</small>"));
  assert.doesNotMatch(html, /prawo wyboru|Własny cennik/);
  const wsz = htmlCenSekcji2(zbierzDane(hassWybor("wszystkie")), widokSekcji2(zbierzDane(hassWybor("wszystkie"))));
  for (const e of ["Enea — prawo wyboru", "Enea — EneoPewność", "Własny cennik"]) assert.ok(wsz.includes(e));
  assert.ok(wsz.indexOf("Enea — prawo wyboru") < wsz.indexOf("Enea — EneoPewność") && wsz.indexOf("Enea — EneoPewność") < wsz.indexOf("Własny cennik"));   // kolejność z listy opcji
});
test("ceny sekcji 2: brak atrybutów oferty → „brak danych”; nazwy escapowane; akcyza własnego cennika", () => {
  const zla = oferta("x", "<b>oferta</b>", [], "G12", 700, 400, 300);
  const d = zbierzDane(hassZ({ scenariusze: [pstryk(G12), zla], roznice: { kompleksowa_x_G12: -100 } }));
  const html = htmlCenSekcji2(d, widokSekcji2(d));
  assert.ok(html.includes("brak danych") && !html.includes("<b>oferta"));
  assert.ok(html.includes("&#60;b&#62;oferta&#60;/b&#62; · G12"));
  const h = hassWybor("cennik");
  const eid = Object.keys(h.entities).find((e) => h.states[e].attributes.scenariusz === "cennik_G12" && h.entities[e].translation_key === "razem");
  h.states[eid].attributes.akcyza_kwh = 0.005;
  const dc = zbierzDane(h);
  assert.ok(htmlCenSekcji2(dc, widokSekcji2(dc)).includes("Własny cennik · Akcyza</th>"));
});
test("brutto z tabeli × kWh odtwarza kwotę sekcji (syntetycznie)", () => {
  // 100 kWh po 0,3214 netto → 39,53 zł brutto; tyle samo co netto × 1,23 liczone na sumie
  const brutto = Number(komorkaCeny(0.3214, 0.23).match(/brutto">([\d,]+)/)[1].replace(",", "."));
  assert.ok(Math.abs(brutto * 100 - 0.3214 * 100 * 1.23) < 0.005 * 100);
});

// --- v0.6.0: grupowanie listy „Sprzedawca” po sprzedawcy (Enea → Tauron → PGE → Energa) ---

const OPCJE_6 = ["wszystkie", "enea_2026_wybor", "enea_eneopewnosc_2026", "tauron_extra_2026", "tauron_natura_2026", "pge_taryfowy_gtpa", "energa_podstawowa_2026", "cennik"];
const oferta6 = (id, sprzedawca, of, t, razem) => {
  const sc = [`kompleksowa_${id}_${t}`, `${sprzedawca} ${of} + ${t}`, razem, 400, 300, 0, false, meta("kompleksowa", sprzedawca, t, of)];
  return [...sc.slice(0, 7), { ...sc[7], id_oferty: id }];
};
const KATALOG6 = (stan = "wszystkie") => hassWybor(stan, { opcje: OPCJE_6, extraScen: [
  PSEZ,
  oferta6("tauron_extra_2026", "Tauron", "Twój Extra Elektryk 24H", "G12", 720),
  oferta6("tauron_natura_2026", "Tauron", "Energia dla natury i pszczół", "G12", 730),
  oferta6("pge_taryfowy_gtpa", "PGE", "cennik taryfowy", "G12", 900),
  oferta6("energa_podstawowa_2026", "Energa", "Podstawowa 2 lata", "G12", 715),
]});

test("grupyOpcji: „wszystkie” u góry, grupy wg sprzedawcy (Enea → Tauron → PGE → Energa), „cennik” na końcu", () => {
  const d = zbierzDane(KATALOG6());
  assert.deepEqual(grupyOpcji(OPCJE_6, d.kompleksowa), {
    gory: ["wszystkie"],
    grupy: [
      { sprzedawca: "Enea", opcje: ["enea_2026_wybor", "enea_eneopewnosc_2026"] },
      { sprzedawca: "Tauron", opcje: ["tauron_extra_2026", "tauron_natura_2026"] },
      { sprzedawca: "PGE", opcje: ["pge_taryfowy_gtpa"] },
      { sprzedawca: "Energa", opcje: ["energa_podstawowa_2026"] },
    ],
    dol: ["cennik"],
  });
});
test("HTML listy: <optgroup> w kolejności, „wszystkie” u góry / „cennik” na końcu, pełny katalog 6 ofert w sekcji 2", () => {
  const d = zbierzDane(KATALOG6());
  const po = sekcja2(htmlWynikow(d));
  assert.deepEqual([...po.matchAll(/<optgroup label="([^"]+)">/g)].map((m) => m[1]), ["Enea", "Tauron", "PGE", "Energa"]);
  assert.ok(po.indexOf('<option value="wszystkie" selected>') < po.indexOf('<optgroup label="Enea">'));
  assert.ok(po.indexOf('<optgroup label="Energa">') < po.indexOf('<option value="cennik"'));
  assert.match(po, /<option value="tauron_extra_2026">Tauron — Twój Extra Elektryk 24H<\/option>/);
  assert.match(po, /<option value="tauron_natura_2026">Tauron — Energia dla natury i pszczół<\/option>/);
  assert.match(po, /<option value="pge_taryfowy_gtpa">PGE — cennik taryfowy<\/option>/);
  assert.match(po, /<option value="energa_podstawowa_2026">Energa — Podstawowa 2 lata<\/option>/);
  assert.equal(new Set(d.kompleksowa.filter((s) => s.idOferty !== "cennik").map((s) => s.idOferty)).size, 6);   // Enea ×2 + Tauron ×2 + PGE + Energa
  for (const e of ["Enea prawo wyboru + G12", "Enea EneoPewność + G12", "Tauron Twój Extra Elektryk 24H + G12", "Tauron Energia dla natury i pszczół + G12", "PGE cennik taryfowy + G12", "Energa Podstawowa 2 lata + G12"]) assert.ok(po.includes(e), e);
});
test("nagłówek sekcji 2: pojedynczy sprzedawca Tauron → dopełniacz „od Tauronu”", () => {
  assert.match(sekcja2(htmlWynikow(zbierzDane(KATALOG6("tauron_natura_2026")))), /^Umowa kompleksowa Tauron \(prąd i dystrybucja od Tauronu\)<\/h3>/);
});
test("adnotacje braków dla nowych ofert: brakuje im G12w, G12sezON i G13active", () => {
  const po = sekcja2(htmlWynikow(zbierzDane(KATALOG6())));
  for (const of_ of ["Twój Extra Elektryk 24H", "Energia dla natury i pszczół", "cennik taryfowy", "Podstawowa 2 lata"]) {
    assert.ok(po.includes(`Oferta „${of_}” nie obejmuje G12w ani G12sezON ani G13active.`), of_);
  }
});
test("htmlOpcji: opcja bez wiersza na końcu, label optgroup i etykieta opcji escapowane", () => {
  const zly = { idOferty: "x", sprzedawca: "\"><img onerror=1>", oferta: "Of", taryfa: "G12" };
  const html = htmlOpcji(["wszystkie", "x", "bez"], [zly], null);
  assert.ok(html.includes('<optgroup label="&#34;&#62;&#60;img onerror=1&#62;">'));
  assert.ok(html.includes('<option value="x">&#34;&#62;&#60;img onerror=1&#62; — Of</option>'));
  assert.ok(html.includes('<option value="bez">bez</option>'));
  assert.ok(html.indexOf('<option value="bez">') > html.indexOf("</optgroup>"));
  assert.doesNotMatch(html, /<img/);
});
