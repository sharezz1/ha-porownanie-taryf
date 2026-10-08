# Porównanie taryf / Tariff comparison

Integracja Home Assistant (HACS) · Home Assistant custom integration (HACS)

[Polski](#polski) · [English](#english)

---

## Polski

Integracja liczy koszt prądu (**brutto**) dla okresu wybranego przez Ciebie, w scenariuszach *sprzedawca × taryfa dystrybucyjna*, i pomaga odpowiedzieć na dwa pytania:

1. Czy taryfa **G11**, **G12w**, **G12sezON** lub **G13active** jest tańsza od obecnej (np. G12) przy niezmienionym zużyciu?
2. Czy opłaca się wrócić do sprzedawcy z umową kompleksową zamiast sprzedaży dynamicznej **Pstryk** — z uwzględnieniem **Tarczy Pstryk**?

Dane zużycia i koszty sprzedaży pochodzą z API Pstryk. Stawki dystrybucyjne pochodzą z presetu (Enea Operator 2026: G11, G12, G12w, G12sezON, G13active) i można je zmienić w opcjach.

### Ważne zastrzeżenia

Przeczytaj, zanim zaufasz wynikowi.

- **Nieoficjalny endpoint.** Integracja korzysta z endpointu Pstryk, który nie jest opisany w dokumentacji Pstryk (`.../meter-data/unified-metrics/`). Może się zmienić lub zniknąć bez uprzedzenia. Wtedy integracja pokazuje w Naprawach problem „Endpoint Pstryk odrzuca zapytania” i liczy dalej z danych zapisanych lokalnie (bez nowych godzin).
- **Tarcza Pstryk 2027 jest niezweryfikowana.** Preset 2026 odtwarza fakturę; preset 2027 pochodzi z artykułu prasowego, a nie z regulaminu Pstryk. Ostrzeżenie `tarcza_niezweryfikowana:2027` towarzysi każdemu wynikowi, który go używa. Zweryfikuj parametry w regulaminie i popraw je w opcjach.
- **Stawki dystrybucyjne zmieniają się co roku.** Nowa taryfa operatora jest publikowana w grudniu. Preset jest na rok 2026; dla odczytów z innego roku pojawia się ostrzeżenie `stawki_spoza_roku:<rok>`. Po zmianie taryfy zaktualizuj stawki.
- **Zapis opcji „VAT i stawki” oraz „Tarcza” utrwala WSZYSTKIE wartości z formularza.** Późniejsze poprawki presetu w nowej wersji integracji (np. stawki na 2027 czy zweryfikowana Tarcza 2027) nie trafią do Ciebie, dopóki nie zmienisz tych wartości ręcznie albo nie usuniesz i nie dodasz integracji od nowa.
- **Zużycie jest stałe.** Wynik zakłada, że po zmianie taryfy lub sprzedawcy zużywasz prąd w tych samych godzinach. To często nieprawda: jeśli na przykład ładujesz samochód w godzinach 13–15, bo opłaca się to przy G12 i cenach dynamicznych, u sprzedawcy ze stałą ceną albo w innej taryfie optymalny wzorzec byłby inny. Integracja tego nie modeluje.
- **Zegar strefowy licznika.** Taryfa operatora (pkt 2.2.12) dopuszcza liczniki, których zegar stref pozostaje przez cały rok na czasie zimowym (CET), jeśli licznik sam się nie przestawia. Integracja liczy strefy wg zegara ściennego (czas lokalny). Jeśli Twój licznik trzyma czas zimowy, latem rzeczywiste strefy są przesunięte o godzinę (np. dla G12sezON 5–7 i 10–18). Dotyczy to wszystkich taryf strefowych.
- **Pojedynczy miesiąc myli.** Taryfa droższa w jednym miesiącu bywa tańsza w skali roku (różnice sezonowe). **Decyzję o taryfie opieraj na okresie co najmniej 12 miesięcy** (okres „Rok” albo własny zakres).
- To narzędzie orientacyjne. Wynik nie jest poradą ani gwarancją; porównaj go z fakturami.

### Wymagania

- Jesteś klientem **Pstryk** i masz klucz API (w ustawieniach konta Pstryk, w sekcji API) — to ten klucz, o który integracja prosi przy dodawaniu.
- Dane z licznika energii elektrycznej są dostępne w API Pstryk.
- Home Assistant **2026.8** lub nowszy.
- Zainstalowany **HACS**.
- Preset dopasowano do obszaru **Enea Operator**. W obszarze innego operatora (OSD) możesz zmienić stawki dystrybucyjne w opcjach, ale definicje stref G12w, G12sezON i G13active pozostają takie jak u Enei (nie da się ich edytować).

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
| Obecna taryfa | G11, G12, G12w, G12sezON lub G13active. Wszystkie „różnice względem obecnej” są liczone względem Pstryk + ta taryfa. |
| Tanie godziny G12 | Godziny rozpoczęcia tanich godzin (domyślnie 22–6 i 13–15). Dotyczy tylko G12. |

G11 ma jedną strefę całodobową (całe zużycie liczy się wtedy jako „tanie”, „drogie” = 0). Strefy G12w, G12sezON i G13active pochodzą z presetu i nie są edytowalne w interfejsie (G12w: szczyt w dni robocze 6–21, poza szczytem reszta oraz soboty, niedziele i święta; G13active: strefy zależne od miesiąca).

**G12sezON** ma dwie strefy: *zalecanego poboru* (tania) i *pozostałe godziny*. Godziny strefy zalecanej zależą od sezonu i są takie same we wszystkie dni tygodnia, także w weekendy i święta:

| Sezon | Strefa zalecanego poboru (godziny od–do, zegar ścienny) |
|---|---|
| kwiecień–wrzesień | 4–6 oraz 9–17 |
| październik–marzec | 22–6 oraz 11–13 |

Godziny liczone są wg zegara ściennego (Europe/Warsaw), czyli lokalnego czasu urzędowego. Stawki sieciowe G12sezON w presecie Enea są takie same jak G12 (zalecana = jak noc G12); różnią się wyłącznie godziny stref. To osobne wartości: zmiana stawek G12 w opcjach nie zmienia stawek G12sezON (i odwrotnie), więc przy innych stawkach popraw obie taryfy. Zmiana grupy taryfowej u operatora jest ograniczona (zasadniczo raz na 12 miesięcy), więc sprawdź warunki u swojego OSD, zanim ją wybierzesz.

**Opcje** (Ustawienia → Urządzenia i usługi → Porównanie taryf → Konfiguruj), zapis każdego kroku przeładowuje integrację:

- **VAT i stawki dystrybucyjne:** VAT (domyślnie 0,23) i wszystkie stawki netto presetu.
- **Tarcza Pstryk:** dla 2026 i 2027 — limit średniej ceny, podstawa (brutto/netto), czy w średniej liczy się opłata handlowa, daty obowiązywania.
- **Własny cennik sprzedawcy:** jeden cennik (obok wbudowanych ofert kompleksowych, patrz „Oferty kompleksowe”): nazwa, opłata handlowa (zł/mc netto), akcyza (domyślnie 0,005 zł/kWh) i ceny netto energii w strefach wybranych taryf. Taryfa uczestniczy w porównaniu tylko z kompletem stref. Pusta nazwa usuwa cennik.

### Encje

Wszystkie encje należą do jednego urządzenia (usługi) „Porównanie taryf”, więc ich identyfikatory zaczynają się od `porownanie_taryf_` (np. `select.porownanie_taryf_okres`).

**Sterowanie okresem** (stan jest przywracany po restarcie):

| Encja | Działanie |
|---|---|
| `select` Okres | Dzień / Miesiąc / Rok / Zakres własny (domyślnie Miesiąc). |
| `select` Sprzedawca | Oferta kompleksowa pokazywana w sekcji 2 panelu: Wszystkie oferty (domyślnie) / Enea — prawo wyboru / Enea — EneoPewność / Własny cennik (gdy zdefiniowany). Tylko filtruje widok panelu, nie zmienia liczb; wybór spoza listy wraca do „Wszystkie oferty”. |
| `date` Data | Dzień (lub miesiąc/rok zawierający tę datę, lub początek zakresu). Domyślnie 1. dzień poprzedniego miesiąca. |
| `date` Koniec zakresu | Używany tylko w trybie „Zakres własny”. Domyślnie równy Dacie (zakres jednodniowy). |

Zmiana okresu przelicza wynik z danych zapisanych lokalnie, **bez zapytań do API**. Jeśli koniec zakresu wypada przed datą, sensory mają stan `unknown`, a atrybut `powod` = `koniec_przed_data`.

**Sensory** (PLN, brutto, `device_class: monetary`, bez `state_class`, zaokrąglone do 2 miejsc):

| Encja | Znaczenie |
|---|---|
| `<scenariusz> — razem` | Sprzedaż po Tarczy + dystrybucja dla scenariusza. |
| `<scenariusz> — różnica względem obecnej` | `razem` scenariusza minus `razem` obecnego. **Dodatnia = drożej niż obecnie**, ujemna = taniej. Nie ma jej dla scenariusza obecnego. |
| `kWh w tanich godzinach` / `kWh w drogich godzinach` | Zużycie w tanich i w pozostałych strefach obecnej taryfy (kWh). |

Scenariusze to *Pstryk + G11*, *Pstryk + G12*, *Pstryk + G12w*, *Pstryk + G12sezON*, *Pstryk + G13active*, wbudowane oferty kompleksowe *Enea prawo wyboru + G11 / G12 / G12w* i *Enea EneoPewność + G11 / G12 / G12w / G12sezON / G13active* (patrz niżej) oraz, jeśli zdefiniujesz własny cennik, `<nazwa cennika> + <taryfa>` dla taryf z kompletem cen.

**Atrybuty sensorów** (nazwy bez polskich znaków, wygodne w szablonach):

| Atrybut | Znaczenie |
|---|---|
| `okres_od`, `okres_do` | Granice okresu (ISO). |
| `pokrycie` | Udział godzin zmierzonych w godzinach możliwych w okresie (0–1). |
| `dane_z` | Czas ostatniego udanego pobrania z API (ISO) lub `null`. |
| `scenariusz` | Klucz scenariusza, np. `pstryk_G12` (tylko sensory `razem` i `roznica`). |
| `etykieta` | Czytelna nazwa scenariusza, np. `Pstryk + G12` albo `Enea EneoPewność + G12`. |
| `grupa` | `pstryk` (sprzedaż dynamiczna) albo `kompleksowa` (oferta kompleksowa, także własny cennik). |
| `sprzedawca` | Nazwa sprzedawcy: `Pstryk`, `Enea` albo nazwa własnego cennika. |
| `oferta` | Nazwa oferty: `prawo wyboru` albo `EneoPewność` (Enea); pusta dla Pstryk i własnego cennika. |
| `uwagi` | Lista uwag do oferty (warunki, ważność cennika); pusta dla Pstryk i własnego cennika. |
| `id_oferty` | Klucz oferty z katalogu (np. `enea_eneopewnosc_2026`), `cennik` dla własnego cennika, pusty dla Pstryk (sensory `razem` i `roznica`). |
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
| `vat` | Stawka VAT (ułamek, np. `0.23`). Tabela cen poniżej: tylko sensory `razem`, kwoty netto zł/kWh lub zł/mc, 4 miejsca. |
| `stawki_dystrybucji` | Stawka dystrybucji na strefę: składnik zmienny + opłata jakościowa + OZE + kogeneracyjna. |
| `oplaty_dystrybucji_mc` | Opłaty miesięczne dystrybucji: `sieciowa` (składnik stały), `abonament`, `mocowa`. |
| `ceny_energii` | Oferty kompleksowe i własny cennik: cena energii na strefę. |
| `oplata_handlowa_mc` | Oferty kompleksowe i własny cennik: opłata handlowa (zł/mc). |
| `akcyza_kwh` | Akcyza zł/kWh: 0 w katalogu (ceny z akcyzą), z cennika własnego; dla Pstryk średnia z okresu (`null` bez odczytów). |
| `srednia_cena_energii` | Tylko Pstryk: `przed_tarcza` i `po_tarczy`, średnia cena energii z obsługą (zł/kWh) w okresie; `null` bez odczytów. |
| `powod` | Tylko gdy wynik jest niedostępny: `koniec_przed_data`. |

Sensory „kWh” mają tylko `okres_od`, `okres_do`, `pokrycie` i `dane_z`.

### Oferty kompleksowe

Obok scenariuszy Pstryk integracja ma wbudowane dwie oferty kompleksowe **Enea** (w kodzie to katalog ofert; wszystkie ceny są netto **z akcyzą**, VAT jest doliczany do całości).

**1. „Prawo wyboru” (`enea_2026_wybor`)** — taryfa dla klienta, który zmienił sprzedawcę i wraca do Enei, 2026: opłata handlowa 10,49 zł/mc netto.

| Taryfa | Ceny energii (zł/kWh netto, z akcyzą) |
|---|---|
| G11 | 0,5050 |
| G12 | dzień 0,5900 · noc 0,3486 |
| G12w | szczyt 0,5050 · pozaszczyt 0,5050 |

- **Źródło:** „Taryfa dla energii elektrycznej dla klientów z grup taryfowych G korzystających z prawa wyboru sprzedawcy”, Zarządzenie Dyr. Dep. Sprzedaży Enea S.A. nr 558/2025 z 16.12.2025, od 1.01.2026 (`https://www.enea.pl/media/6823/taryfa-g-tpapdf.pdf`). To cennik handlowy, nie zatwierdzany przez URE; nie sprawdzono, czy nowemu klientowi Enea zaproponuje właśnie ten cennik, a nie taryfę URE lub ofertę rynkową. Potwierdź w Enei.
- Nie obejmuje G12sezON ani G13active, więc nie ma scenariuszy *prawo wyboru + G12sezON* ani *+ G13active* (brak encji i brak błędu).
- W G12w cena energii Enei jest taka sama w szczycie i poza szczytem; zysk z G12w wynika wtedy wyłącznie z dystrybucji.

**2. „EneoPewność” (`enea_eneopewnosc_2026`)** — oferta rynkowa Enei, cennik dla umów zawieranych od 1.10 do 31.12.2026, opłata handlowa 15,94 zł/mc netto.

| Taryfa | Ceny energii (zł/kWh netto, z akcyzą) |
|---|---|
| G11 | 0,4950 |
| G12 | dzień 0,5736 · noc 0,3365 |
| G12w | szczyt 0,6464 · pozaszczyt 0,3459 |
| G12sezON | pozostałe godziny 0,5841 · zalecany pobór 0,3465 |
| G13active | ograniczanie 0,6435 · pozostałe 0,4950 · pobór 0,2772 |

- **Opłata i czas trwania:** cena energii i opłata handlowa są stałe przez **36 miesięcy**. Opłata 15,94 zł/mc netto dotyczy e-faktury (przy fakturze papierowej jest wyższa: 20,01 zł netto) i obejmuje usługę „Elektryk”, której nie można odłączyć od oferty.
- **Warunek grupy taryfowej:** przy zawarciu umowy w związku ze zmianą sprzedawcy grupa taryfowa dystrybucji rozliczana bezpośrednio przed zmianą musi być taka sama jak grupa wybrana w nowej umowie. Jeśli dziś masz G12, a chcesz inną grupę (np. G12sezON), najpierw zmień grupę u operatora; samą zmianą sprzedawcy się nie da.
- **Ważność cennika:** obowiązuje dla umów zawieranych od 1.10 do 31.12.2026, ceny są stałe przez 36 miesięcy.
- **Źródło:** Cennik oferty EneoPewność 36 miesięcy (nr EP36010330_G) i Regulamin oferty z 1.10.2026, `https://www.enea.pl/eneopewnosc`. To oferta rynkowa; przed decyzją potwierdź warunki w Enei.

Pozostałe informacje:

- Scenariusze Enei mają `grupa` = `kompleksowa`, `sprzedawca` = `Enea`, a oferty rozróżnia atrybut `oferta` i klucz scenariusza. Własny cennik ma tę samą `grupę`, `sprzedawca` to jego nazwa, a `oferta` jest pusta; wszystkie mogą występować jednocześnie.
- Ofertę pokazywaną w sekcji 2 panelu wybierasz encją `select` Sprzedawca (nie zmienia obliczeń). Ważność cenników: „prawo wyboru” to cennik na 2026 rok; „EneoPewność” to umowy zawierane od 1.10 do 31.12.2026, ceny stałe przez 36 miesięcy.

**Aktualizacja z v0.3: zmiana nazw encji oferty kompleksowej.** Klucz scenariusza zawiera teraz identyfikator oferty: `kompleksowa_G12` zmienił się na `kompleksowa_enea_2026_wybor_G12` (i analogicznie dla G11, G12w, oraz encji `razem` i `roznica`). Po aktualizacji stare encje oferty Enea znikają z rejestru, a w ich miejsce powstają nowe, z nowymi identyfikatorami. **Zaktualizuj automatyzacje, szablony i karty, które odwoływały się do starych encji**. Encje Pstryk i własnego cennika zostają bez zmian.

### Panel „Porównanie taryf”

Integracja sama dodaje do paska bocznego HA panel **Porównanie taryf** (ikona wagi, widoczny dla wszystkich użytkowników). Panel składa się z linijki podsumowania i dwóch sekcji, które mają wspólną skalę pasków:

- **Linijka podsumowania** na górze: kwota obecnej umowy za wybrany okres i najtańsza opcja ogółem z obu sekcji (albo informacja, że obecna jest najtańsza lub równie tania jak inna).
- **Sekcja 1. „Prąd z Pstryka + dystrybucja Enea Operator”:** własny werdykt (najtańsza taryfa dystrybucyjna albo „obecna taryfa jest najtańsza”), wykres taryf G11 / G12 / G12w / G12sezON / G13active przy umowie z Pstryk oraz kafelki: Tarcza Pstryk, zużycie, tanie i drogie godziny, data danych.
- **Sekcja 2. „Umowa kompleksowa Enea”:** własny werdykt (najtańsza oferta kompleksowa kontra obecna umowa z Pstryk) i jeden wspólny ranking wszystkich ofert z katalogu (Enea prawo wyboru, Enea EneoPewność) oraz własnego cennika, jeśli go zdefiniujesz. Pod wykresem panel pokazuje dla każdej oferty, których taryf ona nie obejmuje, oraz jej uwagi (warunki, ważność cennika, potwierdzenie oferty w Enei).

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

1. Is **G11**, **G12w**, **G12sezON** or **G13active** cheaper than your current tariff (e.g. G12) with unchanged consumption?
2. Is it worth going back to a seller with a comprehensive contract instead of **Pstryk** dynamic pricing, taking the **Pstryk Shield (Tarcza Pstryk)** rebate into account?

Consumption data and sales costs come from the Pstryk API. Distribution rates come from a preset (Enea Operator 2026: G11, G12, G12w, G12sezON, G13active) that you can edit in the options.

### Important caveats

Read these before trusting a result.

- **Unofficial endpoint.** The integration uses a Pstryk endpoint that is not described in Pstryk's documentation (`.../meter-data/unified-metrics/`). It may change or disappear without notice. When that happens the integration raises a Repair issue ("Pstryk endpoint rejects requests") and keeps calculating from locally stored data (no new hours).
- **The 2027 Pstryk Shield is unverified.** The 2026 preset reproduces an invoice; the 2027 preset comes from a press article, not from Pstryk's terms. The warning `tarcza_niezweryfikowana:2027` accompanies every result that uses it. Check the parameters against the terms and correct them in the options.
- **Distribution rates change every year.** The operator publishes the new tariff in December. The preset is for 2026; for readings from any other year the warning `stawki_spoza_roku:<year>` appears. Update the rates when the tariff changes.
- **Saving the "VAT and rates" or "Shield" options persists ALL values in the form.** Later preset corrections shipped in a newer version (e.g. 2027 rates or a verified 2027 Shield) will not reach you until you change those values by hand or remove and re-add the integration.
- **Consumption is assumed unchanged.** The result assumes you use electricity in the same hours after changing tariff or seller. That is often untrue: if, for example, you charge an EV at 13–15 because that pays off under G12 and dynamic prices, the best pattern under a fixed-price seller or another tariff would differ. The integration does not model this.
- **Meter zone clock.** The operator tariff (item 2.2.12) allows meters whose zone clock stays on winter time (CET) all year unless the meter adjusts itself. The integration uses wall-clock local time. If your meter keeps winter time, in summer the real zones are shifted by one hour (e.g. G12sezON 5–7 and 10–18). This applies to all zoned tariffs.
- **A single month misleads.** A tariff that is more expensive in one month can be cheaper over a year (seasonal differences). **Base a tariff decision on a period of at least 12 months** (the "Year" period or a custom range).
- This is an indicative tool. A result is neither advice nor a guarantee; compare it with your invoices.

### Requirements

- You are a **Pstryk** customer with an API key (in your Pstryk account settings, in the API section) — this is the key the integration asks for when you add it.
- Electricity meter data is available in the Pstryk API.
- Home Assistant **2026.8** or newer.
- **HACS** installed.
- The preset fits the **Enea Operator** area. In another distribution operator's area (DSO) you can override the distribution rates in the options, but the G12w, G12sezON and G13active zone definitions remain Enea's (they are not editable).

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
| Current tariff | G11, G12, G12w, G12sezON or G13active. Every "difference vs current" is measured against Pstryk + this tariff. |
| G12 cheap hours | Hours at which a cheap hour starts (default 22–6 and 13–15). Applies to G12 only. |

G11 has a single all-day zone (all consumption counts as "cheap", "expensive" = 0). The G12w, G12sezON and G13active zones come from the preset and are not editable in the UI (G12w: peak on working days 6–21, off-peak otherwise plus Saturdays, Sundays and public holidays; G13active: zones depend on the month).

**G12sezON** has two zones: the *recommended-usage* zone (cheap) and *other hours*. The recommended zone depends on the season and is the same every day of the week, weekends and public holidays included:

| Season | Recommended-usage zone (hours from–to, wall-clock) |
|---|---|
| April–September | 4–6 and 9–17 |
| October–March | 22–6 and 11–13 |

Hours follow the wall clock (Europe/Warsaw), i.e. local civil time. G12sezON network rates in the Enea preset are the same as G12 (recommended = like G12 night); only the zone hours differ. They are separate values: overriding the G12 rates in the options does not change the G12sezON rates (and vice versa), so if your rates differ, edit both tariffs. Changing the tariff group at the operator is restricted (in general once per 12 months), so check the terms with your DSO before choosing it.

**Options** (Settings → Devices & services → Porównanie taryf → Configure); saving any step reloads the integration:

- **VAT and distribution rates:** VAT (default 0.23) and all net preset rates.
- **Pstryk Shield:** for 2026 and 2027 — average price limit, basis (gross/net), whether the trading fee counts towards the average, validity dates.
- **Own seller price list:** one price list (besides the built-in comprehensive offers, see "Comprehensive offers"): name, trading fee (PLN/month net), excise duty (default 0.005 PLN/kWh) and net energy prices per zone for the tariffs you choose. A tariff takes part only with all of its zones filled in. An empty name removes the price list.

### Entities

All entities belong to a single device (service) named "Porównanie taryf", so their IDs start with `porownanie_taryf_` (e.g. `select.porownanie_taryf_period`).

**Period controls** (state is restored after a restart):

| Entity | Behaviour |
|---|---|
| `select` Period | Day / Month / Year / Custom range (default Month). |
| `select` Seller | Comprehensive offer shown in panel section 2: All offers (default) / Enea — right to choose / Enea — EneoPewność / Own price list (when defined). It only filters the panel view and does not change any figure; a value outside the list falls back to "All offers". |
| `date` Date | The day (or the month/year containing the date, or the start of the range). Defaults to the 1st day of the previous month. |
| `date` Range end | Used only in "Custom range" mode. Defaults to the Date (a one-day range). |

Changing the period recalculates from locally stored data, **without any API calls**. If the range end is before the date, the sensors show state `unknown` and the attribute `powod` = `koniec_przed_data`.

**Sensors** (PLN, gross, `device_class: monetary`, no `state_class`, rounded to 2 places):

| Entity | Meaning |
|---|---|
| `<scenario> — total` | Sales after the Shield + distribution for the scenario. |
| `<scenario> — difference vs current` | The scenario's `total` minus the current scenario's `total`. **Positive = more expensive than now**, negative = cheaper. Not created for the current scenario. |
| `kWh in cheap hours` / `kWh in expensive hours` | Consumption in the cheap and in the remaining zones of the current tariff (kWh). |

The scenarios are *Pstryk + G11*, *Pstryk + G12*, *Pstryk + G12w*, *Pstryk + G12sezON*, *Pstryk + G13active*, the built-in comprehensive offers *Enea prawo wyboru + G11 / G12 / G12w* and *Enea EneoPewność + G11 / G12 / G12w / G12sezON / G13active* (see below) and, if you define an own price list, `<price list name> + <tariff>` for the tariffs with a complete set of prices.

**Sensor attributes** (names are ASCII, convenient in templates):

| Attribute | Meaning |
|---|---|
| `okres_od`, `okres_do` | Period bounds (ISO). |
| `pokrycie` | Share of measured hours in the possible hours of the period (0–1). |
| `dane_z` | Time of the last successful API fetch (ISO) or `null`. |
| `scenariusz` | Scenario key, e.g. `pstryk_G12` (only the `total` and `difference` sensors). |
| `etykieta` | Readable scenario name, e.g. `Pstryk + G12` or `Enea EneoPewność + G12`. |
| `grupa` | `pstryk` (dynamic sales) or `kompleksowa` (comprehensive offer, own price list included). |
| `sprzedawca` | Seller name: `Pstryk`, `Enea` or the name of your own price list. |
| `oferta` | Offer name: `prawo wyboru` or `EneoPewność` (Enea); empty for Pstryk and an own price list. |
| `uwagi` | List of notes on the offer (conditions, price list validity); empty for Pstryk and an own price list. |
| `id_oferty` | Catalogue offer key (e.g. `enea_eneopewnosc_2026`), `cennik` for the own price list, empty for Pstryk (`total` and `difference` sensors). |
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
| `vat` | VAT rate (fraction, e.g. `0.23`). The price table below is on the `total` sensors only; net amounts, PLN/kWh or PLN/month, 4 decimals. |
| `stawki_dystrybucji` | Distribution rate per zone: variable component + quality + renewables + cogeneration fees. |
| `oplaty_dystrybucji_mc` | Monthly distribution fees: `sieciowa` (fixed component), `abonament`, `mocowa` (capacity fee). |
| `ceny_energii` | Comprehensive offers and own price list: energy price per zone. |
| `oplata_handlowa_mc` | Comprehensive offers and own price list: trading fee (PLN/month). |
| `akcyza_kwh` | Excise PLN/kWh: 0 for the catalogue (prices include excise), from the own price list; for Pstryk the period average (`null` without readings). |
| `srednia_cena_energii` | Pstryk only: `przed_tarcza` (before the Shield) and `po_tarczy` (after), average energy price including the service fee (PLN/kWh) over the period; `null` without readings. |
| `powod` | Only when the result is unavailable: `koniec_przed_data`. |

The "kWh" sensors only have `okres_od`, `okres_do`, `pokrycie` and `dane_z`.

### Comprehensive offers

Besides the Pstryk scenarios the integration has two built-in comprehensive offers from **Enea** (in code this is an offer catalogue; all prices are net **including excise duty**, VAT is added to the whole).

**1. "Prawo wyboru" ("right to choose", `enea_2026_wybor`)** — the tariff for a customer who switched seller and returns to Enea, 2026: trading fee 10.49 PLN/month net.

| Tariff | Energy prices (PLN/kWh net, excise included) |
|---|---|
| G11 | 0.5050 |
| G12 | day 0.5900 · night 0.3486 |
| G12w | peak 0.5050 · off-peak 0.5050 |

- **Source:** "Tariff for electricity for customers of the G tariff groups using the right to choose a seller" (Polish title: "Taryfa dla energii elektrycznej dla klientów z grup taryfowych G korzystających z prawa wyboru sprzedawcy"), Enea S.A. order no. 558/2025 of 16 Dec 2025, in force from 1 Jan 2026 (`https://www.enea.pl/media/6823/taryfa-g-tpapdf.pdf`). It is a commercial price list not approved by the regulator (URE); it has not been verified whether Enea would offer a returning customer this price list rather than the URE tariff or a market offer. Confirm with Enea.
- It covers neither G12sezON nor G13active, so there are no *prawo wyboru + G12sezON* or *+ G13active* scenarios (no entity and no error).
- Under G12w Enea's energy price is the same in peak and off-peak; the gain from G12w then comes from distribution alone.

**2. "EneoPewność" (`enea_eneopewnosc_2026`)** — Enea's market offer, a price list for contracts signed from 1 Oct to 31 Dec 2026, trading fee 15.94 PLN/month net.

| Tariff | Energy prices (PLN/kWh net, excise included) |
|---|---|
| G11 | 0.4950 |
| G12 | day 0.5736 · night 0.3365 |
| G12w | peak 0.6464 · off-peak 0.3459 |
| G12sezON | other hours 0.5841 · recommended usage 0.3465 |
| G13active | ograniczanie 0.6435 · pozostałe 0.4950 · pobór 0.2772 |

- **Fee and duration:** the energy price and the trading fee are fixed for **36 months**. The 15.94 PLN/month net fee applies to e-invoicing (a paper invoice costs more: 20.01 PLN net) and includes the "Elektryk" (electrician) service, which cannot be detached from the offer.
- **Tariff group condition:** when the contract is concluded as part of a seller change, the distribution tariff group billed immediately before the change must be the same as the group chosen in the new contract. If you have G12 today and want another group (e.g. G12sezON), change the group at the operator first; a seller change alone will not do.
- **Price list validity:** it applies to contracts signed from 1 Oct to 31 Dec 2026, with prices fixed for 36 months.
- **Source:** the EneoPewność 36-month price list (no. EP36010330_G) and the offer's terms of 1 Oct 2026, `https://www.enea.pl/eneopewnosc`. It is a market offer; confirm the terms with Enea before deciding.

Other notes:

- Enea scenarios have `grupa` = `kompleksowa`, `sprzedawca` = `Enea`, and the offers are told apart by the `oferta` attribute and the scenario key. An own price list has the same `grupa`, its name as `sprzedawca` and an empty `oferta`; all of them can exist at once.
- The offer shown in panel section 2 is chosen with the Seller `select` entity (it does not change any calculation). Validity of the price lists: "prawo wyboru" is the 2026 price list; "EneoPewność" is for contracts signed from 1 Oct to 31 Dec 2026, with prices fixed for 36 months.

**Upgrading from v0.3: the comprehensive-offer entities are renamed.** The scenario key now contains the offer id: `kompleksowa_G12` became `kompleksowa_enea_2026_wybor_G12` (likewise for G11, G12w, and for both the `razem`/total and `roznica`/difference entities). After the update the old Enea-offer entities disappear from the registry and new ones, with new IDs, are created in their place. **Update any automations, templates and cards that referenced the old entities**. Pstryk and own-price-list entities are unchanged.

### "Tariff comparison" panel

The integration adds a **Porównanie taryf** panel (always in Polish, as Pstryk and Enea operate only in Poland) to the HA sidebar by itself (scale icon, visible to all users). It consists of a summary line and two sections on a shared bar scale:

- **Summary line** at the top: the current contract's cost for the selected period and the cheapest option overall across both sections (or a note that the current one is the cheapest or as cheap as another).
- **Section 1, "Pstryk power + Enea Operator distribution":** its own verdict (the cheapest distribution tariff, or "the current tariff is the cheapest"), a chart of G11 / G12 / G12w / G12sezON / G13active under the Pstryk contract and tiles: Pstryk Shield, consumption, cheap and expensive hours, data date.
- **Section 2, "Enea comprehensive contract":** its own verdict (the cheapest comprehensive offer versus the current Pstryk contract) and one shared ranking of all catalogue offers (Enea prawo wyboru, Enea EneoPewność) plus your own price list, if you define one. Under the chart the panel shows, per offer, which tariffs it does not cover and its notes (conditions, price list validity, confirming the offer with Enea).

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
