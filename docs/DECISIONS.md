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

## 2026-10-29 — wznowienie M4 i kolejnych etapów
Aktualizacja 2026-10-29: właściciel zlecił kontynuację M4 i dalszych etapów. To uchyla wcześniejszy STOP po M3; produkcja AutoLogika/Supabase, wydatki, operator i sprzęt pozostają wyłączone.

Adapter pozostaje wyłącznie na dwóch audytowanych GET. Capabilities nie sprawdza sieci i nie zwraca origin/PIN. Odpowiedzi mają limit 2 MiB oraz 12 s całkowitego czasu; niezgodny envelope i obce order_id są odrzucane. Mock służy testom; awaria live nie przełącza się po cichu na DEMO.

## M4.4 — jawny adapter laboratoryjny
Oddzielny namespace write-lab i stan RAM zapobiegają myleniu zatwierdzenia DEMO z zapisem do AutoLogiki. Brak nowych tabel/migracji Core; żadne parametry nie wybierają produkcyjnego adaptera. Live pozostaje BLOCKED, a mock jest dostępny do przetestowania przepływu użytkownika.


## 2026-11-06 — M5.1 ograniczony odczyt
WebSocket Home Assistant jest jednorazowym get_states, bez subskrypcji i usług. Filtrowanie encji i atrybutów odbywa się w Core; nie utożsamiamy go z upstream ACL. Brak rzeczywistego konta z potwierdzonymi uprawnieniami pozostawia live M5.1 BLOCKED. Następne niezależne prace MQTT wyłącznie w izolowanym laboratorium.

## 2026-11-26 — dostęp zdalny przez tunel, 2FA, operator, kamery (0.12.0)

- Zamiast osobnej strony internetowej rozbudowano Control Center JARVIS (właściciel wybrał kontynuację JARVIS‑OS). Strona = panel `/control/` + PWA; logika urządzeń pozostaje w jednym rdzeniu.
- JARVIS nadal słucha na loopback; dostęp z internetu wyłącznie przez tunel uruchomiony na PC (Cloudflare Tunnel lub Tailscale). Polityka po stronie serwera: tunel bez `JARVIS_REMOTE_ACCESS=true` → 403; zdalnie tylko sesje kont otwarte z TOTP; klucz właściciela i tokeny usługowe tylko lokalnie. Rozpoznanie „zdalne” po nagłówkach tunelu lub nielokalnym Host — lokalny proces jest zaufany (jak dotąd).
- TOTP RFC 6238 zaimplementowany bez zależności (hmac/sha1), ochrona przed powtórzeniem przez `last_step`, kody zapasowe tylko jako SHA‑256. Sekret TOTP musi być odwracalny, więc leży w SQLite — ta sama klasa ochrony co plik bazy.
- Rola `operator` (status, brama, komendy głosowe, kamery) zamiast rozszerzania `owner`; czat z modelem i pamięć pozostają właścicielskie. Głos operatora idzie do `/voice/command` (tylko deterministyczny parser).
- Kamery przez go2rtc zamiast własnej obsługi RTSP: hasła kamer zostają w go2rtc.yaml, JARVIS proxuje pojedyncze klatki JPEG (limit 4 MiB, 8 s, allowlista sieci). Płynne wideo (WebRTC) odłożone — wymagałoby przepuszczenia mediów przez tunel.
- Schemat SQLite 13: CHECK ról wymaga przebudowy tabeli `identity_users` (procedura SQLite przy `foreign_keys=OFF` w jednej transakcji, z kopią `before-schema13-*`).

## 2026-11-26 — passkeys (0.14.0)

- Logowanie WebAuthn z wymaganą weryfikacją użytkownika traktujemy jak dwa składniki (posiadanie urządzenia + biometria/PIN), więc sesja ma `mfa=1` i działa zdalnie. Konto z TOTP może dodać klucz tylko w sesji otwartej kodem — hasło samo nie wystarcza do „przeniesienia” konta na nowe urządzenie.
- Biblioteka `webauthn` (Duo Labs) zamiast własnej weryfikacji CBOR/COSE/podpisów. Klucz zapisujemy z rp_id i wymagamy zgodności przy logowaniu (obrona w głąb obok ochrony przeglądarki).
- Origin akceptujemy, gdy to `https://` + nagłówek Host (domena tunelu — Cloudflare kieruje ruch po nazwie hosta, a przeglądarka wiąże klucz z domeną), `http://localhost` lub jawna lista. Klucz z witryny phishingowej nie może zostać użyty dla naszej domeny.

## 2026-11-26 — program desktopowy (0.15.0)

- Okno programu = Edge/Chrome w trybie `--app` z własnym profilem, a nie WebView2 (pywebview) ani Electron. WebView2 nie obsługuje Web Speech API (rozpoznawanie mowy, na którym opiera się widok Głos i ekran Warsztat), a Electron dodałby ~150 MB i drugi runtime. Edge jest częścią Windows 10/11; fallback: domyślna przeglądarka.
- Serwer pozostaje jeden (launcher z oknem „serwer”), więc program i strona (PC, telefon przez tunel) zawsze pokazują te same dane i uprawnienia.

## 2026-11-27 — brama Setti/Tuya lokalnie (0.16.0)

- Sterownik `tuya_local` (tinytuya 1.21.1) steruje bramą w LAN bez chmury, bo wygaśnięcie okresu próbnego IoT Core / wstrzymanie centrum danych zatrzymywało bramę.
- Adres sterownika musi być prywatny (RFC 1918 / ULA; bez loopback, link-local, multicast, publicznych). Ten sterownik **nie** używa `JARVIS_NETWORK_ALLOWLIST` (domyślnie tylko loopback), bo inaczej każdy właściciel musiałby edytować `.env`; walidacja adresu zastępuje allowlistę. Konfiguruje go tylko właściciel.
- Klucz lokalny jest sekretem jak Access Secret: maskowany w odpowiedziach, zachowywany przy zapisie maski. Endpoint `/tuya-local/key` zwraca klucz właścicielowi jednorazowo (żeby wpisał go do formularza i zapisał); audyt zapisuje tylko ID urządzenia.
- Skan LAN to wyłącznie nasłuch broadcastu UDP (`poll=False`) — bez łączenia się z urządzeniami.

## 2026-11-28 — wbudowany go2rtc dla kamer (0.18.0)

- Instalator dołącza go2rtc v1.9.14 (MIT) i FFmpeg LGPL (BtbN, `latest`): pliki pobierane w CI z wydań GitHub i sprawdzane z SHA-256 podanym przez GitHub (`digest`), w `tools\THIRD-PARTY.txt` wersje, sumy i źródła. Build LGPL, bo GPL wymagałby udostępniania źródeł całości; brak libx264 nie przeszkadza (dekodowanie H.264 i kodowanie JPEG są natywne).
- JARVIS (proces serwera) uruchamia go2rtc jako proces potomny na 127.0.0.1:1984 z wyłączonym RTSP; konfiguracja jest generowana jako JSON (poprawny YAML), więc żadne pole z panelu nie może wstrzyknąć innych opcji go2rtc. Restart tylko przy zmianie treści pliku.
- Sekrety (RTSP, client_secret Tuya) są w `go2rtc.yaml` w prywatnym folderze danych — tak samo jak baza SQLite. API zwraca RTSP zamaskowany; zapis maski zachowuje zapisany adres.
- UID dla źródła Tuya Cloud jest odczytywany z `/v1.0/devices/{id}` tego samego projektu co brama (bez osobnych danych logowania). Kamery Setti wymagają aktywnego IoT Core — w przeciwieństwie do bramy lokalnej.
- Tryb `external` (adres własnego go2rtc + nazwy strumieni) zostaje dla istniejących konfiguracji i zaawansowanych; nowe instalacje startują w `builtin`.

## 2026-11-28 — pytania bez rąk: Siri + odpowiedzi z internetu (0.19.0)

- Właściciel wybrał: iPhone w kieszeni + słuchawka, „Hej Siri, Jarvis”, a dane techniczne „niech bierze z internetu”. Odpowiedzi daje Claude API z narzędziem `web_search_20250305` na własnym kluczu właściciela (opcjonalne, wyłączone domyślnie; płatne za użycie po stronie Anthropic). Prompt wymusza: wartość z jednostką i warunkami, nazwę źródła, przyznanie się do rozbieżności, bez zgadywania; odpowiedź zawiera linki źródeł. To nie są dane producenta — opisane w panelu i dokumentacji.
- Siri nie może logować się z 2FA, więc dodano **klucze telefonu** (`identity_device_keys`, schemat 15): tylko dla kont z włączonym 2FA, tworzone z sesji otwartej kodem 2FA, pokazane raz, przechowywane jako SHA-256, zakres wyłącznie `voice:ask` + `gate:control` (także dla właściciela — rola `device` nie ma obejścia `*`), przez tunel tylko `/api/v1/voice/ask` i `/api/v1/devices/gate/command`, unieważniane przy resecie/wyłączeniu 2FA.
- `/voice/ask`: polecenia bramy/potwierdzenia obsługuje lokalny parser (nigdy model), resztę model. Błędy wracają jako zdanie (HTTP 200) dla Siri; limit 15 pytań/min na urządzenie (koszty). Audyt zapisuje długość pytania i liczbę wyszukiwań, nie treść.
- Na pytanie o darmową opcję dodano dostawcę **Groq** (domyślny): `groq/compound` z wbudowanym wyszukiwaniem, darmowy plan bez karty (po limicie błąd 429 → „wyczerpany darmowy limit”, bez opłat). Gemini odrzucony, bo wyszukiwanie Google w API wymaga podpiętej płatności. Konfiguracja zapisana przed Groq z kluczem Claude zostaje przy Claude.
- Wpis zakresu w AGENTS.md zostawiony właścicielowi (plik reguł właściciela).

