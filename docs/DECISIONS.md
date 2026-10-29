# Ustalenia wiążące — stan 22.10.2026

To zaakceptowane wymagania produktu i granice pracy, nie lista zaimplementowanych funkcji. Stan implementacji jest w PROJECT_STATUS.json.

| ID | Decyzja |
|---|---|
| D01 | Rozwijamy osobny JARVIS OS i integrację z AutoLogiką. Produkcyjnego repo AutoLogika-OS nie zmieniamy bez osobnej zgody. |
| D02 | Wszystkie 11 pierwotnych obszarów pozostaje w zakresie. Dostarczamy kod etapami, testy, Docker, dokumentację i stan realizacji. |
| D03 | Codex może kontynuować odwracalne prace i testy bez każdorazowego pytania o pozwolenie. Rzeczywiste pytania o brakujące zachowanie produktu są mile widziane. |
| D04 | Preferowane rozwiązania open source i niskie koszty. Sprawdzamy kod, licencje i licencje modeli; n8n jest source-available. Nie łączymy bezmyślnie całych repozytoriów. |
| D05 | Wywołanie głosowe zarówno przyciskiem, jak i hasłem Jarvis. Po aktywacji swobodny dialog bez powtarzania hasła. Koniec poleceniem lub po 30 s ciszy, czas regulowany w panelu. |
| D06 | Dom i warsztat: mikrofony/głośniki w miejscu rozmowy. Poza nimi: rozmowy telefoniczne w obie strony. Hałas, echo, prywatne wyjście i równoległe sesje wymagają projektu/testów, nie są rozwiązane samym uploadem WAV. |
| D07 | Pamięć osobista automatyczna według zasad: preferencje, sprzęt, projekty, decyzje i sposób pracy; źródła, korekta, usunięcie, nowsze ustalenia zastępują stare. „Tego nie zapamiętuj” blokuje zapis. |
| D08 | Nie zapisujemy automatycznie haseł, API keys, danych płatniczych ani prywatnych danych klientów w pamięci osobistej. Dane klientów należą do odrębnej recepcji/spraw warsztatu. |
| D09 | Numer warsztatu to SIM Play. JARVIS ma odbierać od razu. Użytkownik ma drugi numer do eskalacji; nie podał jego wartości — ustawi lokalnie w panelu. |
| D10 | Eskalacja do właściciela: kryzys albo klient bardzo nalega (ponawia prośbę i odrzuca pomoc). Zwykłe zdenerwowanie/przeklinanie nie wystarcza. Pierwszą prośbę obsługujemy pytaniem o sprawę/propozycją pomocy. |
| D11 | Dostępność właściciela ustawiana w głównym panelu: dni/godziny Europe/Warsaw, urlopy/wyjątki, ręczny/czasowy DND. Brak uzgodnionych domyślnych godzin, numerów i kalendarza świąt. |
| D12 | Kryzys nie omija godzin, urlopu ani DND. Poza dostępnością pilna sprawa i ciche powiadomienie, bez telefonu. Docelowy kanał cichych powiadomień pozostaje do konfiguracji. |
| D13 | Przed przekazaniem właściciel otrzymuje prywatne podsumowanie i może zaakceptować kontakt. Klient nie słyszy wewnętrznego briefingu. Brak odpowiedzi/odmowa → prośba o oddzwonienie, bez obietnicy godziny i bez ponawiania kontaktu w tej samej rozmowie. |
| D14 | Klienci nie mają uprawnień właściciela. Numer dzwoniącego ani głos/hasło Jarvis same nie uwierzytelniają właściciela. Brak ujawniania zlecenia tylko po numerze dzwoniącego. |
| D15 | AI nie wymyśla cen i dostępności, nie potwierdza rezerwacji bez autorytatywnych danych i uprawnionej operacji. Obecny most AutoLogiki jest tylko do odczytu. |
| D16 | Nie aktywujemy przekierowania/operatora i płatnych rozmów w ramach testów kodu. WhatsApp Business Calling wymaga osobnego sprawdzenia aktualnych warunków Twilio/Meta i aktywacji konta. |
| D17 | Fizyczna brama i inne wrażliwe urządzenia wymagają osobnego potwierdzenia. Modele/treść klienta nie mogą obchodzić reguł backendu ani wykonywać kodu. |
| D18 | Zmiany zachowania przez rozmowę mają docelowo prowadzić do ustawień/automatyzacji i propozycji kodu z zatwierdzeniem, testami i rollbackiem. Dziś propozycje kodu są opisem. |
| D19 | Środa 28.10.2026: użytkownik testuje Windows i sprzęt. Do tego czasu pracujemy na syntetycznych danych i sprawdzalnych laboratoriach. |
| D20 | Każdy commit zawiera aktualizację README: konkretne zmiany, rzeczywiście wykonane sprawdzenia i pozostałe ograniczenia. Polecenie właściciela z bieżącej sesji. |

Nie pytaj ponownie, czy właściciel chce wake-word, automatyczną pamięć, odbiór od razu lub konfigurację godzin w panelu. Nie traktuj tych decyzji jako dowodu, że funkcje już działają.

## R04 — granica bieżącej implementacji

Trwała kolejka i adapter lab są sposobem przygotowania/testu powyższych wymagań, nie nową zgodą na operatora. Ręczny dispatch, pojedyncza próba oraz jednostki symulowanego kosztu opisują obecne laboratorium; nie ustalają stawek, numerów, kanału cichych powiadomień ani zasad aktywacji płatnych usług. Nie dodają wyjątków od D11–D16. Szczegóły kodu i aktualnych granic: [TRANSPORT-TELEFONII.md](TRANSPORT-TELEFONII.md).

## M0.4 — architektura po przyjęciu planu nadrzędnego

[ADR010](adr/0010-master-plan-architecture.md) zachowuje modułowy monolit i istniejący kod; określa etapowe przejście z JS/SQLite do React/TS i osobnego Postgres/Supabase JARVIS. To wdrożenie celu z masterplanu, nie rezygnacja z żadnej funkcji ani zgoda na zmiany produkcji. Obecne adaptery readonly, izolacja klientów i wyłączone skutki zewnętrzne pozostają wymagane.

## M0.5 — zależności i dowody

Graf JARVIS_MASTER_DEPENDENCIES.json doprecyzowuje kolejność implementacji45zadań bez zmiany ich zakresu. Zależności VERIFIED są wymagane przed oznaczeniem następnej funkcji jako VERIFIED; kod/mock nie zamyka bramki realnego sprzętu/operatora. Strategia: TEST-STRATEGY.md; odbiór Windows: WINDOWS-CHECKLIST.md. Zablokowane urządzenie nie wstrzymuje niezależnego backendu/UI. To decyzja implementacyjna, nie nowe uprawnienie do integracji.

## M3.2 — oddzielna rozmowa z odczytami

Kontrolowany tool-calling jest osobnym, domyślnie wyłączonym API właściciela z jawnym wyborem narzędzi i dostawcy. Zachowuje istniejący zwykły czat/voice/parser i nie dołącza automatycznie prywatnej pamięci. Pozwala zweryfikować izolację i protokoły przed szerszymi wieloetapowymi zadaniami M3.5; nie usuwa żadnej pierwotnej funkcji z backlogu. Bieżący zakres to odczyty; zapisy, propozycje zmian i kanał klientów pozostają za własnymi regułami. Kontrakt: [TOOL-CALLING.md](TOOL-CALLING.md).

## M3.3 — odrębna historia kontekstu PostgreSQL

Nowe odpowiedzi wykorzystujące prywatne dane PostgreSQL muszą pozostać w historii PostgreSQL z RLS per konto i zakresem sesji. Wcześniejsza historia/pamięć SQLite nadal jest wspólna dla ownerów; nie importujemy jej i nie zapisujemy w niej takich odpowiedzi. Jawne owner API tworzy sesję tekstową z niezmiennym zakresem/dostawcą i TTL, wybiera notatki po ID/revision i rewaliduje również pochodzenie wcześniejszego kontekstu. To etapowa integracja M3.3, bez przebudowy całego Core i bez podłączenia voice/recepcji/tool-chat. Dotychczasowe funkcje pozostają; GUI nowej pamięci należy do M3.4. Kontrakt: [POSTGRES-CONTEXT.md](POSTGRES-CONTEXT.md).

## 2026-10-27 — zakres i profile M3.4

Właściciel ograniczył kontynuację do końca M3; M4 pozostaje TODO. Profil/revision jest immutable pinem nowej sesji, zmiana źródła daje409 zamiast cichej podmiany. Profile określają styl, nie role/tools. GUI PG jest osobną zakładką od wspólnego SQLite; dane kont nie są łączone. Testy protokołów i browser używają syntetycznych odpowiedzi; jakość inferencji nie jest zaliczana.

## 2026-10-27 — M3.5, zakończenie zakresu M3

Wieloetapowe zadania są jawnym API read-only na istniejącej pętli, nie nowym autonomicznym wykonawcą. Plan1–4etapy pochodzi od właściciela; wspólny limit kosztu, aktualna autoryzacja i cancel przy ostatnimdispatch. RAM-only/jedenworker/TTL900s i brakautoreplay po restarcie są świadomymi ograniczeniami MVP. Nie dołączamy prywatnej pamięci do tego przepływu. CałeM3zakończone; zgodnie z poleceniem właściciela nie rozpoczynamyM4.

## 2026-10-28 — instalator bieżącego M3

Właściciel zlecił instalator do lokalnego obejrzenia interfejsu. Pakujemy obecne M3 jako osobne zadanie dystrybucji, bez M4 i bez zmiany statusów M8. Per-user/offline runtime, localhost-only, osobny katalog danych, lokalny losowy klucz, brak automatycznego uruchamiania i brak aktywacji integracji. Deinstalacja zachowuje dane. Panel pozostaje aplikacją web w domyślnej przeglądarce, launcher zarządza lokalnym procesem.

2026-10-29: HUD jako warstwa React/CSS istniejącego panelu, bez zastępowania autoryzacji. Radar jest nawigacją do stanu Core, nie symulacją skanowania sprzętu. Pakiet Windows 0.10.4.2 zachowuje AppId i dane.
