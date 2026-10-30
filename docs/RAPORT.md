
## M4.2 — diagnostyka i odczyty warsztatu (2026-10-29)

Kopia schema18 udostępnia dodatkową domenę diagnostics: objawy, DTC, pomiary, hipotezę, wnioski, zalecenia i czas. Odczyt przez GET /api/v1/autologika/snapshot/diagnostics ma paginację, pomija usunięte zlecenia i nie modyfikuje źródła. Brak tabeli/kolumn daje503; pozostałe domeny pozostają dostępne. Panel AutoLogika udostępnia diagnostykę właścicielowi i workshop_reader; finanse/raporty/powiadomienia nadal owner-only. Terminarz, pojazdy, klienci i części pozostają odczytami offline, nie wymyślonymi trasami live.

Testy backendu adapter/snapshot:39 PASS na syntetycznych danych. Produkcja i rzeczywista synchronizacja NOT_RUN.
M4.1 pełna regresja: **861 PASS /75skip**,240.21s; pipcheckPASS.


## M4.1 — adapter AutoLogika (2026-10-29)

Właściciel autoryzował M4 i dalsze etapy. Adapter używa wyłącznie potwierdzonych GET /api/orders i /api/order/{id}; dodano limit odpowiedzi 2 MiB, całkowity deadline12s, kontrolę envelope i powiązania rekordów z order_id. GET /api/v1/autologika/capabilities wymaga workshop:read i pokazuje ograniczenia bez odpytywania usługi lub ujawniania konfiguracji. Audyt lokalnych źródeł: docs/audits/M4-AUTOLOGIKA-SOURCE.md. Brak awaryjnego przełączania live na DEMO.

Testy kontraktów i snapshot:36 PASS; pip check PASS. Produkcyjna AutoLogika/Supabase i realne urządzenia NOT_RUN. Schemat bazy i instalator HUD3 bez zmian; ten commit rozwija źródła backendu.

# JARVIS OS 0.10.4 — M3 ukończone

Dostawa Windows 28.10: instalator 0.10.4-windows.1 VERIFIED; instalacja/reinstalacja/runtime/API/assets/Tk/restart/uninstall PASS, dane zachowane. Regresja847PASS/75skip258.56s; podpis i wizualny podgląd NOT_RUN. Instrukcja: WINDOWS-INSTALLER.md, dowód evals/windows-installer-0104.json. Osobna dostawa na nowe polecenie, M4 nadal nierozpoczęte.

Aktualizacja publikacji 28.10.2026: [raport synchronizacji](audits/GITHUB-SYNC-2026-10-28.md). Snapshot zweryfikowany, brak historii .git w dostawie; publikacja źródeł 8cf20683525bdaeb20192e604d2cf881ce4afb1f potwierdzona zdalnie, B5 CLOSED. Świeże kontrole Windows:843pytest PASS/75skip,149UI/typecheck/build,protokoły zadań/JS/pip/plan PASS. Poniższe wyniki M3 pochodzą z 27.10.2026.

2026-10-27T08:15:42+00:00. **20/45 VERIFIED. M3.1–M3.5 zakończone; STOP przedM4 zgodnie z poleceniem właściciela.**

Core0.10.4: jarvis/ai_tasks.py owner-private RAMTaskManager i main.py API POST/chat/tasks,GET/{id},POST/{id}/cancel.1–4jawneetapy przez istniejący ToolLoop/ToolGateway; currentauth/config/schema i cancellation przy ostatniejgranicy dispatch, provenance poprzednichodpowiedzi, wspólnyrezerwowanybudżetOpenAI przezwszystkieetapy. UUIDidempotency perkonto/15min,2active/32records/180s/128KiB/16KiBcontext, cleanupTTL/lifespan i bezpiecznemetadataaudit/error; brakwznowienia po restarcie/produkcji/zapisów. Taskvalidation422 bez echo/Unicode500.26nowychtests/test_ai_tasks.py, scripts/check_tool_chat.py --tasks i jobCI; docs/AI-TASKS/API/TOOLS/DECISIONS/README/start/status/raport/handoff/changelog/master/evals. M3 zakończone; zgodnie z poleceniem STOP przedM4, wszystkieM4TODO.

PASS .venv/bin/python -m pytest -q:843/75skip128.17s; pipcheck/JSsyntax/diff/typecheck/build. PASS genuineTCP Core/Ollama/OpenAI/OpenAPI/MCP SDK:4kombinacjepo2etapy,26providerPOST/6HTTPread/6MCPread zsyntetycznymiodpowiedziami, idempotentreplaybezI/O, cancelpodczasHTTPprzeddispatch, privacy. Unit/API: cancelmodel/discovery/read i dostawcatłumiącycancel,role/revoke/capacity/TTL/timeout/shutdown/rozmiary/Unicode/config/budgetcałegozadania; stareM3.2bezregresji. PASS76realnePG/API/Chromium/0skip po integracjiM3.5, frontendUI149=M3.4 bezpowtórki; buildponowiony. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. WstępneFAILimportenabled/oczekiwany409/Unicode naprawione; finalPASS. Realnainferencja/cloudaccount/Windows/sprzęt/GitHubCI NOT_RUN.

Zadania są RAM-only w jednym workerze, bez wznowienia/replay po restarcie i bez osobnego GUI zadań. Anulowanie nie cofa wysłanych żądań ani kosztu. TTL900s oznacza odmowę dostępu i lazy cleanup przy kolejnym użyciu rejestru; bez ruchu RAM czyszczony przy shutdown. Szczegóły AI-TASKS.md. Pamięć/profile/panelM3.4 pozostają sprawdzone, PGfeature4/PGfoundation1/SQLite12. Nie edytuj migracji0001–0004.

Najpierw odczytaj masterTXT/MD i AGENTS. M4 pozostajeTODO; nie wybieraj go automatycznie tylko dlatego, że walidator zależności wskazuje je jako technicznie możliwe. GitHubpush potwierdzony 28.10, B5 CLOSED; brakująca historia źródłowego ZIP nie została odzyskana; produkcjaAutoLogika/Supabase bez zmian.

## JARVIS HUD — 2026-10-29

Nowy cyjanowy interfejs: pulpit z animowanym rdzeniem prowadzącym do Systemu, telemetria z API, skrót rozmowy dla właściciela, motyw logowania i paneli. Animacje wyłączają się przy prefers-reduced-motion. Role i dotychczasowe funkcje zachowane; M4 nie rozpoczęto.

Wykonano: 149 testów UI PASS, TypeScript/build PASS, node --check jarvis/app.js PASS. Rzeczywisty Chrome + izolowany Core: logowanie, role, wylogowanie/unieważnienie, brak sekretów w storage/URL, CSP, klawiatura, radar i reduced-motion PASS; 390px bez overflow. Obejrzano zrzuty desktop/mobile. Backend bez zmian, pełnej regresji backendu nie powtarzano.

Instalator HUD: wydanie v0.10.4-windows.2, wersja pakietu 0.10.4.2 (Core nadal 0.10.4). Niepodpisany; modele i integracje nie są aktywowane.

Kontrola paczki HUD: kompilacja Inno Setup PASS; dołączony Python/Core/API/assets na izolowanych danych PASS (docs/evals/windows-hud-smoke.json); 4 testy launchera PASS. Instalacja/reinstalacja/deinstalacja nowego EXE NOT_RUN: wykryto istniejącą instalację użytkownika. Poprzednie testy instalacji nie są wynikiem nowej paczki. SHA256: e0d996551441e5b397dd147bc6f4353c75152affdff07271e5e86b9d737f4686.

## HUD 3 — spójny panel rozmów (2026-10-29)

Poprawiono cyjanowe zaznaczenie aktywnej trasy (aria-current), wybranej rozmowy, wiadomości i pól formularza. Zachowano kolory ostrzeżeń i błędów. Rozszerzono scripts/check_control_browser.cjs o rzeczywiste utworzenie sesji DEMO, wysłanie wiadomości i odczyt odpowiedzi oraz układ czatu przy 390px.

Wykonano: TypeScript/build PASS; node --check jarvis/app.js i check_control_browser.cjs PASS; Chrome z tymczasowym Core PASS (25 żądań API, auth/role/CSP/klawiatura/radar/reduced-motion/rozmowa/390px). Obejrzano docs/evals/control-hud-chat.png i control-hud-chat-mobile.png. Zmiana CSS nie zmienia backendu; 149 testów UI z poprzedniej dostawy nie powtarzano. M4 nie rozpoczęto.

Pakiet Windows 0.10.4.3 (Core 0.10.4): v0.10.4-windows.3. Instalacja na istniejącej kopii użytkownika NOT_RUN; dane i rejestracja pozostają nietknięte.

Wynik paczki HUD3: Inno Setup build PASS; Python 3.12.16/API/UI z paczki na izolowanych danych PASS (docs/evals/windows-hud3-smoke.json). Instalacja nowego EXE NOT_RUN — istniejąca instalacja użytkownika. SHA256: fe268664ad0ba001289e2d40abd286ea12cfa765cfbe6683c24971bb07d28442.

## Eksperyment OpenClaw — lokalny prototyp (2026-10-30)

Zintegrowano przypięty OpenClaw `2026.10.7` jako warstwę rozmowy bez przejmowania reguł JARVIS. Plugin ma tylko dwa odczyty: ograniczony snapshot zleceń i jawnie dozwoloną encję Home Assistant. Nie ma terminala, plików hosta, Docker socket, wiadomości, zakupów ani sterowania. Token `workshop:read` jest wąski i odwoływalny; `home:read` pozostaje osobnym poświadczeniem.

Nowy test end-to-end uruchomił prawdziwy runtime pluginu i lokalne transporty HTTP z kontrolowanym serwerem modelu: odczyt warsztatu i HA PASS, źródła obecne, scope denial/revoke/unregistered operation/timeout/offline/redakcja/prompt injection PASS. Kontrolowany serwer nie wykonuje inferencji. WSL2, Docker, prawdziwy model, prawdziwy HA i produkcja `NOT_RUN`. Szczegóły: `OPENCLAW-INTEGRATION.md` oraz `evals/openclaw-prototype-2026-10-30.json`.

Regresja po integracji: backend 865 PASS / 75 skip w 227.83 s; frontend 149 PASS oraz typecheck/build; plugin 6 PASS i package dry-run; pip check, JS, py_compile i plan 45 zadań PASS.

Publikacja PASS: branch `experiment/openclaw-integration`, źródłowy checkpoint prototypu `9de7d074dadd0409630f5fd85c1517c7e8141223`; lokalny i zdalny hash były identyczne. Bez force push i bez scalenia do `main`.
