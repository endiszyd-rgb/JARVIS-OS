
## M4.1 — adapter AutoLogika (2026-10-29)

Właściciel autoryzował M4 i dalsze etapy. Adapter używa wyłącznie potwierdzonych GET /api/orders i /api/order/{id}; dodano limit odpowiedzi 2 MiB, całkowity deadline12s, kontrolę envelope i powiązania rekordów z order_id. GET /api/v1/autologika/capabilities wymaga workshop:read i pokazuje ograniczenia bez odpytywania usługi lub ujawniania konfiguracji. Audyt lokalnych źródeł: docs/audits/M4-AUTOLOGIKA-SOURCE.md. Brak awaryjnego przełączania live na DEMO.

Testy kontraktów i snapshot:36 PASS; pip check PASS. Produkcyjna AutoLogika/Supabase i realne urządzenia NOT_RUN. Schemat bazy i instalator HUD3 bez zmian; ten commit rozwija źródła backendu.

# Windows delivery 0.10.4 — 2026-10-28

- Samowystarczalny instalator x64, launcher lokalnego panelu i prywatny katalog danych.
- Odrębny test instalacji/reinstalacji/runtime/API/assets/GUI lifecycle/deinstalacji.
- Bez zmian API/migracji; M4 nie rozpoczęto.

## 0.10.4 — M3.5 i koniec M3, 2026-10-27

- Owner-only zadania1–4etapowe odczytu z postępem/cancel, idempotency, limitami i wspólnym budżetem. Aktualna tożsamość/config i cancellation także przy ostatnimdispatch.
- RAM-only/jedenworker/TTL900s, cleanupshutdown, brakautoreplay; wyniki modeli nie nadają uprawnień. Walidacja zadań nie odbija błędnych treści i nie powoduje Unicode500.
-843pytest/75skip,4genuine2-stepkombinacje26POST/12odczytów i cancel,76PG/API/Chromium,nowyDocker/typecheck/build PASS.149UI=M3.4 bezpowtórki. Realna inferencja/Windows/produkcja NOT_RUN.
-20/45VERIFIED, całeM3zakończone. STOP przedM4 zgodnie z właścicielem.

## 0.10.3 — M3.4, 2026-10-27

- Wersjonowane profile jawnie przypięte do sesjiAI, rewalidacja RLS/revision, bez nadawania uprawnień. Migration4 zachowuje wcześniejsze sesje.
- Panel React pamięci/profili: CRUD/history/CAS, potwierdzenie usunięcia, osobny zakres, jawny kontekstAI i cloudzgoda per tura, czyszczenie po401/zmianie konta.
-817pytest/75skip,149UI/typecheck/build,76realnePG/API/Chromium/0skip i nowyDocker PASS. Realna inferencja/Windows/sprzęt/CI NOT_RUN.19/45VERIFIED; następneM3.5, STOP przedM4.

## 0.10.2 — M3.3, 2026-10-26

- Pamięć PostgreSQL/pgvector i prywatne sesje tekstowe z jawnym kontekstem notatek: RLS per konto/zakres, TTL, limity i trwała dzierżawa tury, revision i atomowy audyt.
- Pochodzenie historycznych danych jest rewalidowane; zmiana źródła/revoke/membership/expiry blokuje starą odpowiedź. Brak zapisu prywatnych danychPG do wspólnej historiiSQLite, parsera, narzędzi i autozapamiętywania. Cloud wymaga jawnego potwierdzenia kontekstu w każdej turze.
- Osobna featuremigration2, zachowanie feature1 wektorów zweryfikowane ograniczonym migratorem.810pytest/61skip,62realnePG/API/0skip, genuineCoreTCP/embedding/LLM, nowyDocker/typecheck/buildPASS. Inferencja/GUI/Windows/sprzęt/CI NOT_RUN.18/45VERIFIED, następneM3.4.

## 0.10.1 — M3.2, 2026-10-26

- Osobne opt-in ownerAPI/chat/tools: pełna walidacja listy, wybór zatwierdzonych odczytów, aktualna autoryzacja/konfiguracja, pin schematu, limity i koszt całego przebiegu. Wyniki nie nadają uprawnień; bez pamięci prywatnej i historii tego przebiegu.
- Realne odczyty OpenAPI z query naprawione z zachowaniem origin/DNS/IP; kontrola schematu i sesji również po ostatnim discoveryMCP. Runner4kombinacji lokalnych protokołów dodany doCI.
-767pytest/24skip, typecheck/build, rzeczywistyTCP Core/LLM/OpenAPI/MCP SDK i nowyDockerPASS. Bez nowego GUI, inferencji, produkcji i aktywacji urządzeń.17/45VERIFIED; następneM3.3.

## 0.10.0 — M3.1, 2026-10-26

- Wspólny kontrakt i adaptery Ollama/OpenAI, integracja katalogu/sesji/czatu/ustawień i GUI, kontekst chmurowy jawnie oznaczony.
- Konfiguracja opt-in/SecretStr/cenyUSD i limit przed I/O, pełny kontekst jako granica kosztu, bounded I/O/no retries/no tools; usage bez udawania faktury.
-710pytest/24skip,141UI/typecheck/build, realny localhostHTTP/Chromium390px i nowyDocker/Compose PASS. Prawdziwe konto/inferencja/Windows/sprzęt/CI NOT_RUN.
-16/45 VERIFIED w zakresie implementacji/protokołów; następneM3.2.

## 0.9.4 — M2.5, 2026-10-26

- Wspólny przegląd propozycji z osobnymi decyzjami i rollback. Code→review_required bez wykonania; preflight bezCAS, brakautoretry.
- Fokus potwierdzenia/wyniku/anulowania, poprawka menu mobilnego; Chromium struktura16widoków i klawiatura390px PASS.
-139UI/typecheck/build,662pytest/24skip i nowyDocker/Compose PASS. PełnyWCAG/czytnik/Safari/Windows/sprzęt NOT_RUN.
-15/45 VERIFIED; następneM3.1.

## 0.9.3 — M2.4, 2026-10-26

- Dziewięć widoków modułów React i przewijana nawigacja; role home/workshop reader, owner-only dane prywatne.
- CRUD/polityka pamięci, zatwierdzane przypomnienia, lokalne powiadomienia, telefonia z rewizją i konta/sesje/tokeny.
-128UI i662pytest/24skip PASS, typecheck/build, actualChromium9widoków390px i Docker/Compose PASS. Usługi właściciela/sprzęt/Windows NOT_RUN.
-14/45 VERIFIED; następneM2.5.

## 0.9.2 — M2.3, 2026-10-25

- React Plugin Manager: status, manifesty, pełna konfiguracja, lokalne zatwierdzenia, enable/disable i jawny odczyt testowy. Brak ukrytych wywołań, sekret wyłącznie jako nazwaenv.
- PUT i40s dla discovery/invoke, ownergate i prywatny lifecycle. Konfiguracja wyłącza plugin; lokalny katalog nie udaje testu połączenia.
-662pytest/24skip,60UI/typecheck/build, rzeczywistyChromium/Core/localhostHTTP i nowyDocker/Compose PASS. Usługiwłaściciela/Windows/sprzęt/CI NOT_RUN.
-13/45 VERIFIED; oba plany/README/kod wtym samymcommicie, następneM2.4.

## 0.9.1 — M2.2, 2026-10-25

- React: rozmowy/sesje i wybór modelu, ustawienia z podglądem i osobnym zatwierdzeniem, historia ostatnich100zdarzeń. Ownergate, escapedtext,401/logoutcleanup; legacy15widoków zachowane.
- Chat95s, przerwanie oczekiwania wymaga synchronizacji; poprawiono powtórny wybórsesji i zmianę tożsamości. Settingspreflight niejest atomowym CAS.
-662pytest PASS/24skip,40UI/typecheck/build, rzeczywistyChromiumDEMO390px i nowyDocker/Compose PASS. Realnemodele/Windows/sprzęt/CI NOT_RUN.
-12/45 VERIFIED, następneM2.3. README i obaplany wtym samymcommicie.

## 0.9.0 — M2.1, 2026-10-24

- React/TypeScript Control Center pod /control/: login kontem/kluczem, rzeczywisty pulpit/System, responsive390px i nawigacja klawiaturowa. Legacy15widoków zachowane pod /.
- Bezpieczne assets/CSP, token tylko w pamięci, logoutserver/401/abort; DockerbudujeUI i sprawdzaHTML/JS/CSS, notice i lockfile zachowane.
-662pytest PASS/24skip,10komponentów/typecheck/build i actualChromium auth/privacy/roles/CSP/mobile PASS; nowyDocker/Compose PASS. Windows/urządzenia/produkcja/CI NOT_RUN.
-11/45 VERIFIED, oba plany/README i kod razem; następneM2.2.

## 0.8.8 — M1.5, 2026-10-24

- Wspólny rejestr i gateway DEMO/OpenAPI/MCP, wersjonowany katalog bez I/O i zachowany invoke; scope i lokalne zatwierdzenia.
- Schematy/argumenty/odpowiedzi i wykonanie ograniczone; timeout/cancel/capacity, audyt bez treści, zgodność starszej konfiguracji z bezpiecznym422.
-657pytest PASS/24skip, w tym realny localhostSDKlab; pipcheck/app.js/newDockerCompose PASS. PostgreSQL i Chromium nie powtarzano; produkcja/Windows/sprzęt/CI NOT_RUN.
-10/45 VERIFIED; oba dzienniki i README wraz z kodem, następne M2.1.

## 0.8.7 — M1.4, 2026-10-24

- Osobny opt-in PostgreSQL z migracją1, SHA256, blokadą, FORCE RLS i minimalnymi grantami; Core pozostaje SQLite12.
- Ograniczony runtime, transakcyjne claims, CRUD z rewizjami i atomowym audytem; API właścicielskie i wyraźny disabled.
-573pytest PASS/24skip bez PG; osobno25realPG PASS/0skip z migratorem bez superuser, restartem i cleanup. Pip check/app.js syntax i nowy LinuxDocker/Compose PASS. Supabase/Windows/sprzęt/CI NOT_RUN.
- Dokumentacja, oba plany i README razem z kodem; następne M1.5.

## 0.8.6 — M1.3, 2026-10-23

- Konta/role PBKDF2-SHA256, sesje TTL z hashowanym tokenem, odwołanie i rewizje; migracja11→12 z backupem.
- Wspólne limity obu API, osobny loginlimit, jawny CORS, actor i odmowy w audycie; uruchomienia Uvicorn bez zaufania do proxyheaders.
-453pytest, pip check, JS/Chromium syntetyczny i nowy LinuxDocker/Compose PASS. Windows/produkcja/sprzęt/realne modele/CI NOT_RUN. Brak SSO/resetu/UIlogowania; limity perproces.
- Oba plany, README i dokumentacja w tym samym commicie; następne M1.4.

## 0.8.5 — M1.2, 2026-10-23

- Dockerhealthcheck bada gotowość, Compose przekazuje zwalidowany timeout; opcjonalny publicznyCA przez BuildKitsecret bez warstw obrazu.
- Izolowany Compose smoke z wyłączonymi integracjami, osobnym wolumenem i ponownym odczytem dynamicznego portu po restarcie; build/auth/persistence/413/non-root/healthy/cleanup PASS.
- Instrukcja Windows11/WSL2 i osobny jobCI; natywne Windows/WSL2 i wykonanie GitHubCI NOT_RUN.353pytest pozostaje wynikiem M1.1, backend bez nowych zmian.

## 0.8.5 — 2026-10-23, M1.1

- Kanoniczne /api/v1 i zgodny /api z jednego routera, wszystkie moduły i wspólne stany/uprawnienia; zachowane limity JSON/WAV i podpisany webhook.
- Osobny /ready, walidowana konfiguracja środowiska Core, maskowany klucz i ograniczony odczyt lokalnej bazy; schema11 bez migracji.
-353testy Python, pip check, JS oraz regresja Chromium głosu/transportu PASS. Realne modele, sprzęt, Windows i Docker NOT_RUN.
- Plan/dziennik TXT/MD i README w tym samym commicie; następne M1.2.

## 0.8.4 — 2026-10-22, R04 transport laboratoryjny i panel

- Ścisły interfejs adaptera, osobne kanały i token klienta; trwałe zdarzenia/outbox i atomowość z recepcją, schema10→11 z backupem.
- Prywatna oferta, zgoda na bieżącą próbę, osobne dostarczenie mostu i ponowne sprawdzenie polityki; limity serwerowe, timeout/odmowa/awaria bez ponawiania.
- Nowy panel transportu, sprzątanie tokenu/stanu, usuwanie zakończonych testów i poprawka układu 390px/statusu listy.
- 276 pytest, pip check, składnia JS, 6 sprawdzeń panelu, pełna ścieżka Chromium z syntetycznymi danymi i regresja syntetycznego głosu. Setup/CI obejmują nowy panel; GitHub CI nie wykonano.
- Laboratorium tekstowe i zamknięte frazy testowe, ręczny dispatch i terminy przy odczycie/zdarzeniu. Bez operatora, PSTN/SIP, audio telefonicznego i realnej inferencji. README zaktualizowane w tym samym commicie.

## 0.8.3 — 2026-10-22, R03 ręczna rozmowa półdupleksowa

- AudioWorklet/PCM WAV i ograniczona segmentacja energii; STT→domyślny review→osobny czat voice→TTS, powrót do słuchania i komenda końca.
- Backend blokuje parsery i pamięć dla voice; schematu 9→10 oddziela historie z backupem i testem.
- Poprawki timerów natywnych z testu Chromium i wyścigów cancel/start; pełne sprzątanie zasobów.
- 229 testów Python; 12 + 10 + 18 kontrolowanych sprawdzeń audio JS; Chromium z syntetycznym mikrofonem i usługami: dwie tury, korekta, TTS, koniec, tracki/konteksty zamknięte.
- Realne modele/sprzęt, hałas, wake-word, pełny dupleks i prywatne wyjście nadal oczekujące. README zaktualizowane w tym samym commicie.

## 0.8.2 — 2026-10-22, R02 ograniczona pamięć / R03 laboratorium mikrofonu

- Zamknięte deklaracje pamięci pl-declarations-v1; domyślnie manual. Atomowy capture, źródła sesji/tury, opt-out, deduplikacja, jawna aktualizacja i ochrona ręcznych korekt.
- Migracja 8→9 z backupem i testem; wykrywanie zmian podczas odpowiedzi i pełny rollback.
- Sesje audio i ręczny kontroler mikrofonu z timeoutem, anulowaniem, sprzątaniem i testami zegara. Nie podłączono ciągłego STT/TTS ani wykrywania mowy/wake-word.
- 213 testów Python, 10 kontrolowanych testów JS audio oraz testy DOM/API. Realny sprzęt, przeglądarka i inferencja niesprawdzone.

## 0.8.1 — 2026-10-22, R02 część 1

- Osobna polityka pamięci, pochodzenie wpisów, korekty z rewizją i historią, jawna retencja i panel.
- Migracja schematu 7→8 z kopią. Blokada zapisu obejmuje ręczny czat i API.
- 8 nowych testów pamięci, łącznie 164. Kontrolowany DOM/API; brak testu rzeczywistej przeglądarki.
- Automatyczna ekstrakcja, wykluczenia podczas ekstrakcji i deduplikacja pozostają do wykonania.
- Pakowanie regeneruje manifest zamiast pakować stary manifest do jego własnej listy sum.

## 2026-10-22 — R01

- Import zweryfikowanego przekazania i 147 bazowych testów.
- Wersjonowane 30 syntetycznych rozmów PL, CLI ewaluacji, raport JSON/Markdown, odrębne błędy środowiska i jakości.
- 9 nowych testów przez kontrolowany HTTP; razem 156. Jakość rzeczywistego modelu niesprawdzona.

# Zmiany

## 0.8-handoff.1 — 22.10.2026

- Płaski ZIP z instrukcją startową, gotowym poleceniem, maszynowym statusem11obszarów, zatwierdzonymi decyzjami i kolejką z kryteriami odbioru.
- Powtarzalne pakowanie wyłącznie śledzonych plików i weryfikacja SHA256 dostarczonego źródła.
- Brak zmian zachowania aplikacji, wersja0.8.0/schema7. Bazowe147testów.

## 0.8.0 — 22.10.2026

- Opcjonalna analiza recepcji Ollama JSON Schema: pochodzenie cytatów/faktów, niepewność, granice uprawnień i kontrola rewizji.
- Panel analizy, model na allowliście, brak automatycznego przechodzenia do heurystyki przy awarii.
- Pakiet przekazania do Codex Cloud: AGENTS.md, dokument stanu i skrypt setup/checks.
- 147 testów, lokalny test HTTP i DOM; brak rzeczywistej inferencji i aktywowanej telefonii. Schemat bazy nadal7.

## 0.7.0 — 22.10.2026

- Laboratorium recepcji, stany rozmowy, oddzielne podsumowanie właściciela i zgłoszenia.
- Ponowna ocena dostępności przed akceptacją, obsługa odmowy i braku odpowiedzi, idempotencja i transakcje.
- Osobny panel, migracja Core 7, usuwanie danych rozmowy i 127 testów. Bez operatora, połączeń i klasyfikacji AI.

## 0.6.0 — 22.10.2026

- Panel Telefonia i API właściciela: tygodniowy grafik, urlop/wyjątki, DND, numery i podgląd eskalacji bez operatora.
- Europe/Warsaw z fallbackiem tzdata, rewizje ustawień, migracja do schematu 6 z backupem.
- 112 testów i test DOM z działającym Core; brak rzeczywistych rozmów.

## 0.5.0 — 22.10.2026

- Wyoming STT/TTS przez jawne pliki, lokalny FTS5 i opcjonalna pamięć hybrydowa przez Ollama.
- Przegląd repozytoriów i licencji, limity ciał HTTP i zdarzeń audio, schemat 5.
- 93 testy; rzeczywiste silniki i Windows nadal wymagają sprawdzenia.

## 0.4.0 — 22.10.2026

- Trwałe sesje i wiadomości, tytuły, eksport JSON, usuwanie kaskadowe oraz podgląd/aplikacja ręcznej retencji.
- Katalog nazw modeli z listy właściciela, faktyczny wybór modelu per sesja i respektowanie domyślnego dostawcy; brak automatycznego pobierania modeli.
- Ograniczony kontekst udanych wiadomości bieżącej sesji, blokada równoległych tur, zapis niepowodzeń i odzyskanie starej blokady.
- Most tylko do odczytu 8 domen z jawnie przygotowanej kopii schematu AutoLogiki 18; spójny import SQLite backup API, manifest i SHA-256, bez zmian repozytorium AutoLogiki.
- Raporty i finanse z kopii mogą być jawnie dołączone do rozmowy; bez automatycznego przekazywania list klientów.
- Zakładka AutoLogika · kopia, rozwinięty panel rozmów, syntetyczna baza warsztatu do testów i kopia przed migracją Core do schematu 4.
- 83 testy pytest oraz test zachowania nowych widoków DOM.

## 0.3.0 — 22.10.2026

- Transport MCP Streamable HTTP przez oficjalny Python SDK 1.30: inicjalizacja sesji, lista narzędzi i wywołania jawnie zatwierdzonych odczytów. Bez stdio i uruchamiania procesów pluginów.
- Ograniczony importer OpenAPI 3.x: GET, operationId, skalarne parametry path/query i walidacja; bez zewnętrznych referencji, requestBody, zapisów i automatycznego pobierania specyfikacji.
- Konfiguracja pluginów w panelu, sekrety wskazywane nazwą zmiennej .env. Zmiana konfiguracji wyłącza plugin do ponownego włączenia.
- Kontrola sieci: jawne zakresy IP, rozwiązywanie DNS z przypięciem IP, kontrola Host/SNI, blokada przekierowań oraz limit odpowiedzi.
- Ograniczone tokeny z terminem ważności i cofnięciem; sekret pokazywany tylko raz, w bazie SHA-256. Scheduler nie wymaga klucza właściciela.
- Czytnik Home Assistant: allowlista encji, tylko stany, bez usług sterujących.
- Twilio/WhatsApp: podpisany webhook, dokładny publiczny adres HTTPS, allowlista nadawców i konta, deduplikacja także po usunięciu wiadomości, inbox i niewysyłane szkice.
- Zakładki Dom, WhatsApp i Dostęp; laboratorium integracyjne bez kont; nieaktywny szablon workflow n8n; lock zależności i automatyczna kopia przed rozszerzeniem schematu 0.2 → 0.3.
- Testy obejmują pełną ścieżkę Core → osobny proces serwera MCP/OpenAPI na localhost.

## 0.2.0

Pierwszy Core i panel, audyt AutoLogiki, rzeczywisty adapter GET zleceń, DEMO integracji, pamięć/Ollama, propozycje i rollback, scheduler, backup oraz 36 testów. Raport historyczny: docs/history/RAPORT-v0.2.md.

## JARVIS HUD — 2026-10-29

Nowy cyjanowy interfejs: pulpit z animowanym rdzeniem prowadzącym do Systemu, telemetria z API, skrót rozmowy dla właściciela, motyw logowania i paneli. Animacje wyłączają się przy prefers-reduced-motion. Role i dotychczasowe funkcje zachowane; M4 nie rozpoczęto.

Wykonano: 149 testów UI PASS, TypeScript/build PASS, node --check jarvis/app.js PASS. Rzeczywisty Chrome + izolowany Core: logowanie, role, wylogowanie/unieważnienie, brak sekretów w storage/URL, CSP, klawiatura, radar i reduced-motion PASS; 390px bez overflow. Obejrzano zrzuty desktop/mobile. Backend bez zmian, pełnej regresji backendu nie powtarzano.

Instalator HUD: wydanie v0.10.4-windows.2, wersja pakietu 0.10.4.2 (Core nadal 0.10.4). Niepodpisany; modele i integracje nie są aktywowane.

## HUD 3 — spójny panel rozmów (2026-10-29)

Poprawiono cyjanowe zaznaczenie aktywnej trasy (aria-current), wybranej rozmowy, wiadomości i pól formularza. Zachowano kolory ostrzeżeń i błędów. Rozszerzono scripts/check_control_browser.cjs o rzeczywiste utworzenie sesji DEMO, wysłanie wiadomości i odczyt odpowiedzi oraz układ czatu przy 390px.

Wykonano: TypeScript/build PASS; node --check jarvis/app.js i check_control_browser.cjs PASS; Chrome z tymczasowym Core PASS (25 żądań API, auth/role/CSP/klawiatura/radar/reduced-motion/rozmowa/390px). Obejrzano docs/evals/control-hud-chat.png i control-hud-chat-mobile.png. Zmiana CSS nie zmienia backendu; 149 testów UI z poprzedniej dostawy nie powtarzano. M4 nie rozpoczęto.

Pakiet Windows 0.10.4.3 (Core 0.10.4): v0.10.4-windows.3. Instalacja na istniejącej kopii użytkownika NOT_RUN; dane i rejestracja pozostają nietknięte.
