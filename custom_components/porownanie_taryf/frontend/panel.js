// Panel „Porównanie taryf” (spec v0.7 §2–§6): waniliowy web component, bez bibliotek, bez kroku budowania, bez zasobów z sieci.
// Czyste funkcje są eksportowane dla testów (node --test tests/js/*.test.mjs); element definiowany tylko w przeglądarce.

const DOMENA = "porownanie_taryf";
const ISO = /^\d{4}-\d{2}-\d{2}$/;
const RODZAJE = ["dzien", "miesiac", "rok", "zakres"];
const liczba = (st) => {
  const n = parseFloat(st?.state);
  return Number.isFinite(n) ? n : null;
};
const zaokr = (x) => Math.round(x * 100) / 100 + 0; // + 0: bez „-0”
const porownaj = (a, b) => a.razem - b.razem || b.obecny - a.obecny;
const encjeIntegracji = (hass) => Object.values(hass?.entities ?? {}).filter((e) => e.platform === DOMENA);

// undefined = rejestr encji frontendu jeszcze pusty (panel nic nie pokazuje); null = rejestr jest, ale bez naszej integracji
export function zbierzDane(hass) {
  if (!Object.keys(hass?.entities ?? {}).length) return undefined;
  const wszystkie = encjeIntegracji(hass);
  // kilka wpisów → urządzenie pierwszego (po entity_id) sensora `razem`
  const pierwszy = wszystkie.filter((e) => e.translation_key === "razem").map((e) => e.entity_id).sort()[0];
  if (!pierwszy) return null;
  const encje = wszystkie.filter((e) => e.device_id === hass.entities[pierwszy].device_id);
  const jedna = (tk) => encje.find((e) => e.translation_key === tk)?.entity_id;
  const stany = (tk) => encje.filter((e) => e.translation_key === tk).map((e) => hass.states?.[e.entity_id]).filter(Boolean);

  const roznice = new Map(stany("roznica").map((s) => [s.attributes?.scenariusz, liczba(s)]));
  const razem = stany("razem");
  const scenariusze = razem
    .filter((s) => liczba(s) !== null && s.attributes?.scenariusz)
    .map(({ attributes: a, ...s }) => ({
      klucz: a.scenariusz,
      etykieta: a.etykieta ?? a.scenariusz,
      // brak atrybutów grupy (sensory sprzed v0.3.0) = Pstryk
      grupa: a.grupa === "kompleksowa" ? "kompleksowa" : "pstryk",
      sprzedawca: a.sprzedawca ?? null,
      taryfa: a.taryfa ?? a.scenariusz.split("_").at(-1) ?? null,
      oferta: a.oferta ?? "", // "" = Pstryk albo własny cennik
      idOferty: a.id_oferty ?? "", // klucz katalogu albo "cennik"; Pstryk ""
      vat: typeof a.vat === "number" ? a.vat : null,
      ceny: { // atrybuty cen (netto); brak = null → „brak danych”
        stawki: a.stawki_dystrybucji ?? null, oplatyMc: a.oplaty_dystrybucji_mc ?? null, energia: a.ceny_energii ?? null,
        handlowaMc: a.oplata_handlowa_mc ?? null, akcyza: a.akcyza_kwh ?? null, srednia: a.srednia_cena_energii ?? null,
      },
      uwagi: Array.isArray(a.uwagi) ? a.uwagi : [],
      cenaDo: typeof a.cena_do === "string" ? a.cena_do : "", // "" = bez gwarancji stałości ceny
      znaczniki: Array.isArray(a.znaczniki) ? a.znaczniki.filter((z) => Array.isArray(z) && z.length >= 2) : [], // [[etykieta, dymek], …]
      razem: liczba(s),
      sprzedazPo: a.sprzedaz_po ?? 0,
      dystrybucja: a.dystrybucja ?? 0,
      tarcza: a.tarcza ?? 0,
      roznica: roznice.get(a.scenariusz) ?? null,
      obecny: a.obecny === true,
    }));
  const obecny = scenariusze.find((s) => s.obecny) ?? null;
  for (const s of scenariusze) {
    // stan sensora `roznica` jest dokładny (liczony przed zaokrągleniem); odejmowanie to tylko zapas
    if (s.obecny) s.roznica = 0;
    else if (s.roznica === null && obecny) s.roznica = zaokr(s.razem - obecny.razem);
  }
  const grupa = (g) => scenariusze.filter((s) => s.grupa === g).sort(porownaj);
  const ranking = grupa("pstryk");
  const kompleksowa = grupa("kompleksowa");
  // uwagi do ofert katalogu: grupa (sprzedawca, oferta) z atrybutów; własny cennik (oferta "") uwag nie dostaje
  const oferty = new Map();
  for (const s of scenariusze.filter((x) => x.grupa === "kompleksowa" && x.oferta)) {
    const k = JSON.stringify([s.sprzedawca, s.oferta]);
    if (!oferty.has(k)) oferty.set(k, { sprzedawca: s.sprzedawca, oferta: s.oferta, uwagi: [...new Set(s.uwagi)] }); // uwagi z pierwszego sensora oferty
  }
  const uwagi = [...oferty.values()].filter((o) => o.uwagi.length);

  const a = (razem.find((s) => s.attributes?.obecny) ?? razem[0])?.attributes ?? {};
  const pokrycie = typeof a.pokrycie === "number" ? a.pokrycie : null;
  const encjeOkresu = { okres: jedna("okres"), data: jedna("data"), koniec: jedna("koniec") };
  const stanOkresu = (k) => hass.states?.[encjeOkresu[k]]?.state ?? null;
  return {
    okres: { rodzaj: stanOkresu("okres"), data: stanOkresu("data"), koniec: stanOkresu("koniec"), encje: encjeOkresu },
    // okres bez żadnego odczytu (np. przyszły miesiąc) dałby ranking samych zer
    brakWyniku: !obecny || pokrycie === 0,
    powod: a.powod ?? (pokrycie === 0 ? "brak_odczytow" : null),
    ranking,
    kompleksowa,
    taryfy: Array.isArray(a.taryfy) ? a.taryfy.map(String) : null, // kolejność kolumn tabeli z integracji (null = starsza integracja)
    uwagi,
    obecny,
    kwh: { tanie: liczba(hass.states?.[jedna("kwh_tanie")]), drogie: liczba(hass.states?.[jedna("kwh_drogie")]) },
    pokrycie,
    okresOd: a.okres_od ?? null,
    okresDo: a.okres_do ?? null,
    ostrzezenia: [...new Set(razem.flatMap((s) => s.attributes?.ostrzezenia ?? []))].sort(),
  };
}

const format = (x, opcje = {}) =>
  new Intl.NumberFormat("pl", { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: "always", ...opcje }).format(zaokr(x));

export const kwota = (x, zeZnakiem = false) =>
  format(x, zeZnakiem ? { signDisplay: "exceptZero" } : {}).replace("-", "−") + " zł";

// drugi udział to 100 − pierwszy, żeby udziały zawsze dawały 100%
export function udzialy(tanie, drogie) {
  const suma = (tanie ?? 0) + (drogie ?? 0);
  if (!(suma > 0)) return [null, null];
  const t = tanie === null ? null : Math.round((tanie / suma) * 100);
  return [t, drogie === null ? null : t === null ? 100 : 100 - t];
}

const kwh = (x) => (x === null ? "—" : `${format(x)} kWh`);

const mozna = (dane) => dane?.obecny && !dane.brakWyniku;

// --- tabela oferta × taryfa (v0.7) ---

export const PROG = 0.01; // różnica poniżej 1% kosztu obecnej umowy = „≈ tyle samo”
const nazwaWiersza = (s) => (s.grupa === "pstryk" ? "Pstryk" : s.oferta ? `${s.sprzedawca} ${s.oferta}` : "Własny cennik");

// kolumny = taryfy z integracji (atrybut `taryfy`), potem ewentualne dodatkowe w kolejności pierwszego wystąpienia
export const kolumnyTaryf = (dane) => [...new Set([...(dane.taryfy ?? []), ...[...dane.ranking, ...dane.kompleksowa].map((s) => s.taryfa)])];

// wymaga dane.obecny (wywołanie tylko gdy `mozna(dane)`); komórka = scenariusz: oferta (wiersz) × taryfa (kolumna)
export function wierszeTabeli(dane) {
  const scenariusze = [...dane.ranking, ...dane.kompleksowa];
  const o = dane.obecny;
  const kolumny = kolumnyTaryf(dane);
  const prog = zaokr(PROG * o.razem);
  const wiersze = new Map();
  for (const s of scenariusze) {
    const klucz = s.grupa === "pstryk" ? "pstryk" : s.idOferty || JSON.stringify([s.sprzedawca, s.oferta]);
    if (!wiersze.has(klucz)) wiersze.set(klucz, { klucz, etykieta: nazwaWiersza(s), znaczniki: [], cenaDo: "", obecny: false, komorki: Object.fromEntries(kolumny.map((t) => [t, null])) });
    const w = wiersze.get(klucz);
    if (!w.cenaDo) w.cenaDo = s.cenaDo;
    if (!w.znaczniki.length) w.znaczniki = s.znaczniki;
    w.obecny ||= s.obecny;
    w.komorki[s.taryfa] = { wiersz: w.etykieta, taryfa: s.taryfa, roznica: s.roznica, razem: s.razem, obecny: s.obecny };
  }
  const komorki = [...wiersze.values()].flatMap((w) => Object.values(w.komorki).filter(Boolean));
  const inne = komorki.filter((c) => !c.obecny);
  const maks = Math.max(0, ...inne.map((c) => Math.abs(c.roznica)));
  for (const c of komorki) {
    const rowne = c.obecny || c.roznica === 0 || Math.abs(c.roznica) < prog;
    c.klasa = rowne ? "rowne" : c.roznica < 0 ? "taniej" : "drozej";
    c.sila = rowne ? 0 : Math.abs(c.roznica) / maks; // 0…1, nasycenie koloru
  }
  const tarcza = Math.round(-o.tarcza);
  const pstryk = wiersze.get("pstryk");
  if (pstryk && tarcza > 0) pstryk.znaczniki = [[`Tarcza −${tarcza} zł`, `Tarcza Pstryk (${kwota(o.tarcza)} w tym okresie) jest już odjęta od kosztu.`]];
  for (const w of wiersze.values()) w.min = Math.min(...Object.values(w.komorki).filter(Boolean).map((c) => c.roznica));
  const posortowane = [...wiersze.values()].sort((a, b) => a.min - b.min || b.obecny - a.obecny || a.etykieta.localeCompare(b.etykieta, "pl"));
  const najtansza = (lista) => lista.reduce((n, c) => (!n || c.roznica < n.roznica ? c : n), null);
  const najBez = najtansza(posortowane.map((w) => w.komorki[o.taryfa]).filter((c) => c && !c.obecny));
  const naj = najtansza([najBez, ...posortowane.flatMap((w) => Object.values(w.komorki).filter((c) => c && !c.obecny))].filter(Boolean)); // remis: komórka w obecnej taryfie
  const istotna = (c) => c && c.roznica < 0 && c.roznica <= -prog; // oszczędność co najmniej 1% (prog 0 przy zerowych kosztach: tylko ujemna)
  if (istotna(naj)) naj.najtansza = true;
  if (istotna(najBez) && najBez !== naj) najBez.najtanszaBez = true;
  return { kolumny, obecnaTaryfa: o.taryfa, wiersze: posortowane, naj, najBez, prog };
}

// linijka odpowiedzi (spec §4); null = brak obecnej umowy lub wyniku (panel pokazuje wtedy komunikat)
export function odpowiedz(dane) {
  if (!mozna(dane)) return null;
  const { naj, najBez, prog } = wierszeTabeli(dane);
  const o = dane.obecny;
  if (!naj?.najtansza) return { typ: "obecna", blisko: !!naj && Math.abs(naj.roznica) < prog, pod: `${kwota(o.razem)} (${o.etykieta})` };
  const wymaga = naj.taryfa !== o.taryfa;
  const bez = wymaga && !!najBez?.najtanszaBez;
  const cel = bez ? najBez : naj;
  return {
    typ: "najtaniej", oferta: cel.wiersz, taryfa: cel.taryfa, mniej: zaokr(-cel.roznica),
    bezZmiany: bez, zmianaTaryfy: wymaga && !bez,
    obok: bez ? `ze zmianą na ${naj.wiersz === cel.wiersz ? "" : `${naj.wiersz} + `}${naj.taryfa}: ${kwota(naj.roznica, true)}` : "",
    pod: `${kwota(cel.razem)} zamiast ${kwota(o.razem)} (${o.etykieta})`,
  };
}

export function przesun(rodzaj, dataISO, krok) {
  const [r, m, d] = dataISO.split("-").map(Number);
  const nowa = { dzien: [r, m - 1, d + krok], miesiac: [r, m - 1 + krok, 1], rok: [r + krok, 0, 1] }[rodzaj];
  return nowa ? new Date(Date.UTC(...nowa)).toISOString().slice(0, 10) : dataISO;
}

const dzien = (iso) => new Date(`${iso}T00:00:00Z`);

export function nazwaOkresu(rodzaj, odISO, doISO) {
  if (!ISO.test(odISO ?? "")) return "";
  if (rodzaj === "rok") return `rok ${odISO.slice(0, 4)}`;
  if (rodzaj === "miesiac") {
    return new Intl.DateTimeFormat("pl", { timeZone: "UTC", month: "long", year: "numeric" }).format(dzien(odISO));
  }
  const f = new Intl.DateTimeFormat("pl", { timeZone: "UTC", day: "numeric", month: "long", year: "numeric" });
  if (rodzaj !== "zakres" || !ISO.test(doISO ?? "") || doISO === odISO) return f.format(dzien(odISO));
  // koniec przed początkiem (brak wyniku): pokaż obie daty, żeby błąd był widoczny
  return doISO > odISO ? f.formatRange(dzien(odISO), dzien(doISO)) : `${f.format(dzien(odISO))} – ${f.format(dzien(doISO))}`;
}

const OSTRZEZENIA = {
  pokrycie_ponizej_95: () => "Dane są niepełne: brakuje odczytów licznika z ponad 5% godzin tego okresu, więc kwoty mogą być zaniżone.",
  okres_krotszy_niz_miesiac: () => "Okres jest krótszy niż miesiąc, więc wynik jest tylko orientacyjny — Tarcza i część opłat rozliczane są miesięcznie.",
  tarcza_niezweryfikowana: (rok) => `Zasady Tarczy Pstryk na ${rok} nie są jeszcze potwierdzone, więc rabat za ten rok jest szacunkowy.`,
  brak_tarczy: (rm) => `W miesiącu ${rm.slice(5)}.${rm.slice(0, 4)} Tarcza Pstryk nie obowiązuje, więc koszt liczony jest bez rabatu.`,
  stawki_spoza_roku: (rok) => `Stawki dystrybucji pochodzą z taryfy na ${rok}, a okres obejmuje inny rok, więc koszt dystrybucji jest przybliżony.`,
};

export function tekstOstrzezenia(kod) {
  const [nazwa, arg = ""] = String(kod).split(":");
  return Object.hasOwn(OSTRZEZENIA, nazwa) ? OSTRZEZENIA[nazwa](arg) : kod;
}

// Render tylko gdy zmieniły się encje panelu: każda zmiana stanu w HA podmienia `hass`.
export const kluczRenderu = (hass) =>
  JSON.stringify([
    Object.keys(hass?.entities ?? {}).length > 0, // pusty rejestr (nic nie rysujemy) ≠ rejestr bez naszej integracji (komunikat)
    ...encjeIntegracji(hass).map((e) => {
      const s = hass.states?.[e.entity_id];
      return [e.entity_id, e.device_id, e.translation_key, s?.state, s?.attributes];
    }),
  ]);

const STREFY = {
  calodobowa: "całodobowo", dzien: "dzień", noc: "noc", szczyt: "szczyt", pozaszczyt: "pozaszczyt", zalecana: "strefa zalecana",
  pozostale: "pozostałe godziny", ograniczanie: "ograniczanie poboru", pobor: "zalecany pobór",
};
export const nazwaStrefy = (z) => (Object.hasOwn(STREFY, z) ? STREFY[z] : String(z));
const OPLATY = { sieciowa: "Opłata sieciowa stała", abonament: "Abonament", mocowa: "Opłata mocowa" };

const T = {
  tytul: "Porównanie taryf", okres: "Okres", rodzaje: ["Dzień", "Miesiąc", "Rok", "Zakres"],
  wstecz: "Poprzedni okres", dalej: "Następny okres", od: "Od", do: "Do",
  cenyIStawki: "Ceny i stawki", uwagiDoOfert: "Uwagi do ofert", brakDanych: "brak danych",
  taryfa: "Taryfa", strefa: "Strefa", oferta: "Oferta", ofertaTaryfa: "Oferta i taryfa", cenyEnergii: "Ceny energii", cenaKwh: "Cena za kWh", doplaty: "Opłaty stałe (zł/mies.)",
  stawkiDystr: "Dystrybucja: stawki za kWh", srednia: "Pstryk: średnia cena energii w okresie (z opłatą handlową Pstryka)", pozycja: "Pozycja", przedTarcza: "przed Tarczą", poTarczy: "po Tarczy",
  akcyza: "Akcyza", akcyzaBezVat: "Akcyza (bez VAT)", handlowa: "Opłata handlowa", razemOplaty: "Opłaty",
  tarcza: "Tarcza Pstryk", zuzycie: "Zużycie",
  rada: "O zmianie taryfy decyduj na okresie co najmniej 12 miesięcy.",
  brakIntegracji: "Dodaj integrację Porównanie taryf",
  brakIntegracjiOpis: "Ustawienia → Urządzenia i usługi → Dodaj integrację → Porównanie taryf.",
  powody: {
    koniec_przed_data: "Koniec zakresu jest wcześniejszy niż jego początek. Popraw daty powyżej.",
    brak_odczytow: "Brak odczytów licznika w tym okresie.",
  },
  brakWyniku: "Brak wyniku dla tego okresu. Dane z Pstryk mogą się jeszcze wczytywać — spróbuj za chwilę.",
};

export const tekst = (klucz) => T[klucz];

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

// brutto (= netto × (1 + vat)) wielkim drukiem, pod nim „netto X”; brak liczby → „brak danych”
export function komorkaCeny(netto, vat, jednostka = "zł/kWh", miejsca = 4) {
  if (!Number.isFinite(netto) || !Number.isFinite(vat)) return `<td class="cena brak">${T.brakDanych}</td>`;
  const f = (x) => new Intl.NumberFormat("pl", { minimumFractionDigits: miejsca, maximumFractionDigits: miejsca, useGrouping: "always" }).format(x);
  return `<td class="cena"><span class="brutto">${f(netto * (1 + vat))} ${jednostka}</span><small>netto ${f(netto)}</small></td>`;
}
const komorkaBezVat = (x) => // akcyza Pstryk (z API): poza podstawą VAT, więc jedna liczba
  Number.isFinite(x) ? `<td class="cena"><span class="brutto">${new Intl.NumberFormat("pl", { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(x)} zł/kWh</span></td>` : `<td class="cena brak">${T.brakDanych}</td>`;
const tabela = (podpis, naglowki, wiersze) =>
  `<div class="tabela"><table><caption>${podpis}</caption><thead><tr>${naglowki.map((h) => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${wiersze.join("")}</tbody></table></div>`;
const wierszeStref = (nazwaHtml, stawki, vat, jednostka) => {
  const zony = Object.entries(stawki ?? {});
  if (!zony.length) return [`<tr><th scope="row">${nazwaHtml}</th><td>—</td>${komorkaCeny(null)}</tr>`];
  return zony.map(([z, v], i) => `<tr>${i ? "" : `<th scope="row" rowspan="${zony.length}">${nazwaHtml}</th>`}<td>${esc(nazwaStrefy(z))}</td>${komorkaCeny(v, vat, jednostka)}</tr>`);
};
const details = (id, ui, tytul, tresc) =>
  `<details class="ceny" data-id="${id}"${ui?.otwarte?.has(id) ? " open" : ""}><summary>${tytul}</summary>${tresc}</details>`;

// stawki dystrybucji każdej taryfy (strefy + opłaty stałe) i średnia cena energii Pstryk przed/po Tarczy
export function htmlCenSekcji1(dane) {
  const kol = kolumnyTaryf(dane);
  const po_taryfie = new Map();
  for (const s of dane.ranking) if (!po_taryfie.has(s.taryfa)) po_taryfie.set(s.taryfa, s);
  const wiersze = [...po_taryfie.values()].sort((a, b) => kol.indexOf(a.taryfa) - kol.indexOf(b.taryfa));
  const stawki = tabela(T.stawkiDystr, [T.taryfa, T.strefa, T.cenaKwh], wiersze.flatMap((s) => wierszeStref(esc(s.taryfa), s.ceny.stawki, s.vat, "zł/kWh")));
  const klucze = [...new Set(wiersze.flatMap((s) => Object.keys(s.ceny.oplatyMc ?? {})))];
  const stale = klucze.length
    ? tabela(T.doplaty, [T.taryfa, ...klucze.map((k) => esc(Object.hasOwn(OPLATY, k) ? OPLATY[k] : k))],
      wiersze.map((s) => `<tr><th scope="row">${esc(s.taryfa)}</th>${klucze.map((k) => komorkaCeny(s.ceny.oplatyMc?.[k], s.vat, "zł/mies.", 2)).join("")}</tr>`))
    : "";
  const p = dane.ranking.find((s) => s.ceny.srednia) ?? dane.ranking[0];
  const sr = p?.ceny.srednia ?? {};
  const pstryk = tabela(T.srednia, [`<span class="ukryte">${T.pozycja}</span>`, T.cenaKwh], [
    `<tr><th scope="row">${T.przedTarcza}</th>${komorkaCeny(sr.przed_tarcza, p?.vat)}</tr>`,
    `<tr><th scope="row">${T.poTarczy}</th>${komorkaCeny(sr.po_tarczy, p?.vat)}</tr>`,
    ...(Number.isFinite(p?.ceny.akcyza) ? [`<tr><th scope="row">${T.akcyzaBezVat}</th>${komorkaBezVat(p.ceny.akcyza)}</tr>`] : []),
  ]);
  return stawki + stale + pstryk;
}

// ceny energii ofert (własny cennik też) w strefach i opłaty handlowe
export function htmlCenSekcji2(dane) {
  const kol = kolumnyTaryf(dane);
  const grupy = new Map(); // (oferta, taryfa) → pierwszy wiersz; oferta → pierwszy wiersz
  const oferty = new Map();
  for (const s of dane.kompleksowa) {
    const id = s.idOferty || JSON.stringify([s.sprzedawca, s.oferta]);
    if (!grupy.has(`${id}|${s.taryfa}`)) grupy.set(`${id}|${s.taryfa}`, s);
    if (!oferty.has(id)) oferty.set(id, s);
  }
  const nazwaOferty = (s) => esc(nazwaWiersza(s));
  const poNazwie = (a, b) => nazwaWiersza(a).localeCompare(nazwaWiersza(b), "pl");
  const energia = tabela(T.cenyEnergii, [T.ofertaTaryfa, T.strefa, T.cenaKwh],
    [...grupy.values()].sort((a, b) => poNazwie(a, b) || kol.indexOf(a.taryfa) - kol.indexOf(b.taryfa))
      .flatMap((s) => wierszeStref(`${nazwaOferty(s)} · ${esc(s.taryfa)}`, s.ceny.energia, s.vat, "zł/kWh")));
  const oplaty = tabela(T.razemOplaty, [T.oferta, T.handlowa],
    [...oferty.values()].sort(poNazwie).flatMap((s) => [
      `<tr><th scope="row">${nazwaOferty(s)}</th>${komorkaCeny(s.ceny.handlowaMc, s.vat, "zł/mies.", 2)}</tr>`,
      ...(s.ceny.akcyza > 0 ? [`<tr><th scope="row">${nazwaOferty(s)} · ${T.akcyza}</th>${komorkaCeny(s.ceny.akcyza, s.vat)}</tr>`] : []),
    ]));
  return energia + oplaty;
}

const ZMIANA_TARYFY = "Wymaga zmiany taryfy u operatora (wniosek)";
const znacznik = ([etykieta, dymek]) => `<span class="znacznik" title="${esc(dymek)}">${esc(etykieta)}</span>`;

// linijka odpowiedzi nad tabelą (spec §4); `odp` z odpowiedz(dane)
export function htmlOdpowiedzi(odp) {
  if (!odp) return "";
  const pod = `<div class="pod">${esc(odp.pod)}</div>`;
  if (odp.typ === "obecna") return `<div class="odpowiedz"><div class="glowna">Twoja umowa jest najtańsza${odp.blisko ? ' <span class="przygaszone">(różnice poniżej 1%)</span>' : ""}</div>${pod}</div>`;
  const dopisek = odp.bezZmiany ? ` <span class="przygaszone">(bez zmiany taryfy)</span>`
    : odp.zmianaTaryfy ? ` <span class="znacznik ostrzezenie" title="${ZMIANA_TARYFY}">zmiana taryfy</span>` : "";
  return `<div class="odpowiedz"><div class="glowna">Najtaniej: <b>${esc(odp.oferta)} + ${esc(odp.taryfa)}</b> — <b class="taniej">${kwota(odp.mniej)} mniej</b>${odp.zmianaTaryfy ? "" : " niż teraz"}${dopisek}</div>`
    + `${odp.obok ? `<div class="obok">${esc(odp.obok)}</div>` : ""}${pod}</div>`;
}

// tabela oferta × taryfa (spec §3); `t` z wierszeTabeli(dane)
export function htmlTabeli(t) {
  const glowa = t.kolumny.map((k) => (k === t.obecnaTaryfa
    ? `<th scope="col" class="obecna">${esc(k)}<small>obecna</small></th>`
    : `<th scope="col" title="${ZMIANA_TARYFY}">${esc(k)}</th>`)).join("");
  const komorka = (c, k) => {
    const kol = k === t.obecnaTaryfa ? " kol-obecna" : "";
    if (!c) return `<td class="brak${kol}">—</td>`;
    const klasy = `${c.klasa}${kol}${c.najtansza ? " najtansza" : ""}${c.najtanszaBez ? " najtansza-bez" : ""}`;
    const styl = c.klasa === "rowne" ? "" : ` style="--a:${Math.round(20 + 50 * c.sila)}%"`; // nasycenie koloru 20–70%
    const tekst = c.obecny ? `<i class="teraz">teraz</i> ${kwota(c.roznica, true)}` : `${c.klasa === "rowne" ? "≈ " : ""}${kwota(c.roznica, true)}`;
    return `<td class="${klasy}"${styl} title="${esc(`${c.wiersz} + ${c.taryfa}: ${kwota(c.razem)}`)}">${tekst}</td>`;
  };
  const wiersz = (w) => `<tr><th scope="row">${esc(w.etykieta)}${w.znaczniki.map(znacznik).join("")}</th>`
    + `${t.kolumny.map((k) => komorka(w.komorki[k], k)).join("")}<td class="stala">${w.cenaDo ? esc(w.cenaDo) : "—"}</td></tr>`;
  return `<div class="kolory"><table><thead><tr><th><span class="ukryte">Oferta</span></th>${glowa}<th scope="col">cena stała</th></tr></thead>`
    + `<tbody>${t.wiersze.map(wiersz).join("")}</tbody></table></div>`;
}

// --- Zakładka „Fotowoltaika” (spec v0.8) ---
export const BOK_M = 60;
export const PIKSELE = 600;
const KIERUNKI = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const MIESIACE = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"];

export function urlOrto(e, n) {
  const r = BOK_M / 2;
  return "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/HighResolution?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
    + `&LAYERS=Raster&STYLES=&SRS=EPSG:2180&BBOX=${e - r},${n - r},${e + r},${n + r}&WIDTH=${PIKSELE}&HEIGHT=${PIKSELE}&FORMAT=image/png`;
}

// x, y w pikselach wyświetlonego obrazu (szer × wys); północ na górze, oś Y ekranu w dół
export function pikselNaPuwg(x, y, szer, wys, e, n) {
  const r = BOK_M / 2;
  return { e: e - r + (x / szer) * BOK_M, n: n + r - (y / wys) * BOK_M };
}

export const azymutKalenicy = (p1, p2) => ((Math.atan2(p2.e - p1.e, p2.n - p1.n) * 180 / Math.PI) % 180 + 180) % 180;
export const polacieZKalenicy = (a) => [(Math.round(a) + 90) % 360, (Math.round(a) + 270) % 360]; // zaokrąglenie przed modulo: nigdy 360
export const kierunekSlownie = (az) => KIERUNKI[Math.round(az / 22.5) % 16];
export function koniecStrzalki(az, dl) {
  const r = (az * Math.PI) / 180;
  return { x: PIKSELE / 2 + Math.sin(r) * dl, y: PIKSELE / 2 - Math.cos(r) * dl };
}

// ten sam wpis, który pokazuje zakładka „Taryfy”: urządzenie pierwszego (po entity_id) sensora `razem`
export function entryIdPv(hass) {
  const razem = Object.values(hass?.entities ?? {})
    .filter((e) => e.platform === DOMENA && e.translation_key === "razem").map((e) => e.entity_id).sort()[0];
  if (!razem) return null;
  return hass.devices?.[hass.entities[razem].device_id]?.config_entries?.[0] ?? null;
}

const TEKSTY_PV = {
  brak_konfigu: "Skonfiguruj dach powyżej i zapisz.",
  za_malo_danych: "Za mało danych zużycia: potrzeba co najmniej 6 pełnych miesięcy (po 2 z lata i zimy).",
  brak_pogody: "Brak danych pogodowych — spróbuj później.",
  brak_rce: "Brak cen RCE z PSE — spróbuj później.",
  not_loaded: "Integracja jest niedostępna (przeładowuje się albo została usunięta).",
  adres_nieznaleziony: "Nie znaleziono adresu — sprawdź pisownię (miejscowość, ulica numer).",
  blad: "Nie udało się pobrać wyników — spróbuj później.",
  unauthorized: "Tę czynność może wykonać tylko administrator Home Assistanta.",
  invalid_format: "Sprawdź wartości pól — któreś jest poza zakresem.",
  pv_koszt_szacowany: "Część godzin bez kosztów z Pstryka — uzupełniono średnią miesiąca.",
  pv_brak_rce: "Dla części godzin brak ceny RCE — eksport z nich wyceniony na 0 zł.",
};
export const tekstPv = (kod) => {
  const [k, arg] = String(kod).split(":");
  if (k === "pv_miesiac_uzupelniony") {
    const [, r, m] = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(arg ?? "") ?? [];
    if (r) return `${MIESIACE[Number(m) - 1]} ${r}: brak pełnych danych — uzupełniono z sąsiednich miesięcy.`;
    return String(kod); // brak lub zły argument: sam kod zamiast wyjątku i „undefined”
  }
  return Object.hasOwn(TEKSTY_PV, k) ? TEKSTY_PV[k] : tekstOstrzezenia(kod);
};

export function htmlWynikowPv(w) {
  if (w?.blad) return `<p class="komunikat">${esc(tekstPv(w.blad))}</p>`;
  if (!w || w.stan !== "ok") {
    const t = tekstPv(w?.stan ?? "brak_konfigu");
    return `<p class="komunikat">${esc(w?.stan === "za_malo_danych" ? `${t} Masz: ${w.miesiace_danych}.` : t)}</p>`;
  }
  const naj = [...w.warianty].filter((v) => v.zwrot_lata !== null).sort((a, b) => a.zwrot_lata - b.zwrot_lata)[0]?.id;
  const proc = (x) => `${Math.round(x * 100)}%`;
  const wiersze = w.warianty.map((v) => {
    const kwp = v.kwp.map((p) => `${String(p.kwp).replace(".", ",")} kWp ${kierunekSlownie(p.az)}`).join(" + ");
    const mag = v.magazyn_kwh ? ` + ${v.magazyn_kwh} kWh` : "";
    return `<tr${v.id === naj ? ' class="najlepszy"' : ""}><th scope="row">${esc(kwp + mag)}</th>
      <td>${kwota(v.koszt)}</td><td>${Math.round(v.produkcja_kwh)} kWh</td><td>${proc(v.autokonsumpcja)}</td><td>${proc(v.pobor_vs_dzis)}</td>
      <td${v.oszczednosc_rok <= 0 ? ' class="ujemna"' : ""}>${kwota(v.oszczednosc_rok)}</td>
      <td>${v.zwrot_lata === null ? "nie zwraca się w 20 l." : `${v.zwrot_lata} l.`}</td><td>${kwota(v.bilans_20_lat, true)}</td></tr>`;
  }).join("");
  const ostrz = w.ostrzezenia.length ? `<ul class="ostrzezenia">${w.ostrzezenia.map((o) => `<li>${esc(tekstPv(o))}</li>`).join("")}</ul>` : "";
  const dep = w.warianty.some((v) => v.depozyt_niewykorzystany > 0) ? "<p>Część depozytu przekracza łączne rachunki za rok — liczona jako 0 zł (konserwatywnie).</p>" : "";
  const pelne = Object.values(w.pokrycie ?? {}).filter((p) => p >= 0.8).length;
  const uzup = 12 - pelne;
  const uzupSlowo = uzup === 1 ? "uzupełniony" : uzup >= 2 && uzup <= 4 ? "uzupełnione" : "uzupełnionych";
  const miesiaceDanych = `<p class="podstawa">Z ${pelne} miesięcy pomiaru, ${uzup} ${uzupSlowo}.</p>
    <details data-id="pv-pokrycie"><summary>Pokrycie danymi po miesiącach</summary><ul>${Object.entries(w.pokrycie ?? {})
      .map(([m, p]) => `<li>${esc(MIESIACE[Number(m.slice(5)) - 1] ?? m.slice(5))} ${esc(m.slice(0, 4))}: ${Math.round(p * 100)}%</li>`).join("")}</ul></details>`;
  return `${ostrz}<div class="przewin"><table class="pv"><thead><tr><th>Wariant</th><th>Koszt</th><th>Produkcja/rok</th><th>Autokonsumpcja</th>
    <th>Pobór vs dziś</th><th>Oszczędność/rok</th><th>Zwrot</th><th>Bilans 20 l.</th></tr></thead><tbody>${wiersze}</tbody></table></div>${miesiaceDanych}
    <p class="podstawa">Obecnie: ${esc(w.baza.etykieta)}, ${kwota(w.baza.razem_rok)}/rok · okres ${esc(w.od)} – ${esc(w.do)}. Bilans 20 l. to scenariusz nominalny (bez dyskontowania).</p>${dep}
    <details data-id="pv-zalozenia"><summary>Założenia</summary><ul>
      <li>Nadwyżka do sieci wyceniana godzinowo po cenie rynkowej (RCE z PSE jako przybliżenie ceny RDN Pstryka; ujemna = 0) × 1,23 i trafia do depozytu, który u Pstryka pokrywa energię i opłaty, a nadwyżka (Bonus) także dystrybucję. Bilans liczony łącznie za 12 miesięcy (depozyt nie wygasa); reszta ponad rachunki liczona jako 0 zł.</li>
      <li>Pobór i produkcja bilansowane w obrębie godziny (dane godzinowe) — rzeczywista autokonsumpcja bywa nieco niższa.</li>
      <li>Magazyn ładuje się tylko z nadwyżki paneli (bez ładowania z sieci w tanich godzinach).</li>
      <li>Uzysk bez lokalnego cienia (kominy, drzewa, sąsiedzi) — wpisz zacienienie połaci, jeśli je masz.</li>
      <li>Pogoda jednego roku — w innym roku uzysk zwykle różni się o ±10%.</li>
      <li>Opłata mocowa liczona wg obecnego progu zużycia — przy małym poborze po PV może spaść, czego model nie uwzględnia.</li>
      <li>Wymiana falownika (12. rok, 10% kosztu paneli) i magazynu (15. rok, 70% jego kosztu) wliczona.</li>
    </ul></details>`;
}

// pola „Zaawansowane”: etykieta, jednostka, czy wyświetlać i wpisywać w % (w konfiguracji ułamek), opis
export const ZAAWANSOWANE = {
  pr: ["PR — współczynnik wydajności", "", false, "ułamek 0,5–1; typowo 0,8–0,9"],
  degradacja: ["Degradacja paneli", "%/rok", true],
  sprawnosc_mag: ["Sprawność magazynu", "%", true],
  dod: ["Głębokość rozładowania", "%", true],
  zwrot_depozytu: ["Zwrot niewykorzystanego depozytu", "%", true],
  falownik_rok: ["Rok wymiany falownika", "", false],
  falownik_pct: ["Koszt wymiany falownika", "% ceny paneli", true],
  magazyn_rok: ["Rok wymiany magazynu", "", false],
  magazyn_pct: ["Koszt wymiany magazynu", "% ceny magazynu", true],
};
const DOMYSLNE_KOSZTY = { koszt_kwp: 3000, koszt_kwh_mag: 2000 };

export function htmlKartyDachu(s) {
  const k = s.konfig ?? { polacie: [] };
  const foto = s.punkt && s.zdjecieBlad
    ? '<div class="mapa-blad"><p class="blad">Geoportal nie odpowiada — zdjęcia lotniczego nie udało się wczytać.</p><button type="button" data-akcja="zdjecie-ponow">Wczytaj zdjęcie ponownie</button></div>'
    : s.punkt ? (() => {
    const strz = (lista, klasa) => (lista ?? []).map((p) => {
      const c = koniecStrzalki(p.az, 120);
      return `<line class="${klasa}" x1="${PIKSELE / 2}" y1="${PIKSELE / 2}" x2="${c.x}" y2="${c.y}" marker-end="url(#grot)"/>`;
    }).join("");
    const kal = s.klik1 ? `<circle cx="${s.klik1.x}" cy="${s.klik1.y}" r="6" class="klik"/>` : "";
    return `<div class="mapa${s.tryb === "kalenica" ? " celownik" : ""}">
      <img src="${urlOrto(s.punkt.e, s.punkt.n)}" alt="Zdjęcie lotnicze działki" width="${PIKSELE}" height="${PIKSELE}" data-akcja="mapa" data-url="${urlOrto(s.punkt.e, s.punkt.n)}">
      <svg viewBox="0 0 ${PIKSELE} ${PIKSELE}" aria-hidden="true"><defs><marker id="grot" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs>
        <text x="${PIKSELE / 2}" y="18" class="roza">N</text>${strz(s.nmpt, "nmpt")}${strz(k.polacie.filter((p) => p.panele), "polac")}${kal}</svg></div>`;
  })() : "";
  let nmpt = "";
  if (s.punkt && s.nmpt === null) nmpt = `<p class="info">Szukam połaci w modelu wysokości Geoportalu… (do 6 min)</p>`;
  else if (s.nmptBlad) nmpt = `<p class="info">Automat nie dał rady (Geoportal nie odpowiada) — wskaż kalenicę na zdjęciu.</p>`;
  else if (s.nmpt?.length) nmpt = `<p class="info">Propozycja: ${s.nmpt.map((p) => `${kierunekSlownie(p.az)} ${Math.round(p.az)}°, ${Math.round(p.nachylenie)}°`).join("; ")}.
    Z pomiaru laserowego — może być starszy niż dom. Porównaj ze zdjęciem. <button type="button" data-akcja="zgadza">Zgadza się</button></p>`;
  else if (s.punkt && s.nmpt) nmpt = `<p class="info">Model wysokości nie pokazuje tu budynku (dane mogą być starsze niż dom) — wskaż kalenicę.</p>`; // undefined = zapisany punkt, nic nie szukano
  const tryb = s.tryb === "kalenica" ? `<p class="info">${s.klik1 ? "Kliknij drugi koniec kalenicy." : "Kliknij pierwszy koniec kalenicy."}</p>` : "";
  const polacie = k.polacie.map((p, i) => `<li><label><input type="checkbox" data-pv-polac="${i}" data-pv-pole="panele"${p.panele ? " checked" : ""}>
    ${kierunekSlownie(p.az)} ${Math.round(p.az)}°</label>
    <label>nachylenie <input type="number" min="0" max="65" step="1" value="${p.nachylenie}" data-pv-polac="${i}" data-pv-pole="nachylenie">°</label>
    <label>maks. <input type="number" min="0" max="30" step="0.5" value="${p.kwp_max}" data-pv-polac="${i}" data-pv-pole="kwp_max"> kWp</label>
    <label>zacienienie <input type="number" min="0" max="50" step="5" value="${Math.round(p.cien * 100)}" data-pv-polac="${i}" data-pv-pole="cien">%</label></li>`).join("");
  return `<section class="karta"><h2>Dach</h2>
    <p class="prywatnosc">Adres i współrzędne trafiają do GUGiK/Geoportalu (geokoder, zdjęcie, model wysokości) i Open-Meteo (pogoda). Pstryk i PSE nie dostają adresu ani współrzędnych.</p>
    <div class="adres"><input type="text" data-pv-adres value="${esc(s.adresWpis ?? k.adres ?? "")}" placeholder="Miejscowość, ulica numer" aria-label="Adres">
      <button type="button" data-akcja="szukaj"${s.zajety ? " disabled" : ""}>Szukaj</button>
      <button type="button" data-akcja="z-lokalizacji"${s.zajety ? " disabled" : ""}>Z lokalizacji HA</button>
      ${k.adres ? '<button type="button" data-akcja="usun-lokalizacje">Usuń lokalizację</button>' : ""}</div>
    ${s.bladAdresu ? `<p class="blad">${esc(tekstPv(s.bladAdresu))}</p>` : ""}
    ${foto}${nmpt}${tryb}
    ${s.punkt && !s.zdjecieBlad ? '<button type="button" data-akcja="kalenica">Wskaż kalenicę</button>' : ""}
    ${polacie ? `<ul class="polacie">${polacie}</ul>` : ""}
    ${s.blad ? `<p class="blad">${esc(tekstPv(s.blad))}</p>` : ""}
    <button type="button" data-akcja="zapisz"${s.punkt && !s.zajety ? "" : " disabled"}>Zapisz</button></section>`;
}

export function htmlKartyKosztow(k) {
  const szac = k.koszt_kwp === DOMYSLNE_KOSZTY.koszt_kwp && k.koszt_kwh_mag === DOMYSLNE_KOSZTY.koszt_kwh_mag;
  const z = k.zaawansowane ?? {};
  const pole = (nazwa, etyk, v, krok, jedn) => `<label>${etyk} <input type="number" step="${krok}" value="${v}" data-pv-pole="${nazwa}"> ${jedn}</label>`;
  return `<section class="karta"><h2>Koszty</h2>
    ${szac ? '<p class="pasek">Koszty instalacji szacunkowe — zwrot zależy od nich najbardziej. Wpisz kwoty ze swojej oferty.</p>' : ""}
    ${pole("koszt_kwp", "Panele z montażem", k.koszt_kwp, 100, "zł/kWp")}
    ${pole("koszt_kwh_mag", "Magazyn", k.koszt_kwh_mag, 100, "zł/kWh")}
    ${pole("wzrost_cen", "Wzrost cen prądu", Math.round(k.wzrost_cen * 100), 1, "%/rok")}
    <p class="podpowiedz">Typowo 2500–4000 zł/kWp i 1500–2500 zł/kWh (szacunek, październik 2026).</p>
    <details data-id="pv-zaawansowane"><summary>Zaawansowane</summary>
      ${Object.entries(ZAAWANSOWANE).map(([n, [etyk, jedn, proc, opis]]) => {
        const v = proc ? Number((z[n] * 100).toFixed(2)) : z[n];
        return `<label>${etyk} <input type="number" step="any" value="${v}" data-pv-zaaw="${n}"> ${esc(jedn)}${opis ? ` <small>(${esc(opis)})</small>` : ""}</label>`;
      }).join("")}
    </details></section>`;
}

const STYL = `
.ukryte { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }
:host { display: block; height: 100%; overflow: hidden; background: var(--primary-background-color); color: var(--primary-text-color); }
[hidden] { display: none !important; }
button { font: inherit; cursor: pointer; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
.pasek-ha { display: flex; align-items: center; height: var(--header-height, 56px); padding: 0 12px; box-sizing: border-box;
  background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, var(--text-primary-color));
  border-bottom: var(--app-header-border-bottom, none); }
.menu { width: 40px; height: 40px; border: 0; border-radius: 50%; background: transparent; color: inherit; font-size: 24px; line-height: 1; }
h1 { margin: 0 0 0 12px; font-size: 20px; font-weight: 400; }
.przewijanie { height: calc(100% - var(--header-height, 56px)); overflow-y: auto; }
.tresc { max-width: 1200px; margin: 0 auto; padding: 16px; box-sizing: border-box;
  display: flex; flex-direction: column; gap: 16px; }
.karta { margin: 0; padding: 16px; background: var(--ha-card-background, var(--card-background-color));
  border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); }
h2 { margin: 0; font-weight: 500; }

.okres { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.rodzaje { display: flex; flex-wrap: wrap; gap: 8px; }
.rodzaje button, .zakladki button { min-height: 40px; padding: 0 16px; border-radius: 20px; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); }
.rodzaje button[aria-pressed="true"], .zakladki button[aria-selected="true"] { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color); font-weight: 500; }
.nawigacja { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 8px 12px; }
.nazwa { font-size: 20px; min-width: 9em; text-align: center; }
.strzalka { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); font-size: 20px; line-height: 1; }
.zakres { display: flex; flex-wrap: wrap; gap: 8px 12px; }
.zakres label { display: flex; align-items: center; gap: 6px; color: var(--secondary-text-color); }
input[type="date"] { font: inherit; min-height: 40px; padding: 0 8px; box-sizing: border-box; border-radius: 8px;
  border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
:host([narrow]) .okres { flex-direction: column; }

summary:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
.wyniki { display: flex; flex-direction: column; gap: 16px; }
.ostrzezenia { margin: 0; padding-left: 20px; font-size: 14px; color: var(--secondary-text-color); }
.odpowiedz { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 16px; padding: 12px 16px;
  background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); }
.glowna { font-size: 17px; line-height: 1.5; }
.obok, .pod { font-size: 13px; color: var(--secondary-text-color); }
.obok { white-space: nowrap; }
.pod { flex-basis: 100%; }
.przygaszone { color: var(--secondary-text-color); font-size: 13px; }
.taniej { color: color-mix(in srgb, var(--success-color) 70%, var(--primary-text-color)); }
.znacznik { display: inline-block; margin-left: 6px; padding: 0 8px; border-radius: 9px; border: 1px solid var(--divider-color);
  font-size: 11px; line-height: 18px; font-weight: 500; color: var(--secondary-text-color); white-space: nowrap; vertical-align: 1px; }
.znacznik.ostrzezenie { border-color: var(--warning-color); color: color-mix(in srgb, var(--warning-color) 70%, var(--primary-text-color)); }
.kolory { overflow-x: auto; }
.kolory table { width: 100%; border-collapse: separate; border-spacing: 3px; font-variant-numeric: tabular-nums; }
.kolory th { font-weight: 500; font-size: 12px; color: var(--secondary-text-color); text-align: center; padding: 4px; white-space: nowrap; }
.kolory th small { display: block; font-size: 10px; color: color-mix(in srgb, var(--primary-color) 60%, var(--primary-text-color)); }
.kolory th[scope="row"], .kolory thead th:first-child { position: sticky; left: 0; z-index: 1; background: var(--primary-background-color); text-align: left; font-size: 14px;
  color: var(--primary-text-color); padding: 6px 8px; min-width: 14em; white-space: normal; }
.kolory td { position: relative; text-align: center; padding: 10px 6px; border-radius: 6px; font-size: 14px; white-space: nowrap;
  background: var(--card-background-color); color: var(--primary-text-color); }
.kolory td.taniej { background: color-mix(in srgb, var(--success-color) var(--a), var(--card-background-color)); }
.kolory td.drozej { background: color-mix(in srgb, var(--error-color) var(--a), var(--card-background-color)); }
.kolory td.rowne { color: var(--secondary-text-color); }
.kolory td.brak { color: var(--disabled-text-color, var(--secondary-text-color)); }
.kolory td.stala { text-align: left; background: none; font-size: 12px; color: var(--secondary-text-color); }
.kolory .kol-obecna { border-left: 2px solid var(--primary-color); border-right: 2px solid var(--primary-color); }
.kolory td.najtansza { outline: 3px solid var(--primary-text-color); outline-offset: -1px; font-weight: 700; }
.kolory td.najtansza-bez { outline: 2px dashed var(--primary-text-color); outline-offset: -1px; font-weight: 600; }
.teraz { display: block; line-height: 1; margin-bottom: 2px; font-size: 9px; font-style: normal; font-weight: 700; text-transform: uppercase; color: color-mix(in srgb, var(--primary-color) 60%, var(--primary-text-color)); }
.statystyki { margin: 0; font-size: 13px; color: var(--secondary-text-color); }
.statystyki b { color: var(--primary-text-color); font-weight: 600; }
.ceny { margin: 12px 0 0; }
.ceny summary { cursor: pointer; padding: 8px 0; font-size: 14px; font-weight: 500; color: var(--secondary-text-color); }
.tabela { overflow-x: auto; margin: 4px 0 12px; }
.tabela table { width: 100%; border-collapse: collapse; font-size: 14px; }
.tabela caption { text-align: left; padding: 4px 0; font-weight: 500; }
.tabela th, .tabela td { padding: 6px 8px; text-align: left; vertical-align: top; border-top: 1px solid var(--divider-color); }
.tabela thead th { border-top: 0; color: var(--secondary-text-color); font-weight: 400; }
.tabela td.cena { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.tabela td.cena small { display: block; font-size: 12px; color: var(--secondary-text-color); }
.tabela td.brak { color: var(--secondary-text-color); }
.adnotacja { margin: 8px 0 0; font-size: 13px; color: var(--secondary-text-color); }
.komunikat { text-align: center; padding: 32px 16px; }
.komunikat h2 { font-size: 20px; margin-bottom: 8px; }
.komunikat p { margin: 0; }

.zakladki { display: flex; gap: 8px; }
.tab-taryfy, .tab-pv { display: flex; flex-direction: column; gap: 16px; }
.tab-pv .karta > * { margin-top: 12px; margin-bottom: 0; }
.tab-pv .karta > h2 { margin-top: 0; }
.tab-pv label { display: inline-flex; align-items: center; gap: 6px; margin: 4px 16px 4px 0; }
.tab-pv input[type="number"], .tab-pv input[type="text"] { font: inherit; min-height: 36px; padding: 0 8px; box-sizing: border-box; border-radius: 8px;
  border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
.tab-pv input[type="number"] { width: 6em; }
.tab-pv button[data-akcja] { min-height: 36px; padding: 0 16px; border-radius: 18px; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); }
.tab-pv button[data-akcja="zapisz"] { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color); }
.tab-pv button[disabled] { opacity: 0.5; cursor: default; }
.adres { display: flex; flex-wrap: wrap; gap: 8px; }
.adres input[type="text"] { flex: 1 1 16em; }
.prywatnosc, .podpowiedz, .podstawa { font-size: 13px; color: var(--secondary-text-color); }
.blad { color: var(--error-color); }
.polacie { list-style: none; padding: 0; }
.mapa { position: relative; max-width: 600px; }
.mapa img, .mapa svg { width: 100%; height: auto; display: block; }
.mapa svg { position: absolute; inset: 0; pointer-events: none; }
.mapa.celownik img { cursor: crosshair; }
line.nmpt { stroke: var(--warning-color); stroke-dasharray: 6 4; stroke-width: 3 }
line.polac { stroke: var(--primary-color); stroke-width: 4 }
circle.klik { fill: var(--error-color); stroke: #fff; stroke-width: 2px }
.roza { fill: #fff; font-weight: 700; text-anchor: middle; paint-order: stroke; stroke: #000; stroke-width: 3px }
table.pv { width: 100%; border-collapse: collapse; font-size: 14px; font-variant-numeric: tabular-nums; }
table.pv th, table.pv td { padding: 6px 8px; text-align: right; border-top: 1px solid var(--divider-color); }
table.pv th:first-child { text-align: left; }
table.pv tr.najlepszy { outline: 2px solid var(--success-color) }
td.ujemna { color: var(--error-color) }
.pasek { background: color-mix(in srgb, var(--warning-color) 20%, transparent); padding: 8px; border-radius: 6px }
.przewin { overflow-x: auto }
`;

// linijka pod tabelą: zużycie, udział tanich godzin, Tarcza (tylko gdy > 0)
function statystyki(dane) {
  const { tanie, drogie } = dane.kwh;
  const suma = tanie === null && drogie === null ? null : (tanie ?? 0) + (drogie ?? 0);
  const [pTanie] = udzialy(tanie, drogie);
  return [
    `${T.zuzycie} <b>${kwh(suma)}</b>`,
    ...(pTanie === null ? [] : [`tanie godziny <b>${pTanie}%</b>`]),
    ...(zaokr(dane.obecny.tarcza) < 0 ? [`${T.tarcza} <b>${kwota(dane.obecny.tarcza)}</b>`] : []),
  ].join(" · ");
}

export function htmlWynikow(dane, ui = {}) {
  if (dane === undefined) return "";
  if (!dane) return `<div class="karta komunikat"><h2>${T.brakIntegracji}</h2><p>${T.brakIntegracjiOpis}</p></div>`;
  if (dane.brakWyniku) return `<div class="karta komunikat"><p>${T.powody[dane.powod] ?? T.brakWyniku}</p></div>`;

  const ostrzezenia = dane.ostrzezenia.map((w) => `<li>${esc(tekstOstrzezenia(w))}</li>`).join("");
  const uwagi = dane.uwagi.map(({ sprzedawca, oferta, uwagi }) => `<p class="adnotacja"><strong>${esc(`${sprzedawca} ${oferta}`)}:</strong> ${uwagi.map(esc).join(" ")}</p>`).join("");
  return `
    ${ostrzezenia ? `<ul class="ostrzezenia">${ostrzezenia}</ul>` : ""}
    ${htmlOdpowiedzi(odpowiedz(dane))}
    ${htmlTabeli(wierszeTabeli(dane))}
    <p class="statystyki">${statystyki(dane)}</p>
    ${details("ceny", ui, T.cenyIStawki, htmlCenSekcji1(dane) + htmlCenSekcji2(dane))}
    ${details("uwagi", ui, T.uwagiDoOfert, `${uwagi}<p class="adnotacja">${T.rada}</p>`)}`;
}

if (globalThis.customElements && !customElements.get("porownanie-taryf-panel")) {
  customElements.define(
    "porownanie-taryf-panel",
    class extends HTMLElement {
      constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this.shadowRoot.addEventListener("click", (e) => this._klik(e));
        this.shadowRoot.addEventListener("change", (e) => this._zmiana(e));
        this.shadowRoot.addEventListener("keydown", (e) => {
          if (e.key === "Enter" && e.target.matches?.("[data-pv-adres]")) this._pvKlik({ dataset: { akcja: "szukaj" } });
        });
        this._zakladka = (() => {
          try { return localStorage.getItem("porownanie_taryf_zakladka") === "pv" ? "pv" : "taryfy"; } catch { return "taryfy"; }
        })();
        this._pv = { konfig: null, punkt: null, nmpt: undefined, wyniki: null };
        this._pvHtml = {};
        this._otwarte = new Set(); // rozwinięte <details> przeżywają odświeżenie wyników
        this.shadowRoot.addEventListener("toggle", (e) => {
          const id = e.target.dataset?.id;
          if (id) e.target.open ? this._otwarte.add(id) : this._otwarte.delete(id);
        }, true); // toggle nie bąbelkuje
        // ha-menu-button ładuje się leniwie (po F5 bywa niezdefiniowany): do tego czasu na telefonie działa przycisk zastępczy
        customElements.whenDefined("ha-menu-button").then(() => this._menu());
      }

      connectedCallback() {
        if (this._pv.punkt && this._pv.nmpt === null) this._pvSondaStart(); // element wrócił do DOM w trakcie szukania połaci
      }

      disconnectedCallback() {
        this._pvSondaStop();
      }

      set hass(hass) {
        this._hass = hass;
        const klucz = kluczRenderu(hass);
        if (klucz !== this._klucz) {
          this._klucz = klucz;
          this._render();
        }
      }

      set narrow(narrow) {
        this._narrow = !!narrow;
        this.toggleAttribute("narrow", this._narrow); // układ przełącza CSS (:host([narrow]))
        this._menu();
      }

      _menu() {
        const b = this.shadowRoot.querySelector("button.menu");
        if (b) b.hidden = !(this._narrow && !customElements.get("ha-menu-button"));
      }

      _render() {
        if (!this._szkieletGotowy) {
          this._szkielet();
          this._szkieletGotowy = true;
        }
        const dane = (this._dane = zbierzDane(this._hass));
        const $ = (s) => this.shadowRoot.querySelector(s);
        this._pokazZakladke(this._zakladka); // idempotentne; startuje PV, gdy rejestr encji jest już gotowy
        $(".okres").hidden = !dane;
        if (dane) {
          const { rodzaj, data, koniec } = dane.okres;
          for (const b of this.shadowRoot.querySelectorAll("[data-rodzaj]")) b.setAttribute("aria-pressed", String(b.dataset.rodzaj === rodzaj));
          for (const b of this.shadowRoot.querySelectorAll("[data-krok]")) b.hidden = rodzaj === "zakres";
          $(".zakres").hidden = rodzaj !== "zakres";
          for (const pole of this.shadowRoot.querySelectorAll("input[data-pole]")) {
            const v = dane.okres[pole.dataset.pole];
            // pole edytowane właśnie przez użytkownika zostaje nietknięte (fokus i wpisywane cyfry)
            if (pole !== this.shadowRoot.activeElement && ISO.test(v ?? "") && pole.value !== v) pole.value = v;
          }
          const nazwa = nazwaOkresu(rodzaj, dane.okresOd ?? data, dane.okresDo ?? koniec);
          if ($(".nazwa").textContent !== nazwa) $(".nazwa").textContent = nazwa;
        }
        // kontrolki okresu żyją w szkielecie; podmieniane są tylko wyniki, i to gdy HTML faktycznie się zmienił
        const html = htmlWynikow(dane, { otwarte: this._otwarte });
        if (html === this._html) return;
        this._html = html;
        $(".wyniki").innerHTML = html;
      }

      _szkielet() {
        this.shadowRoot.innerHTML = `<style>${STYL}</style>
          <div class="pasek-ha"><ha-menu-button></ha-menu-button><button type="button" class="menu" aria-label="Menu" hidden>☰</button><h1>${T.tytul}</h1></div>
          <div class="przewijanie"><div class="tresc">
            <div class="zakladki" role="tablist">
              <button type="button" role="tab" data-zakladka="taryfy">Taryfy</button>
              <button type="button" role="tab" data-zakladka="pv">Fotowoltaika</button>
            </div>
            <div class="tab-taryfy">
            <section class="okres">
              <div class="rodzaje" role="group" aria-label="${T.okres}">
                ${RODZAJE.map((r, i) => `<button type="button" data-rodzaj="${r}" aria-pressed="false">${T.rodzaje[i]}</button>`).join("")}
              </div>
              <div class="nawigacja">
                <button type="button" class="strzalka" data-krok="-1" aria-label="${T.wstecz}">←</button>
                <h2 class="nazwa" aria-live="polite"></h2>
                <button type="button" class="strzalka" data-krok="1" aria-label="${T.dalej}">→</button>
                <div class="zakres" hidden>
                  <label>${T.od} <input type="date" data-pole="data"></label>
                  <label>${T.do} <input type="date" data-pole="koniec"></label>
                </div>
              </div>
            </section>
            <div class="wyniki"></div>
            </div>
            <div class="tab-pv" hidden>
              <div class="pv-dach"></div><div class="pv-koszty"></div>
              <section class="karta"><h2>Wyniki</h2><div class="pv-wyniki"></div></section>
            </div>
          </div></div>`;
        this._menu();
      }

      _klik(e) {
        if (e.target.closest?.("button.menu")) {
          this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
          return;
        }
        const zk = e.target.closest?.("[data-zakladka]");
        if (zk) {
          try { localStorage.setItem("porownanie_taryf_zakladka", zk.dataset.zakladka); } catch { /* tryb prywatny: zakładka tylko na tę sesję */ }
          this._pokazZakladke(zk.dataset.zakladka);
          return;
        }
        const ak = e.target.closest?.("[data-akcja]");
        if (ak) {
          this._pvKlik(ak, e);
          return;
        }
        const b = e.target.closest?.("button[data-rodzaj], button[data-krok]");
        const d = this._dane;
        if (!b || !d) return;
        const { rodzaj, data, koniec, encje } = d.okres;
        if (b.dataset.krok) {
          if (ISO.test(data ?? "")) this._ustawDate(encje.data, przesun(rodzaj, data, Number(b.dataset.krok)));
          return;
        }
        const nowy = b.dataset.rodzaj;
        if (nowy === rodzaj) return;
        // zakres z końcem przed początkiem dałby od razu „brak wyniku”: koniec = koniec oglądanego okresu (nie przed datą)
        if (nowy === "zakres" && !(ISO.test(koniec ?? "") && koniec >= data)) {
          this._ustawDate(encje.koniec, d.okresDo >= data ? d.okresDo : data);
        }
        this._usluga("select", "select_option", { entity_id: encje.okres, option: nowy });
      }

      _zmiana(e) {
        const t = e.target;
        const ds = t.dataset ?? {};
        const k = this._pv.konfig;
        if (k && (ds.pvPolac !== undefined || ds.pvPole || ds.pvZaaw)) {
          const v = Number(t.value);
          if (t.type !== "checkbox" && (t.value === "" || !Number.isFinite(v))) return; // puste/niepoprawne pole: zostaje poprzednia wartość
          if (ds.pvPolac !== undefined) {
            const p = k.polacie[Number(ds.pvPolac)];
            if (p) p[ds.pvPole] = ds.pvPole === "panele" ? t.checked : ds.pvPole === "cien" ? v / 100 : v;
          } else if (ds.pvZaaw) k.zaawansowane[ds.pvZaaw] = ZAAWANSOWANE[ds.pvZaaw]?.[2] ? v / 100 : v;
          else k[ds.pvPole] = ds.pvPole === "wzrost_cen" ? v / 100 : v;
          return; // zapis dopiero przyciskiem „Zapisz”
        }
        const pole = e.target.dataset?.pole;
        // Chrome zgłasza change w trakcie wpisywania roku (0002-…, 0020-…): wysyłamy tylko pełny rok 20xx
        if (pole && this._dane && /^20\d\d-\d\d-\d\d$/.test(e.target.value)) this._ustawDate(this._dane.okres.encje[pole], e.target.value);
      }

      // --- zakładka „Fotowoltaika” ---

      _pokazZakladke(z) {
        this._zakladka = z;
        const $ = (s) => this.shadowRoot.querySelector(s);
        $(".tab-taryfy").hidden = z !== "taryfy";
        $(".tab-pv").hidden = z !== "pv";
        for (const b of this.shadowRoot.querySelectorAll("[data-zakladka]")) b.setAttribute("aria-selected", String(b.dataset.zakladka === z));
        // start dopiero gdy rejestr encji jest wczytany (po F5 pierwszy `hass` bywa pusty), i tylko raz
        if (z === "pv" && !this._pvStartowano && Object.keys(this._hass?.entities ?? {}).length) {
          this._pvStartowano = true;
          this._pvStart();
        }
      }

      _pvBlad(err) {
        const kod = err?.code ?? "blad";
        if (kod === "not_loaded") this._pv.wyniki = { blad: kod };
        return kod;
      }

      async _pvStart() {
        const pv = this._pv;
        pv.id = entryIdPv(this._hass);
        if (!pv.id) {
          pv.wyniki = { blad: "not_loaded" };
          this._pvStartowano = false; // integracja jeszcze się ładuje: kolejne wejście w zakładkę / odświeżenie spróbuje ponownie
          this._pvRender();
          return;
        }
        this._pvRender();
        try {
          pv.konfig = await this._hass.callWS({ type: `${DOMENA}/pv/konfig`, entry_id: pv.id });
        } catch (err) {
          pv.wyniki = { blad: this._pvBlad(err) };
          if (pv.wyniki.blad === "not_loaded") this._pvStartowano = false;
          this._pvRender();
          return;
        }
        if (pv.konfig.e != null) pv.punkt = { e: pv.konfig.e, n: pv.konfig.n }; // zapisany punkt: ortofoto bez nowego szukania
        await this._pvWyniki();
      }

      async _pvWyniki() {
        const pv = this._pv;
        const tok = (this._pvWTok = (this._pvWTok ?? 0) + 1);
        pv.wyniki = null; // „Liczę…”
        this._pvRender();
        let w;
        try {
          w = await this._hass.callWS({ type: `${DOMENA}/pv/wyniki`, entry_id: pv.id });
        } catch (err) {
          w = { blad: this._pvBlad(err) };
        }
        if (tok !== this._pvWTok) return; // nowsze zapytanie wyprzedziło to
        pv.wyniki = w;
        this._pvRender();
      }

      _pvRender() {
        const pv = this._pv;
        const $ = (s) => this.shadowRoot.querySelector(s);
        const ustaw = (sel, html) => {
          if (this._pvHtml[sel] === html) return false;
          this._pvHtml[sel] = html;
          // asynchroniczne odświeżenie (NMPT, wyniki) nie może zgubić tekstu wpisywanego w polu: zapamiętujemy i odtwarzamy pole z fokusem
          const aktywne = this.shadowRoot.activeElement;
          const w = aktywne && $(sel).contains(aktywne) && aktywne.matches?.("input")
            ? { sel: [...aktywne.attributes].filter((a) => a.name.startsWith("data-")).map((a) => `[${a.name}="${a.value}"]`).join(""),
              v: aktywne.value, od: aktywne.selectionStart, do: aktywne.selectionEnd } : null;
          $(sel).innerHTML = html;
          const pole = w?.sel && $(sel).querySelector(`input${w.sel}`);
          if (pole) {
            pole.value = w.v;
            pole.focus();
            try { pole.setSelectionRange(w.od, w.do); } catch { /* pola number nie mają zaznaczenia */ }
          }
          return true;
        };
        // zdjęcie (WMS Geoportalu) nie może się ładować od nowa przy każdym przerysowaniu karty: ten sam węzeł <img> przenosimy do nowego HTML
        const stary = $(".pv-dach img[data-akcja=mapa]");
        const dach = ustaw(".pv-dach", pv.konfig ? htmlKartyDachu(pv) : "");
        ustaw(".pv-koszty", pv.konfig ? htmlKartyKosztow(pv.konfig) : "");
        ustaw(".pv-wyniki", pv.wyniki === null ? '<p class="komunikat">Liczę wyniki…</p>' : htmlWynikowPv(pv.wyniki));
        for (const d of this.shadowRoot.querySelectorAll(".tab-pv details[data-id]")) if (this._otwarte.has(d.dataset.id)) d.open = true;
        const nowy = dach && $(".pv-dach img[data-akcja=mapa]");
        if (nowy) {
          if (stary?.dataset.url === nowy.dataset.url) nowy.replaceWith(stary);
          else this._pvZdjecie(nowy);
        }
      }

      // błąd zdjęcia: jedna ponowna próba po 3 s (parametr `_` WMS ignoruje, a omija zbuforowany błąd), potem komunikat zamiast całej mapy (z nakładką SVG)
      _pvZdjecie(img) {
        let proba = 0;
        img.addEventListener("error", () => {
          if (!img.isConnected) return; // zdjęcie już wymienione na inne
          if (proba++ === 0) {
            setTimeout(() => { if (img.isConnected) img.src = `${img.dataset.url}&_=${Date.now()}`; }, 3000);
            return;
          }
          Object.assign(this._pv, { zdjecieBlad: true, tryb: null, klik1: null });
          this._pvRender();
        });
      }

      _pvSondaStop() {
        clearInterval(this._pvSonda);
        this._pvSonda = null;
      }

      // wynik NMPT liczy się w tle po stronie HA (do 6 min): pytamy co 5 s, ale nie dłużej niż 8 min
      _pvSondaStart() {
        this._pvSondaStop();
        const pv = this._pv;
        const { e, n } = pv.punkt;
        const start = Date.now();
        let trwa = false;
        const id = (this._pvSonda = setInterval(async () => {
          if (trwa) return;
          trwa = true;
          try {
            const st = await this._hass.callWS({ type: `${DOMENA}/pv/dach_status`, entry_id: pv.id, e, n });
            if (this._pvSonda !== id) return; // zatrzymana albo zastąpiona nowym szukaniem
            if (st.polacie_nmpt !== null) {
              this._pvSondaStop();
              pv.nmpt = st.polacie_nmpt;
              pv.nmptBlad = st.nmpt_blad;
              this._pvRender();
            } else if (Date.now() - start > 480000) {
              this._pvSondaStop();
              pv.nmpt = [];
              pv.nmptBlad = "niedostepny";
              this._pvRender();
            }
          } catch (err) {
            if (this._pvSonda !== id) return;
            this._pvSondaStop();
            pv.nmpt = [];
            pv.nmptBlad = this._pvBlad(err);
            this._pvRender();
          } finally {
            trwa = false;
          }
        }, 5000));
      }

      async _pvSzukaj(zapytanie, wpis) {
        const pv = this._pv;
        this._pvSondaStop();
        Object.assign(pv, { bladAdresu: null, adresWpis: wpis, zajety: true });
        this._pvRender();
        try {
          const d = await this._hass.callWS({ type: `${DOMENA}/pv/dach`, entry_id: pv.id, ...zapytanie });
          pv.konfig = { ...pv.konfig, adres: d.adres, e: d.e, n: d.n, lat: d.lat, lon: d.lon };
          Object.assign(pv, { adresWpis: undefined, zdjecieBlad: false, punkt: { e: d.e, n: d.n }, nmpt: d.polacie_nmpt, nmptBlad: d.nmpt_blad, tryb: null, klik1: null });
          if (d.polacie_nmpt === null) this._pvSondaStart();
        } catch (err) {
          pv.bladAdresu = this._pvBlad(err);
        }
        pv.zajety = false;
        this._pvRender();
      }

      async _pvZapisz(konfig) {
        const pv = this._pv;
        Object.assign(pv, { blad: null, zajety: true });
        this._pvRender();
        try {
          pv.konfig = await this._hass.callWS({ type: `${DOMENA}/pv/konfig`, entry_id: pv.id, konfig });
        } catch (err) {
          pv.blad = this._pvBlad(err);
          pv.zajety = false;
          this._pvRender();
          return;
        }
        pv.zajety = false;
        await this._pvWyniki();
      }

      _pvKlik(el, ev) {
        const pv = this._pv;
        const k = pv.konfig;
        if (!k || !pv.id || (pv.zajety && el.dataset.akcja !== "mapa")) return;
        switch (el.dataset.akcja) {
          case "szukaj": {
            const wpis = this.shadowRoot.querySelector("[data-pv-adres]")?.value.trim() ?? "";
            if (wpis.length < 3) {
              Object.assign(pv, { bladAdresu: "adres_nieznaleziony", adresWpis: wpis });
              this._pvRender();
            } else this._pvSzukaj({ adres: wpis }, wpis);
            break;
          }
          case "z-lokalizacji": // jawna akcja użytkownika: dopiero tu współrzędne HA trafiają do GUGiK
            this._pvSzukaj({ lat: this._hass.config.latitude, lon: this._hass.config.longitude });
            break;
          case "zdjecie-ponow":
            pv.zdjecieBlad = false;
            this._pvRender();
            break;
          case "kalenica":
            Object.assign(pv, { tryb: "kalenica", klik1: null });
            this._pvRender();
            break;
          case "mapa": {
            if (pv.tryb !== "kalenica" || !pv.punkt) break;
            const r = el.getBoundingClientRect();
            const x = ((ev.clientX - r.left) * PIKSELE) / r.width;
            const y = ((ev.clientY - r.top) * PIKSELE) / r.height;
            if (!pv.klik1) pv.klik1 = { x, y };
            else {
              const { e, n } = pv.punkt;
              const a = azymutKalenicy(pikselNaPuwg(pv.klik1.x, pv.klik1.y, PIKSELE, PIKSELE, e, n), pikselNaPuwg(x, y, PIKSELE, PIKSELE, e, n));
              k.polacie = polacieZKalenicy(a).map((az) => ({ az, nachylenie: 35, kwp_max: 6, cien: 0, panele: true }));
              Object.assign(pv, { tryb: null, klik1: null });
            }
            this._pvRender();
            break;
          }
          case "zgadza": // backend przyjmuje najwyżej 4 połacie i az < 360
            k.polacie = [...(pv.nmpt ?? [])].sort((a, b) => b.powierzchnia_m2 - a.powierzchnia_m2).slice(0, 4).map((p) => ({
              az: Math.round(p.az) % 360, nachylenie: Math.min(65, Math.round(p.nachylenie)),
              kwp_max: Math.min(12, Math.floor(0.18 * p.powierzchnia_m2 * 0.6 * 2) / 2), cien: 0, panele: true,
            }));
            this._pvRender();
            break;
          case "usun-lokalizacje":
            this._pvSondaStop();
            Object.assign(pv, { punkt: null, zdjecieBlad: false, nmpt: undefined, nmptBlad: null, tryb: null, klik1: null, bladAdresu: null, adresWpis: undefined });
            this._pvZapisz({ ...k, adres: null, e: null, n: null, lat: null, lon: null, polacie: [] });
            break;
          case "zapisz":
            this._pvZapisz(k);
            break;
        }
      }

      _ustawDate(entity_id, date) {
        if (entity_id && date) this._usluga("date", "set_value", { entity_id, date });
      }

      _usluga(domena, usluga, dane) {
        // błąd wywołania pokazuje sam frontend HA (toast); tu tylko bez nieobsłużonego odrzucenia
        Promise.resolve(this._hass.callService(domena, usluga, dane)).catch(() => {
          this._html = null; // nieudana zmiana: odśwież, żeby kontrolki wróciły do stanu encji
          this._render();
        });
      }
    },
  );
}
