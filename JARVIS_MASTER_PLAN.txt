# JARVIS OS — MASTER PLAN I DZIENNIK POSTĘPU

> **Jedno źródło prawdy dla Codex / Work.** Aktualny stan jest zapisywany identycznie w `JARVIS_MASTER_PLAN.txt` i `JARVIS_MASTER_PLAN.md`; źródło planu: commit `a8b5ee8`. Ten plik jest jednocześnie specyfikacją, checklistą, raportem i dziennikiem realizacji. Aktualizuj go W TYM SAMYM COMMICIE co kod. Nie usuwaj zadań, nie fałszuj wyników testów i nie deklaruj ukończenia na podstawie samej dokumentacji.

## Projekt i cel

Repozytorium referencyjne AutoLogika OS: https://github.com/endiszyd-rgb/Autologika-OS. Twórz **osobny** JARVIS OS; nie modyfikuj produkcyjnej AutoLogiki, Supabase ani fizycznych urządzeń bez osobnego zatwierdzenia. Docelowo Windows 11 + Docker/WSL2, panel iPhone/Android, FastAPI, React/TS, Supabase/Postgres, Home Assistant, MQTT/ESP32, n8n, Twilio WhatsApp i modularny system pluginów MCP/OpenAPI. Preferuj modułowy monolit, niski koszt, gotowe biblioteki i izolację integracji.

Wszystkie funkcje są w zakresie: AI tekst/głos, pamięć i edycja pamięci, zmiana modeli i instrukcji, samodzielna konfiguracja i automatyzacje, pluginy, AutoLogika (terminarz, zlecenia, klienci, pojazdy, diagnostyka, części, wyceny, QC, finanse), dom/światła/brama/czujniki, Twilio WhatsApp wiadomości/głosówki/Calling (jeśli kwalifikacja), obsługa klientów i pilne przekazywanie połączeń, godziny dostępności, Windows/iPhone/Android, bezpieczeństwo, kopie i aktualizacje.

## Nienegocjowalne reguły agenta

1. **Na początku KAŻDEJ sesji** przeczytaj cały ten plik i `AGENTS.md` (jeśli istnieje), sprawdź git status i istniejący kod; rozpocznij od pierwszego zadania TODO/BLOCKED możliwego do wykonania. Nie powtarzaj wykonanej pracy.
2. **Przed każdym zadaniem** ustaw status `IN_PROGRESS`, wpisz datę UTC, plan implementacji i kryterium akceptacji. Zapisz plik.
3. **Po każdym zadaniu** zaktualizuj status, konkretny rezultat, ścieżki plików, komendy i wyniki testów, commit/hash (jeśli jest), ryzyka i następny krok. Aktualizuj ten sam plik w tym samym commicie. Zapisuj prawdziwe wyniki: `NOT_RUN`, `PASS`, `FAIL`.
4. Statusy: `TODO` = nierozpoczęte, `IN_PROGRESS` = w trakcie, `BLOCKED` = zależność, `DONE` = implementacja bez pełnej weryfikacji, `VERIFIED` = kod + odpowiednie testy i kryteria akceptacji spełnione. Symulator nigdy nie dowodzi działania sprzętu.
5. **Nie zatrzymuj się po napisaniu planu.** Realizuj kolejny bezpieczny punkt, testuj i kontynuuj aż do ograniczeń środowiska. Nie pytaj o zgodę na rutynowe, odwracalne prace lokalne.
6. Wymagaj osobnej zgody na: wydatki, produkcyjne zmiany, publikację sekretów, wdrożenie, dostęp do cudzych danych, realne sterowanie bramą, modyfikacje repo AutoLogika.
7. Sekrety tylko w `.env`/menedżerze sekretów, nigdy w Git. RLS i minimalne uprawnienia. WhatsApp/caller ID nie autoryzuje otwarcia bramy; użyj potwierdzenia w zaufanej aplikacji i fizycznych zabezpieczeń.
8. Nie wymyślaj istniejących endpointów AutoLogiki ani funkcji Twilio. Gdy usługa niedostępna, dodaj adapter/mock, testy i oznacz `BLOCKED` dla realnej integracji.
9. Jeśli zmieniasz zakres lub architekturę, dopisz uzasadnienie do `docs/DECISIONS.md` i zachowaj wszystkie pierwotne funkcje w backlogu.
10. Na koniec każdej sesji odśwież **Snapshot**, **Dziennik**, **Blokady** i **Następny krok**. Użytkownik powinien móc otworzyć TYLKO TEN PLIK i zrozumieć postęp.

## Snapshot (aktualizuj po każdej sesji)

- Data ostatniej aktualizacji: 2026-10-28T14:58:29+00:00
- Bieżący etap: M3 — ukończony; STOP przed M4
- Aktualne zadanie: dostawa instalatora Windows VERIFIED; M3 ukończone, M4 nie rozpoczęto
- Zadania VERIFIED: 20 / 45
- Zadania DONE: 0 / 45
- Ostatni commit źródeł: 8cf20683525bdaeb20192e604d2cf881ce4afb1f, potwierdzony na origin/main; bieżący commit zapisuje zamknięcie B5
- Testy: 28.10 Windows PASS843pytest/75skip220.45s,149UI/typecheck/build, task HTTP/MCP, pip/JS/plan. PG76/Chromium/Docker to historyczne wyniki 27.10, bez powtórki lokalnie.
- Co działa rzeczywiście: Core0.10.4/SQLite12/PGfoundation1/memoryfeature4: pamięć/profile/GUI i bounded wieloetapowe zadania read-only z anulowaniem; M3.1–M3.5 VERIFIED
- Co działa tylko jako mock/demo: odpowiedzi modeli w testach protokołów i embeddingów są syntetyczne; MQTT/n8n/Twilio mają adaptery DEMO; telefonia działa jako laboratorium bez operatora; brak fizycznego sterowania.
- Następny krok: zainstalować JARVIS OS i ocenić panel lokalny. Integracje M4+ wymagają osobnego polecenia; nie rozpoczęto ich w ramach instalatora.

### Potwierdzone wyniki i granice bieżącego stanu

| Obszar | Stan i dowód |
|---|---|
| M3.1 — dostawcy LLM | VERIFIED, commit aa3f44a. Ollama/OpenAI i koszty; realna płatna inferencja NOT_RUN. |
| M3.2 — tool-calling | VERIFIED, commit 08f8b91. Serwerowa autoryzacja, schematy i limity; docs/evals/tool-chat-m32.json. Zwykły czat i voice nie uruchamiają narzędzi. |
| M3.3 — pamięć PostgreSQL | VERIFIED. Feature2: długotrwała pamięć PG/pgvector i account-private krótkie sesje z jawnym kontekstem AI, TTL/lease/sourcevalidation; commit e220662. GUI/instrukcje/profile ukończone w M3.4. |
| M3.4 — historia i profile | VERIFIED, commit377cdbf. Feature4, pinned profile/revision, RLS przedLLM/zapisem, panel CRUD/history/AI i actualChromium. |
| M3.5 — etapy i przerwania | VERIFIED. Owner-private RAMtasks1–4etapy, currentauth/cancel przydispatch, UUIDidempotency i budżet całego zadania; docs/evals/ai-tasks-m35.json. |
| Ostatnia regresja backendu | PASS843pytest/75skip128.17s; pipcheck/JSsyntax. Skip nie jest zaliczeniem PG. |
| Izolowany PostgreSQL i embedding | PASS76/0skip w --memory --browser po integracji M3.5; evals/postgres-m35.json. Rzeczywisty PG/Core/Chromium/HTTP, syntetyczne odpowiedzi modeli i wektory. |
| Docker Core | PASS nowy M3.5 build/Compose/assets/auth/persistence/limits/non-root/cleanup; docs/evals/docker-m35.json. |
| Interfejs | PASS149UI/typecheck/build, actualChromium390px+desktop nowego panelu PG; docs/evals/control-m34-mobile.png i desktop.png. |
| GitHub | PASS push origin/main i zgodność ls-remote/HEAD: 8cf20683525bdaeb20192e604d2cf881ce4afb1f. Snapshot 5aba06c zaimportowany na zachowaną historię a8b5ee8; lokalna historia źródłowa nie była w ZIP. B5 CLOSED; local_commits_pushed=true. |
| Produkcja i urządzenia | AutoLogika/Supabase bez zmian. Windows/WSL2, telefony, sprzęt, operator i wykonanie GitHub CI NOT_RUN. |

## Procedura wykonania pojedynczego zadania

1. Sprawdź zależności, odczytaj odpowiednie źródła i ustal kryteria akceptacji.
2. Zmień status poniżej na `IN_PROGRESS`; zapisz.
3. Implementuj najmniejszy testowalny fragment; dodaj testy i dokumentację.
4. Uruchom testy, lint/typecheck/build właściwe dla fragmentu. Zanotuj dokładne komendy i wynik.
5. Jeśli testy przejdą, ustaw `VERIFIED`; jeśli nie da się przetestować — `DONE` lub `BLOCKED` z przyczyną.
6. Uaktualnij Snapshot, Dziennik, Blokady i Następny krok, wykonaj commit, przejdź dalej.

## Zadania (każde ma osobny status i notatki)

### M0 — Audyt i przygotowanie

#### M0.1 — Przeczytaj ten plik, AGENTS.md, istniejący starter i dokumentację; ustal stan rzeczywisty.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-22T19:35:21+00:00
- **Kryterium akceptacji:** Odczytano pełny plan i kod; raport rozróżnia faktyczne funkcje, symulacje i braki; bazowe testy i kontrole zależności przechodzą.
- **Plan implementacji:** odczyt instrukcji i kodu, audyt modułów i braków wobec M0–M8, uruchomienie istniejących testów oraz utrwalenie dowodów.
- **Wykonano / dowody (pliki, commit):** Potwierdzony audyt istniejącego Core0.8.4/schema11 i luk wobec M0–M8: docs/audits/M0-1-CURRENT-STATE.md. Pobrano plan z a8b5ee8, połączono historię origin z lokalnym kodem, zsynchronizowano TXT/MD; AGENTS.md, 00_START_HERE.md, README.md, PROJECT_STATUS.json, docs/NEXT_TASKS.md. Dawny wpis blokady zachowano w docs/history/JARVIS_MASTER_PLAN-before-import.md. Commit: bieżący wpis M0.1 w Git.
- **Testy (komenda, wynik):** PASS .venv/bin/python -m pytest -q:276 (22.40s); PASS pip check; PASS node --check 7plików i 8 skryptów check_* UI; NOT_RUN nowy browser/Windows/Docker/model/hardware.
- **Blokady / dalsze kroki:** brak; następne: M0.2

#### M0.2 — Zbadaj repozytorium AutoLogika-OS: struktura, backend, Supabase, auth, RLS, migracje, API, modele i testy. Bez zmian produkcyjnych.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-22T19:40:43+00:00
- **Plan implementacji:** Ponowny odczyt publicznego AutoLogika-OS, przypięcie HEAD, weryfikacja hashy źródeł i audyt auth/RLS/migracji/API/modeli/testów bez wykonania aplikacji i zmian produkcyjnych.
- **Kryterium akceptacji:** Raport audytu z aktualnym commitem, źródłami i SHA-256, rozróżnieniem zadeklarowanych testów od uruchomionych oraz granicami dostępu.
- **Wykonano / dowody (pliki, commit):** Ponowny statyczny audyt publicznego HEAD681f7f5;8/8 starych i9 dodatkowych hashy, schema18,57 nazw tabel,262 IPC,52pliki testowe. Raport docs/audits/M0-2-AUTOLOGIKA.md, dowody docs/audits/M0-2-evidence.json; korekta opisu importu w audycieM0.1. Bez instalacji/wykonania AutoLogiki,SQL,Supabase. Commit: bieżący M0.2.
- **Testy (komenda, wynik):** PASS git ls-remote HEAD; PASS SHA25617plików; PASS JSON i git diff --check. NOT_RUN testy/aplikacja/upstream/RLS na produkcji.
- **Blokady / dalsze kroki:** brak; następne: M0.3

#### M0.3 — Udokumentuj potwierdzone interfejsy i braki; nie wymyślaj tabel ani endpointów.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-22T19:41:43+00:00
- **Plan implementacji:** Spisać potwierdzone kontrakty HTTP/IPC/snapshot/Supabase i mapowanie8domen; sprawdzić istniejące testy readonly i snapshot.
- **Kryterium akceptacji:** Kontrakt rozróżnia istniejące interfejsy, nasz adapter i braki; operacje mają źródła/zakres; testy readonly i snapshot przechodzą.
- **Wykonano / dowody (pliki, commit):** Kontrakt docs/contracts/AUTOLOGIKA.md i autologika-http.json:9 źródłowych tras, tylko2GET w adapterze, zakresy HTTP/IPC/snapshot/Supabase, mapowanie8domen i braki diagnostyki/QC/zapisów. Bez wymyślania tabel/endpoints i zmian upstream. Commit: bieżący M0.3.
- **Testy (komenda, wynik):** PASS pytest tests/test_autologika.py tests/test_workshop.py:22 (1.41s), syntetyczne HTTP/SQLite; PASS JSON i git diff --check; NOT_RUN produkcja/RLS.
- **Blokady / dalsze kroki:** brak; następne: M0.4

#### M0.4 — Utwórz osobne monorepo JARVIS OS i ADR dotyczące architektury, bezpieczeństwa i kosztów.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-22T19:42:39+00:00
- **Plan implementacji:** Potwierdzić osobne repo JARVIS, uzupełnić ADR o przyjęcie masterplanu, modułowy monolit, przejścieReact/TS i Postgres oraz granice bezpieczeństwa/kosztów bez utraty istniejących funkcji.
- **Kryterium akceptacji:** JARVIS jest osobnym repo; ADR wskazuje stan obecny i docelowy, migrację etapową, bezpieczeństwo i koszty; wszystkie45zadań pozostają w planie.
- **Wykonano / dowody (pliki, commit):** Potwierdzono osobny monorepoJARVIS i istniejące moduły; dodano docs/adr/0010-master-plan-architecture.md oraz aktualizacje docs/DECISIONS.md, docs/ARCHITEKTURA.md. Etapowa migracjaReact/TS i Postgres, izolacja integracji, bezpieczeństwo i koszty; zachowano45zadań. Commit: bieżący M0.4.
- **Testy (komenda, wynik):** PASS git root/remote i obecność modułów; PASS45ID i zgodnośćTXT/MD; PASS git diff --check. NOT_RUN nowe testy runtime, brak zmian kodu.
- **Blokady / dalsze kroki:** brak; następne: M0.5

#### M0.5 — Ustal zależności i priorytety; przygotuj Windows checklist i strategię testów.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-22T19:46:34+00:00
- **Plan implementacji:** Dostarczyć jawny graf45zależności, kontrolę zgodności statusów/TXT/MD i wybór następnego zadania; Windows11/WSL2 checklist i strategię testów. Zintegrować sprawdzenie zCI.
- **Kryterium akceptacji:** Graf ma45znanychID i brak cykli; walidator wykrywa błędne statusy/kopie i niedotrzymane zależności; strategia rozróżnia lokalne testy, kontenery i urządzenia NOT_RUN.
- **Wykonano / dowody (pliki, commit):** Graf45zadań JARVIS_MASTER_DEPENDENCIES.json i walidator scripts/check_master_plan.py z25testami tests/test_master_plan.py; docs/TEST-STRATEGY.md i docs/WINDOWS-CHECKLIST.md; reguły w docs/DECISIONS.md, CI i cloud_setup.py. Zachowano45oryginalnych definicji, brak cykli, wybór następnego M1.1. Commit: bieżący M0.5.
- **Testy (komenda, wynik):** PASS pytest -q:301 (23.95s), w tym25testów walidatora; PASS pip check; PASS python3 scripts/check_master_plan.py; PASS zachowane45nagłówków i git diff --check. NOT_RUN Windows/WSL2/sprzęt; Dockerdaemon dostępny, build nieuruchomiony.
- **Blokady / dalsze kroki:** brak; następne: M1.1

### M1 — Fundament backendu

#### M1.1 — FastAPI, wersjonowane REST API, health/readiness, konfiguracja .env i walidacja.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-23T05:31:52+00:00
- **Plan implementacji:** Dodać kanoniczne /api/v1 z kompatybilnym /api, zachować auth/bodylimity/webooki, osobne readiness i walidowaną konfigurację env; testy kontraktowe i regresja.
- **Kryterium akceptacji:** Wersjonowane i stare trasy zachowują te same zabezpieczenia/stany; readiness bada konfigurację i bazę bez ujawniania sekretów, health jest niezależne; błędna konfiguracja odrzucana; pełna regresja przechodzi.
- **Wykonano / dowody (pliki, commit):** Core0.8.5: wspólny APIRouter/api/v1 i/api w jarvis/main.py; montowane audio_sessions.py/memory_policy.py/telephony_transport.py zachowują zgodność i wspólne magazyny; body_limit.py oba prefiksy. runtime_config.py: env/SecretStr/read-only readiness. Testy test_api_versioning.py(14) i test_runtime_config.py(38), .env.example, docs/API.md, RAPORT/handoff/status/start/README/CHANGELOG. Schema11 bez migracji. Commit: bieżący M1.1.
- **Testy (komenda, wynik):** PASS .venv/bin/python -m pytest -q:353 (45.67s); PASS pip check, node --check i kontrolowaneJS; PASS Chromium transport13żądań/390px i voice2tury/zasoby zamknięte. NOT_RUN prawdziwe modele/Windows/Docker/sprzęt/CI.
- **Blokady / dalsze kroki:** brak; następne: M1.2

#### M1.2 — Docker Compose i instrukcje Windows 11/WSL2, bez wymagania komputera do budowania w chmurze.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-23T05:44:38+00:00
- **Plan implementacji:** Zbudować rzeczywisty obrazCore z zaufanymCA przez BuildKitsecret, uruchomić izolowany Compose z syntetycznym kluczem/wolumenem i sprawdzić ready/auth/API/restart. Uzupełnić Windows11/WSL2 i wyraźneNOT_RUN urządzeń.
- **Kryterium akceptacji:** Dockerbuild i izolowany Composeup przechodzą; proces nie-root, gotowość zdrowa, auth/bodylimity działają, dane przetrwają restart, sprzątane tylko zasobytestowe. InstrukcjaWindows/WSL2 kompletna, bez twierdzenia o wykonanymWindows.
- **Wykonano / dowody (pliki, commit):** Dockerfile:readinesshealthcheck, nie-root, opcjonalnyCAsecret; compose.yaml:timeoutenv. scripts/check_docker.py:izolowanyUUIDprojekt/port/wolumen, syntetycznyklucz i integracjeoff, auth/restart/413/healthy/cleanup. docs/DOCKER-WINDOWS.md, WINDOWS-CHECKLIST, .github/workflows/test.yml jobDocker, docs/evals/docker-m12.json i README/raport/handoff/changelog/status. Commit: bieżący M1.2.
- **Testy (komenda, wynik):** PASS rzeczywisty Dockerbuild + Composebuild/up, /health+/ready,401/owner200,201+restartpersistence,413,UID10001,healthy,cleanup; wynik/imageSHA w docs/evals/docker-m12.json. Wcześniejsze FAIL helperNameError/staryport poprawione; finalPASS. PASS syntax/diff/master.353pytest=M1.1 bez powtórki. NOT_RUN Windows11/WSL2/hardware/GitHubCI.
- **Blokady / dalsze kroki:** brak; następne: M1.3

#### M1.3 — Uwierzytelnianie, role, sesje, rate limits, CORS, audit trail, bezpieczne przechowywanie sekretów.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-23T06:03:39+00:00
- **Plan implementacji:** Dodać lokalne konta i role z hashowaniem haseł, wygasające/odwoływane sesje, ograniczone uprawnienia bez dostępu do pamięci właściciela; limity API/login i jawny CORS, audyt aktora. Migracja11→12 z backupem i testami; pełna regresja.
- **Kryterium akceptacji:** Kontrola role/scope i sesji jest po stronie backendu; hasła i tokeny nie trafiają do odpowiedzi/logów/bazy jawnie; wyłączenie/zmiana roli odwołuje sesje, anon/wrongrole zablokowane; login/API429 nie można ominąć aliasem, CORS tylkoallowlista. Migracja zachowuje dane i testy przechodzą.
- **Wykonano / dowody (pliki, commit):** Core0.8.6/schema12: identity.py,security_api.py,security_limits.py i integracja main.py; konta/role PBKDF2, sesjeSHA256/TTL/revoke/revision, uprawnienia workshop/home/runner bez prywatnych danych, limity obuAPI/login,CORS,audytaktora. Backup11→12 i testy zachowania danych; --no-proxy-headers Docker/start.ps1/README z testemTCP. SECURITY-ACCESS/API/raport/handoff/status/changelog/start/README i docs/evals/docker-m13.json. Przegląd poprawił lookup przed publicznym probe, testmissing/corrupt. Commit: bieżący M1.3.
- **Testy (komenda, wynik):** PASS .venv/bin/python -m pytest -q:453(60.37s); PASS pip check,7JSsyntax/8kontrolowanychskryptów; PASS rzeczywistyChromium voice2tury/cleanup i transport13żądań/390px; PASS nowyLinuxDockerbuild/Compose/auth/restart/413/non-root/healthy/cleanup. Pierwszybłędnytesttrasy i błądprobe poprawione przedfinalPASS. NOT_RUN Windows/WSL2/realnemodele/sprzęt/produkcja/CI.
- **Blokady / dalsze kroki:** brak; następne: M1.4

#### M1.4 — PostgreSQL/Supabase, migracje, RLS, minimalne granty dla anon/authenticated/service_role zgodnie z potrzebami i testy uprawnień.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-24T07:47:42+00:00
- **Plan implementacji:** Dostarczyć osobną opt-in warstwę PostgreSQL JARVIS: numerowane migracje z checksum/blokadą, prywatne i warsztatowe rekordy z RLS/minimalnymi grantami, repozytorium i API korzystające z tożsamości M1.3. Oddzielny migrator/runtime bezBYPASSRLS, rzeczywisty lokalnyDockerPostgres i testy dwóch użytkowników/warsztatów, rollback/revisions/context. Zachować CoreSQLite; nie uruchamiać produkcyjnegoSupabase.
- **Kryterium akceptacji:** Rzeczywiste migracje i CRUD na ograniczonym połączeniuPG przechodzą; anon/service_role bez uprawnień aplikacyjnych, authenticated widzi własne/memberrekordy, obcy subject/tenant i nieuprawnionyUPDATE blokowane. Checksum/replay/rollback/restart i izolacja kontekstu zweryfikowane. API bierze subject wyłącznie ze zweryfikowanej sesji, DSNbezsekretów wlogach, brakDDL przy starcie; pełna regresjaPASS. Dokumentacja uczciwie wskazuje pozostającySQLite i Supabase NOT_RUN.
- **Wykonano / dowody (pliki, commit):** Core0.8.7/SQLite12 + osobny opcjonalny PostgreSQLmigration1: migrations/postgres/0001_foundation.sql, postgres_migrations.py/CLI, postgres_store.py/API/main.py. FORCE RLS/private/workshops/memberships, jawnegranty, ograniczonyruntime, subjectzsesji, revision i atomowyaudyt. Testy config/integration/API, check_postgres.py i jobCI, zależnościpsycopg; POSTGRES/API/start/status/README/raport/handoff/changelog i dowodyevals. DotychczasoweSQLite zachowane; brakprodukcji. Commit: bieżący M1.4.
- **Testy (komenda, wynik):** PASS pytest573/24skip(61.98s) bezPG; PASS osobny realnyDockerPostgres16.15:25/0skip, RLS2users/2warsztaty, granty, claims, migracje/checksum/rollback, auditrollback, migratorbezsuper/BYPASS, restart/cleanup. PASS pipcheck,app.js syntax,diff i nowyDocker0.8.7/Compose/auth/restart/413/non-root/healthy/cleanup. Poprawiono testsslrootcert po wymaganiu user/dbname; final119configPASS. Chromium=M1.3; NOT_RUN produkcyjnySupabase/Windows/sprzęt/CI.
- **Blokady / dalsze kroki:** brak; następne: M1.5

#### M1.5 — Rejestr narzędzi i polityki wykonania; mocki, testy unit/integration i CI.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-24T07:59:32+00:00
- **Plan implementacji:** Ujednolicić istniejące DEMO/OpenAPI/MCP w zaufanym rejestrze narzędzi ze schematem argumentów i wspólną polityką uruchomienia. Istniejący invoke oraz katalog mają współdzielić kontrolę tożsamości/scope, aktywności, zatwierdzonych odczytów, limitów czasu/współbieżności i wielkości. Zachować allowlisty sieci i blokadę skutków; testy odmowy przedI/O, realne lokalne laboratorium oraz pełna regresja/CI.
- **Kryterium akceptacji:** Rejestr publikuje jednoznaczne ID/schemat/protokół/lokalne zatwierdzenie, nie przyznaje praw z danych zdalnych. Każda ścieżka invoke korzysta z tej samej polityki i zweryfikowanej tożsamości; błędne scope/args/niezatwierdzone operacje nie wykonują transportu. Limit/cancel zwalnia zasoby, wynik ograniczony, audyt bez argumentów/sekretów. Unit/integration i realny localhostMCP/OpenAPI przechodzą, bez nowych realnych zapisów/LLMloop.
- **Wykonano / dowody (pliki, commit):** Core0.8.8: tool_registry.py ToolSpec/Gateway, wspólny invoke/discover i GET/tools w main.py; plugins.py pełne schemaOpenAPI/MCP, duplikaty/limity/ref-regexban. Principal/scope/localreview,30s/4slots/64KiBinput/1MiBresult, cancelcleanup i metadataaudit. test_tool_registry.py(41),test_tool_transport_schemas.py(37),test_tool_api.py(6), rzeczywisty localhostSDKlab. TOOLS/API/README/start/status/raport/handoff/changelog i docker-m15.json. Bez nowej migracji i zewnętrznych skutków. Commit: bieżący M1.5.
- **Testy (komenda, wynik):** PASS pytest657/24skip(68.97s), pipcheck,app.js syntax,diff i nowyDockerbuild/Compose/auth/restart/413/non-root/healthy/cleanup. PASS realny localhostMCP/OpenAPI; brakdispatchpo odmowie, schema/cancel/deadline/capacity/privacy/legacyconfig. Poprawiono początkowytypdiscovery i500staregoregexconfig, finalPASS. PG25testów=M1.4/Chromium=M1.3 bezpowtórki; NOT_RUN Windows/produkcja/modele/sprzęt/CI.
- **Blokady / dalsze kroki:** brak; następne: M2.1

### M2 — JARVIS Control Center

#### M2.1 — React + TypeScript, responsywny dark UI z nawigacją i dashboardem.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-24T21:58:42+00:00
- **Plan implementacji:** Dodać React/TypeScript/Vite Control Center pod /control/ obok działającego panelu, responsywny dark UI z nawigacją/pulpitem na rzeczywistych statusach API. Logowanie kontem lub kluczem, token tylko w pamięci, logout/revokacja i cleanup; produkcyjne assety z lokalnym CSP. Build/testkomponentów i rzeczywistyChromium desktop390px, statyczne trasy backendu i DockerbuildUI; zachować15starychwidoków.
- **Kryterium akceptacji:** Typecheck/build i znaczące testy komponentów/API przechodzą; React działa z rzeczywistym Core, pokazuje poprawne liczniki i odróżnia DEMO/optional/unready. Login/logout/401 nie ujawnia tokenów ani zachowuje prywatnych danych; role respektowane. Nawigacja klawiaturą i mobilna390px bezoverflow, assetsbeztraversal/CSPbezinline, buildDockeruruchamiaUI. Starypanel/funkcje nadal sprawne; nie oznaczać nowychportówM2.2-.4 jako gotowych.
- **Wykonano / dowody (pliki, commit):** Core0.9.0: frontend/ ReactTS/Vite source+lock+10tests, /control/ pulpit/System/loginmobile; control_ui.py bezpieczneassets i main.py,5testówbackend. DockerNodebuild/dist/notice, git/dockerignore, cloud_setup/CI/check_dockerUIassets, dedicatedbrowserfixture+Chromiumscript. CONTROL-CENTER/API/start/status/README/raport/handoff/changelog, licenses i evals/control-m21.json/PNG/docker-m21.json. Legacy15widoków zachowane, noweportyM2.2-.4 nadalTODO. Commit: bieżącyM2.1.
- **Testy (komenda, wynik):** PASS662pytest/24skip(62.48s),pipcheck,app.js; npmci108pkg,10componentPASS(4.83s),typecheck/productionbuildPASS. PASS actualChromiumCore/login/logout/revoke/roles/privacy/CSP/focus/390px; PASS nowyDockerbuild/UIHTML-JS-CSS/Compose/auth/restart/413/non-root/healthy/cleanup. Poprawionotypytestów i dwaa11yfocusbłędy, finalPASS. NOT_RUN Windows/WSL2/Safari/iPhone/Android/sprzęt/modele/CI; PG=M1.4 bezpowtórki.
- **Blokady / dalsze kroki:** brak; następne: M2.2

#### M2.2 — Panel rozmów, ustawień, modeli AI i historii działań.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-25T12:34:11+00:00
- **Plan implementacji:** Przenieść do React właścicielskie rozmowy/sesje/wybór modeli, ustawienia przez propozycję→osobne zatwierdzenie oraz ostatnie100zdarzeń. Rozszerzyć wspólny klientHTTP o metody i timeout95s dla czatu, abort/epoch i odczyt stanu po przerwaniu. Zachować izolację voice/text, owner-only UI/API i15legacywidoków. Komponenty/testy domenowe równolegle, rzeczywistyCoreDEMO/Chromium oraz build/Docker i regresja.
- **Kryterium akceptacji:** Rozmowy rzeczywiście zapisują/odczytują historię, działają nowe/istniejące sesje i wybór jawnego modelu bez instalacji/pobierania; błędy409/502/504 i przerwanie nie udają zatrzymania backendu. Ustawienia zapisują pełny podgląd przez osobne zatwierdzenie, historia rzetelnie pokazuje ostatnie100. Role ograniczone nie pobierają privateAPI, logout/401/stale odpowiedź nie przywraca danych, tekst bezHTMLinjection. Typecheck/build/komponenty/realnyChromiumCore i właściwa regresjaPASS, brak realnych usług/produkcji.
- **Wykonano / dowody (pliki, commit):** Core0.9.1: frontend/src/features/chat/settings/activity, App.tsx ownernav/gate, api.ts metody/95s i40UItests. Trwałe sesje/model/history, voice readonly, propozycja→decyzja fullsettings i latest100audit; abort/sync/401/credentialcleanup, poprawka ponownego wyboru sesji. scripts/check_conversation_browser.cjs i evals/control-m22.json/4PNG/docker-m22.json; CONTROL-CENTER/API/README/start/status/raport/handoff/changelog. SQLite12/PG1 bezmigracji; legacy15 zachowane. Commit: bieżącyM2.2.
- **Testy (komenda, wynik):** PASS pytest662/24skip74.97s,pipcheck,app.js,diff;40UItests11.59s,typecheck/build. PASS rzeczywistyChromiumCoreDEMO persistence/reload/model/HTML/voice/proposals/audit/roles/privacy/CSP/logout/revoke/401 i3widoki390px; PASS nowyDockerbuild/Composeassets/auth/restart/persistence/413/non-root/healthy/cleanup. Testylifecycle kontrolowane, preflightsettings bezCAS. NOT_RUN realnemodele/Windows/WSL2/Safari/iPhone/Android/sprzęt/CI; PG=M1.4 bezpowtórki.
- **Blokady / dalsze kroki:** brak; następne: M2.3

#### M2.3 — Plugin Manager: status, konfiguracja, uprawnienia, test połączenia, enable/disable.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-25T12:44:17+00:00
- **Plan implementacji:** Dodać właścicielski PluginManager React na istniejącym API: lista/status, rejestracja manifestu, pełna konfiguracja endpoint/envname/reviewedreads/OpenAPI, świadome enable/disable i jawne testowanie przez MCPdiscovery lub zatwierdzony odczyt. Nie wykonywać discovery/invoke przy mount, nie zapisywać sekretów ani instalować kodu. Wspólny HTTP dodaPUT/40s, lifecycle401/epoch/abort i czytelne ograniczenia. Testy komponentów/kontraktów i rzeczywisty Chromium/Core z izolowanym lokalnym serwerem testowym.
- **Kryterium akceptacji:** UI rzeczywiście zapisuje konfigurację, pokazuje forceddisabled po zapisie i respektuje autoryzację; status transport_ready nie udaje połączenia. Discovery/invoke wyłącznie po jawnej akcji i dla lokalnie zatwierdzonych odczytów, test bez sieci nie deklaruje sukcesu transportu. Błędy/blocked/timeout i sekrety renderowane bez ujawniania, logout/401/credentialchange czyszczą dane. Typecheck/build/UItests oraz rzeczywistyCore/browser i lokalny transportPASS; brak produkcji/zewnętrznych zapisów.
- **Wykonano / dowody (pliki, commit):** Core0.9.2: frontend/src/features/plugins PluginPanel/API/CSS/tests; App route/nav/owner gate i poprawka hashpo logowaniu, apiRequestPUT/40s; ignorowanie cache node_modules. Lista/status/manifest/fullconfig/reviewedreads/envname/forceddisable/enable-disable, jawny katalog i odczyt, brak autoI/O. scripts/check_plugins_browser.cjs/browser_plugins_fixture.py, evals/control-m23.json/2PNG/docker-m23.json; CONTROL-CENTER/API/README/start/status/raport/handoff/changelog. SQLite12/PG1 bezmigracji. Commit: bieżącyM2.3.
- **Testy (komenda, wynik):** PASS pytest662/24skip64.26s,pipcheck,app.js,diff;60UItests,typecheck/build. PASS actualChromium/temporaryCore/genuine localhostHTTP: no hiddenI/O, configforce-disable/enable-disable/localcatalog/explicit authorizedGET/escapedtext/privacy/roles/CSP/390px; PASS nowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup. MCPUI controlled; SDKtransport=M1.5 i PG=M1.4 bezpowtórki. NOT_RUN usługiwłaściciela/Windows/WSL2/Safari/iPhone/Android/modele/sprzęt/CI.
- **Blokady / dalsze kroki:** brak; następne: M2.4

#### M2.4 — Widoki AutoLogika, Home, Devices, Automations, Memory, Telephony, Notifications, Security, Logs.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-26T03:22:07+00:00
- **Plan implementacji:** Dodać Reactwidoki AutoLogika, Home, Devices, Automations, Memory, Telephony, Notifications, Security i Logs na potwierdzonych API. Podział domenowy, istniejące legacy/laboratoria zachowane. home_reader tylkoHome, workshop_reader tylko dozwolone odczytyAutoLogika; pozostałe nowe moduły owner-only. Odczyty zewnętrzne wyłącznie jawne, brak fikcyjnego sterowania/OSlogs. Zachować rewizje i osobne zgody,401/abort/epoch/credentialcleanup; testy komponentów, prawdziwyCore/Chromium390px, build/Docker i regresja.
- **Kryterium akceptacji:** Wszystkie9widoków prezentują rzeczywiste dostępne dane i stany, bez wymyślonych endpointów, deklaracji zdrowia usług ani sprzętu. Działają obsługiwane lokalne operacje z walidacją/revision/proposal-approval; ograniczone konta nie pobierają prywatnych API. Pamięć/hasła/tokeny i sesje nie przeciekają po logout/401/zmianie tożsamości. Typecheck/build/UItests i realnyCore/browserPASS, istniejące15legacywidoków zachowane; produkcja i urządzenia bez zmian.
- **Wykonano / dowody (pliki, commit):** Core0.9.3: frontend/src/features/workshop,home,devices,automations,memory,telephony,notifications,security (API/TSX/CSS/tests), App.tsx role-aware routes i przewijana nawigacja15widoków, styles.css. Logs współdzieli ActivityPanel; legacy/laboratoria zachowane. Memory CRUD/revision/history/origins/policy/retention, automation proposal→approval/tick, telephony policy/revision/preview, security users/sessions/service tokens. scripts/browser_modules_fixture.py i check_modules_browser.cjs; evals/control-m24.json/11PNG/docker-m24.json; README/start/status/API/CONTROL-CENTER/raport/handoff/changelog. SQLite12/PG1 bez migracji. Commit: bieżący M2.4.
- **Testy (komenda, wynik):** PASS pytest662/24skip62.62s, pipcheck/app.js/diff;128UItests46.44s,typecheck/build. ActualChromium/Core:9widoków390px, snapshot readonly5/8domen, memoryCRUD/history, separateapproval/ticknotification z kontrolowanym terminem fixture, DNDpreview, users/sessionrevoke/one-time token cleanup, reader scopes/privacy/CSP; zero outboundattempts. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Poprawiono typ testuDevices i synchronizację mobilnego menu w teście. NOT_RUN Windows/WSL2/Safari/iPhone/Android/usługiwłaściciela/modele/sprzęt/CI; PG=M1.4 bezpowtórki.
- **Blokady / dalsze kroki:** brak; następne: M2.5

#### M2.5 — Przegląd zmian i zatwierdzeń; testy komponentów, accessibility i build.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-26T05:56:11+00:00
- **Plan implementacji:** Dodać wspólny przegląd ostatnich100propozycji settings/automation/code w React: szczegóły, osobny wybór i zatwierdzenie/odrzucenie oraz jawny rollback. Zachować code jako review_required bez wykonania kodu i odmowy409; testy lifecycle/401/transportbezretry. Sprawdzić accessibility/klawiaturę/mobile i build na wszystkich widokach, bez deklaracji audytuWCAG na podstawie samych testów.
- **Kryterium akceptacji:** Przegląd pokazuje prawdziwe statusy i zakres skutków, decyzje i rollback wymagają osobnego jawnego kroku; kod nie jest uruchamiany. Role/privacy/lifecycle zachowane; testy komponentów/kontraktów, rzeczywistyChromium a11y/keyboard i build PASS. Ograniczenia preflight bezCAS oraz nieobsługiwane operacje opisane.
- **Wykonano / dowody (pliki, commit):** Core0.9.4: features/changes/ChangesPanel.tsx,changes.css,ChangesPanel.test.tsx i API; App route/nav/owner gate i styles.css z poprawką mobilnego focusu, expanded role test. Osobny podgląd→decide/rollback, freshread/preflight bezCAS, code review_required bez wykonania, mutationerror wymagarefresh, lifecycle401/abort/keyedcredential, escapedtext i focus. scripts/check_changes_browser.cjs, evals/control-m25.json/2PNG/docker-m25.json; README/start/status/API/CONTROL-CENTER/raport/handoff/changelog. Commit: bieżącyM2.5.
- **Testy (komenda, wynik):** PASS 139UItests,typecheck/build,pytest662/24skip87.79s,pipcheck/app.js/diff. ActualChromium/tempCore: approve+realsettingsrollback, code review bezexecution, structure16views(main/h1/labels/uniqueIDs), mobilekeyboard focus/Tabtrap/Escape/390px, privacy/CSP/owner gate. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Poprawiono browserhelper deklarację screenshot i rzeczywisty focus mobilnego menu; finalPASS. PełnyWCAG/czytnik/Safari/Windows/WSL2/telefony/modele/sprzęt/CI NOT_RUN.
- **Blokady / dalsze kroki:** brak; następne: M3.1

### M3 — AI, rozmowa i pamięć

#### M3.1 — Abstrakcja dostawców LLM, Ollama i przynajmniej jeden provider cloud z konfiguracją kosztów.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-26T06:23:57+00:00
- **Plan implementacji:** Wspólny kontrakt dostawcówLLM i jawna polityka cen/budżetu, adapter Ollama oraz co najmniej jeden provider cloud z opt-in i bezpiecznymi transportami/sekretami. Połączyć istniejący chat/katalog bez utraty text/voice/history/memory; walidacja tokenów/modeli, kontrolowane testy odmów i protokołów, pełna regresja. Prawdziwa płatna inferencja pozostaje wyłączona bez aktywacji.
- **Kryterium akceptacji:** Ollama i providercloud współdzielą kontrakt i polityki, konfiguracja waliduje model/endpoint/tokenlimity/koszty, odmawia przed I/O po przekroczeniu budżetu lub bez aktywacji. Sekrety i diagnostyka nie przeciekają. Testy kontrolowanych transportów i pełna regresja PASS; jakość realnych modeli i wydatki nie są deklarowane bez testu.
- **Wykonano / dowody (pliki, commit):** Core0.10.0: llm.py i llm_providers.py wspólny kontrakt/Ollama/OpenAI/CostPolicy, main.py+conversations.py integracja czatu/sesji/katalogu/settings/usageaudit;30adaptertests+18cost. Frontend typy/guards/labels/default/cloudnotice+2tests, legacyapp/voice poprawione. Env/Compose defaultsoff, LLM-PROVIDERS/API/CONTROL-CENTER/README/start/status/raport/handoff/changelog. scripts/browser_llm_fixture.py/check_llm_browser.cjs i evals/control-m31.json/2PNG/docker-m31.json. SQLite12/PG1 bezmigracji. Realnycloud/inferencja NOT_RUN; commit bieżącyM3.1.
- **Testy (komenda, wynik):** PASS pytest710/24skip74.44s,pipcheck,JSsyntax+controlledvoice/chatmemory,diff;141UItests38.98s,typecheck/build. RealnylocalhostHTTP obu protokołów, odmowy przedI/O/budget/model/flags/secret, usage/privacy/voice/cancel/errors/JSONguards; actualChromium syntheticcloud1request/persistence/defaultapproval/contextnotice/privacy/CSP/390px. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Poprawiono pustą asercjętestu i nieprawidłowe strukturyJSON bez500; finalPASS. Prawdziwe konto/inferencja/Windows/WSL2/Safari/iPhone/Android/sprzęt/CI NOT_RUN.
- **Blokady / dalsze kroki:** brak; następne: M3.2

#### M3.2 — Pętla tool-calling ze schematami argumentów, limitami, autoryzacją i odpornością na prompt injection.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-26T06:50:59+00:00
- **Plan implementacji:** Dodać ograniczoną pętlę tool-calling z serwerowym mapowaniem aliasów do ToolSpec i filtrowanym katalogiem; walidować cały plan przed dispatch. Każdy krok ponownie autoryzuje ToolGateway ze zweryfikowanym Principal i bieżącą konfiguracją. Limity tur/wywołań/czasu/kontekstu/kosztów, brak uprawnień z instrukcji modelu lub wyników narzędzi. Rozszerzyć protokoły dostawców i jawny opt-in, zachować izolację voice/private. Testy promptinjection/schematów/odmów przed I/O oraz kontrolowane E2E i regresja.
- **Kryterium akceptacji:** Model może wybierać wyłącznie jawnie dopuszczone odczyty, nie nadaje scope/role ani nie wykonuje kodu/zapisów. Schematy/args/replay/limity sprawdzane przed wykonaniem, gateway ponownie sprawdza tożsamość i konfigurację przy każdym kroku. Pętla kończy się bez autoretry po limicie/błędzie/cancel, koszt obejmuje kolejne żądania. Kod/providerAPI/E2E i właściwa regresja PASS, realne usługi pozostają osobną aktywacją.
- **Wykonano / dowody (pliki, commit):** Core0.10.1: tool_plan.py/tool_llm.py/tool_loop.py i main.py ownerAPI/chat/tools opt-in; pełna lista przeddispatch, serwerowealiasy/args/schema/replay/limity, aktualnatożsamość/config,4tury/8calls/90s/2slots i kosztcałegoprzebiegu. tool_registry.py/plugins.py pin+auth po ostatnimdiscoveryMCP; network.py legalnequery z zachowaniemorigin/DNS/IP. tests/test_tool_plan.py/test_tool_chat.py/test_network_query.py i3transporttests; scripts/check_tool_chat.py/CI/evals/tool-chat-m32.json/docker-m32.json. TOOL-CALLING/TOOLS/LLM-PROVIDERS/API/DECISIONS/README/start/status/raport/handoff/changelog. BeznowegoGUI/privatecontext/history/zapisów; commitbieżącyM3.2.
- **Testy (komenda, wynik):** PASS pytest767/24skip89.22s, wybranyzestaw141/8.09s,pipcheck/JSsyntax/diff,typecheck/build. GenuineTCP Core+syntetyczneOllama/OpenAI+OpenAPIquery/MCP SDK:4kombinacje2tury/1read, odmowacałejlisty,privacy/audit/cleanup. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. WstępnyFAILquerytransportu naprawiony, finalPASS; poprawne npmfrontendbuildPASS.141UI/Chromium=M3.1 iPG=M1.4 bezpowtórki. Inferencja/kontocloud/Windows/WSL2/telefony/sprzęt/GitHubCI NOT_RUN.
- **Blokady / dalsze kroki:** brak; następne: M3.3

#### M3.3 — Pamięć krótkoterminowa, długoterminowa (Postgres/pgvector), podział danych prywatnych i warsztatowych.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-26T08:27:20+00:00
- **Plan implementacji:** Dokończyć istniejącą pamięć PG bez ponownego pisania fundamentu. Dodać osobną migrację feature2: sesje tekstowe przypisane do subject i niezmiennego private/workshop zakresu, TTL, limity, trwała dzierżawa jednej tury, atomowa historia i audyt. Jawnie wybierać rekordy pamięci z rewizjami; rewalidować RLS i źródła historii przed inferencją i zapisem. Osobne owner API sesji z istniejącymi dostawcami LLM/kosztami, bez narzędzi i bez SQLite/voice/customer. Testy PG/API/protokołów, wygaśnięcia, konkurencji, zmian źródeł i revoke, regresja i Docker.
- **Kryterium akceptacji:** Pamięć długa PG/pgvector i krótki kontekst sesji rzeczywiście współpracują przez owner API. Sesje i historia są izolowane per konto i zakres, TTL/limity i blokada tury działają, odwołanie konta/członkostwa albo zmiana źródła uniemożliwia zapis/zwrot starego kontekstu. Brak zapisu prywatnych odpowiedzi PG do wspólnego SQLite. Migracja i zachowanie feature1 danych, RLS/grants/CAS/audit/cleanup, aktualne kontrole kosztu/modelu oraz odpowiednia regresja PASS. Modele/protokoły syntetyczne wyraźnie odróżnione od realnej inferencji; brak produkcji.
- **Wykonano / dowody (pliki, commit):** Core0.10.2: postgres_context.py/postgres_context_api.py i main.py, migrations/postgres_memory/0002_context.sql; account-private sesje z immutable scope/model/TTL, ograniczony kontekst i jawne notatki, RLS/revision/sources przedLLM i zapisem, propagacja provenance, trwałyclaim/CAS/atomic-history-audit/cascade. Cloudallowcontext, obecniLLM/cost, bezSQLite/voice/customer/toolchat. postgres_memory.status feature1/2; check_postgres.py i tests/test_postgres_context.py/test_postgres_context_integration.py +7APIguards/aktualizacjaPGtestów. POSTGRES-CONTEXT/POSTGRES-MEMORY/API/DECISIONS/README/start/status/raport/handoff/changelog i evals/postgres-memory-m33.json/docker-m33.json. GUI pamięci wM3.4; commit bieżącyM3.3.
- **Testy (komenda, wynik):** PASS .venv/bin/python -m pytest -q:810/61skip112.72s; selectedcontext/API28PASS3.64s; pipcheck/JSsyntax/diff/typecheck/build. PASS realDockerPG/pgvector62/0skip (25M1.4+13memory+24context): upgrade1→2 restrictedmigrator/vectorpreservation,RLS/lease/revision/TTL/quota/provenance/auditrollback/cascade, actualOllama/OpenAIHTTP z syntetycznymi odpowiedziami i revoke/source/membership/expiry/timeout. GenuineCoreTCP→embedding→pgvector/search→2turns/history→foreign404→sourcechange/pre-I/O409→delete PASS. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS.141UI/Chromium=M3.1 bezpowtórki; realnamodelinference/cloudaccount/GUI/Windows/sprzęt/GitHubCI NOT_RUN.
- **Blokady / dalsze kroki:** brak; następne: M3.4

#### M3.4 — Przeglądanie, korekta, usuwanie pamięci; instrukcje, profile, wersjonowanie.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-27T07:59:26+00:00
- **Plan implementacji:** Wykorzystać dotychczasową pamięć SQLite/UI i ukończone PGmemory/context. Dodać featuremigration3 dla historii rewizji notatek i wersjonowanych profili/instrukcji private/workshop; CAS/RLS i atomowy audyt, usuwanie treści historii wraz z rekordem. Jawnie przypinać profil/revision do nowej sesji, rewalidować przedLLM i zapisem, bez uprawnień z treści. Udostępnić owner API historii/profili i rozszerzyć panel pamięci z właściwym statusem optionalPG, potwierdzeniem usunięcia i lifecycle/401/scope. Testy unit/realPG/API/profilechanges/upgrade oraz komponenty/browser/build/regresja.
- **Kryterium akceptacji:** Przegląd/korekta/usuwanie pamięci i profili faktycznie działają w wybranym zakresie; historia odzwierciedla zachowane rewizje, nie wymyśla wersji sprzed migracji. Nieaktualne revision i profile są odrzucane, obce konta/warsztaty niewidoczne. Profil jawnie wybierany i pinned przy sesji; nie przyznaje tools ani scope. UI obsługuje disabled/error/abort/401 i nie zachowuje danych po zmianie konta; adekwatne realne testy, regresja i build PASS. Realna inferencja/Windows/produkcja pozostają NOT_RUN.
- **Wykonano / dowody (pliki, commit):** Core0.10.3: feature3 versions/profiles + nowa0004_session_profiles.sql; postgres_context.py/API immutable profile_ref/revision, aktualne RLS/scope przedLLM i zapisem, zmiana/usunięcie wymaga nowej sesji, stare feature2sesje zachowane. React MemoryPanel/PostgresMemoryPanel/postgresApi z private/workshop, paginacją20, CRUD/history100/CAS i osobnym potwierdzeniem usunięcia, profile/notatki jawnie do nowej sesji, cloudzgoda per tura,401/abort/credentialcleanup. Nowe testy profili i optional Chromium w check_postgres.py --memory --browser; docs/POSTGRES-PROFILES/API/CONTEXT/CONTROL-CENTER/README/start/status/raport/handoff/changelog i evals. AGENTS/master: zakres tylko do końcaM3; M4 nie rozpoczynać.
- **Testy (komenda, wynik):** PASS .venv/bin/python -m pytest -q:817/75skip141.41s; npmtest149/70.48s,typecheck/build,pipcheck/JSsyntax/diff. PASS76realnePG/API/Chromium/0skip: poprzednie69+6profilepin+1browser; actualCoreTCP/PG/LLMHTTP z syntetycznymi odpowiedziami, CRUD/history/two-turns/staleprofile,390px/desktop/privacy/logout. Upgrade1→2→4 ograniczonym migratorem zachowuje wektory i wcześniejszą sesję. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. WstępneFAILrowlockreadonly/etykietybrowser/testasercja poprawione; finalPASS. Realna inferencja/cloudaccount/Windows/sprzęt/GitHubCI NOT_RUN.
- **Blokady / dalsze kroki:** brak; następne: M3.5

#### M3.5 — Zadania wieloetapowe, przerwania i testy scenariuszy.
- **Status:** VERIFIED
- **Rozpoczęto / aktualizacja UTC:** 2026-10-27T08:15:42+00:00
- **Plan implementacji:** Dodać ograniczone owner-only zadania1–4 jawnych etapów odczytu na sprawdzonej pętli M3.2. Osobny status/postęp, idempotencyUUID, izolacja perkonto, start/status/cancel, TTL/limityRAM/czasu i cleanupshutdown. Autoryzacja/config przedkażdymetapem/dispatch i po modelu, wspólny limit kosztu przez wszystkieetapy, kontekst poprzednich wyników jako niezaufane dane. Bez narzędzi zapisu/produkcji/automatycznego wznowienia po restarcie. Testy scenariuszy, cancel w różnych fazach, revoke/config/budget i genuineHTTP; regresja iDocker. Po M3.5 STOP, nie rozpoczynać M4.
- **Kryterium akceptacji:** Wieloetapowy przebieg faktycznie wykonuje jawny plan przez istniejących dostawców i ToolGateway; każdy etap rewaliduje uprawnienia i catalog/schema. Przerwanie kończy przyszłe wywołania i czyści wyniki, zwalnia sloty; status odróżnia cancel od cofnięcia jużwykonanych odczytów. Brak replay przy tym samymrequest_id, boundedTTL/capacity/cost, innekonto404. Testy protokołów/scenariuszy i regresjaPASS; realnamodelinferencja/Windows/sprzęt NOT_RUN. M4 pozostajeTODO.
- **Wykonano / dowody (pliki, commit):** Core0.10.4: jarvis/ai_tasks.py owner-private RAMTaskManager i main.py API POST/chat/tasks,GET/{id},POST/{id}/cancel.1–4jawneetapy przez istniejący ToolLoop/ToolGateway; currentauth/config/schema i cancellation przy ostatniejgranicy dispatch, provenance poprzednichodpowiedzi, wspólnyrezerwowanybudżetOpenAI przezwszystkieetapy. UUIDidempotency perkonto/15min,2active/32records/180s/128KiB/16KiBcontext, cleanupTTL/lifespan i bezpiecznemetadataaudit/error; brakwznowienia po restarcie/produkcji/zapisów. Taskvalidation422 bez echo/Unicode500.26nowychtests/test_ai_tasks.py, scripts/check_tool_chat.py --tasks i jobCI; docs/AI-TASKS/API/TOOLS/DECISIONS/README/start/status/raport/handoff/changelog/master/evals. M3 zakończone; zgodnie z poleceniem STOP przedM4, wszystkieM4TODO.
- **Testy (komenda, wynik):** PASS .venv/bin/python -m pytest -q:843/75skip128.17s; pipcheck/JSsyntax/diff/typecheck/build. PASS genuineTCP Core/Ollama/OpenAI/OpenAPI/MCP SDK:4kombinacjepo2etapy,26providerPOST/6HTTPread/6MCPread zsyntetycznymiodpowiedziami, idempotentreplaybezI/O, cancelpodczasHTTPprzeddispatch, privacy. Unit/API: cancelmodel/discovery/read i dostawcatłumiącycancel,role/revoke/capacity/TTL/timeout/shutdown/rozmiary/Unicode/config/budgetcałegozadania; stareM3.2bezregresji. PASS76realnePG/API/Chromium/0skip po integracjiM3.5, frontendUI149=M3.4 bezpowtórki; buildponowiony. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. WstępneFAILimportenabled/oczekiwany409/Unicode naprawione; finalPASS. Realnainferencja/cloudaccount/Windows/sprzęt/GitHubCI NOT_RUN.
- **Blokady / dalsze kroki:** Brak blokady kodu; zakończono zlecony zakresM3. STOP przedM4 zgodnie z właścicielem.

### M4 — AutoLogika OS

#### M4.1 — Adapter wyłącznie do rzeczywiście znalezionych endpointów/operacji; mock przy braku dostępu.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M4.2 — Odczyt terminarza, pojazdów, klientów, zleceń, diagnostyki i części.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M4.3 — Raporty, finanse, powiadomienia i statusy QC, jeśli wspierane przez system.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M4.4 — Operacje zapisu: notatki, zadania, wyceny i statusy tylko z uprawnieniami oraz potwierdzeniem.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M4.5 — Testy kontraktowe, RLS i separacji klientów; dokumentacja nieobsługiwanych funkcji.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

### M5 — Dom, warsztat i ESP32

#### M5.1 — Adapter Home Assistant REST/WebSocket z ograniczonym tokenem.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M5.2 — MQTT/Mosquitto, ESPHome/ESP32, status urządzeń i reconnect.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M5.3 — Światło: on/off, dimming, sceny, harmonogramy i czujniki.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M5.4 — Symulator bramy: stany, blokady, logi, timeout i potwierdzenie w zaufanej aplikacji.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M5.5 — Adapter prawdziwej bramy tylko po inspekcji centrali, czujników i fabrycznych zabezpieczeń; bez zdalnego otwarcia w testach.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

### M6 — Automatyzacje i zmiany zachowania

#### M6.1 — Integracja n8n self-hosted; import/eksport i wersjonowanie workflow.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M6.2 — Raport poranny AutoLogika, przypomnienia części, opóźnienia zleceń, raport dnia.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M6.3 — Automatyzacje światła, statusu bramy, alertów o połączeniach i godzin dostępności.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M6.4 — Zmiana reguł z rozmowy: propozycja -> walidacja -> podgląd -> zatwierdzenie -> zapis -> rollback.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M6.5 — Zmiana kodu wyłącznie przez osobny branch/PR, testy i zatwierdzenie; żadnego autonomicznego deploy produkcyjnego.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

### M7 — WhatsApp, telefonia i głos

#### M7.1 — Zweryfikuj aktualne Twilio WhatsApp Business Calling: wymagania Meta, zgody, ograniczenia, realny transport audio i koszty.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M7.2 — WhatsApp Messaging: webhook signature validation, idempotency, wysyłka i odbiór; sandbox jako test wiadomości, nie połączeń.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M7.3 — Głosówki, STT/TTS, streaming, interruption i mierzenie opóźnienia.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M7.4 — Połączenia przychodzące/wychodzące tylko gdy konto i dokumentacja potwierdzą możliwość; fallback tekstowy.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M7.5 — Asystent klienta: intencje, zgłoszenia, eskalacja pilna, godziny dostępności i reguły przekierowań; oddzielny adapter GSM/SIP w przyszłości.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

### M8 — Urządzenia, stabilizacja i wdrożenie

#### M8.1 — Panel mobilny PWA na iPhone/Android; integracja z Android AutoLogika po audycie.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M8.2 — Powiadomienia, monitoring, health checks, retry i alerty.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M8.3 — Backup, restore drill, migracje, aktualizacje i rollback.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M8.4 — Testy end-to-end, bezpieczeństwa, regresji, CI i skan sekretów.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

#### M8.5 — Instrukcja uruchomienia Windows i checklista testów w środę; wyraźne oddzielenie demo/production.
- **Status:** TODO
- **Rozpoczęto / aktualizacja UTC:** —
- **Kryterium akceptacji:** działająca, udokumentowana implementacja lub potwierdzony audyt; testy adekwatne do zadania.
- **Wykonano / dowody (pliki, commit):** —
- **Testy (komenda, wynik):** NOT_RUN
- **Blokady / dalsze kroki:** —

## Wymagane przykładowe scenariusze E2E

- „Jakie samochody mam jutro?” -> realny odczyt AutoLogiki lub jawny mock.
- „Dodaj notatkę do zlecenia Peugeota” -> podgląd, autoryzacja, zapis, audyt.
- „Włącz światło w salonie na 30% i wyłącz za godzinę” -> Home Assistant + reguła n8n, potwierdzony stan.
- „Otwórz bramę” -> brak wykonania bez niezależnego potwierdzenia; symulator i czujnik stanu.
- „Od jutra przypominaj o częściach po 10” -> propozycja, walidacja, zapis wersji, rollback.
- Klient dzwoni poza godzinami -> zbierz wiadomość; pilne eskalacje tylko według ustawionych reguł.
- Brak Twilio/Meta -> reszta systemu działa; funkcje telefoniczne jawnie niedostępne.

## Dziennik realizacji (dopisywać chronologicznie)

| Data UTC | Zadanie | Zmiana i dowody | Testy | Commit | Następny krok |
|---|---|---|---|---|---|
| 2026-10-22T19:35:21+00:00 | M0.1 VERIFIED | Potwierdzony audyt istniejącego Core0.8.4/schema11 i luk wobec M0–M8: docs/audits/M0-1-CURRENT-STATE.md. Pobrano plan z a8b5ee8, połączono historię origin z lokalnym kodem, zsynchronizowano TXT/MD; AGENTS.md, 00_START_HERE.md, README.md, PROJECT_STATUS.json, docs/NEXT_TASKS.md. Dawny wpis blokady zachowano w docs/history/JARVIS_MASTER_PLAN-before-import.md. Commit: bieżący wpis M0.1 w Git. | PASS .venv/bin/python -m pytest -q:276 (22.40s); PASS pip check; PASS node --check 7plików i 8 skryptów check_* UI; NOT_RUN nowy browser/Windows/Docker/model/hardware. | bieżący commit wpisu M0.1; historia Git | M0.2 |
| 2026-10-22T19:40:43+00:00 | M0.2 VERIFIED | Ponowny statyczny audyt publicznego HEAD681f7f5;8/8 starych i9 dodatkowych hashy, schema18,57 nazw tabel,262 IPC,52pliki testowe. Raport docs/audits/M0-2-AUTOLOGIKA.md, dowody docs/audits/M0-2-evidence.json; korekta opisu importu w audycieM0.1. Bez instalacji/wykonania AutoLogiki,SQL,Supabase. Commit: bieżący M0.2. | PASS git ls-remote HEAD; PASS SHA25617plików; PASS JSON i git diff --check. NOT_RUN testy/aplikacja/upstream/RLS na produkcji. | bieżący commit wpisu M0.2; historia Git | M0.3 |
| 2026-10-22T19:41:43+00:00 | M0.3 VERIFIED | Kontrakt docs/contracts/AUTOLOGIKA.md i autologika-http.json:9 źródłowych tras, tylko2GET w adapterze, zakresy HTTP/IPC/snapshot/Supabase, mapowanie8domen i braki diagnostyki/QC/zapisów. Bez wymyślania tabel/endpoints i zmian upstream. Commit: bieżący M0.3. | PASS pytest tests/test_autologika.py tests/test_workshop.py:22 (1.41s), syntetyczne HTTP/SQLite; PASS JSON i git diff --check; NOT_RUN produkcja/RLS. | bieżący commit wpisu M0.3; historia Git | M0.4 |
| 2026-10-22T19:42:39+00:00 | M0.4 VERIFIED | Potwierdzono osobny monorepoJARVIS i istniejące moduły; dodano docs/adr/0010-master-plan-architecture.md oraz aktualizacje docs/DECISIONS.md, docs/ARCHITEKTURA.md. Etapowa migracjaReact/TS i Postgres, izolacja integracji, bezpieczeństwo i koszty; zachowano45zadań. Commit: bieżący M0.4. | PASS git root/remote i obecność modułów; PASS45ID i zgodnośćTXT/MD; PASS git diff --check. NOT_RUN nowe testy runtime, brak zmian kodu. | bieżący commit wpisu M0.4; historia Git | M0.5 |
| 2026-10-22T19:46:34+00:00 | M0.5 VERIFIED | Graf45zadań JARVIS_MASTER_DEPENDENCIES.json i walidator scripts/check_master_plan.py z25testami tests/test_master_plan.py; docs/TEST-STRATEGY.md i docs/WINDOWS-CHECKLIST.md; reguły w docs/DECISIONS.md, CI i cloud_setup.py. Zachowano45oryginalnych definicji, brak cykli, wybór następnego M1.1. Commit: bieżący M0.5. | PASS pytest -q:301 (23.95s), w tym25testów walidatora; PASS pip check; PASS python3 scripts/check_master_plan.py; PASS zachowane45nagłówków i git diff --check. NOT_RUN Windows/WSL2/sprzęt; Dockerdaemon dostępny, build nieuruchomiony. | bieżący commit wpisu M0.5; historia Git | M1.1 |
| 2026-10-23T05:31:52+00:00 | M1.1 VERIFIED | Core0.8.5: wspólny APIRouter/api/v1 i/api w jarvis/main.py; montowane audio_sessions.py/memory_policy.py/telephony_transport.py zachowują zgodność i wspólne magazyny; body_limit.py oba prefiksy. runtime_config.py: env/SecretStr/read-only readiness. Testy test_api_versioning.py(14) i test_runtime_config.py(38), .env.example, docs/API.md, RAPORT/handoff/status/start/README/CHANGELOG. Schema11 bez migracji. Commit: bieżący M1.1. | PASS .venv/bin/python -m pytest -q:353 (45.67s); PASS pip check, node --check i kontrolowaneJS; PASS Chromium transport13żądań/390px i voice2tury/zasoby zamknięte. NOT_RUN prawdziwe modele/Windows/Docker/sprzęt/CI. | bieżący commit wpisu M1.1; historia Git | M1.2 |
| 2026-10-23T05:44:38+00:00 | M1.2 VERIFIED | Dockerfile:readinesshealthcheck, nie-root, opcjonalnyCAsecret; compose.yaml:timeoutenv. scripts/check_docker.py:izolowanyUUIDprojekt/port/wolumen, syntetycznyklucz i integracjeoff, auth/restart/413/healthy/cleanup. docs/DOCKER-WINDOWS.md, WINDOWS-CHECKLIST, .github/workflows/test.yml jobDocker, docs/evals/docker-m12.json i README/raport/handoff/changelog/status. Commit: bieżący M1.2. | PASS rzeczywisty Dockerbuild + Composebuild/up, /health+/ready,401/owner200,201+restartpersistence,413,UID10001,healthy,cleanup; wynik/imageSHA w docs/evals/docker-m12.json. Wcześniejsze FAIL helperNameError/staryport poprawione; finalPASS. PASS syntax/diff/master.353pytest=M1.1 bez powtórki. NOT_RUN Windows11/WSL2/hardware/GitHubCI. | bieżący commit wpisu M1.2; historia Git | M1.3 |
| 2026-10-23T06:03:39+00:00 | M1.3 VERIFIED | Core0.8.6/schema12: identity.py,security_api.py,security_limits.py i integracja main.py; konta/role PBKDF2, sesjeSHA256/TTL/revoke/revision, uprawnienia workshop/home/runner bez prywatnych danych, limity obuAPI/login,CORS,audytaktora. Backup11→12 i testy zachowania danych; --no-proxy-headers Docker/start.ps1/README z testemTCP. SECURITY-ACCESS/API/raport/handoff/status/changelog/start/README i docs/evals/docker-m13.json. Przegląd poprawił lookup przed publicznym probe, testmissing/corrupt. Commit: bieżący M1.3. | PASS .venv/bin/python -m pytest -q:453(60.37s); PASS pip check,7JSsyntax/8kontrolowanychskryptów; PASS rzeczywistyChromium voice2tury/cleanup i transport13żądań/390px; PASS nowyLinuxDockerbuild/Compose/auth/restart/413/non-root/healthy/cleanup. Pierwszybłędnytesttrasy i błądprobe poprawione przedfinalPASS. NOT_RUN Windows/WSL2/realnemodele/sprzęt/produkcja/CI. | bieżący commit wpisu M1.3; historia Git | M1.4 |
| 2026-10-24T07:47:42+00:00 | M1.4 VERIFIED | Core0.8.7/SQLite12 + osobny opcjonalny PostgreSQLmigration1: migrations/postgres/0001_foundation.sql, postgres_migrations.py/CLI, postgres_store.py/API/main.py. FORCE RLS/private/workshops/memberships, jawnegranty, ograniczonyruntime, subjectzsesji, revision i atomowyaudyt. Testy config/integration/API, check_postgres.py i jobCI, zależnościpsycopg; POSTGRES/API/start/status/README/raport/handoff/changelog i dowodyevals. DotychczasoweSQLite zachowane; brakprodukcji. Commit: bieżący M1.4. | PASS pytest573/24skip(61.98s) bezPG; PASS osobny realnyDockerPostgres16.15:25/0skip, RLS2users/2warsztaty, granty, claims, migracje/checksum/rollback, auditrollback, migratorbezsuper/BYPASS, restart/cleanup. PASS pipcheck,app.js syntax,diff i nowyDocker0.8.7/Compose/auth/restart/413/non-root/healthy/cleanup. Poprawiono testsslrootcert po wymaganiu user/dbname; final119configPASS. Chromium=M1.3; NOT_RUN produkcyjnySupabase/Windows/sprzęt/CI. | bieżący commit wpisu M1.4; historia Git | M1.5 |
| 2026-10-24T07:59:32+00:00 | M1.5 VERIFIED | Core0.8.8: tool_registry.py ToolSpec/Gateway, wspólny invoke/discover i GET/tools w main.py; plugins.py pełne schemaOpenAPI/MCP, duplikaty/limity/ref-regexban. Principal/scope/localreview,30s/4slots/64KiBinput/1MiBresult, cancelcleanup i metadataaudit. test_tool_registry.py(41),test_tool_transport_schemas.py(37),test_tool_api.py(6), rzeczywisty localhostSDKlab. TOOLS/API/README/start/status/raport/handoff/changelog i docker-m15.json. Bez nowej migracji i zewnętrznych skutków. Commit: bieżący M1.5. | PASS pytest657/24skip(68.97s), pipcheck,app.js syntax,diff i nowyDockerbuild/Compose/auth/restart/413/non-root/healthy/cleanup. PASS realny localhostMCP/OpenAPI; brakdispatchpo odmowie, schema/cancel/deadline/capacity/privacy/legacyconfig. Poprawiono początkowytypdiscovery i500staregoregexconfig, finalPASS. PG25testów=M1.4/Chromium=M1.3 bezpowtórki; NOT_RUN Windows/produkcja/modele/sprzęt/CI. | bieżący commit wpisu M1.5; historia Git | M2.1 |
| 2026-10-24T21:58:42+00:00 | M2.1 VERIFIED | Core0.9.0: frontend/ ReactTS/Vite source+lock+10tests, /control/ pulpit/System/loginmobile; control_ui.py bezpieczneassets i main.py,5testówbackend. DockerNodebuild/dist/notice, git/dockerignore, cloud_setup/CI/check_dockerUIassets, dedicatedbrowserfixture+Chromiumscript. CONTROL-CENTER/API/start/status/README/raport/handoff/changelog, licenses i evals/control-m21.json/PNG/docker-m21.json. Legacy15widoków zachowane, noweportyM2.2-.4 nadalTODO. Commit: bieżącyM2.1. | PASS662pytest/24skip(62.48s),pipcheck,app.js; npmci108pkg,10componentPASS(4.83s),typecheck/productionbuildPASS. PASS actualChromiumCore/login/logout/revoke/roles/privacy/CSP/focus/390px; PASS nowyDockerbuild/UIHTML-JS-CSS/Compose/auth/restart/413/non-root/healthy/cleanup. Poprawionotypytestów i dwaa11yfocusbłędy, finalPASS. NOT_RUN Windows/WSL2/Safari/iPhone/Android/sprzęt/modele/CI; PG=M1.4 bezpowtórki. | bieżący commit wpisu M2.1; historia Git | M2.2 |
| 2026-10-25T12:34:11+00:00 | M2.2 VERIFIED | Core0.9.1: frontend/src/features/chat/settings/activity, App.tsx ownernav/gate, api.ts metody/95s i40UItests. Trwałe sesje/model/history, voice readonly, propozycja→decyzja fullsettings i latest100audit; abort/sync/401/credentialcleanup, poprawka ponownego wyboru sesji. scripts/check_conversation_browser.cjs i evals/control-m22.json/4PNG/docker-m22.json; CONTROL-CENTER/API/README/start/status/raport/handoff/changelog. SQLite12/PG1 bezmigracji; legacy15 zachowane. Commit: bieżącyM2.2. | PASS pytest662/24skip74.97s,pipcheck,app.js,diff;40UItests11.59s,typecheck/build. PASS rzeczywistyChromiumCoreDEMO persistence/reload/model/HTML/voice/proposals/audit/roles/privacy/CSP/logout/revoke/401 i3widoki390px; PASS nowyDockerbuild/Composeassets/auth/restart/persistence/413/non-root/healthy/cleanup. Testylifecycle kontrolowane, preflightsettings bezCAS. NOT_RUN realnemodele/Windows/WSL2/Safari/iPhone/Android/sprzęt/CI; PG=M1.4 bezpowtórki. | bieżący commit wpisu M2.2; historia Git | M2.3 |
| 2026-10-25T12:44:17+00:00 | M2.3 VERIFIED | Core0.9.2: frontend/src/features/plugins PluginPanel/API/CSS/tests; App route/nav/owner gate i poprawka hashpo logowaniu, apiRequestPUT/40s; ignorowanie cache node_modules. Lista/status/manifest/fullconfig/reviewedreads/envname/forceddisable/enable-disable, jawny katalog i odczyt, brak autoI/O. scripts/check_plugins_browser.cjs/browser_plugins_fixture.py, evals/control-m23.json/2PNG/docker-m23.json; CONTROL-CENTER/API/README/start/status/raport/handoff/changelog. SQLite12/PG1 bezmigracji. Commit: bieżącyM2.3. | PASS pytest662/24skip64.26s,pipcheck,app.js,diff;60UItests,typecheck/build. PASS actualChromium/temporaryCore/genuine localhostHTTP: no hiddenI/O, configforce-disable/enable-disable/localcatalog/explicit authorizedGET/escapedtext/privacy/roles/CSP/390px; PASS nowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup. MCPUI controlled; SDKtransport=M1.5 i PG=M1.4 bezpowtórki. NOT_RUN usługiwłaściciela/Windows/WSL2/Safari/iPhone/Android/modele/sprzęt/CI. | bieżący commit wpisu M2.3; historia Git | M2.4 |
| 2026-10-26T03:22:07+00:00 | M2.4 VERIFIED | Core0.9.3: frontend/src/features/workshop,home,devices,automations,memory,telephony,notifications,security (API/TSX/CSS/tests), App.tsx role-aware routes i przewijana nawigacja15widoków, styles.css. Logs współdzieli ActivityPanel; legacy/laboratoria zachowane. Memory CRUD/revision/history/origins/policy/retention, automation proposal→approval/tick, telephony policy/revision/preview, security users/sessions/service tokens. scripts/browser_modules_fixture.py i check_modules_browser.cjs; evals/control-m24.json/11PNG/docker-m24.json; README/start/status/API/CONTROL-CENTER/raport/handoff/changelog. SQLite12/PG1 bez migracji. Commit: bieżący M2.4. | PASS pytest662/24skip62.62s, pipcheck/app.js/diff;128UItests46.44s,typecheck/build. ActualChromium/Core:9widoków390px, snapshot readonly5/8domen, memoryCRUD/history, separateapproval/ticknotification z kontrolowanym terminem fixture, DNDpreview, users/sessionrevoke/one-time token cleanup, reader scopes/privacy/CSP; zero outboundattempts. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Poprawiono typ testuDevices i synchronizację mobilnego menu w teście. NOT_RUN Windows/WSL2/Safari/iPhone/Android/usługiwłaściciela/modele/sprzęt/CI; PG=M1.4 bezpowtórki. | bieżący commit wpisu M2.4; historia Git | M2.5 |

| 2026-10-26T03:24:03+00:00 | M2.5 IN_PROGRESS | API przeglądu propozycji i5testów gotowe; UI/a11y pozostają do implementacji. | PASS5API/typecheck, pełna weryfikacjaM2.5 NOT_RUN | bieżący checkpointM2.5WIP | M2.5 |
| 2026-10-26T05:56:11+00:00 | M2.5 VERIFIED | Core0.9.4: features/changes/ChangesPanel.tsx,changes.css,ChangesPanel.test.tsx i API; App route/nav/owner gate i styles.css z poprawką mobilnego focusu, expanded role test. Osobny podgląd→decide/rollback, freshread/preflight bezCAS, code review_required bez wykonania, mutationerror wymagarefresh, lifecycle401/abort/keyedcredential, escapedtext i focus. scripts/check_changes_browser.cjs, evals/control-m25.json/2PNG/docker-m25.json; README/start/status/API/CONTROL-CENTER/raport/handoff/changelog. Commit: bieżącyM2.5. | PASS 139UItests,typecheck/build,pytest662/24skip87.79s,pipcheck/app.js/diff. ActualChromium/tempCore: approve+realsettingsrollback, code review bezexecution, structure16views(main/h1/labels/uniqueIDs), mobilekeyboard focus/Tabtrap/Escape/390px, privacy/CSP/owner gate. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Poprawiono browserhelper deklarację screenshot i rzeczywisty focus mobilnego menu; finalPASS. PełnyWCAG/czytnik/Safari/Windows/WSL2/telefony/modele/sprzęt/CI NOT_RUN. | bieżący commit wpisu M2.5; historia Git | M3.1 |

| 2026-10-26T06:00:52+00:00 | M3.1 IN_PROGRESS | Fundament kontraktuLLM i kosztówUSD; adaptery i podłączenie do czatu nadal niewykonane. | PASS680pytest/24skip,18kosztów,pipcheck; cloud NOT_RUN | bieżący checkpoint M3.1 WIP | M3.1 |
| 2026-10-26T06:23:57+00:00 | M3.1 VERIFIED | Core0.10.0: llm.py i llm_providers.py wspólny kontrakt/Ollama/OpenAI/CostPolicy, main.py+conversations.py integracja czatu/sesji/katalogu/settings/usageaudit;30adaptertests+18cost. Frontend typy/guards/labels/default/cloudnotice+2tests, legacyapp/voice poprawione. Env/Compose defaultsoff, LLM-PROVIDERS/API/CONTROL-CENTER/README/start/status/raport/handoff/changelog. scripts/browser_llm_fixture.py/check_llm_browser.cjs i evals/control-m31.json/2PNG/docker-m31.json. SQLite12/PG1 bezmigracji. Realnycloud/inferencja NOT_RUN; commit bieżącyM3.1. | PASS pytest710/24skip74.44s,pipcheck,JSsyntax+controlledvoice/chatmemory,diff;141UItests38.98s,typecheck/build. RealnylocalhostHTTP obu protokołów, odmowy przedI/O/budget/model/flags/secret, usage/privacy/voice/cancel/errors/JSONguards; actualChromium syntheticcloud1request/persistence/defaultapproval/contextnotice/privacy/CSP/390px. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Poprawiono pustą asercjętestu i nieprawidłowe strukturyJSON bez500; finalPASS. Prawdziwe konto/inferencja/Windows/WSL2/Safari/iPhone/Android/sprzęt/CI NOT_RUN. | bieżący commit wpisu M3.1; historia Git | M3.2 |
| 2026-10-26T06:50:59+00:00 | M3.2 VERIFIED | Core0.10.1: tool_plan.py/tool_llm.py/tool_loop.py i main.py ownerAPI/chat/tools opt-in; pełna lista przeddispatch, serwerowealiasy/args/schema/replay/limity, aktualnatożsamość/config,4tury/8calls/90s/2slots i kosztcałegoprzebiegu. tool_registry.py/plugins.py pin+auth po ostatnimdiscoveryMCP; network.py legalnequery z zachowaniemorigin/DNS/IP. tests/test_tool_plan.py/test_tool_chat.py/test_network_query.py i3transporttests; scripts/check_tool_chat.py/CI/evals/tool-chat-m32.json/docker-m32.json. TOOL-CALLING/TOOLS/LLM-PROVIDERS/API/DECISIONS/README/start/status/raport/handoff/changelog. BeznowegoGUI/privatecontext/history/zapisów; commitbieżącyM3.2. | PASS pytest767/24skip89.22s, wybranyzestaw141/8.09s,pipcheck/JSsyntax/diff,typecheck/build. GenuineTCP Core+syntetyczneOllama/OpenAI+OpenAPIquery/MCP SDK:4kombinacje2tury/1read, odmowacałejlisty,privacy/audit/cleanup. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. WstępnyFAILquerytransportu naprawiony, finalPASS; poprawne npmfrontendbuildPASS.141UI/Chromium=M3.1 iPG=M1.4 bezpowtórki. Inferencja/kontocloud/Windows/WSL2/telefony/sprzęt/GitHubCI NOT_RUN. | bieżący commit wpisu M3.2; historia Git | M3.3 |
| 2026-10-26T07:05:17+00:00 | M3.3 IN_PROGRESS | Fundament: jarvis/postgres_memory.py, migrations/postgres_memory/0001_memory.sql i osobna historia wpostgres_migrations.py; private/workshopRLS, metadataaudit/CAS/hashtrigger, pgvectorcosine/namespace/dimensions/invalidation. CLI migrate_postgres.py --memory/check_postgres.py --memory, tests/test_postgres_memory.py(15)/test_postgres_memory_integration.py(9), POSTGRES-MEMORY/POSTGRES/evals/README/raport/handoff/status. NiepodłączoneHTTP/embedding/kontekstkrótki; zadaniepozostajewtoku. BieżącycheckpointM3.3WIP. | PASS pytest782/33skip76.91s,pipcheck/diff;134walidacjiunit/configPASS;34rzeczywistePG/pgvector/0skip (25M1.4+9memory), migracje/RLS/search/revision/invalidation/atomic-audit/restart/cleanup. WstępneFAILmiejsca/SQLformat/immutableexpression poprawione przedfinalPASS. API/krótkikontekst/realneembeddingi NOT_RUN; CoreDocker/typecheck=M3.2,Chromium=M3.1 bezpowtórki. | bieżący checkpoint M3.3 WIP | M3.3 |
| 2026-10-26T07:13:32+00:00 | M3.3 IN_PROGRESS | Fundament+API: postgres_memory.py/postgres_memory_api.py/main.py, osobna migrations/postgres_memory/0001_memory.sql i historiafeature; private/workshopRLS/CAS/hashtrigger/pgvector. Owner-only opt-in/storage/memory CRUD/index/search, jawnylocalembedding i reauth poI/O, brakautoimportuSQLite/recall. CLI/check_postgres.py --memory,15walidacji+9API+13realPGmemory (z25M1.4 łącznie38); CIpostgres-memory; env/Compose,docsAPI/POSTGRES-MEMORY/POSTGRES/evals/README/raport/handoff/status. Kontekstkrótki/integracjaAI nieukończone; bieżącycheckpointM3.3API WIP. | PASS pytest791/37skip90.90s,pipcheck/JSsyntax/diff; wybranyAPI/memory/conversations33PASS4.18s;38realnePG/pgvector/API/0skip (25M1.4+13memory), actualHTTP/api/embed syntetyczny, private/workshop/revision/revocation/migracje/search/restart/cleanup. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Kontekstkrótki/integracjaAI/realnamodelinference/Windows/CI NOT_RUN; UI141/Chromium=M3.1 bezpowtórki. | bieżący checkpoint M3.3 API WIP | M3.3 |
| 2026-10-26T07:19:08+00:00 | M3.3 IN_PROGRESS | Właściciel autoryzował push aktualnego projektu do GitHub. Kod4a974eb bez zmian; źródła/testy/docs zapisane. FetchPASS,28commitów lokalnie/0zdalnych; pushFAILbrak uwierzytelnienia, gh401. Po uzyskaniu połączenia ponów bez pytania o zgodę. | PASS fetch/status/master/TXT-MD; FAIL gitpush/ghAPIauth; regresja791/37skip i38PG/API bezpowtórki | bieżący zapis publikacji | Naprawić połączenie i zweryfikować push; kodowo M3.3 |
| 2026-10-26T07:43:51+00:00 | M3.3 IN_PROGRESS — aktualizacja planu | Polecenie właściciela: odświeżono Snapshot, opis M3.3, potwierdzone commity i dowody, rozdział wyników rzeczywistych/syntetycznych, blokadę publikacji B5 i następne kroki. Zmienione JARVIS_MASTER_PLAN.txt/.md, README.md i PROJECT_STATUS.json; kod i statusy 45 zadań bez zmian. | PASS scripts/check_master_plan.py: 45 zadań, 17 VERIFIED, 1 IN_PROGRESS, 27 TODO; PASS cmp TXT/MD; PASS pytest tests/test_master_plan.py: 25 testów (0.15s); PASS git diff --check. Regresja backendu/PG/Docker bez ponowienia; zachowano poprzednie wyniki. | bieżący commit aktualizacji planu; git log -1 --format=%h | M3.3; publikacja wymaga usunięcia B5 |
| 2026-10-26T08:27:20+00:00 | M3.3 VERIFIED | Core0.10.2: postgres_context.py/postgres_context_api.py i main.py, migrations/postgres_memory/0002_context.sql; account-private sesje z immutable scope/model/TTL, ograniczony kontekst i jawne notatki, RLS/revision/sources przedLLM i zapisem, propagacja provenance, trwałyclaim/CAS/atomic-history-audit/cascade. Cloudallowcontext, obecniLLM/cost, bezSQLite/voice/customer/toolchat. postgres_memory.status feature1/2; check_postgres.py i tests/test_postgres_context.py/test_postgres_context_integration.py +7APIguards/aktualizacjaPGtestów. POSTGRES-CONTEXT/POSTGRES-MEMORY/API/DECISIONS/README/start/status/raport/handoff/changelog i evals/postgres-memory-m33.json/docker-m33.json. GUI pamięci wM3.4; commit bieżącyM3.3. | PASS .venv/bin/python -m pytest -q:810/61skip112.72s; selectedcontext/API28PASS3.64s; pipcheck/JSsyntax/diff/typecheck/build. PASS realDockerPG/pgvector62/0skip (25M1.4+13memory+24context): upgrade1→2 restrictedmigrator/vectorpreservation,RLS/lease/revision/TTL/quota/provenance/auditrollback/cascade, actualOllama/OpenAIHTTP z syntetycznymi odpowiedziami i revoke/source/membership/expiry/timeout. GenuineCoreTCP→embedding→pgvector/search→2turns/history→foreign404→sourcechange/pre-I/O409→delete PASS. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS.141UI/Chromium=M3.1 bezpowtórki; realnamodelinference/cloudaccount/GUI/Windows/sprzęt/GitHubCI NOT_RUN. | bieżący commit wpisu M3.3; historia Git | M3.4 |
| 2026-10-26T08:39:13+00:00 | M3.4 IN_PROGRESS | Fundament+API: migrations/postgres_memory/0003_versions_profiles.sql, jarvis/postgres_profiles.py/postgres_profiles_api.py i main.py; immutable snapshots notatek/profili, scopedCRUD/history i metadataaudit, historySELECTonlyruntime/FORCERLS/definerrestrictedinsert, kaskadowe usuwanie treści. postgres_memory.status wspiera1–3; check_postgres.py+test_postgres_profiles_api.py(7)/test_postgres_profiles_integration.py(7), aktualizacja wcześniejszychtestów i restrictedmigrator history. POSTGRES-PROFILES/API/README/changelog/raport/handoff/master/status/evals. Profile niepodłączone doAI i GUI, zadanieIN_PROGRESS. | PASS .venv/bin/python -m pytest -q:817/68skip103.40s;7APIguards3.30s; pipcheck/diff. PASS69realnePG/API/0skip (wcześniejsze62+7profile/version), private/workshop/read-only/history/CAS/cascade/atomicrollback, restrictedmigrator snapshots także przy kolejnych korektach, restart/cleanup. Docker/typecheck/build=M3.3,UI141/Chromium=M3.1 bezpowtórki. Pinningprofili/GUI/realnamodelinference/Windows/GitHubCI NOT_RUN. | bieżący checkpoint M3.4 WIP | M3.4:profilepin/GUI |
| 2026-10-27T07:59:26+00:00 | M3.4 VERIFIED | Core0.10.3: feature3 versions/profiles + nowa0004_session_profiles.sql; postgres_context.py/API immutable profile_ref/revision, aktualne RLS/scope przedLLM i zapisem, zmiana/usunięcie wymaga nowej sesji, stare feature2sesje zachowane. React MemoryPanel/PostgresMemoryPanel/postgresApi z private/workshop, paginacją20, CRUD/history100/CAS i osobnym potwierdzeniem usunięcia, profile/notatki jawnie do nowej sesji, cloudzgoda per tura,401/abort/credentialcleanup. Nowe testy profili i optional Chromium w check_postgres.py --memory --browser; docs/POSTGRES-PROFILES/API/CONTEXT/CONTROL-CENTER/README/start/status/raport/handoff/changelog i evals. AGENTS/master: zakres tylko do końcaM3; M4 nie rozpoczynać. | PASS .venv/bin/python -m pytest -q:817/75skip141.41s; npmtest149/70.48s,typecheck/build,pipcheck/JSsyntax/diff. PASS76realnePG/API/Chromium/0skip: poprzednie69+6profilepin+1browser; actualCoreTCP/PG/LLMHTTP z syntetycznymi odpowiedziami, CRUD/history/two-turns/staleprofile,390px/desktop/privacy/logout. Upgrade1→2→4 ograniczonym migratorem zachowuje wektory i wcześniejszą sesję. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. WstępneFAILrowlockreadonly/etykietybrowser/testasercja poprawione; finalPASS. Realna inferencja/cloudaccount/Windows/sprzęt/GitHubCI NOT_RUN. | bieżący commit wpisu M3.4; historia Git | M3.5 |
| 2026-10-27T08:15:42+00:00 | M3.5 VERIFIED | Core0.10.4: jarvis/ai_tasks.py owner-private RAMTaskManager i main.py API POST/chat/tasks,GET/{id},POST/{id}/cancel.1–4jawneetapy przez istniejący ToolLoop/ToolGateway; currentauth/config/schema i cancellation przy ostatniejgranicy dispatch, provenance poprzednichodpowiedzi, wspólnyrezerwowanybudżetOpenAI przezwszystkieetapy. UUIDidempotency perkonto/15min,2active/32records/180s/128KiB/16KiBcontext, cleanupTTL/lifespan i bezpiecznemetadataaudit/error; brakwznowienia po restarcie/produkcji/zapisów. Taskvalidation422 bez echo/Unicode500.26nowychtests/test_ai_tasks.py, scripts/check_tool_chat.py --tasks i jobCI; docs/AI-TASKS/API/TOOLS/DECISIONS/README/start/status/raport/handoff/changelog/master/evals. M3 zakończone; zgodnie z poleceniem STOP przedM4, wszystkieM4TODO. | PASS .venv/bin/python -m pytest -q:843/75skip128.17s; pipcheck/JSsyntax/diff/typecheck/build. PASS genuineTCP Core/Ollama/OpenAI/OpenAPI/MCP SDK:4kombinacjepo2etapy,26providerPOST/6HTTPread/6MCPread zsyntetycznymiodpowiedziami, idempotentreplaybezI/O, cancelpodczasHTTPprzeddispatch, privacy. Unit/API: cancelmodel/discovery/read i dostawcatłumiącycancel,role/revoke/capacity/TTL/timeout/shutdown/rozmiary/Unicode/config/budgetcałegozadania; stareM3.2bezregresji. PASS76realnePG/API/Chromium/0skip po integracjiM3.5, frontendUI149=M3.4 bezpowtórki; buildponowiony. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. WstępneFAILimportenabled/oczekiwany409/Unicode naprawione; finalPASS. Realnainferencja/cloudaccount/Windows/sprzęt/GitHubCI NOT_RUN. | bieżący commit wpisu M3.5; historia Git | STOP po M3 |

| 2026-10-28T14:16:39+00:00 | Publikacja IN_PROGRESS | Import snapshotu 5aba06c (379 plików), zachowana historia origin; poprawki przenośności 3 testów, README/status/ignore. docs/audits/GITHUB-SYNC-2026-10-28.md. | Manifest/149UI/build/protokoły/JS/pip/plan PASS; końcowy backend843PASS/75skip/0FAIL220.45s. | bieżący commit importu | push, weryfikacja HEAD, zamknięcie B5; STOP po M3 |

| 2026-10-28T14:20:39+00:00 | Publikacja VERIFIED | git push origin main PASS; ls-remote potwierdza 8cf20683525bdaeb20192e604d2cf881ce4afb1f. Zamknięto B5, README/status/handoff/raport/master zaktualizowane. | Źródła843pytest/75skip,149UI/build/protokoły/JS/pip/plan PASS; dokumentacja: plan25testów i diff. | źródła8cf2068; bieżący commit zamknięcia B5 | STOP po M3 |

| 2026-10-28T14:58:29+00:00 | Instalator Windows VERIFIED (osobna dostawa) | Samowystarczalny per-user x64, localhost launcher, prywatny klucz/dane, skróty i uninstall. README/docs/WINDOWS-INSTALLER.md, scripts/windows_launcher.py/build_windows_installer.py/check_windows_installer.py, packaging/windows/jarvis.iss. | PASS847pytest/75skip,pipcheck/build,instalacja/reinstalacja/API/assets/Tk/restart/uninstall z zachowaniem danych; visual NOT_RUN | bieżący commit instalatora | odbiór lokalnego panelu; M4 STOP |

## Blokady i decyzje użytkownika

| ID | Blokada / pytanie | Co można robić mimo blokady | Status |
|---|---|---|---|
| B1 | Brak lokalnego PC do środy | Kod, testy CI, mocki, dokumentacja | OPEN |
| B2 | Brak kont Twilio i Meta Business | Adapter i webhook testowy bez prawdziwych rozmów | OPEN |
| B3 | Nieznany model centrali bramy i oświetlenia | Symulatory, interfejsy i polityki bezpieczeństwa | OPEN |
| B4 | Publiczne źródła AutoLogika odczytano w M0.2 (681f7f5),17hashy potwierdzono; brak instalacji/danych produkcyjnych | Adapter readonly i kontrakty lab, bez zmian AutoLogiki/Supabase | SOURCE_AUDIT_CLOSED; LIVE_OPEN |
| B5 | Publikacja źródeł potwierdzona 2026-10-28T14:20:39+00:00: git push origin main PASS, zdalny HEAD=8cf20683525bdaeb20192e604d2cf881ce4afb1f. | Zgoda i uwierzytelnienie potwierdzone; import snapshotu bez odtworzenia brakujących commitów. STOP po M3. | CLOSED |

## Następny krok

**STOP — zakończono M3.1–M3.5.** Właściciel 2026-10-27 ograniczył zlecenie do końcaM3. Nie rozpoczynaj M4 ani późniejszych etapów. Wszystkie zadaniaM4 zachowująTODO. Następne prace wymagają nowego polecenia właściciela; nie jest to blokada techniczna ani fałszywy statusBLOCKED. Publikacja GitHub została potwierdzona 28.10.2026; B5 zamknięta, historia zdalna zachowana. Brak historii źródłowej ZIP opisano w raporcie synchronizacji.

## Instrukcja uruchomienia agenta (do wklejenia Codex)

**Bieżący limit właściciela ma pierwszeństwo nad ogólnym promptem poniżej: M3 ukończone, STOP przed M4.**

> Przeczytaj `JARVIS_MASTER_PLAN.md` i traktuj go jako nadrzędną instrukcję oraz jedyny dziennik postępu. Wykonuj zadania M0–M8 kolejno, aktualizując status, dowody, testy, Snapshot, Dziennik i Następny krok w tym samym pliku po KAŻDYM zadaniu. Nie kończ na planie; twórz kod i testy. Nie zmieniaj produkcyjnej AutoLogiki, Supabase ani urządzeń. Kontynuuj od pierwszego niewykonanego zadania. Jeżeli czegoś nie da się wykonać, oznacz BLOCKED, opisz przyczynę i realizuj następne niezależne zadanie.

## Synchronizacja GitHub 2026-10-28 — VERIFIED

Plan: import 379 plików zweryfikowanego manifestu 5aba06c na istniejącą historię origin/main, kontrole i push bez force, następnie zamknięcie B5 dopiero po potwierdzeniu zdalnego HEAD. Kryterium: opublikowane źródła/testy/migracje/dokumentacja, brak sekretów i zgodność HEAD. Dostarczono snapshot ZIP bez .git/bundle; historyczne commity nie są dostępne i nie zostaną odtworzone sztucznie. M4+ poza zakresem.

Kontrole przed push: 843pytest PASS/75skip/0FAIL (220.45 s),149UI PASS,typecheck/build,task-protocols,pip,JS,plan i git diff --check PASS. Pierwsze trzy błędy przenośności testów Windows poprawiono, pełny backend powtórzono. Nie powtarzano lokalnie PG/Docker/Chromium.

Wynik publikacji 2026-10-28T14:20:39+00:00: źródła 8cf20683525bdaeb20192e604d2cf881ce4afb1f opublikowane i potwierdzone przez git ls-remote. B5 CLOSED. Bieżący commit dokumentacji wymaga osobnego push, zgodnie z poleceniem właściciela; po nim końcowy HEAD sprawdzany zdalnie.

## Instalator Windows — VERIFIED (2026-10-28T14:44:51+00:00)

Nowe polecenie właściciela: dostarczyć instalator i możliwość obejrzenia obecnego interfejsu. Osobne zadanie dystrybucji 0.10.4; nie rozpoczyna M4 i nie oznacza całego M8 jako ukończonego. Plan: samowystarczalny runtime Python3.12 + dependencies + frontend/dist, launcher localhost, prywatny katalog danych/klucz, skróty i deinstalator. Kryteria: kompilacja instalatora, izolowana instalacja/uruchomienie/API/assets/restart/persistence/uninstall, testy launchera, zachowanie danych.

Wynik 2026-10-28T14:58:29+00:00: instalator x64 offline 28 223 337 bajtów, SHA256 2b58ceff9f0558054c0231f8c7781520b3ed32765db4f4b5f78527d33e9b660a. scripts/build_windows_installer.py + packaging/windows/jarvis.iss, launcher i testy; dowód docs/evals/windows-installer-0104.json. PASS rzeczywista instalacja/reinstalacja/runtime/API/assets/restart/retencja danych/deinstalacja oraz Tk lifecycle/browser handoff/early close; pełna regresja847PASS/75skip258.56s,pipcheck/build. Kontrola wizualna NOT_RUN: narzędzie UI nie inicjalizuje się. Certyfikat podpisu instalatora niedostępny; plik niepodpisany. M4+ nie rozpoczęto, statusy45zadań bez zmian. Następne: instalacja i odbiór panelu przez właściciela, potem osobno konfiguracja modelu/PG.
