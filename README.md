# Porównanie taryf / Tariff comparison

Integracja Home Assistant (HACS) · Home Assistant custom integration (HACS)

[Polski](#polski) · [English](#english)

---

## Polski

Integracja liczy koszt prądu (**brutto**) dla okresu wybranego przez Ciebie, w scenariuszach *sprzedawca × taryfa dystrybucyjna*, i pomaga odpowiedzieć na dwa pytania:

1. Czy taryfa **G11**, **G12w** lub **G13active** jest tańsza od obecnej (np. G12) przy niezmienionym zużyciu?
2. Czy opłaca się wrócić do sprzedawcy z umową kompleksową zamiast sprzedaży dynamicznej **Pstryk** — z uwzględnieniem **Tarczy Pstryk**?

Dane zużycia i koszty sprzedaży pochodzą z API Pstryk. Stawki dystrybucyjne pochodzą z presetu (Enea Operator 2026: G11, G12, G12w, G13active) i można je zmienić w opcjach.

### Ważne zastrzeżenia

Przeczytaj, zanim zaufasz wynikowi.

- **Nieoficjalny endpoint.** Integracja korzysta z endpointu Pstryk, który nie jest opisany w dokumentacji Pstryk (`.../meter-data/unified-metrics/`). Może się zmienić lub zniknąć bez uprzedzenia. Wtedy integracja pokazuje w Naprawach problem „Endpoint Pstryk odrzuca zapytania” i liczy dalej z danych zapisanych lokalnie (bez nowych godzin).
- **Tarcza Pstryk 2027 jest niezweryfikowana.** Preset 2026 odtwarza fakturę; preset 2027 pochodzi z artykułu prasowego, a nie z regulaminu Pstryk. Ostrzeżenie `tarcza_niezweryfikowana:2027` towarzysi każdemu wynikowi, który go używa. Zweryfikuj parametry w regulaminie i popraw je w opcjach.
- **Stawki dystrybucyjne zmieniają się co roku.** Nowa taryfa operatora jest publikowana w grudniu. Preset jest na rok 2026; dla odczytów z innego roku pojawia się ostrzeżenie `stawki_spoza_roku:<rok>`. Po zmianie taryfy zaktualizuj stawki.
- **Zapis opcji „VAT i stawki” oraz „Tarcza” utrwala WSZYSTKIE wartości z formularza.** Późniejsze poprawki presetu w nowej wersji integracji (np. stawki na 2027 czy zweryfikowana Tarcza 2027) nie trafią do Ciebie, dopóki nie zmienisz tych wartości ręcznie albo nie usuniesz i nie dodasz integracji od nowa.
- **Zużycie jest stałe.** Wynik zakłada, że po zmianie taryfy lub sprzedawcy zużywasz prąd w tych samych godzinach. To często nieprawda: jeśli na przykład ładujesz samochód w godzinach 13–15, bo opłaca się to przy G12 i cenach dynamicznych, u sprzedawcy ze stałą ceną albo w innej taryfie optymalny wzorzec byłby inny. Integracja tego nie modeluje.
- **Pojedynczy miesiąc myli.** Taryfa droższa w jednym miesiącu bywa tańsza w skali roku (różnice sezonowe). **Decyzję o taryfie opieraj na okresie co najmniej 12 miesięcy** (okres „Rok” albo własny zakres).
- To narzędzie orientacyjne. Wynik nie jest poradą ani gwarancją; porównaj go z fakturami.

### Wymagania

- Jesteś klientem **Pstryk** i masz klucz API (w ustawieniach konta Pstryk, w sekcji API) — to ten klucz, o który integracja prosi przy dodawaniu.
- Dane z licznika energii elektrycznej są dostępne w API Pstryk.
- Home Assistant **2026.8** lub nowszy.
- Zainstalowany **HACS**.
- Preset dopasowano do obszaru **Enea Operator**. W obszarze innego operatora (OSD) możesz zmienić stawki dystrybucyjne w opcjach, ale definicje stref G12w i G13active pozostają takie jak u Enei (nie da się ich edytować).

### Instalacja przez HACS

1. W Home Assistant otwórz **HACS**, kliknij menu **⋮** (trzy kropki, prawy górny róg) → **Niestandardowe repozytoria**.
2. W polu „Repozytorium” wklej `https://github.com/sharezz1/ha-porownanie-taryf`, jako typ wybierz **Integracja** i kliknij **Dodaj**.
3. Znajdź w HACS **Porównanie taryf**, kliknij **Pobierz** i potwierdź.
4. **Zrestartuj Home Assistant** (wymagana wersja 2026.8 lub nowsza).
5. Wejdź w **Ustawienia → Urządzenia i usługi → Dodaj integrację**, wyszukaj **Porównanie taryf** i wybierz ją.
6. Wklej **klucz API Pstryk** (znajdziesz go w ustawieniach konta Pstryk, w sekcji API), ustaw układ przyłącza (3f lub 1f) i obecną taryfę, potwierdź.
7. W pasku bocznym pojawi się panel **Porównanie taryf**. Przy pierwszym uruchomieniu integracja pobiera dane do 24 miesięcy wstecz, więc wyniki mogą pojawić się po chwili.

**Instalacja ręczna (bez HACS):** skopiuj katalog `custom_components/porownanie_taryf` z tego repozytorium do `/config/custom_components/` w swoim Home Assistant, zrestartuj go i dodaj integrację jak w punktach 5–7.

### Konfiguracja

| Pole | Znaczenie |
|---|---|
| Klucz API Pstryk | Sprawdzany jednym zapytaniem o 1 dobę danych. Zapisywany w konfiguracji HA, wysyłany tylko do Pstryk. |
| Układ przyłącza | 3f lub 1f; wpływa na stały składnik opłaty dystrybucyjnej. |
| Preset | Na razie tylko Enea Operator 2026. |
| Obecna taryfa | G11, G12, G12w lub G13active. Wszystkie „różnice względem obecnej” są liczone względem Pstryk + ta taryfa. |
| Tanie godziny G12 | Godziny rozpoczęcia tanich godzin (domyślnie 22–6 i 13–15). Dotyczy tylko G12. |

G11 ma jedną strefę całodobową (całe zużycie liczy się wtedy jako „tanie”, „drogie” = 0). Strefy G12w i G13active pochodzą z presetu i nie są edytowalne w interfejsie (G12w: szczyt w dni robocze 6–21, poza szczytem reszta oraz soboty, niedziele i święta; G13active: strefy zależne od miesiąca).

**Opcje** (Ustawienia → Urządzenia i usługi → Porównanie taryf → Konfiguruj), zapis każdego kroku przeładowuje integrację:

- **VAT i stawki dystrybucyjne:** VAT (domyślnie 0,23) i wszystkie stawki netto presetu.
- **Tarcza Pstryk:** dla 2026 i 2027 — limit średniej ceny, podstawa (brutto/netto), czy w średniej liczy się opłata handlowa, daty obowiązywania.
- **Własny cennik sprzedawcy:** jeden cennik (obok wbudowanej oferty kompleksowej, patrz „Oferta kompleksowa”): nazwa, opłata handlowa (zł/mc netto), akcyza (domyślnie 0,005 zł/kWh) i ceny netto energii w strefach wybranych taryf. Taryfa uczestniczy w porównaniu tylko z kompletem stref. Pusta nazwa usuwa cennik.

### Encje

Wszystkie encje należą do jednego urządzenia (usługi) „Porównanie taryf”, więc ich identyfikatory zaczynają się od `porownanie_taryf_` (np. `select.porownanie_taryf_okres`).

**Sterowanie okresem** (stan jest przywracany po restarcie):

| Encja | Działanie |
|---|---|
| `select` Okres | Dzień / Miesiąc / Rok / Zakres własny (domyślnie Miesiąc). |
| `date` Data | Dzień (lub miesiąc/rok zawierający tę datę, lub początek zakresu). Domyślnie 1. dzień poprzedniego miesiąca. |
| `date` Koniec zakresu | Używany tylko w trybie „Zakres własny”. Domyślnie równy Dacie (zakres jednodniowy). |

Zmiana okresu przelicza wynik z danych zapisanych lokalnie, **bez zapytań do API**. Jeśli koniec zakresu wypada przed datą, sensory mają stan `unknown`, a atrybut `powod` = `koniec_przed_data`.

**Sensory** (PLN, brutto, `device_class: monetary`, bez `state_class`, zaokrąglone do 2 miejsc):

| Encja | Znaczenie |
|---|---|
| `<scenariusz> — razem` | Sprzedaż po Tarczy + dystrybucja dla scenariusza. |
| `<scenariusz> — różnica względem obecnej` | `razem` scenariusza minus `razem` obecnego. **Dodatnia = drożej niż obecnie**, ujemna = taniej. Nie ma jej dla scenariusza obecnego. |
| `kWh w tanich godzinach` / `kWh w drogich godzinach` | Zużycie w tanich i w pozostałych strefach obecnej taryfy (kWh). |

Scenariusze to *Pstryk + G11*, *Pstryk + G12*, *Pstryk + G12w*, *Pstryk + G13active*, wbudowana oferta kompleksowa *Enea + G11 / G12 / G12w* (patrz niżej) oraz, jeśli zdefiniujesz własny cennik, `<nazwa cennika> + <taryfa>` dla taryf z kompletem cen.

**Atrybuty sensorów** (nazwy bez polskich znaków, wygodne w szablonach):

| Atrybut | Znaczenie |
|---|---|
| `okres_od`, `okres_do` | Granice okresu (ISO). |
| `pokrycie` | Udział godzin zmierzonych w godzinach możliwych w okresie (0–1). |
| `dane_z` | Czas ostatniego udanego pobrania z API (ISO) lub `null`. |
| `scenariusz` | Klucz scenariusza, np. `pstryk_G12` (tylko sensory `razem` i `roznica`). |
| `etykieta` | Czytelna nazwa scenariusza, np. `Pstryk + G12`. |
| `grupa` | `pstryk` (sprzedaż dynamiczna) albo `kompleksowa` (oferta kompleksowa, także własny cennik). |
| `sprzedawca` | Nazwa sprzedawcy: `Pstryk`, `Enea` albo nazwa własnego cennika. |
| `taryfa` | Taryfa dystrybucyjna scenariusza, np. `G12`. |
| `obecny` | `true` dla scenariusza obecnej taryfy. |
| `sprzedaz_przed` | Sprzedaż brutto przed Tarczą. |
| `tarcza` | Rabat Tarczy (wartość ujemna lub 0). |
| `sprzedaz_po` | Sprzedaż po Tarczy (`sprzedaz_przed` + `tarcza`). |
| `dystrybucja` | Dystrybucja brutto. |
| `netto` | Suma bez VAT (z akcyzą): sprzedaż po Tarczy + dystrybucja. |
| `szacunek` | `true`, gdy w magazynie brakuje części godzin miesiąca użytego do Tarczy, więc rabat jest oszacowany. |
| `ostrzezenia` | Lista kodów ostrzeżeń (patrz niżej). |
| `kwh_na_strefe` | Zużycie (kWh) w poszczególnych strefach taryfy scenariusza. |
| `powod` | Tylko gdy wynik jest niedostępny: `koniec_przed_data`. |

Sensory „kWh” mają tylko `okres_od`, `okres_do`, `pokrycie` i `dane_z`.

### Oferta kompleksowa

Obok scenariuszy Pstryk integracja ma wbudowaną ofertę kompleksową **Enea S.A.** w taryfie „z prawem wyboru sprzedawcy” (dla klienta, który zmienił sprzedawcę i wraca do Enei), 2026: opłata handlowa 10,49 zł/mc netto, akcyza wliczona w ceny.

| Taryfa | Ceny energii (zł/kWh netto, z akcyzą) |
|---|---|
| G11 | 0,5050 |
| G12 | dzień 0,5900 · noc 0,3486 |
| G12w | szczyt 0,5050 · pozaszczyt 0,5050 |

- **Źródło:** „Taryfa dla energii elektrycznej dla klientów z grup taryfowych G korzystających z prawa wyboru sprzedawcy”, Zarządzenie Dyr. Dep. Sprzedaży Enea S.A. nr 558/2025 z 16.12.2025, od 1.01.2026 (`https://www.enea.pl/media/6823/taryfa-g-tpapdf.pdf`). To cennik handlowy, nie zatwierdzany przez URE; nie sprawdzono, czy nowemu klientowi Enea zaproponuje właśnie ten cennik, a nie taryfę URE lub ofertę rynkową. Potwierdź w Enei.
- **Żaden cennik Enei dla gospodarstw domowych (grupa G) na 2026 nie obejmuje G13active**, więc nie ma scenariusza *Enea + G13active* (brak encji i brak błędu). G13active istnieje tylko po stronie dystrybucji.
- W G12w cena energii Enei jest taka sama w szczycie i poza szczytem; zysk z G12w wynika wtedy wyłącznie z dystrybucji.
- Scenariusze Enei mają `grupa` = `kompleksowa`, `sprzedawca` = `Enea`. Własny cennik ma tę samą `grupę`, a `sprzedawca` to jego nazwa; oba mogą występować jednocześnie.
- Wybór innego sprzedawcy z katalogu nie ma jeszcze interfejsu; lista sprzedawców zostanie rozszerzona w przyszłych wersjach. Cenniki z 2026 roku obowiązują do końca roku, na 2027 trzeba je zaktualizować.

### Panel „Porównanie taryf”

Integracja sama dodaje do paska bocznego HA panel **Porównanie taryf** (ikona wagi, widoczny dla wszystkich użytkowników). Panel składa się z linijki podsumowania i dwóch sekcji, które mają wspólną skalę pasków:

- **Linijka podsumowania** na górze: kwota obecnej umowy za wybrany okres i najtańsza opcja ogółem z obu sekcji (albo informacja, że obecna jest najtańsza lub równie tania jak inna).
- **Sekcja 1. „Prąd z Pstryka + dystrybucja Enea Operator”:** własny werdykt (najtańsza taryfa dystrybucyjna albo „obecna taryfa jest najtańsza”), wykres taryf G11 / G12 / G12w / G13active przy umowie z Pstryk oraz kafelki: Tarcza Pstryk, zużycie, tanie i drogie godziny, data danych.
- **Sekcja 2. „Umowa kompleksowa Enea”:** własny werdykt (najtańsza oferta kompleksowa kontra obecna umowa z Pstryk), wykres oferty Enei (i własnego cennika, jeśli go zdefiniujesz) oraz uwagi: gdy sprzedawca nie oferuje którejś taryfy, jest o tym adnotacja, a przy ofercie Enei także przypomnienie, że to cennik 2026 dla klientów, którzy zmieniali sprzedawcę, i że ofertę trzeba potwierdzić w Enei.

Gdy inna opcja kosztuje tyle samo co obecna (po zaokrągleniu do groszy), panel pisze, że jest „równie tania”. Dane bierze z encji integracji, więc niczego nie trzeba konfigurować. Panel pojawia się po dodaniu integracji i znika razem z ostatnim wpisem. Żeby go ukryć, zmień kolejność lub widoczność pozycji w pasku bocznym (przytrzymaj nagłówek paska bocznego lub wybierz „Edytuj pasek boczny”).

### Kody ostrzeżeń

| Kod | Znaczenie |
|---|---|
| `pokrycie_ponizej_95` | Zmierzono mniej niż 95% godzin okresu (np. dziura w danych albo okres jeszcze trwa). Wynik jest niepełny. |
| `okres_krotszy_niz_miesiac` | Okres krótszy niż 28 dni. Opłaty stałe są liczone proporcjonalnie, a Tarcza przypisana proporcjonalnie do zużycia; wynik bywa mylący dla decyzji o taryfie. |
| `tarcza_niezweryfikowana:<rok>` | Użyto parametrów Tarczy z presetu, który nie został potwierdzony w regulaminie (obecnie 2027). |
| `brak_tarczy:<RRRR-MM>` | Dla tego miesiąca żaden preset Tarczy nie obowiązuje; rabat = 0. |
| `stawki_spoza_roku:<rok>` | Okres zawiera odczyty z roku innego niż rok stawek presetu; użyto stawek presetu. |

### Dane, odświeżanie i błędy

- Pierwsze pobranie sięga do 24 miesięcy wstecz. Potem odświeżanie co 6 godzin, od ostatniej zapisanej godziny minus 48 h (korekty nadpisują stare wartości).
- Godziny są zapisywane lokalnie w magazynie HA. Do Pstryk wychodzi wyłącznie klucz API i zapytanie o zakres dat.
- 401/403: HA prosi o ponowną autoryzację (nowy klucz). 400/404: naprawa „Endpoint Pstryk odrzuca zapytania”, praca na danych lokalnych. 429: respektowany `Retry-After`. Błąd sieci lub 5xx: dane lokalne zostają, a `dane_z` pokazuje czas ostatniego udanego pobrania.

### Jak liczone są koszty (skrót)

- **Dystrybucja:** stawki zmienne × kWh w strefach (wg zegara ściennego Europe/Warsaw) + opłaty stałe proporcjonalnie do zmierzonych godzin miesiąca, razem z VAT.
- **Sprzedaż Pstryk:** rzeczywiste koszty z API. **Tarcza** jest modelowana wzorem: rabat = nadwyżka średniej miesięcznej ceny ponad limit × zużycie. Dla miesiąca objętego okresem tylko częściowo średnia liczona jest z całego miesiąca, a rabat przypisany proporcjonalnie do kWh.
- **Oferta kompleksowa (Enea) i własny cennik:** ceny netto w strefach wybranej taryfy × kWh + opłata handlowa, z VAT, plus akcyza poza VAT.

### Testy

```bash
python3.14 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

Testy publiczne używają wyłącznie danych syntetycznych. Testy oznaczone `reference` wymagają prywatnych plików spoza repozytorium (baza `REF_DB` oraz JSON z oczekiwanymi kwotami `REF_EXPECTED`, domyślnie `oczekiwane_referencja.json` obok `REF_DB`) i są pomijane.

---

## English

This integration computes the electricity cost (**gross**) for a period you choose, across *seller × distribution tariff* scenarios, and helps answer two questions:

1. Is **G11**, **G12w** or **G13active** cheaper than your current tariff (e.g. G12) with unchanged consumption?
2. Is it worth going back to a seller with a comprehensive contract instead of **Pstryk** dynamic pricing, taking the **Pstryk Shield (Tarcza Pstryk)** rebate into account?

Consumption data and sales costs come from the Pstryk API. Distribution rates come from a preset (Enea Operator 2026: G11, G12, G12w, G13active) that you can edit in the options.

### Important caveats

Read these before trusting a result.

- **Unofficial endpoint.** The integration uses a Pstryk endpoint that is not described in Pstryk's documentation (`.../meter-data/unified-metrics/`). It may change or disappear without notice. When that happens the integration raises a Repair issue ("Pstryk endpoint rejects requests") and keeps calculating from locally stored data (no new hours).
- **The 2027 Pstryk Shield is unverified.** The 2026 preset reproduces an invoice; the 2027 preset comes from a press article, not from Pstryk's terms. The warning `tarcza_niezweryfikowana:2027` accompanies every result that uses it. Check the parameters against the terms and correct them in the options.
- **Distribution rates change every year.** The operator publishes the new tariff in December. The preset is for 2026; for readings from any other year the warning `stawki_spoza_roku:<year>` appears. Update the rates when the tariff changes.
- **Saving the "VAT and rates" or "Shield" options persists ALL values in the form.** Later preset corrections shipped in a newer version (e.g. 2027 rates or a verified 2027 Shield) will not reach you until you change those values by hand or remove and re-add the integration.
- **Consumption is assumed unchanged.** The result assumes you use electricity in the same hours after changing tariff or seller. That is often untrue: if, for example, you charge an EV at 13–15 because that pays off under G12 and dynamic prices, the best pattern under a fixed-price seller or another tariff would differ. The integration does not model this.
- **A single month misleads.** A tariff that is more expensive in one month can be cheaper over a year (seasonal differences). **Base a tariff decision on a period of at least 12 months** (the "Year" period or a custom range).
- This is an indicative tool. A result is neither advice nor a guarantee; compare it with your invoices.

### Requirements

- You are a **Pstryk** customer with an API key (in your Pstryk account settings, in the API section) — this is the key the integration asks for when you add it.
- Electricity meter data is available in the Pstryk API.
- Home Assistant **2026.8** or newer.
- **HACS** installed.
- The preset fits the **Enea Operator** area. In another distribution operator's area (DSO) you can override the distribution rates in the options, but the G12w and G13active zone definitions remain Enea's (they are not editable).

### Installation via HACS

1. In Home Assistant open **HACS**, click the **⋮** menu (top right) → **Custom repositories**.
2. Paste `https://github.com/sharezz1/ha-porownanie-taryf` as the repository, choose the type **Integration** and click **Add**.
3. Find **Porównanie taryf** in HACS, click **Download** and confirm.
4. **Restart Home Assistant** (version 2026.8 or newer is required).
5. Go to **Settings → Devices & services → Add integration**, search for **Porównanie taryf** and select it.
6. Paste your **Pstryk API key** (in your Pstryk account settings, in the API section), set the connection type (3f or 1f) and your current tariff, then confirm.
7. A **Porównanie taryf** panel appears in the sidebar. On first run the integration fetches up to 24 months of history, so results may take a moment to show up.

**Manual installation (without HACS):** copy the `custom_components/porownanie_taryf` directory from this repository to `/config/custom_components/` on your Home Assistant, restart it and add the integration as in steps 5–7.

### Configuration

| Field | Meaning |
|---|---|
| Pstryk API key | Checked with a single request for 1 day of data. Stored in the HA configuration and sent to Pstryk only. |
| Connection type | 3f or 1f; affects the fixed component of the distribution fee. |
| Preset | Only Enea Operator 2026 for now. |
| Current tariff | G11, G12, G12w or G13active. Every "difference vs current" is measured against Pstryk + this tariff. |
| G12 cheap hours | Hours at which a cheap hour starts (default 22–6 and 13–15). Applies to G12 only. |

G11 has a single all-day zone (all consumption counts as "cheap", "expensive" = 0). The G12w and G13active zones come from the preset and are not editable in the UI (G12w: peak on working days 6–21, off-peak otherwise plus Saturdays, Sundays and public holidays; G13active: zones depend on the month).

**Options** (Settings → Devices & services → Porównanie taryf → Configure); saving any step reloads the integration:

- **VAT and distribution rates:** VAT (default 0.23) and all net preset rates.
- **Pstryk Shield:** for 2026 and 2027 — average price limit, basis (gross/net), whether the trading fee counts towards the average, validity dates.
- **Own seller price list:** one price list (besides the built-in comprehensive offer, see "Comprehensive offer"): name, trading fee (PLN/month net), excise duty (default 0.005 PLN/kWh) and net energy prices per zone for the tariffs you choose. A tariff takes part only with all of its zones filled in. An empty name removes the price list.

### Entities

All entities belong to a single device (service) named "Porównanie taryf", so their IDs start with `porownanie_taryf_` (e.g. `select.porownanie_taryf_period`).

**Period controls** (state is restored after a restart):

| Entity | Behaviour |
|---|---|
| `select` Period | Day / Month / Year / Custom range (default Month). |
| `date` Date | The day (or the month/year containing the date, or the start of the range). Defaults to the 1st day of the previous month. |
| `date` Range end | Used only in "Custom range" mode. Defaults to the Date (a one-day range). |

Changing the period recalculates from locally stored data, **without any API calls**. If the range end is before the date, the sensors show state `unknown` and the attribute `powod` = `koniec_przed_data`.

**Sensors** (PLN, gross, `device_class: monetary`, no `state_class`, rounded to 2 places):

| Entity | Meaning |
|---|---|
| `<scenario> — total` | Sales after the Shield + distribution for the scenario. |
| `<scenario> — difference vs current` | The scenario's `total` minus the current scenario's `total`. **Positive = more expensive than now**, negative = cheaper. Not created for the current scenario. |
| `kWh in cheap hours` / `kWh in expensive hours` | Consumption in the cheap and in the remaining zones of the current tariff (kWh). |

The scenarios are *Pstryk + G11*, *Pstryk + G12*, *Pstryk + G12w*, *Pstryk + G13active*, the built-in comprehensive offer *Enea + G11 / G12 / G12w* (see below) and, if you define an own price list, `<price list name> + <tariff>` for the tariffs with a complete set of prices.

**Sensor attributes** (names are ASCII, convenient in templates):

| Attribute | Meaning |
|---|---|
| `okres_od`, `okres_do` | Period bounds (ISO). |
| `pokrycie` | Share of measured hours in the possible hours of the period (0–1). |
| `dane_z` | Time of the last successful API fetch (ISO) or `null`. |
| `scenariusz` | Scenario key, e.g. `pstryk_G12` (only the `total` and `difference` sensors). |
| `etykieta` | Readable scenario name, e.g. `Pstryk + G12`. |
| `grupa` | `pstryk` (dynamic sales) or `kompleksowa` (comprehensive offer, own price list included). |
| `sprzedawca` | Seller name: `Pstryk`, `Enea` or the name of your own price list. |
| `taryfa` | The scenario's distribution tariff, e.g. `G12`. |
| `obecny` | `true` for the current tariff's scenario. |
| `sprzedaz_przed` | Gross sales before the Shield. |
| `tarcza` | Shield rebate (negative or 0). |
| `sprzedaz_po` | Sales after the Shield (`sprzedaz_przed` + `tarcza`). |
| `dystrybucja` | Gross distribution. |
| `netto` | Total excluding VAT (including excise): sales after the Shield + distribution. |
| `szacunek` | `true` when part of the hours of the month used for the Shield is missing from storage, so the rebate is an estimate. |
| `ostrzezenia` | List of warning codes (see below). |
| `kwh_na_strefe` | Consumption (kWh) per zone of the scenario's tariff. |
| `powod` | Only when the result is unavailable: `koniec_przed_data`. |

The "kWh" sensors only have `okres_od`, `okres_do`, `pokrycie` and `dane_z`.

### Comprehensive offer

Besides the Pstryk scenarios the integration has a built-in comprehensive offer from **Enea S.A.** under its "right to choose a seller" tariff (for a customer who switched seller and returns to Enea), 2026: trading fee 10.49 PLN/month net, excise duty included in the prices.

| Tariff | Energy prices (PLN/kWh net, excise included) |
|---|---|
| G11 | 0.5050 |
| G12 | day 0.5900 · night 0.3486 |
| G12w | peak 0.5050 · off-peak 0.5050 |

- **Source:** "Tariff for electricity for customers of the G tariff groups using the right to choose a seller" (Polish title: "Taryfa dla energii elektrycznej dla klientów z grup taryfowych G korzystających z prawa wyboru sprzedawcy"), Enea S.A. order no. 558/2025 of 16 Dec 2025, in force from 1 Jan 2026 (`https://www.enea.pl/media/6823/taryfa-g-tpapdf.pdf`). It is a commercial price list not approved by the regulator (URE); it has not been verified whether Enea would offer a returning customer this price list rather than the URE tariff or a market offer. Confirm with Enea.
- **None of Enea's 2026 household (G group) price lists includes G13active**, so there is no *Enea + G13active* scenario (no entity and no error). G13active exists on the distribution side only.
- Under G12w Enea's energy price is the same in peak and off-peak; the gain from G12w then comes from distribution alone.
- Enea scenarios have `grupa` = `kompleksowa`, `sprzedawca` = `Enea`. An own price list has the same `grupa`, with its name as `sprzedawca`; both can exist at once.
- Choosing another seller from the catalogue has no UI yet; the list of sellers will grow in future versions. The 2026 price lists apply until the end of the year and need updating for 2027.

### "Tariff comparison" panel

The integration adds a **Porównanie taryf** panel (always in Polish, as Pstryk and Enea operate only in Poland) to the HA sidebar by itself (scale icon, visible to all users). It consists of a summary line and two sections on a shared bar scale:

- **Summary line** at the top: the current contract's cost for the selected period and the cheapest option overall across both sections (or a note that the current one is the cheapest or as cheap as another).
- **Section 1, "Pstryk power + Enea Operator distribution":** its own verdict (the cheapest distribution tariff, or "the current tariff is the cheapest"), a chart of G11 / G12 / G12w / G13active under the Pstryk contract and tiles: Pstryk Shield, consumption, cheap and expensive hours, data date.
- **Section 2, "Enea comprehensive contract":** its own verdict (the cheapest comprehensive offer versus the current Pstryk contract), a chart of Enea's offer (and your own price list, if you define one) and notes: when a seller does not offer a tariff a note says so, and for Enea's offer it also reminds you that these are 2026 prices for customers who changed supplier and that you should confirm the offer with Enea.

When another option costs the same as the current one (after rounding to the cent), the panel says it is "as cheap". It reads everything from the integration's entities, so there is nothing to configure. The panel appears once the integration is added and disappears with the last config entry. To hide it, edit the sidebar (press and hold the sidebar title, or choose "Edit sidebar") and turn the item off.

### Warning codes

| Code | Meaning |
|---|---|
| `pokrycie_ponizej_95` | Fewer than 95% of the period's hours were measured (e.g. a data gap or a period still in progress). The result is incomplete. |
| `okres_krotszy_niz_miesiac` | The period is shorter than 28 days. Fixed fees are prorated and the Shield is assigned proportionally to consumption; the result can mislead a tariff decision. |
| `tarcza_niezweryfikowana:<year>` | Shield parameters come from a preset not confirmed in the terms (currently 2027). |
| `brak_tarczy:<YYYY-MM>` | No Shield preset applies to that month; rebate = 0. |
| `stawki_spoza_roku:<year>` | The period contains readings from a year other than the preset's rates year; the preset rates were used. |

### Data, refresh and errors

- The first fetch goes back up to 24 months. After that it refreshes every 6 hours, from the last stored hour minus 48 h (corrections overwrite old values).
- Hours are stored locally in HA storage. Only the API key and a date-range request leave your instance, to Pstryk.
- 401/403: HA asks for re-authentication (a new key). 400/404: the "Pstryk endpoint rejects requests" repair, working from local data. 429: `Retry-After` is respected. Network error or 5xx: local data is kept and `dane_z` shows the last successful fetch.

### How costs are computed (short)

- **Distribution:** variable rates × kWh per zone (by Europe/Warsaw wall-clock time) + fixed fees prorated by the measured share of the month's hours, including VAT.
- **Pstryk sales:** actual costs from the API. The **Shield** is modelled by a formula: rebate = the amount by which the monthly average price exceeds the limit × consumption. For a month covered only partly by the period, the average is computed over the whole month and the rebate is assigned proportionally to kWh.
- **Comprehensive offer (Enea) and own price list:** net prices per zone of the chosen tariff × kWh + trading fee, with VAT, plus excise duty outside VAT.

### Tests

```bash
python3.14 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

Public tests use synthetic data only. Tests marked `reference` need private files kept outside the repository (the `REF_DB` database and a JSON with expected amounts, `REF_EXPECTED`, by default `oczekiwane_referencja.json` next to `REF_DB`) and are skipped.
