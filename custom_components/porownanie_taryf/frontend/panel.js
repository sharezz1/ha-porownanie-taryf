// Panel „Porównanie taryf” (spec §7a): waniliowy web component, bez bibliotek, bez kroku budowania, bez zasobów z sieci.
// Czyste funkcje są eksportowane dla testów (node --test tests/js/*.test.mjs); element definiowany tylko w przeglądarce.

const DOMENA = "porownanie_taryf";
const ISO = /^\d{4}-\d{2}-\d{2}$/;
const RODZAJE = ["dzien", "miesiac", "rok", "zakres"];
const TARYFY = ["G11", "G12", "G12w", "G13active"]; // kolejność jak w integracji (nie wg ceny)
const kolejnosc = (t) => (TARYFY.includes(t) ? TARYFY.indexOf(t) : TARYFY.length);

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
      taryfa: a.taryfa ?? a.scenariusz.split("_")[1] ?? null,
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
  // taryfy z pierwszego wykresu, których sprzedawca kompleksowy nie oferuje (własny cennik pomijamy: to wybór użytkownika)
  const brakujace = [...new Set(kompleksowa.filter((s) => !s.klucz.startsWith("cennik_")).map((s) => s.sprzedawca))].map((sprzedawca) => ({
    sprzedawca,
    taryfy: ranking.map((s) => s.taryfa).filter((t) => !kompleksowa.some((k) => k.sprzedawca === sprzedawca && k.taryfa === t)).sort((x, y) => kolejnosc(x) - kolejnosc(y)),
  })).filter((b) => b.taryfy.length);

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
    brakujace,
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

// drugi udział to 100 − pierwszy, żeby kafelki zawsze dawały 100%
export function udzialy(tanie, drogie) {
  const suma = (tanie ?? 0) + (drogie ?? 0);
  if (!(suma > 0)) return [null, null];
  const t = tanie === null ? null : Math.round((tanie / suma) * 100);
  return [t, drogie === null ? null : t === null ? 100 : 100 - t];
}

const kwh = (x) => (x === null ? "—" : `${format(x)} kWh`);

// dopełniacz tylko dla nazw z wbudowanego katalogu; inna nazwa (np. własny cennik) → tytuł ogólny
const DOPELNIACZ = { Enea: "Enei" };

// etykieta wiersza = sama taryfa, gdy wszystkie wiersze mają jednego sprzedawcę (dla sekcji 2: katalogowego) i taryfy się nie powtarzają
export const naTaryfy = (wiersze, sprzedawcaOk = true) =>
  sprzedawcaOk && wiersze.length > 0 && wiersze.every((s) => s.taryfa) &&
  new Set(wiersze.map((s) => s.sprzedawca)).size === 1 && new Set(wiersze.map((s) => s.taryfa)).size === wiersze.length;
const nazwa = (s, wiersze, sprzedawcaOk) => (naTaryfy(wiersze, sprzedawcaOk) ? s.taryfa : s.etykieta);
const remisy = (wiersze) => wiersze.filter((s) => !s.obecny && zaokr(s.roznica) === 0);
const mozna = (dane) => dane?.obecny && !dane.brakWyniku;

// linijka na górze: obecna umowa + najtańsza opcja z obu sekcji (neutralnie, bez „zapłaciłeś”)
export function podsumowanie(dane) {
  if (!mozna(dane)) return "";
  const o = dane.obecny;
  const start = `Twoja umowa (${o.etykieta}): ${kwota(o.razem)}`;
  const wszystkie = [...dane.ranking, ...dane.kompleksowa].sort(porownaj);
  if (wszystkie.length < 2) return start;
  const najtanszy = wszystkie[0];
  if (najtanszy.obecny || zaokr(najtanszy.roznica) === 0) {
    const remis = remisy(wszystkie);
    return remis.length ? `${start} · równie tania jak ${remis.map((s) => s.etykieta).join(", ")}` : `${start} · to najtańsza opcja ogółem`;
  }
  return `${start} · najtańsza opcja ogółem: ${najtanszy.etykieta}, o ${kwota(-najtanszy.roznica)} mniej`;
}

// sekcja 1: najtańsza taryfa dystrybucyjna przy umowie z Pstrykiem; lepsza = true, gdy inna taryfa jest tańsza od obecnej
export function werdyktPstryk(dane) {
  if (!mozna(dane) || dane.ranking.length < 2) return null;
  const n = (s) => nazwa(s, dane.ranking);
  const o = dane.obecny;
  const najtanszy = dane.ranking[0];
  if (najtanszy.obecny || zaokr(najtanszy.roznica) === 0) {
    const remis = remisy(dane.ranking);
    return { lepsza: false, tekst: remis.length ? `Obecna taryfa ${n(o)} jest równie tania jak ${remis.map(n).join(", ")}` : `Obecna taryfa ${n(o)} jest najtańsza` };
  }
  return { lepsza: true, tekst: `Najtańsza taryfa dystrybucyjna: ${n(najtanszy)} — o ${kwota(-najtanszy.roznica)} mniej niż obecna ${n(o)}` };
}

// sekcja 2: najtańsza oferta kompleksowa vs obecna umowa z Pstrykiem
export function werdyktKompleksowa(dane) {
  if (!mozna(dane) || !dane.kompleksowa.length) return null;
  const k = dane.kompleksowa[0];
  const r = zaokr(k.roznica);
  if (r < 0) return { lepsza: true, tekst: `Najtańsza: ${k.etykieta} — o ${kwota(-r)} mniej niż obecna umowa z Pstrykiem` };
  return { lepsza: false, tekst: `Najtańsza: ${k.etykieta} — ${r === 0 ? "tyle samo co" : `o ${kwota(r)} więcej niż`} obecna umowa z Pstrykiem` };
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

const T = {
  tytul: "Porównanie taryf", okres: "Okres", rodzaje: ["Dzień", "Miesiąc", "Rok", "Zakres"],
  wstecz: "Poprzedni okres", dalej: "Następny okres", od: "Od", do: "Do",
  sekcja1: "1. Prąd z Pstryka + dystrybucja Enea Operator",
  sekcja2: (sprzedawca) => (sprzedawca ? `2. Umowa kompleksowa ${sprzedawca} (prąd i dystrybucja od ${DOPELNIACZ[sprzedawca]})` : "2. Umowa kompleksowa"),
  prad: "prąd po tarczy", pradK: "prąd", dystr: "dystrybucja", obecna: "obecna",
  brakTaryfy: (kto, taryfy) => `${kto} nie oferuje ${taryfy.join(" ani ")} gospodarstwom domowym.`,
  cennikEnei: "Ceny Enei z cennika 2026 dla klientów, którzy zmieniali sprzedawcę — przed decyzją potwierdź ofertę w Enei.",
  drozej: "drożej niż obecna", taniej: "taniej niż obecna",
  tarcza: "Tarcza Pstryk", zuzycie: "Zużycie", tanie: "Tanie godziny", drogie: "Drogie godziny", dane: "Dane",
  podTarcza: "rabat już odjęty od kosztu", podZuzycie: "energia pobrana z sieci", podStrefy: "w obecnej taryfie",
  podDane: "godzin z odczytem licznika",
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

const STYL = `
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
.tresc { max-width: 900px; margin: 0 auto; padding: 16px; box-sizing: border-box;
  display: flex; flex-direction: column; gap: 16px; }
.karta { margin: 0; padding: 16px; background: var(--ha-card-background, var(--card-background-color));
  border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); }
h2, h3 { margin: 0; font-weight: 500; }
h3 { font-size: 18px; }

.okres { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.rodzaje { display: flex; flex-wrap: wrap; gap: 8px; }
.rodzaje button { min-height: 40px; padding: 0 16px; border-radius: 20px; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); }
.rodzaje button[aria-pressed="true"] { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color); font-weight: 500; }
.nawigacja { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 8px 12px; }
.nazwa { font-size: 20px; min-width: 9em; text-align: center; }
.strzalka { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); font-size: 20px; line-height: 1; }
.zakres { display: flex; flex-wrap: wrap; gap: 8px 12px; }
.zakres label { display: flex; align-items: center; gap: 6px; color: var(--secondary-text-color); }
input[type="date"] { font: inherit; min-height: 40px; padding: 0 8px; box-sizing: border-box; border-radius: 8px;
  border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
:host([narrow]) .okres { flex-direction: column; }

.wyniki { display: flex; flex-direction: column; gap: 24px; }
.podsumowanie { margin: 0; padding: 12px 16px; font-size: 16px; line-height: 1.5; border-radius: var(--ha-card-border-radius, 12px);
  background: color-mix(in srgb, var(--secondary-text-color) 10%, transparent); }
.werdykt { margin: 8px 0 4px; font-size: 16px; font-weight: 500; line-height: 1.4; }
.werdykt.lepsza { color: color-mix(in srgb, var(--success-color) 75%, var(--primary-text-color)); }

.legenda { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 6px 0 4px; font-size: 13px; color: var(--secondary-text-color); }
.legenda i { display: inline-block; width: 12px; height: 12px; margin-right: 6px; border-radius: 3px; vertical-align: -1px; }
.prad { background: var(--primary-color); }
.prad2 { background: color-mix(in srgb, var(--accent-color) 80%, var(--primary-text-color)); }
.dystr { background: var(--secondary-text-color); opacity: 0.45; }
.ranking { list-style: none; margin: 0; padding: 0; }
.wiersz { display: grid; grid-template-columns: minmax(9em, 13em) 1fr 7.5em 6.5em; grid-template-areas: "etykieta slupek razem roznica";
  align-items: center; gap: 6px 12px; padding: 10px 0; border-top: 1px solid var(--divider-color); }
.wiersz:first-child { border-top: 0; }
:host([narrow]) .wiersz { grid-template-columns: 1fr auto; grid-template-areas: "etykieta razem" "slupek roznica"; }
.etykieta { grid-area: etykieta; }
.obecny .etykieta { font-weight: 500; }
.odznaka { display: inline-block; margin-left: 6px; padding: 0 8px; border-radius: 10px; border: 1px solid var(--primary-color);
  font-size: 12px; line-height: 18px; font-weight: 500; }
.slupek { grid-area: slupek; display: flex; height: 14px; border-radius: 4px; overflow: hidden; }
.razem, .roznica { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.razem { grid-area: razem; font-weight: 500; }
.roznica { grid-area: roznica; font-size: 14px; font-weight: 500; }
.drozej { color: color-mix(in srgb, var(--error-color) 75%, var(--primary-text-color)); }
.taniej { color: color-mix(in srgb, var(--success-color) 75%, var(--primary-text-color)); }

.kafelki { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 16px 0 0; }
.kafel { display: grid; grid-template-areas: "et" "wart" "pod"; align-content: start; gap: 2px; padding: 12px 16px; }
.kafel dt { grid-area: et; font-size: 14px; color: var(--secondary-text-color); }
.kafel dd { margin: 0; }
.wartosc { grid-area: wart; font-size: 18px; font-weight: 500; font-variant-numeric: tabular-nums; }
.pod { grid-area: pod; font-size: 12px; color: var(--secondary-text-color); }
:host([narrow]) .kafelki { grid-template-columns: 1fr; gap: 8px; }
:host([narrow]) .kafel { grid-template-columns: 1fr auto; grid-template-areas: "et wart" "pod wart"; align-items: center; column-gap: 12px; }

.adnotacja { margin: 8px 0 0; font-size: 13px; color: var(--secondary-text-color); }
.uwagi { font-size: 14px; line-height: 1.5; color: var(--secondary-text-color); }
.uwagi ul { margin: 0 0 8px; padding-left: 20px; color: var(--primary-text-color); }
.uwagi p { margin: 0; }
.komunikat { text-align: center; padding: 32px 16px; }
.komunikat h2 { font-size: 20px; margin-bottom: 8px; }
.komunikat p { margin: 0; }
`;

export function htmlWynikow(dane) {
  if (dane === undefined) return "";
  if (!dane) return `<div class="karta komunikat"><h2>${T.brakIntegracji}</h2><p>${T.brakIntegracjiOpis}</p></div>`;
  if (dane.brakWyniku) return `<div class="karta komunikat"><p>${T.powody[dane.powod] ?? T.brakWyniku}</p></div>`;

  const o = dane.obecny;
  const max = Math.max(...[...dane.ranking, ...dane.kompleksowa].map((s) => s.razem)); // wspólna skala obu wykresów
  const szer = (x) => `${(max > 0 ? Math.max(0, (x / max) * 100) : 0).toFixed(2)}%`; // skala względem najdroższego
  const wiersz = (s, etykieta, klasaPrad) => {
    const opis = esc(`${T.pradK} ${kwota(s.sprzedazPo)}, ${T.dystr} ${kwota(s.dystrybucja)}`);
    const [klasa, tytul] = s.roznica > 0 ? ["drozej", T.drozej] : s.roznica < 0 ? ["taniej", T.taniej] : ["", ""];
    return `<li class="wiersz${s.obecny ? " obecny" : ""}">
      <span class="etykieta">${esc(etykieta)}${s.obecny ? `<span class="odznaka">${T.obecna}</span>` : ""}</span>
      <span class="slupek" role="img" aria-label="${opis}" title="${opis}"><span class="${klasaPrad}" style="width:${szer(s.sprzedazPo)}"></span><span class="dystr" style="width:${szer(s.dystrybucja)}"></span></span>
      <span class="razem">${kwota(s.razem)}</span>
      <span class="roznica ${klasa}" title="${tytul}">${s.obecny ? "" : kwota(s.roznica, true)}</span>
    </li>`;
  };
  const legenda = (prad, klasaPrad) => `<div class="legenda" aria-hidden="true"><span><i class="${klasaPrad}"></i>${prad}</span><span><i class="dystr"></i>${T.dystr}</span></div>`;
  const werdykt = (w) => (w ? `<p class="werdykt${w.lepsza ? " lepsza" : ""}">${esc(w.tekst)}</p>` : "");

  const taryfy1 = naTaryfy(dane.ranking);
  const sekcja1 = `<section class="karta">
      <h3>${T.sekcja1}</h3>
      ${werdykt(werdyktPstryk(dane))}
      ${legenda(T.prad, "prad")}
      <ol class="ranking">${dane.ranking.map((s) => wiersz(s, taryfy1 ? s.taryfa : s.etykieta, "prad")).join("")}</ol>
      ${kafelki(dane, o)}
    </section>`;

  const k = dane.kompleksowa;
  const katalog = naTaryfy(k, Object.hasOwn(DOPELNIACZ, k[0]?.sprzedawca)); // jeden katalogowy sprzedawca: nazwa w nagłówku, wiersze = sama taryfa
  const adnotacje = dane.brakujace.map((b) => `<p class="adnotacja">${esc(T.brakTaryfy(b.sprzedawca, b.taryfy))}</p>`).join("");
  // nota tylko dla katalogowej Enei (klucz kompleksowa_*); własny cennik (cennik_*) o tej samej nazwie jej nie dostaje
  const notaEnei = k.some((s) => s.sprzedawca === "Enea" && s.klucz.startsWith("kompleksowa_")) ? `<p class="adnotacja">${esc(T.cennikEnei)}</p>` : "";
  const sekcja2 = k.length
    ? `<section class="karta">
      <h3>${esc(T.sekcja2(katalog ? k[0].sprzedawca : null))}</h3>
      ${werdykt(werdyktKompleksowa(dane))}
      ${legenda(T.pradK, "prad2")}
      <ol class="ranking">${k.map((s) => wiersz(s, katalog ? s.taryfa : s.etykieta, "prad2")).join("")}</ol>
      ${adnotacje}${notaEnei}
    </section>`
    : "";

  const ostrzezenia = dane.ostrzezenia.map((w) => `<li>${esc(tekstOstrzezenia(w))}</li>`).join("");
  return `
    <p class="podsumowanie">${esc(podsumowanie(dane))}</p>
    ${sekcja1}
    ${sekcja2}
    <div class="uwagi">${ostrzezenia ? `<ul>${ostrzezenia}</ul>` : ""}<p>${T.rada}</p></div>`;
}

// kafelki dotyczące umowy z Pstrykiem (pod wykresem sekcji 1)
function kafelki(dane, o) {
  const { tanie, drogie } = dane.kwh;
  const suma = tanie === null && drogie === null ? null : (tanie ?? 0) + (drogie ?? 0);
  const [pTanie, pDrogie] = udzialy(tanie, drogie);
  const udzial = (p) => (p === null ? "" : ` (${p}%)`);
  const pokrycie = dane.pokrycie === null ? "—" : `${new Intl.NumberFormat("pl", { maximumFractionDigits: 1 }).format(Math.floor(dane.pokrycie * 1000) / 10)}%`;
  const kafel = (et, wart, pod) => `<div class="kafel karta"><dt>${et}</dt><dd class="wartosc">${wart}</dd><dd class="pod">${pod}</dd></div>`;
  return `<dl class="kafelki">
      ${kafel(T.tarcza, kwota(o.tarcza), T.podTarcza)}
      ${kafel(T.zuzycie, kwh(suma), T.podZuzycie)}
      ${kafel(T.tanie, kwh(tanie) + udzial(pTanie), T.podStrefy)}
      ${kafel(T.drogie, kwh(drogie) + udzial(pDrogie), T.podStrefy)}
      ${kafel(T.dane, pokrycie, T.podDane)}
    </dl>`;
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
        // ha-menu-button ładuje się leniwie (po F5 bywa niezdefiniowany): do tego czasu na telefonie działa przycisk zastępczy
        customElements.whenDefined("ha-menu-button").then(() => this._menu());
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
        // kontrolki okresu żyją w szkielecie; podmieniane są tylko wyniki
        $(".wyniki").innerHTML = htmlWynikow(dane);
      }

      _szkielet() {
        this.shadowRoot.innerHTML = `<style>${STYL}</style>
          <div class="pasek-ha"><ha-menu-button></ha-menu-button><button type="button" class="menu" aria-label="Menu" hidden>☰</button><h1>${T.tytul}</h1></div>
          <div class="przewijanie"><div class="tresc">
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
          </div></div>`;
        this._menu();
      }

      _klik(e) {
        if (e.target.closest?.("button.menu")) {
          this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
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
        const pole = e.target.dataset?.pole;
        // Chrome zgłasza change w trakcie wpisywania roku (0002-…, 0020-…): wysyłamy tylko pełny rok 20xx
        if (pole && this._dane && /^20\d\d-\d\d-\d\d$/.test(e.target.value)) this._ustawDate(this._dane.okres.encje[pole], e.target.value);
      }

      _ustawDate(entity_id, date) {
        if (entity_id && date) this._usluga("date", "set_value", { entity_id, date });
      }

      _usluga(domena, usluga, dane) {
        // błąd wywołania pokazuje sam frontend HA (toast); tu tylko bez nieobsłużonego odrzucenia
        Promise.resolve(this._hass.callService(domena, usluga, dane)).catch(() => {});
      }
    },
  );
}
