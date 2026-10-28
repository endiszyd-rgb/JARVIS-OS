# Control Center — React i TypeScript

Nowy panel działa pod `/control/`, obok dotychczasowego panelu `/`. M2.1 obejmuje pulpit, widok systemu, nawigację i logowanie. M2.2 dodaje rozmowy, ustawienia, wybór modeli i historię działań. M2.3 dodaje Plugin Manager; M2.4 dodaje pozostałe dziewięć widoków; istniejące 15 widoków pozostaje w dotychczasowym panelu. Przejście między panelami nie przekazuje tokenu przez adres URL ani magazyn przeglądarki.

## Uruchomienie

Docker buduje frontend w osobnym etapie Node, a do obrazu Core kopiuje wyłącznie wynik produkcyjny. Python, Node i npm na komputerze użytkownika nie są wymagane do tej ścieżki:

```sh
docker compose build core
docker compose up -d core
```

Otwórz `http://127.0.0.1:8000/control/`. Konfiguracja i klucz właściciela: [instrukcja Docker](DOCKER-WINDOWS.md) i [dostęp](SECURITY-ACCESS.md). Port domyślnie pozostaje ograniczony do lokalnego komputera.

Przy uruchamianiu Core bez Dockera najpierw zbuduj frontend:

```sh
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
.venv/bin/python -m uvicorn jarvis.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Potrzebny jest Node 22.12+ lub nowszy obsługiwany LTS. Na Windows użyj `.venv\Scripts\python.exe`. Brak `frontend/dist/index.html` powoduje jawne HTTP503 na nowym panelu; dotychczasowy panel i Core pozostają dostępne. Nie dodawaj `node_modules`, `dist`, danych ani `.env` do Git. Źródła i lockfile są częścią repozytorium, wynik builda powstaje lokalnie lub w Dockerze.

W środowisku z firmowym CA zachowaj proxy i weryfikację TLS; npm może wymagać `NODE_EXTRA_CA_CERTS` ze ścieżką do zaufanego bundle. Docker obsługuje opcjonalny sekret `proxy_ca` w kroku instalacji zależności, bez kopiowania certyfikatu do obrazu. Nie używaj `strict-ssl=false`.

## Dane i dostęp

Panel korzysta z kanonicznego `/api/v1`. Logowanie kontem używa istniejącego API sesji; klucz bootstrap jest oddzielną opcją. Sekret pozostaje w pamięci karty, bez `localStorage`, `sessionStorage`, cookies i URL. Odświeżenie strony wymaga ponownego połączenia. Wylogowanie sesji wywołuje serwerowe `/auth/logout`; klucz właściciela jest usuwany lokalnie, ponieważ nie jest odwoływalną sesją.

Role i autoryzacja pozostają po stronie backendu. Odmowa401 usuwa uwierzytelniony widok. Odpowiedzi rozpoczęte przed wylogowaniem nie powinny przywracać danych po zmianie tożsamości. Ograniczona rola nie otrzymuje dostępu do pamięci, rozmów ani administracji. Użycie osobnego panelu nie zmienia uprawnień urządzeń i usług.

Liczniki pulpitu oznaczają wszystkie rekordy zwracane przez `/status`. Nie są liczbą nieprzeczytanych powiadomień, oczekujących zgód ani działań dzisiejszych. Gotowość dotyczy Core, bez potwierdzania dostępności modelu, HA, operatora czy opcjonalnego PostgreSQL. Oznaczenie DEMO i wyłączone skutki pozostają jawne. Katalog nazw dostawców nie jest listą zainstalowanych modeli.

## Pliki i weryfikacja

Źródła: `frontend/`. Produkcyjne pliki serwuje `jarvis/control_ui.py`: osobny HTML i wąska trasa płaskich zasobów `/control/assets/...`. Próby przejścia do innych katalogów i symlinki poza katalogiem zasobów są odrzucane. Obowiązuje CSP z zasobami tego samego pochodzenia, bez `unsafe-inline` i zewnętrznych fontów/skryptów.

```sh
.venv/bin/python -m pytest -q tests/test_control_ui.py
node scripts/check_control_browser.cjs
```

Test przeglądarki wymaga zbudowanego UI, Playwright i lokalnego Chromium (`JARVIS_BROWSER_EXECUTABLE` może wskazać jego ścieżkę). Uruchamia tymczasowy Core z wyłączonymi integracjami i syntetycznymi kontami. Wynik Chromium nie jest testem Safari/iPhone, Androida ani sprzętu. `scripts/check_docker.py` dodatkowo sprawdza, czy rzeczywisty obraz serwuje HTML, JS i CSS nowego panelu.

Bieżące wyniki i ograniczenia zapisuje [masterplan](../JARVIS_MASTER_PLAN.md). M2.1 VERIFIED:662pytest/24skip,10komponentów,typecheck/build, rzeczywistyChromium390px i Docker/Compose PASS. Dowody: [control-m21.json](evals/control-m21.json), [Docker](evals/docker-m21.json), [desktop](evals/control-desktop.png), [mobilny](evals/control-mobile.png).

## M2.2 — rozmowy, ustawienia i historia

Właściciel otrzymuje trzy dodatkowe trasy: `#/chat`, `#/settings`, `#/activity`. Pozostałe role nie montują tych widoków ani nie odpytują ich API, również po bezpośredniej zmianie hash. Backend nadal wymaga właściciela. Wylogowanie,401 i zmiana danych dostępu usuwają prywatny stan; spóźnione odpowiedzi nie przywracają danych.

Rozmowy korzystają z istniejących `/chat`, `/chat/sessions` i `/models`. Lista ma strony po20sesji, historia po100wiadomości. Wybór DEMO/Ollama dotyczy jawnie wskazanego modelu z konfiguracji. Nie instaluje modelu ani nie sprawdza usługi. Sesje voice są tylko do odczytu. Tekst jest renderowany bez interpretacji HTML. Opcja „Nie zapisuj w pamięci” przekazuje `do_not_remember`; nie oznacza usunięcia historii rozmowy. DEMO może wykonać lokalne polecenie pamięci lub utworzyć propozycję.

Oczekiwanie na `/chat` ma95s, wobec90s backendu; zwykłe odczyty10s. Przerwanie, błąd transportu lub409/502/504 wymagają synchronizacji szczegółów i historii przed dalszym wysłaniem. Serwer może nadal pracować po przerwaniu fetch. Nie ma endpointu anulowania ani automatycznego retry.

Ustawienia są odczytywane z `/status.settings`. Podgląd tworzy propozycję pełnego `{name,tone,model}` przez `/proposals`; oddzielny przycisk wysyła `/proposals/{id}/decide`. Ponowny odczyt przed propozycją i akceptacją wykrywa zaobserwowane zmiany innego właściciela. Nie jest atomowym CAS — backend nie udostępnia rewizji ustawień. Nazwy modeli i połączenie dostawcy konfiguruje się na poziomie instalacji.

Historia korzysta z `/audit`: wyłącznie ostatnie100zdarzeń, bez deklarowania pełnego archiwum i bez fikcyjnej paginacji serwera. Filtr działa na pobranym zestawie. Szczegóły JSON i wartości wyświetlane są jako tekst.

`npm --prefix frontend test` sprawdza40przypadków UI i klientaHTTP; `node scripts/check_conversation_browser.cjs` uruchamia rzeczywisty Chromium z tymczasowym Core i DEMO. DowodyM2.2: [UI](evals/control-m22.json), [Docker](evals/docker-m22.json). Rzeczywiste modele, telefony i sprzęt pozostają NOT_RUN.

## M2.3 — Plugin Manager

Widok `#/plugins` jest przeznaczony dla właściciela. Rejestracja manifestu nie instaluje obcego kodu. Konfiguracja wskazuje endpoint, nazwy zatwierdzonych odczytów i opcjonalną nazwę zmiennej sekretu `JARVIS_PLUGIN_SECRET_...`. Nie podaje się wartości sekretu. OpenAPI wymaga lokalnego dokumentu ze wspieranego podzbioru GET; MCP używa Streamable HTTP. [Kontrakty i limity](TOOLS.md).

Zapis konfiguracji zastępuje ją w całości i wyłącza plugin. Ponowne włączenie jest osobną decyzją. Backend nie udostępnia rewizji konfiguracji ani atomowej ochrony przed równoległą edycją. `transport_ready` oznacza istnienie konfiguracji lub adapter DEMO, nie udane połączenie.

Edycja konfiguracji usuwa poprzedni katalog i wynik oraz blokuje test do zapisu. Dzięki temu widoczny projekt nowego endpointu nie jest mylony z testem starszej zapisanej konfiguracji. Odświeżenie listy zamyka edytor; bez zapisu zmiany formularza pozostają tylko w karcie.

Pobranie listy pluginów i lokalnej konfiguracji nie kontaktuje się z usługą. Odczyt narzędzi odbywa się po osobnej akcji: MCP nawiązuje połączenie, OpenAPI i DEMO odczytują lokalne definicje. Test transportu OpenAPI wymaga jawnego uruchomienia wybranego, lokalnie zatwierdzonego odczytu z argumentami. DEMO zwraca wyłącznie symulację. Nie ma automatycznego discovery, invoke ani ponawiania żądań; timeout klienta dla tych operacji wynosi40s wobec30s bramki. Przerwanie oczekiwania w przeglądarce nie stanowi potwierdzenia anulowania po stronie usługi.

Samo włączenie pluginu, pobranie lokalnego katalogu lub odpowiedź `status: blocked` nie są potwierdzeniem działającego połączenia. Nie ma interfejsu zapisu sekretów, usuwania pluginów, instalacji kodu ani zdalnych operacji zapisu. M2.3 VERIFIED:662pytest/24skip,60testówUI,typecheck/build, rzeczywisty Chromium/Core z lokalnym HTTP i Docker/Compose PASS. Skrypt: `node scripts/check_plugins_browser.cjs`; dowody [UI](evals/control-m23.json) i [Docker](evals/docker-m23.json). Usługi właściciela i realny sprzęt pozostają NOT_RUN.

## M2.4 — moduły i zakresy dostępu

AutoLogika czyta kopię ze źródłem/datą/SHA i paginacją50, trzy kolekcje części oraz osobny jawny odczyt usługi. Dom odpytuje dozwolone encje wyłącznie po przycisku. Urządzenia pokazują lokalne możliwości, bez fikcyjnego sterowania. Home reader otrzymuje tylko Dom, workshop reader pięć domen; finanse/raporty/powiadomienia warsztatu pozostają właścicielskie.

Pamięć: CRUD z rewizją korekty, historia/źródła na żądanie, polityka i osobny podgląd/wykonanie retencji. Retencja ponownie liczy dane, nie ma atomowego tokenu podglądu. Hybrid/index pozostają w legacy. Automatyzacje: pełna propozycja i osobne zatwierdzenie/odrzucenie, jawny lokalny tick. Powiadomienia: ostatnie100, bez wysyłki/push. Telefonia: numery/godziny/urlopy/DND z rewizją i podgląd zapisanych zasad bez operatora. Bezpieczeństwo: konta/role/aktywność z zatwierdzeniem, odwoływanie sesji/tokenów i sekret usługowy pokazany raz. Logi to ostatnie100zdarzeń audytu, bez logów systemu/Dockera.

PASS662pytest/24skip(62.62s), pipcheck/app.js;128UItests(46.44s), TypeScript/build. Rzeczywisty Chromium z tymczasowym Core:70żądań API, wszystkie9widoków390/390px, memoryCRUD/history, proposal→approval→ticknotification, politykaDND, konta/odwołanie sesji/token jednorazowy, role/prywatność/CSP. Termin przypomnienia zmieniono kontrolą wyłącznie testowego fixture. Źródłowa syntetyczna kopia i snapshot niezmienione; zero prób transportu zewnętrznego. NowyDocker/Compose build/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Dowody: evals/control-m24.json, docker-m24.json i11PNG; obejrzano pamięćdesktop i bezpieczeństwomobile.

Windows/WSL2/Safari/iPhone/Android, usługi właściciela, modele, sprzęt i CI: NOT_RUN. PG=M1.4, bezpowtórki. CoreSQLite12/PG1 bez migracji. ProdukcjaAutoLogika/Supabase bez zmian. Lokalnecommitybezpush. NastępneM2.5: wspólny przegląd zmian i zatwierdzeń oraz accessibility. Historia: history/RAPORT-v0.9.2.md.

## M2.5 — wspólny przegląd

Przed podglądem i decyzją ponowny odczyt propozycji, dla ustawień również bieżącej konfiguracji. Wykryta zmiana blokuje wysłanie; to preflight bez atomowego CAS. Backend pozostaje autorytetem409. Po niepewnym wyniku mutacji wymagane odświeżenie, bez autoretry. Prywatny stan usuwa401/keyedcredential/abortepoch. Treść i poprzednie ustawienia renderowane jako tekst. Zmiany kont/pamięci/pluginów zachowują własne moduły i zgody; lista propozycji nie udaje pełnego rejestru wszystkich zmian.

Accessibility: fokus nagłówka potwierdzenia, powrót do przycisku po anulowaniu i fokus wyniku. Sprawdzono w Chromium strukturę16widoków: pojedyncze main/h1, brak zduplikowanychID i etykiety pól; mobilne menu fokus/pułapkaTab/ShiftTab/Escape, fokus treści po wyborze. Poprawiono otwieranie menu po przejściu do mobilnego viewportu. Nie jest to kompletny audytWCAG, czytnika ekranu ani Safari.

PASS139testówUI, TypeScript/build; pełne pytest662/24skip87.79s, pipcheck/app.js/diff. RzeczywistyChromium/tempCore: osobna akceptacja ustawień i ich rzeczywisty rollback, kod→review_required, tekst/role/privacy/CSP oraz klawiatura i390px. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Dowody evals/control-m25.json/docker-m25.json/changes-desktop.png/changes-mobile.png.

CoreSQLite12/PG1 bez migracji. Windows/WSL2/Safari/iPhone/Android, czytnik ekranu, realne modele, sprzęt i CI NOT_RUN. PG=M1.4 bezpowtórki. ProdukcjaAutoLogika/Supabase bez zmian; lokalnecommitybezpush. NastępneM3.1: wspólna warstwa dostawcówLLM i kontrola kosztów. Historia: history/RAPORT-v0.9.3.md.

## M3.1 — modele chmurowe

React i starypanel rozpoznają OpenAI, zapisują ten wybór w sesji i obsługują go jako domyślnego dostawcę. Ostrzeżenie kontekstu chmurowego jest wyświetlane przy wyborze. RzeczywistyChromium z syntetyczną usługą przeszedł390px/login/session/approval/privacy; dowody control-m31.json. Konfiguracja cen/sekretów pozostaje serwerowa; [LLM-PROVIDERS.md](LLM-PROVIDERS.md).

## M3.4 — profile sesji i panel pamięci PostgreSQL

Core0.10.3/feature4: tworzenie /storage/memory/conversations przyjmuje opcjonalny profile_ref z id i revision. Profil jest niezmiennie przypięty do nowej sesji; aktualny RLS/scope/revision sprawdzane przedLLM i zapisem. Korekta/usunięcie profilu:409, nowa sesja. React Pamięć ma osobną zakładkę PG: CRUD/history/CAS, potwierdzenie usunięcia, wybór profilu/notatek i osobna rozmowa z cloudzgodą per tura. Szczegóły POSTGRES-PROFILES.md; brak wspólnej historii zeSQLite.
