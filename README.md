# JARVIS OS · 0.10.4

## Instalator Windows — obecna wersja M3

[Pobierz instalator i SHA-256](https://github.com/endiszyd-rgb/JARVIS-OS/releases/tag/v0.10.4-windows.1). Samowystarczalny `JARVIS-OS-0.10.4-Setup-x64.exe`: Windows 10/11 x64, instalacja dla bieżącego użytkownika, Python3.12/zależności i zbudowany panel React w paczce. Nie wymaga osobnego Dockera, Node ani Pythona. Skrót **JARVIS OS** uruchamia lokalny serwer i otwiera `/control/` w przeglądarce. W oknie startowym kliknij **Kopiuj klucz dostępu**, następnie w panelu wybierz **Klucz właściciela** i wklej klucz.

Dane i unikalny klucz są poza katalogiem programu; restart/aktualizacja/deinstalacja zachowują dane. Program nie startuje automatycznie z Windows. Zamknięcie okna startowego zatrzymuje serwer. [Instrukcja instalacji, konfiguracji, usuwania i budowania](docs/WINDOWS-INSTALLER.md). Instalator nie jest podpisany cyfrowo; do pobrania dołączona jest suma SHA-256.

To dystrybucja ukończonego M3 na nowe polecenie właściciela, bez rozpoczęcia integracji M4 ani deklaracji ukończenia M8. Pamięć SQLite i model DEMO działają lokalnie; PostgreSQL/pgvector i rzeczywiste modele są osobną konfiguracją, nie częścią instalatora. Operator i urządzenia nie są aktywowane.

Weryfikacja końcowej paczki: PASS instalacja/reinstalacja, rzeczywisty zainstalowany runtime/API/JS/CSS, restart i zachowanie bazy/klucza, Tk lifecycle (także natychmiastowe zamknięcie) oraz deinstalacja bez usuwania danych. Pełna regresja: **847 PASS / 75 skip (258.56 s)**; pip check i nowy build UI PASS. Testy konfiguracji:4 PASS. Szczegółowy dowód zainstalowanej paczki: [windows-installer-0104.json](docs/evals/windows-installer-0104.json). Sprawdzenie wizualne przez narzędzie Windows niedostępne (błąd inicjalizacji); test Tk weryfikuje cykl okna, przekazanie adresu przeglądarce i zatrzymanie.

**Plan nadrzędny:** [JARVIS_MASTER_PLAN.txt](JARVIS_MASTER_PLAN.txt) i identyczny [dziennik MD](JARVIS_MASTER_PLAN.md) zawierają 45 zadań M0–M8 oraz bieżący postęp. Plan pobrano z GitHub (źródło a8b5ee8); historyczna kolejka R01–R07 pozostaje materiałem pomocniczym. Po każdym zadaniu oba pliki, README i kod trafiają do tego samego commitu.

Bieżąca sesja planu:

| Zadanie | Zmiana | Weryfikacja |
|---|---|---|
| M0.1 | [Audyt stanu MVP i braków](docs/audits/M0-1-CURRENT-STATE.md), import planu | PASS276pytest, pip check, JS; bez testu produkcji |
| M0.2 | [Aktualny audyt AutoLogika](docs/audits/M0-2-AUTOLOGIKA.md) | PASS17hashy źródeł; upstream/Supabase NOT_RUN |
| M0.3 | [Potwierdzone kontrakty i braki](docs/contracts/AUTOLOGIKA.md) | PASS22testy readonly/snapshot; produkcja/RLS NOT_RUN |
| M0.4 | [ADR010 i osobny monorepo](docs/adr/0010-master-plan-architecture.md), bezpieczeństwo/koszty | PASS Git/root/45ID; runtime bez zmian |
| M0.5 | [Graf zależności](JARVIS_MASTER_DEPENDENCIES.json), walidator/CI, [strategia testów](docs/TEST-STRATEGY.md), [Windows checklist](docs/WINDOWS-CHECKLIST.md) | PASS301pytest (25walidatora), pip check, graf/TXT/MD; Windows i buildDocker NOT_RUN |
| M1.1 | Wspólne `/api/v1` i `/api`, publiczne `/ready`, walidacja konfiguracji Core i maskowany klucz | PASS353pytest, pip check, JS i oba Chromium syntetyczne; modele/sprzęt/Windows/Docker NOT_RUN |
| M1.2 | Docker HEALTHCHECK→ready, timeoutenv, BuildKitCAsecret, izolowany [Compose smoke](scripts/check_docker.py), [Windows/WSL2](docs/DOCKER-WINDOWS.md), jobCI | PASS rzeczywisty Linuxbuild/Compose/auth/restart/413/non-root/healthy/cleanup; Windows/WSL2 i GitHubCI NOT_RUN |
| M1.3 | Lokalne konta/role, sesje z odwołaniem, limity API/login, jawny CORS i audyt aktora; [instrukcja dostępu](docs/SECURITY-ACCESS.md) | PASS453pytest, pip check, JS, Chromium głos/transport i nowy Dockerbuild/Compose; Windows i produkcja NOT_RUN |
| M1.4 | Opcjonalny PostgreSQL: migracje/checksum, RLS, ograniczony runtime i API rekordów; [instrukcja](docs/POSTGRES.md) | PASS573pytest/24skip bez PG; osobno25 realnych testów PG/0skip, nowy Dockerbuild/Compose; Supabase i Windows NOT_RUN |
| M1.5 | Wspólny [rejestr i polityki narzędzi](docs/TOOLS.md), schematy DEMO/OpenAPI/MCP, bounded invoke i katalog bez sieci | PASS657pytest/24skip, realny localhost SDK MCP/OpenAPI i nowy Docker/Compose; produkcja i CI NOT_RUN |
| M2.1 | [React/TypeScript Control Center](docs/CONTROL-CENTER.md): pulpit, System, logowanie i układ mobilny pod `/control/` | PASS662pytest/24skip,10komponentów,typecheck/build,Chromium390px i nowyDocker/Compose; Windows i urządzenia NOT_RUN |
| M2.2 | Rozmowy/sesje i wybór modelu, ustawienia z osobnym zatwierdzeniem, ostatnie100 zdarzeń w React | PASS662pytest/24skip,40testówUI/typecheck/build, rzeczywistyChromiumDEMO390px i nowyDocker/Compose; modele i sprzęt NOT_RUN |
| M2.3 | Plugin Manager: status, manifesty, konfiguracja, zatwierdzone odczyty, enable/disable i jawny test transportu | PASS662pytest/24skip,60UI/typecheck/build, Chromium z prawdziwym lokalnym HTTP i Docker/Compose; usługi właściciela NOT_RUN |
| M2.4 | Dziewięć widoków modułów, role odczytu domu/warsztatu, pamięć/telefonia/bezpieczeństwo i lokalne przypomnienia | PASS662pytest/24skip,128UI/typecheck/build, Chromium9widoków390px i Docker/Compose; sprzęt/usługi właściciela NOT_RUN |
| M2.5 | Zmiany i zgody: podgląd, osobna decyzja, rollback; testy dostępności i klawiatury | PASS139UI/typecheck/build,662pytest/24skip,Chromium16widoków/390px i Docker; pełnyWCAG/czytnik/Safari NOT_RUN |
| M3.1 | Wspólni dostawcy Ollama/OpenAI, konfiguracja i kontrola kosztu przed I/O; integracja z czatem/GUI | PASS710pytest/24skip,141UI/build, rzeczywisty lokalny HTTP/Chromium/Docker; prawdziwe konto i inferencja NOT_RUN |
| M3.2 | Oddzielna pętla odczytów Ollama/OpenAI→ToolGateway: wybór narzędzi, schematy, limity, aktualna autoryzacja i koszt całego przebiegu | PASS767pytest/24skip, rzeczywisty TCP Core/oba protokoły/OpenAPI/MCP SDK, typecheck/build i Docker; inferencja NOT_RUN |
| M3.3 | Pamięć PG/pgvector i prywatne sesje AI: zakresy, TTL, rewizje/lease, jawny kontekst notatek | PASS810pytest/61skip,62realnePG/API/0skip, pełny TCP Core/embedding/LLM i nowyDocker; realna inferencja/GUI NOT_RUN |
| M3.4 | Profile przypięte do sesji AI, historia rewizji i panel pamięci PostgreSQL z CAS/RLS | PASS817pytest/75skip,149UI/build,76realnePG/API/Chromium,nowyDocker; inferencja NOT_RUN |
| M3.5 | [Wieloetapowe zadania AI](docs/AI-TASKS.md), status/cancel/idempotency i wspólny budżet | PASS843pytest/75skip,4genuine2-stepkombinacje,76PG/browser i nowyDocker/build; realna inferencja NOT_RUN |


**Przejęcie przez Codexa:** zacznij od [00_START_HERE.md](00_START_HERE.md), a gotowe zlecenie znajdziesz w [PROMPT_CODEX.md](PROMPT_CODEX.md). Maszynowy stan: [PROJECT_STATUS.json](PROJECT_STATUS.json). To istniejący projekt do rozwijania, nie szablon do napisania od nowa.


Osobisty, modułowy asystent dla Andreasa, zintegrowany z AutoLogika OS. Lokalny projekt Python/FastAPI + SQLite + Control Center. Rozwija starter 0.1 oraz wersje 0.2–0.3. **To nadal MVP** — wbudowane adaptery DEMO są oddzielone od rzeczywistych odczytów.

Aktualny stan: **20/45 VERIFIED; całe M3 ukończone. Zatrzymano pracę przed M4 zgodnie z poleceniem właściciela.** Szczegóły i ograniczenia w masterTXT/MD.

## Synchronizacja GitHub — 28.10.2026

Zaimportowano zweryfikowany snapshot 0.10.4 z manifestem źródła `5aba06cf52334454d65522a8fd4161c1a0cd1403` (379 plików). Import rozwija istniejącą historię `origin/main` od `a8b5ee8`; nie nadpisuje zdalnej historii. Dostarczony ZIP nie zawiera `.git`, a bundle nie jest dostępny: źródłowy hash dokumentuje pochodzenie, ale sam commit i jego lokalni przodkowie nie zostali odzyskani. Oryginalna paczka pozostaje bez zmian.

**Publikacja źródeł potwierdzona; B5 zamknięta.** Zwykły push do `origin/main` opublikował `8cf20683525bdaeb20192e604d2cf881ce4afb1f`; `git ls-remote` potwierdził identyczny zdalny HEAD. Bieżąca aktualizacja dokumentacji zapisuje ten dowód i zamyka blokadę. Świeże kontrole: 149 UI PASS, typecheck/build, protokoły zadań, pip check, JS i walidator planu PASS. Poprawiono trzy testy nieprzenośne na Windows; końcowa regresja backendu: **843 PASS / 75 skip / 0 FAIL (220.45 s)**. [Pełny raport przejęcia](docs/audits/GITHUB-SYNC-2026-10-28.md); wyniki etapów z 27.10 są historyczne. M4 i późniejsze etapy nie zostały rozpoczęte.

## Aktualny etap 0.10.4 — koniec M3

Właścicielskie API `/api/v1/chat/tasks` wykonuje1–4jawne etapy na dotychczasowej pętli odczytów. Ma status postępu, anulowanie, idempotencję per konto, limity czasu/RAM i wspólny budżet całego zadania. Każde wywołanie ponownie sprawdza uprawnienia i konfigurację, również przed ostatnim dispatch. Poprzednie wyniki są niezaufanymi danymi. Bez kodu, zapisów, sterowania i prywatnej pamięci w kontekście zadań. [Kontrakt i przykład](docs/AI-TASKS.md).

Zadania działają w pamięci jednego procesu. Wyniki wygasają900s po zakończeniu; RAM jest czyszczony przy kolejnym użyciu rejestru lub zamknięciu procesu. Nie ma trwałej kolejki ani automatycznego wznowienia po restarcie. Anulowanie nie cofa już wykonanych odczytów lub kosztu wysłanego żądania. Wyniki nieudanych/anulowanych przebiegów są czyszczone; audyt zawiera metadane. Funkcja jest opt-in i dostępna przez API, bez nowego panelu zadań.

Pamięć → „Pamięć i profile PostgreSQL” nadal obsługuje CRUD/history/CAS, potwierdzenie usunięcia oraz profil i0–5notatek do osobnej rozmowy. Profil/revision i zakres są stałe, zmiana źródła wymaga nowej sesji. Cloud wymaga zgody per tura. [Profile i GUI](docs/POSTGRES-PROFILES.md), [kontekst](docs/POSTGRES-CONTEXT.md). PGfeature4 wymaga jawnej migracji; SQLite12 i PGfoundation1 bez zmian.

**843pytest PASS/75skip (128.17s),76realnePG/API/Chromium PASS/0skip**, pipcheck/JSsyntax i nowy typecheck/build oraz Docker/Compose PASS.149UI=M3.4 bezpowtórki. [Dowód zadań](docs/evals/ai-tasks-m35.json):26POST modeli,6odczytówOpenAPI,6MCP; cztery kombinacje po dwa etapy i cancel przed odczytem. [PG/browser](docs/evals/postgres-m35.json), [Docker](docs/evals/docker-m35.json). Modele odpowiadają syntetycznie; realna inferencja/konto cloud, Windows/telefony/sprzęt/GitHubCI NOT_RUN. Publikację potwierdzono 28.10.2026; B5 zamknięta.

## Historia: checkpoint M3.4 przed ukończeniem

Dodano optional featuremigration3 oraz owner API profili instrukcji i historii notatek/profili. Zachowane wersje są odseparowane przez bieżące RLS; runtime nie może ich bezpośrednio zmieniać, a usunięcie rodzica usuwa również ich treści. Metadane audytu pozostają. [Zakres i ograniczenia](docs/POSTGRES-PROFILES.md).

**817pytest PASS/68skip** (103.40s), pipcheck i **69testów rzeczywistego PostgreSQL/API PASS/0skip**; [dowód](docs/evals/postgres-profiles-m34-foundation.json). Sprawdzono m.in. historię i CAS, private/workshop/read-only, atomowy rollback, usuwanie wersji oraz działanie triggerów ograniczonego migratora. Nowe profile są przechowywane, lecz nie są jeszcze przypinane do sesji AI ani dostępne w nowym GUI. **W tym historycznym checkpoincie M3.4 by?o IN_PROGRESS,18/45VERIFIED; obecnie M3.4 jest uko?czone, jak opisano powy?ej**. Docker/typecheck/build=M3.3, UI141/Chromium=M3.1 bez powtórki w tym checkpoincie; realna inferencja/Windows/produkcja NOT_RUN.

## Poprzedni etap 0.8.4 — transport telefonii i interfejs laboratorium

Nowa zakładka **Transport · laboratorium** rozdziela kanał klienta, prywatny briefing i decyzję właściciela oraz kolejkę komend symulacji. Można utworzyć rozmowę, przejść przez pierwszą prośbę/naleganie, dostarczyć briefing, przyjąć lub odrzucić kontakt, zasymulować most, rozłączyć i usunąć zakończony test. Poprawiono szerokość listy rozmów na małym ekranie i aktualizację jej statusu.

Backend zapisuje zdarzenia i komendy atomowo z recepcją. Ma rewizje, idempotencję, limity czasu/tur/prób i symulowanego kosztu. Akceptacja dotyczy bieżącej próby, wymaga dostarczonego briefingu i ponownie sprawdza godziny/DND/urlop; dostępność jest sprawdzana jeszcze raz przed mostem. Odmowa, timeout i awaria kończą próbę bez ponawiania. Token klienta daje dostęp tylko do jednej rozmowy, jest przechowywany jako skrót i nie zastępuje klucza właściciela. Migracja **10→11** tworzy kopię i zachowuje recepcję, pamięć oraz historie text/voice.

Komendy dostarcza się **ręcznie** przyciskiem „Dostarcz komendy · symulacja”. Terminy są rozliczane przy odczycie lub zdarzeniu, bez procesu działającego w tle. Klient przyjmuje tekst; laboratorium rozpoznaje tylko trzy pełne, jawne frazy testowe. Nie podłączono operatora, PSTN/SIP, telefonicznego audio ani realnej analizy AI do tego transportu. [Kontrakt, instrukcja i ograniczenia](docs/TRANSPORT-TELEFONII.md).

Sprawdzenia: **276 testów Python 3.12**, pip check, składnia 7 plików JS, 6 kontrolowanych sprawdzeń panelu transportu oraz regresja dotychczasowych testów JS. **Rzeczywisty Chromium** z tymczasową bazą i syntetycznymi danymi przeszedł pełną ścieżkę transportu, izolację żądań klienta, nawigację/wylogowanie i układ przy szerokości 390 px. Ponownie sprawdzono głos w Chromium z syntetycznym mikrofonem/usługami. To testy laboratorium, bez inferencji modeli, sprzętu i połączeń operatora; Windows, Docker i GitHub CI nie były uruchamiane.

R03 zachowuje ręczną rozmowę półdupleksową: AudioWorklet/PCM → Wyoming STT → domyślny przegląd transkrypcji → osobny czat voice → TTS. Głos nie wykonuje parsera ustawień ani zapisu pamięci. [Instrukcja](docs/ROZMOWA-GLOSOWA.md). Realne modele/sprzęt, hałas, wake-word, pełny dupleks i prywatne wyjście pozostają do sprawdzenia lub realizacji.

Historycznie wskazywano R05; obecnie obowiązuje **STOP po M3**, bez rozpoczęcia M4+. Wszystkie 11 obszarów pozostają w zakresie. Każdy commit zawiera aktualizację README z jego zmianami, wykonanymi sprawdzeniami i ograniczeniami. Zmiany lokalne, bez push na GitHub.

## Szybki start na Windows

Zainstaluj Python 3.12, rozpakuj projekt do osobnego katalogu i w PowerShell uruchom:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Skrypt tworzy `.venv`, generuje klucz właściciela w `.env`, instaluje przypięte zależności, uruchamia testy i Core. Otwórz http://127.0.0.1:8000 i wklej JARVIS_API_KEY. Klucz jest tylko w pamięci karty. Nie zastępuj plików AutoLogiki tym projektem.

Linux / ręcznie:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Wstaw wygenerowany klucz do JARVIS_API_KEY w .env.
python -m pytest -q
python -m uvicorn jarvis.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

`requirements.lock` przypina także zależności pośrednie; requirements.txt używa go jako constraints. Lock nie jest audytem bezpieczeństwa ani plikiem z hashami pakietów. Wersje sprawdzono razem w izolowanym środowisku Python 3.12.

## Co działa

| Moduł | Stan |
|---|---|
| Core i Control Center | Trwała baza, panel z 15 widokami (mobilnie sprawdzono ścieżkę transportu), health i audyt |
| MCP | Streamable HTTP: sesja, discovery i wywołania sprawdzonych odczytów przez oficjalny SDK; bez OAuth/stdio |
| OpenAPI | Obsługiwany podzbiór: GET, operationId, skalarne parametry, lokalny schemat bez $ref |
| Uprawnienia | Klucz właściciela i ograniczone tokeny z datą ważności, cofnięciem i przechowywaniem skrótu |
| Home Assistant | Rzeczywisty czytnik stanów jawnie wskazanych encji; bez sterowania |
| WhatsApp | Weryfikowany webhook Twilio, inbox, deduplikacja, szkice; bez wysyłki i Calling |
| AutoLogika | Audyt 681f7f5, istniejące GET zleceń i osobny czytnik 8 domen z przygotowanej kopii schematu 18; bez zapisów |
| Rozmowa i pamięć | DEMO/Ollama, katalog modeli, trwałe sesje i historia, kontekst sesji, eksport/usuwanie i ręczna retencja; jawne podsumowanie warsztatu |
| Zmiany rozmową | „zapamiętaj …”, „ustaw imię Jan”, „przypominaj co 60 minut: Sprawdź części”; propozycje, akceptacja i rollback |
| Telefonia | Grafik/DND/urlop, recepcja i oddzielny transport laboratoryjny z prywatnym briefingiem; bez operatora |
| Automatyzacje | Lokalny tick, worker, opcjonalny n8n i nieaktywny workflow do importu |
| Operacje | Kopie SQLite z SHA-256; kopia przed migracją do schematu 0.4, Docker i testy CI do uruchomienia |

Nie zaimplementowano komend do bramy/świateł ani wysyłania wiadomości WhatsApp. Od modelu nie zależą uprawnienia i zgody. Narzędzia MCP na liście właściciela muszą być wcześniej sprawdzone — sama adnotacja serwera `readOnlyHint` nie daje uprawnień i nie dowodzi braku skutków ubocznych.

## Test integracji bez kont i urządzeń

W drugim terminalu uruchom syntetyczne laboratorium:

```bash
python -m uvicorn examples.lab_server:app --host 127.0.0.1 --port 8765
```

W panelu Integracje zarejestruj plugin z protocol `mcp` albo `openapi`, otwórz Konfiguracja i użyj odpowiedniego pliku `examples/lab.*.config.json`. Zapis wyłącza plugin: przejrzyj konfigurację, włącz go, wybierz Odkryj narzędzia i wywołaj `read_temperature` z argumentami `{}`. To prawdziwy transport do lokalnego serwera, ale dane z niego są syntetyczne. Test automatyczny robi to samo z osobnym procesem serwera na losowym porcie.

## Rozmowy i kopia warsztatu

W Rozmowie utwórz osobną sesję, wybierz model z katalogu właściciela i wracaj do historii po restarcie. Historia nieudanych zapytań jest oznaczona; nie trafia do kontekstu modelu. Można zmienić tytuł, eksportować i usunąć sesję. Katalog definiuje OLLAMA_ALLOWED_MODELS — nie instaluje modeli. Modele z końcówką :cloud wymagają dodatkowego jawnego włączenia.

Bez dostępu do warsztatu przetestuj osiem domen na syntetycznej kopii:

```bash
python -m examples.workshop_fixture
python scripts/import_autologika.py --source data/lab/autologika-fixture.db
```

Ustaw AUTOLOGIKA_SNAPSHOT_ENABLED=true w .env i zrestartuj Core. Zakładka AutoLogika · kopia pokazuje dane offline. Dla finansów laboratorium wybierz miesiąc 2026-10. Przy zaznaczeniu checkboxa w rozmowie model otrzyma agregaty finansowe/statusowe i datę kopii, bez list klientów. Pełna instrukcja, ograniczenia i import rzeczywistej bazy w środę: docs/ROZMOWY-I-WARSZTAT-v0.4.md.

## Docker

Po ustawieniu klucza właściciela w `.env`:

```bash
docker compose config
docker compose up --build -d
```

Panel pozostaje na 127.0.0.1:8000. Dane są w `jarvis-data`. Nie używaj `down -v`, jeśli mają pozostać. Do workera utwórz w panelu token `scheduler:tick`, wpisz w `.env` jako JARVIS_SCHEDULER_TOKEN, następnie `docker compose --profile automation up --build -d`. Klucz właściciela nie jest przekazywany workerowi.

Dla n8n ustaw osobny N8N_ENCRYPTION_KEY i sprawdzony aktualny N8N_IMAGE, uruchom profil n8n. Zaimportuj `examples/n8n-tick.workflow.json`, przypisz w węźle HTTP poświadczenie Header Auth: `X-Jarvis-Key` z tokenem `scheduler:tick`. Workflow jest nieaktywny i wymaga sprawdzenia w zainstalowanej wersji n8n. n8n jest source-available; sprawdź licencję dla przyszłego hostowania komercyjnego.

W kontenerze `127.0.0.1` oznacza kontener. Dla usług Windows użyj `host.docker.internal` i dodaj jego **konkretny adres lub odpowiedni wąski zakres** do JARVIS_NETWORK_ALLOWLIST. Sekrety pluginów JARVIS_PLUGIN_SECRET_* wymagają jawnego przekazania w Compose override — nie są automatycznie eksportowane z pliku `.env` do kontenera.

## Dokumentacja

- `docs/RAPORT.md` — aktualny stan, testy, wymagane konta i plan na środę 28.10.
- `docs/ROZMOWY-I-WARSZTAT-v0.4.md` — historia, modele, retencja, kopia SQLite i zakres 8 domen.
- `docs/MODULY-v0.3.md` — konfiguracja MCP/OpenAPI, sieci, HA, tokenów i WhatsApp.
- `docs/AUDYT_AUTOLOGIKA.md` i `docs/autologika-evidence.json` — rzeczywisty kontrakt AutoLogiki, commit i dowody.
- `docs/ARCHITEKTURA.md` — plan wszystkich 11 obszarów i decyzje.
- `docs/API.md` — kontrakt aktualnego Core.
- `docs/OPERACJE.md` — backup/restore, aktualizacje, Windows i telefon.
- `CHANGELOG.md` — zmiany wersji, `docs/history/` — raport poprzedniej wersji.

Nie zmodyfikowano repozytorium produkcyjnego AutoLogiki. Nie podłączono rzeczywistej instalacji warsztatu, domu ani konta Twilio. Pełne zapisy AutoLogiki, fizyczne sterowanie i połączenia WhatsApp wymagają kolejnych etapów. Kopia SQLite nie daje synchronizacji na żywo ani pełnego parytetu z ekranami desktopu.

## Historia: nowe w 0.5

Panel „Głos lokalny”: jawny upload WAV i synteza przez zewnętrzne usługi Wyoming. Tekst wymaga sprawdzenia; nie wykonuje poleceń. Panel pamięci: FTS5 i opcjonalne hybrydowe wyszukiwanie przez lokalne embeddingi Ollama. Zapis pamięci nadal ręczny; wyszukiwarka nie zmienia automatycznie kontekstu rozmów.

Konfiguracja: [Głos i pamięć](docs/GLOS-I-PAMIEC-v0.5.md). Przegląd kodu/licencji projektów: [Przegląd repozytoriów](docs/OPEN-SOURCE.md). Bieżący stan i środowy plan: [raport](docs/RAPORT.md). Wymagany Python 3.12; Wyoming 1.10.2 korzysta z audioop, usuniętego w Pythonie 3.13.

## Historia: nowe w 0.6

Zakładka Telefonia: ustawienia godzin przekazywania do właściciela, numery, urlopy, DND i podgląd przyczyn decyzji. **Bez wykonywania rozmów** — konfiguracja nie aktywuje przekierowania Play. Instrukcja: [Telefonia](docs/TELEFONIA-v0.6.md). 112 testów pytest, schemat Core 6.

## Historia: nowe w 0.7

Recepcja · laboratorium: tekstowa rozmowa, pierwsza prośba i naleganie, oczekiwanie na właściciela, symulacja przyjęcia/odmowy/nieodebrania i trwałe zgłoszenia. **Bez operatora i analizy AI** — jawne reguły testowe, bez zapisu do AutoLogiki. [Instrukcja](docs/RECEPCJA-v0.7.md). 127 testów, schemat Core 7.

## Historia: nowe w 0.8 i Codex Cloud

Opcjonalna analiza recepcji przez Ollama z JSON Schema, cytatami i uzupełnianiem danych. **Integracja zaimplementowana, jakość rzeczywistego modelu niesprawdzona.** [Instrukcja](docs/ANALIZA-RECEPCJI-v0.8.md). 147 testów; schemat7.

Przeniesienie do osobnego repozytorium i kontynuacja: [CODEX-HANDOFF](docs/CODEX-HANDOFF.md), AGENTS.md i `python3.12 scripts/cloud_setup.py`. Pakiet nie został automatycznie wysłany na GitHub ani uruchomiony w Cloud.

## Paczka przekazania

ZIP ma pliki repo bezpośrednio w głównym katalogu. HANDOFF-MANIFEST.json zawiera commit źródłowy i SHA256 dostarczonych plików. Przed pierwszą zmianą: `python3 scripts/verify_handoff.py`. Po rozpoczęciu kodowania suma zmienionego pliku naturalnie się różni; manifest nie jest podpisem ani stałym testem CI. Historia .git, sekrety, bazy i modele nie są pakowane.

Ponowne utworzenie paczki z czystego, zapisanego repo: `python3 scripts/package_handoff.py --output ../JARVIS-OS.zip`. Nie pakuj ręcznie całego katalogu roboczego z danymi.

## Historia: nowe w 0.8.2

R02: [ograniczona automatyczna pamięć](docs/PAMIEC-AUTOMATYCZNA.md) rozpoznaje całe deklaracje z zamkniętego katalogu, zachowuje źródła, deduplikuje i chroni ręczne korekty. Domyślnie tryb manual. W Rozmowie jest checkbox „Tego nie zapamiętuj”. Nie ma swobodnej ekstrakcji z modelu.

R03: [sesje i laboratorium mikrofonu](docs/SESJE-AUDIO.md) — ręczna aktywacja, anulowanie, limity czasu, zwalnianie zasobów i API stanów. Ciągłe STT/czat/TTS, wykrywanie mowy i wake-word pozostają do podłączenia.

Core schema9 z kopią przed migracją; 213 testów Python, kontrolowane testy JS i walidacja 30 przypadków recepcji. Realne AI, przeglądarka, mikrofon i urządzenia nie były sprawdzone. Zmiany lokalne, bez push na GitHub.

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
