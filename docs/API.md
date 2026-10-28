# API 0.10.2 — M3.3

Publiczne UI React: `/control`, `/control/` i ograniczone `/control/assets/{asset}`; opis builda i logowania: [CONTROL-CENTER.md](CONTROL-CENTER.md). API zachowuje istniejące uprawnienia.

Jednolity katalog `GET /tools`, jawne `/plugins/{id}/tools` i wspólna bramka istniejącego invoke: [TOOLS.md](TOOLS.md). `plugins:read` oraz `plugins:invoke` są odrębne; złożoność schematów i wykonanie są ograniczone.

Opcjonalne właścicielskie `/storage/status` i CRUD `/storage/records`: [POSTGRES.md](POSTGRES.md). To oddzielny magazyn z RLS; istniejące endpointy pamięci/rozmów nadal używają SQLite.

Konta, role, logowanie i administracja sesjami: [SECURITY-ACCESS.md](SECURITY-ACCESS.md). Nowe `/auth/login` jest publiczne i limitowane; `/auth/me` i `/auth/logout` wymagają tożsamości. `/security/users` oraz `/security/sessions` są wyłącznie właścicielskie. Pozostałe wcześniejsze opisy uprawnień należy czytać z aktualną macierzą ról w tej instrukcji.

Kanoniczny REST API ma prefiks `/api/v1`. Dotychczasowe `/api` pozostaje kompatybilnym aliasem tego samego routera: te same funkcje, walidacja, stan SQLite, zależności autoryzacji i polityki. Nowe klienty powinny używać `/api/v1/status`, `/api/v1/chat`, `/api/v1/memory`, `/api/v1/telephony/...` itd. Nie ma wersji v2 ani automatycznego dopasowania nieznanych wersji. Aktualny OpenAPI jest dostępny właścicielowi przez `/api/v1/schema` (także stary `/api/schema`); publiczny `/openapi.json` pozostaje wyłączony.

| Trasa | Warunek / wynik |
|---|---|
| GET `/health` | Publiczna żywotność procesu; nie sprawdza modeli ani integracji |
| GET `/ready` | Publiczna gotowość Core, 200 ready lub 503 not_ready |
| GET `/api/v1/ready`, `/api/ready` | Ten sam test gotowości |
| `/api/v1/...` | Kanoniczne API, uprawnienia jak we wcześniejszych sekcjach |
| `/api/...` | Alias zgodności dla istniejącego panelu i workerów |
| POST `/webhooks/twilio/whatsapp` | Dotychczasowa odrębna trasa i kanoniczny adres podpisu, bez zmiany |

Gotowość sprawdza poprawnie skonfigurowany klucz właściciela i odczyt istniejącej bazy ze schematem12. Nie tworzy brakującej bazy, nie wykonuje migracji i nie odpytuje zewnętrznych usług. SQLite może utworzyć pomocnicze pliki WAL/SHM przy odczycie istniejącej bazy WAL; odczyt uwzględnia aktywny dziennik. Wynik ma status, bool checks.owner_key/database oraz optional_integrations_probed=false, bez sekretów, ścieżek i treści błędów SQLite. Skonfigurowanie modelu/operatora nie jest jego sprawdzonym połączeniem. Health może być200 przy braku gotowości.

Konfiguracja Core: JARVIS_DB, JARVIS_API_KEY i walidowany JARVIS_SQLITE_TIMEOUT_SECONDS (domyślnie15, >0 i <=60; próba readiness ma limit do2s). Błędna ścieżka/timeout blokuje start konfiguracji; nieustawiony/placeholder klucz zamyka chronione API przez503 i daje not_ready. Klucz jest maskowany w reprezentacji konfiguracji; nie należy eksportować jego jawnej wartości.

Limity body zachowano dla obu prefiksów:64KiB JSON/form i2MiB dla POST voice/transcribe. Kanał klienta transportu pod `/api/v1/telephony/transport/caller/{id}` nadal wymaga wyłącznie tokenu danej rozmowy, nigdy nie uzyskuje praw właściciela.

---

# Uzupełnienie API 0.8.4 — R04, Core — schemat 11

Dodano trwały transport **wyłącznie laboratoryjny**. Nie ma operatora, połączeń ani transferu audio. Szczegóły przebiegu, scenariuszy, typów i limitów: [TRANSPORT-TELEFONII.md](TRANSPORT-TELEFONII.md).

| Metoda | Trasa | Dostęp i działanie |
|---|---|---|
| POST | `/api/telephony/transport/calls` | Właściciel; `{event_id,caller?,limits?}`, HTTP 201; nowy caller_token pokazany raz. |
| GET | `/api/telephony/transport/calls` | Właściciel; do 50 ostatnich stanów, odświeża timeout. |
| GET | `/api/telephony/transport/calls/{id}` | Właściciel; pełny stan, prywatne decyzje i kolejka kanałów. |
| POST | `/api/telephony/transport/calls/{id}/events` | Właściciel; `{event_id,revision,action,attempt_id?,fail_next_owner?}`. |
| DELETE | `/api/telephony/transport/calls/{id}` | Właściciel; usuwa ended razem z recepcją, sprawami, kolejką i tokenem; przycisk usunięcia w panelu natychmiast unieważnia dostęp klienta. |
| GET | `/api/telephony/transport/caller/{id}` | Tylko `X-Jarvis-Call-Token`; ograniczona projekcja klienta. |
| POST | `/api/telephony/transport/caller/{id}/events` | Tylko token tej rozmowy; `{event_id,revision,action,text?}` dla turn/hangup. |

Właściciel używa pełnego `X-Jarvis-Key`; tokeny usług są blokowane. Kanał klienta nie przyjmuje klucza właściciela w zastępstwie tokenu rozmowy. Numer nie uwierzytelnia osoby. Token jest zapisany w bazie wyłącznie jako skrót; rotacja go unieważnia, a replay nie ujawnia sekretu ponownie. Końcową projekcję można odczytać do expires_at + 300 s włącznie; potem 401. Klient nie ma dostępu do owner_briefing, decision, attempt_id, limits, kosztów, kolejki ani starego laboratorium właściciela.

UUID są wymagane dla ID tras, event_id i attempt_id. Rewizja dotyczy transportu. Akcje właściciela: dispatch/accept/decline/no_answer/finish/rotate_caller_token. Tylko accept/decline/no_answer wymagają attempt_id bieżącej **dostarczonej** oferty; pozostałe nie przyjmują niepustego attempt_id. Opcjonalne fail_next_owner=true jest legalne tylko dla laboratoryjnego dispatch. Klient ma wyłącznie turn (niepusty tekst do 4000 znaków) lub hangup (tekst pusty/pominięty). Nieznane pola, w tym at/scenario/facts po stronie klienta, dają 422.

Domyślne limits: owner_wait_seconds=30 (1–120), max_call_seconds=600 (30–1800), max_owner_attempts=1 (0–1), max_simulated_cost_units=2 (0–10), max_turns=24 (1–24); ścisłe liczby całkowite. To budżet symulacji: jednostka za zakolejkowanie offer i jednostka za bridge, bez zwrotu po błędzie. Jest najwyżej jedna próba kontaktu, potem callback bez obietnicy godziny. Czas pochodzi z serwera; polityka godzin/DND/urlopów jest sprawdzana także przy zgodzie i delivery bridge.

Dispatch jest ręczny, do 20 oczekujących poleceń. Nie ma workera/timera dostarczającego w tle. GET/list/event odświeżają termin, ale nie dostarczają kolejki. Akceptacja tworzy bridge_pending; dopiero osobny dispatch i poprawny lab Ack dają bridged_lab (publicznie connected_lab). Publiczne wiadomości są tylko dostarczonymi tekstami kanału klienta.

Start/zdarzenia są idempotentne w zachowanych rekordach, a replay zwraca bieżący stan. Zmieniona treść pod tym samym event_id albo stara revision daje 409. Brak/niewłaściwy token klienta daje 401, token usługowy właściciela 403, nieistniejący call na trasie właściciela 404. Utrwalony timeout może zmienić rewizję przed odrzuceniem spóźnionego zdarzenia. Nieoczekiwany błąd zapisu cofa razem recepcję, transport, outbox i receipt. Gwarancja SQLite nie obejmuje przyszłych zewnętrznych skutków operatora.

Powiązanej z transportem recepcji nie wolno mutować przez stare `/api/reception/calls/{id}/events`, `/ai-turn` lub DELETE:409. Odczyt pozostał właścicielski. Migracja 10→11 zachowuje istniejące dane i tworzy before-schema11 backup. Wszystkie flagi operatora/połączeń/powiadomień nadal false. Poprzednie sekcje poniżej opisują wcześniejsze rozszerzenia API.

---

# Uzupełnienie API 0.8.3

POST /api/chat: input_mode text (domyślny) albo voice. Voice wyłącza parser ustawień/przypomnień/pamięci, wymusza brak capture oraz wyklucza osobiste notatki i include_workshop_summary. Sesje mają trwały tryb; niezgodne użycie tego samego session_id daje422 przed wykonaniem modelu/dopisaniem tury. GET/list sesji zwraca input_mode. Stare sesje migrowane jako text; tryb kaskadowo usuwany z sesją. Dźwięk i nazwa Jarvis nie uwierzytelniają właściciela — nadal wymagany jego klucz API.

Przegląd transkrypcji jest domyślną funkcją klienta, zaś voice.transcribe nadal zwraca review_required=true/executed=false. Półdupleksowy klient używa istniejących transcribe/synthesize i sesji audio, nie wykonuje narzędzi. Szczegóły: ROZMOWA-GLOSOWA.md. Core schema10.

---

# Uzupełnienie API 0.8.2

POST /api/chat przyjmuje do_not_remember (domyślnie false) i zwraca memory_capture. Capture dotyczy tylko ograniczonego katalogu właścicielskich deklaracji; nie steruje narzędziami. GET /api/memory/{id}/origins pokazuje źródła automatycznych wpisów. GET /api/memory/policy raportuje aktywność i nazwę ekstraktora. Szczegóły: PAMIEC-AUTOMATYCZNA.md.

POST /api/voice/sessions, GET /api/voice/sessions/{id}, POST /api/voice/sessions/{id}/events: procesowe, właścicielskie API stanów sesji. Nie przyjmuje dźwięku ani nie uruchamia modelu. Eventy mają UUID i oczekiwaną rewizję. Szczegóły przejść i limitów: SESJE-AUDIO.md. Istniejące WAV transcribe/synthesize pozostają osobną funkcją.

---

# API Core 0.4

Panel, pliki UI i `/health` są publiczne. `/api/*` wymagają nagłówka `X-Jarvis-Key`. Webhook Twilio ma oddzielną weryfikację podpisu. Klucz właściciela jest wymagany tam, gdzie nie podano węższego zakresu. Nie dajemy dostępu do zarządzania na podstawie treści rozmowy ani danych z pluginu.

| Metoda | Trasa | Funkcja / zakres tokenu usługowego |
|---|---|---|
| GET | `/api/status` | Stan; `status:read` |
| GET | `/api/schema` | OpenAPI tego Core; właściciel |
| GET | `/api/plugins` | Lista; `plugins:read` |
| POST | `/api/plugins` | Rejestracja manifestu; właściciel |
| PUT | `/api/plugins/{id}` | `{enabled}`; właściciel |
| GET/PUT | `/api/plugins/{id}/config` | Konfiguracja; właściciel |
| GET | `/api/plugins/{id}/tools` | Wykrywanie narzędzi; `plugins:read` |
| POST | `/api/plugins/{id}/invoke` | `{operation,arguments}`; `plugins:invoke` |
| GET | `/api/security/tokens` | Metadane tokenów bez sekretów; właściciel |
| POST | `/api/security/tokens` | `{name,scopes,hours}` → sekret pokazany raz; właściciel |
| DELETE | `/api/security/tokens/{id}` | Cofnięcie dostępu; właściciel |
| GET | `/api/home/states` | Stany encji z allowlisty; `home:read` |
| GET | `/api/home/states/{entity_id}` | Konkretny stan; `home:read` |
| GET | `/api/integrations` | Flagi konfiguracji, bez sekretów; właściciel |
| POST | `/webhooks/twilio/whatsapp` | Formularz, podpis X-Twilio-Signature; bez klucza Core |
| GET | `/api/whatsapp/inbox` | Odebrane; `messages:read` |
| DELETE | `/api/whatsapp/inbox/{MessageSid}` | Usuń treść, zachowaj receipt deduplikacji; właściciel |
| GET | `/api/whatsapp/drafts` | Szkice; `messages:read` |
| POST | `/api/whatsapp/drafts` | `{recipient,body}`; `messages:draft`; nie wysyła |
| DELETE | `/api/whatsapp/drafts/{id}` | Usuń szkic; właściciel |
| GET | `/api/autologika/readonly/orders` | Istniejąca lista AutoLogiki; właściciel |
| GET | `/api/autologika/readonly/orders/{id}` | Szczegóły; właściciel |
| POST | `/api/chat` | `{message,model}`; demo lub ollama |
| GET/POST | `/api/memory` | Lista / `{text}`; opcjonalne `?q=` |
| DELETE | `/api/memory/{id}` | Usunięcie notatki |
| GET/POST | `/api/proposals` | Lista / `{kind,payload}` |
| POST | `/api/proposals/{id}/decide` | `{approve}` |
| POST | `/api/proposals/{id}/rollback` | `{}`; ustawienia i automatyzacje |
| GET | `/api/automations` | Zatwierdzone przypomnienia |
| POST | `/api/automations/tick` | `{}`; `scheduler:tick` |
| GET | `/api/notifications` | Lokalne powiadomienia |
| GET | `/api/audit` | Ostatnie zdarzenia |
| POST | `/api/backups` | `{}`; kopia bazy i SHA-256 |

Konfiguracja pluginu: `{endpoint,secret_env,reviewed_read_tools,openapi}`. Schemat OpenAPI jest wymagany tylko dla protocol=openapi, a zabroniony dla MCP. Nazwa sekretu musi zaczynać się od JARVIS_PLUGIN_SECRET_. Zapis konfiguracji wyłącza plugin do ponownego włączenia. Discovery i invoke wyłączonego pluginu są blokowane.

Invoke DEMO zawsze daje syntetyczny wynik. Invoke skonfigurowanego MCP/OpenAPI łączy się z usługą; wymaga lokalnie zatwierdzonej nazwy odczytu i dozwolonego celu sieciowego. Nie podawaj `arguments.live=true` ani `arguments.dry_run=false`: te flagi nadal powodują blokadę. Nie jest to przełącznik aktywujący zapisy. Brak konfiguracji → 501, wyłączony plugin → 409, niedozwolone narzędzie → 403, błędne argumenty → 422, błąd transportu → 502.

Przykład tokenu dla n8n:

```json
{"name":"n8n","scopes":["scheduler:tick"],"hours":720}
```

Przykład szkicu (bez wysyłki):

```json
{"recipient":"whatsapp:+48123456789","body":"Przykładowy szkic odpowiedzi."}
```

Propozycje ustawień: kind=settings, payload `{name,tone,model}`, tone casual/formal. Automatyzacje: kind=automation, payload `{title,interval_minutes,message}`. Kod: kind=code, payload `{description}`; po akceptacji tylko `review_required`. Lista pamięci, audytu, wiadomości i szkiców ma limit 100; brak pełnej paginacji. Nie wdrożono endpointów sterowania fizycznego, wysyłania WhatsApp ani Calling.


## Rozmowy i kopia warsztatu — nowe w 0.4

Wszystkie poniższe trasy są tylko dla właściciela. Tokeny usług z poprzedniej wersji nie zyskują dostępu do historii ani pełnych danych kopii.

| Metoda | Trasa | Działanie |
|---|---|---|
| GET | `/api/models` | Jawny katalog właściciela; bez połączenia z Ollama |
| POST | `/api/chat/sessions` | `{title,model,model_name}`; pola opcjonalne |
| GET | `/api/chat/sessions` | Lista, limit 1–100, offset |
| GET | `/api/chat/sessions/{id}` | Metadane, message_count i informacja o aktywnej turze |
| PATCH | `/api/chat/sessions/{id}` | `{title}` |
| DELETE | `/api/chat/sessions/{id}` | Usunięcie sesji i jej wiadomości; 409 przy aktywnej turze |
| GET | `/api/chat/sessions/{id}/messages` | Wiadomości w kolejności, limit 1–500 i offset |
| GET | `/api/chat/sessions/{id}/export` | Pobranie sesji jako JSON |
| POST | `/api/chat/retention` | `{days,dry_run}`; domyślnie tylko podgląd |
| GET | `/api/autologika/snapshot` | Manifest lokalnej kopii, kontrakt i lista domen |
| GET | `/api/autologika/snapshot/{domain}` | Odczyt domeny; limit 1–200, offset do 100000 i opcjonalny month YYYY-MM |

POST /api/chat nadal przyjmuje message i model (demo/ollama), a dodatkowo model_name, session_id, include_workshop_summary (domyślnie false) i workshop_month. Brak session_id tworzy nową sesję. Brak model korzysta z ustawienia sesji albo domyślnego dostawcy nowych rozmów. Nazwa modelu musi być na liście właściciela. Wynik zawiera session_id, turn_id i liczbę przekazanych wcześniejszych wiadomości. 409 oznacza równoległą turę; 502/504 awarię albo timeout modelu. Nie ma streamingu odpowiedzi w tej wersji.

Domeny snapshotu: calendar, orders, vehicles, parts, customers, finances, reports, notifications. Tryb odpowiedzi to snapshot_readonly i zawsze zawiera datę kopii oraz SHA-256. To nowe API Core na lokalnej kopii, nie rzekome endpointy serwera AutoLogiki. Brak konfiguracji, inny schemat, niespójny manifest lub brak wymaganych kolumn blokuje odczyt kodem 503. Nie ma endpointu wgrywania dowolnej bazy, wykonywania SQL ani zapisów do AutoLogiki.

## Telefonia 0.6

GET/PUT `/api/telephony/settings`, POST `/api/telephony/preview`: tylko właściciel. PUT wymaga rewizji i pełnej polityki; konflikt 409. Podgląd nie wykonuje działań. Szczegóły w [instrukcji](TELEFONIA-v0.6.md).

## Recepcja 0.7

Laboratoryjne `/api/reception/calls`, `/api/reception/calls/{id}`, `/api/reception/calls/{id}/events` i `/api/reception/cases`: wyłącznie właściciel. Nie wystawiać bezpośrednio klientom. Opis danych i uprawnień: [Recepcja](RECEPCJA-v0.7.md).

## Recepcja AI 0.8

GET `/api/reception/ai/status`, POST `/api/reception/calls/{id}/ai-turn`: tylko właściciel. Turn zawiera event_id, revision i text; nie przyjmuje własnej analizy/faktów/scenariusza. [Instrukcja](ANALIZA-RECEPCJI-v0.8.md).

## Dostawcy LLM

Czat, SessionSpec i Settings dopuszczają `model: openai` oprócz demo/ollama. Nazwę wybiera serwer z jawnej konfiguracji; katalog nie sonduje sieci. Odpowiedzi inferencji mają `usage` z licznikami (dlaOllama nullable), kosztamiUSD jako string/null i `billing_verified:false`. Ustawienie domyślnego dostawcy nie aktywuje usługi. Pełny kontrakt i limity: [LLM-PROVIDERS.md](LLM-PROVIDERS.md).

## M3.2 — jawna rozmowa z odczytami

`POST /api/v1/chat/tools` (alias`/api/chat/tools`) wymaga właściciela, `JARVIS_TOOL_CHAT_ENABLED=true` i ciała `{message, model:"ollama"|"openai", model_name?, tool_ids:["plugin.operation"]}`. Jednorazowy wybór1–8zatwierdzonych odczytów, pełna walidacja listy i aktualnej tożsamości/konfiguracji,4tury/8wywołań/90s/2miejsca na proces. Chmurowy budżet obejmuje sumę rezerwacji wszystkich odpowiedzi. Odpowiedź:reply/model/model_name/tool_calls/provider_turns/usage/private_memory_attached:false/history_saved:false. Bez prywatnej pamięci i historii, głosu, zapisu i wykonania kodu; zwykły/chat pozostaje bez narzędzi. Pełny kontrakt, limity, błędy i ograniczenia: [TOOL-CALLING.md](TOOL-CALLING.md).

## M3.3 — opcjonalna pamięć PostgreSQL

Owner-only/storage/memory: status/list/create/get/update/delete, jawny/index pojedynczego rekordu i semantic/search. Wymaga JARVIS_POSTGRES_MEMORY_ENABLED, ograniczonego PG DSN i osobnych migracji; embedding dodatkowo jawnego lokalnego modelu. Subject z aktualnej sesji, oddzielny private/workshop zakres, revision/hash/RLS po embeddingu. Nie dołącza automatycznie danych do czatu ani nie migruje SQLite. [Kontrakt i ograniczenia](POSTGRES-MEMORY.md). M3.3 VERIFIED; kontekst i integrację AI opisuje POSTGRES-CONTEXT.md.

## M3.3 — izolowany kontekst PostgreSQL

Opt-in owner API dodaje GET/POST/storage/memory/conversations, GET/DELETE/storage/memory/conversations/{id}, GET/{id}/messages i POST/{id}/turns. Featurememory migration2, SQLite12/PGfoundation1 bez zmiany. Sesja ma stały model i private/workshop zakres, prywatnego właściciela, revision, TTL i dzierżawę jednej tury. Body/turns:revision/message/memory_refs[{id,revision}]?/allow_cloud_context?; OpenAI wymaga jawnego true. Brak tools, voice, autozapamiętywania i zapisu do historii SQLite. Kontekst do20wiadomości/16000znaków, wybór do5notatek, aktualne RLS/rewizje także dla źródeł historii, reauth przed inferencją/zapisem. Pełny kontrakt: [POSTGRES-CONTEXT.md](POSTGRES-CONTEXT.md).

## M3.4 w toku — profile i historia

Opt-in owner/storage/memory/profiles: lista/create/get/update/delete/history z revision i private/workshop zakresem. GET/storage/memory/{id}/history zwraca zachowane rewizje notatki. Wymagana osobna featuremigration3, bez zmiany SQLite/fundamentuPG. Runtime nie modyfikuje snapshotów bezpośrednio; usunięcie rodzica usuwa ich treści, audyt zostaje metadanymi. Zapis profilu jeszcze nie dołącza go do modelu; brak GUI tego etapu. [Kontrakt i pozostałe prace](POSTGRES-PROFILES.md). M3.4 nadal IN_PROGRESS.

## M3.4 — profile sesji i panel pamięci PostgreSQL

Core0.10.3/feature4: tworzenie /storage/memory/conversations przyjmuje opcjonalny profile_ref z id i revision. Profil jest niezmiennie przypięty do nowej sesji; aktualny RLS/scope/revision sprawdzane przedLLM i zapisem. Korekta/usunięcie profilu:409, nowa sesja. React Pamięć ma osobną zakładkę PG: CRUD/history/CAS, potwierdzenie usunięcia, wybór profilu/notatek i osobna rozmowa z cloudzgodą per tura. Szczegóły POSTGRES-PROFILES.md; brak wspólnej historii zeSQLite.

## M3.5 — wieloetapowe zadania odczytu

Core0.10.4: owner-only POST/chat/tasks (202, request_id UUID/model/tool_ids/steps1–4), GET/chat/tasks/{id}, POST/chat/tasks/{id}/cancel (202). Prefiks /api/v1 lub /api. Status perkonto, RAM/jedenworker, TTL900s, bezrestartresume; cancel nie cofa wcześniejszych odczytów/kosztu. Ten sam request_id/plan w okresie retencji nie wykonuje ponownie I/O, zmienionyplan409. Wszystkie etapy współdzielą rezerwację budżetu i istniejące ToolGateway/schema/currentauth; wyłącznie opt-in zatwierdzone odczyty. Szczegóły AI-TASKS.md. Walidacja żądania zadań zwraca422 bez kopiowania błędnego inputu.
