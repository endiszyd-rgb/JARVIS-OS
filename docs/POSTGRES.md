# PostgreSQL JARVIS — opcjonalna warstwa rekordów

M1.4 realizuje etap z [ADR010](adr/0010-master-plan-architecture.md): osobny magazyn JARVIS w schemacie `jarvis`, z rekordami prywatnymi i warsztatowymi. Nie zastępuje SQLite Core, nie kopiuje schematu AutoLogiki i nie łączy się z jej produkcyjnym Supabase. Konta, sesje, rozmowy, dotychczasowa pamięć, telefonia i konfiguracja nadal korzystają ze SQLite.

Kod: [postgres_store.py](../jarvis/postgres_store.py), [postgres_api.py](../jarvis/postgres_api.py), [postgres_migrations.py](../jarvis/postgres_migrations.py), [migracja 0001](../migrations/postgres/0001_foundation.sql). Dwie bazy mają niezależne wersje schematu: numer migracji PostgreSQL nie jest `PRAGMA user_version` Core.

## Konfiguracja i tożsamość

Pusty `JARVIS_POSTGRES_DSN` oznacza wyłączenie. Samo uruchomienie Core nie inicjalizuje PostgreSQL i nie wykonuje DDL. Włączenie magazynu wymaga wcześniej przygotowanej, osobnej bazy oraz jawnie wykonanej migracji. Standardowe `/health` i `/ready` Core nie są testem dostępności opcjonalnego PostgreSQL; sprawdza go właściciel przez `/api/v1/storage/status`.

| Zmienna | Domyślnie | Zakres / znaczenie |
| --- | --- | --- |
| `JARVIS_POSTGRES_DSN` | pusta | Sekret połączenia runtime; wyłącznie ograniczone konto `jarvis_runtime`. |
| `JARVIS_POSTGRES_CONNECT_TIMEOUT_SECONDS` | `5` | Liczba całkowita 1–30 sekund. |
| `JARVIS_POSTGRES_STATEMENT_TIMEOUT_MS` | `5000` | Liczba całkowita 100–30000 ms. |
| `JARVIS_POSTGRES_LOCK_TIMEOUT_MS` | `1000` | Liczba całkowita 100–10000 ms. |
| `JARVIS_POSTGRES_MIGRATION_DSN` | brak | Osobne poświadczenie migratora, używane wyłącznie przez CLI migracji. Nie przekazuj go do Core/Compose. |

Runtime DSN może mieć postać URI lub libpq conninfo. Host musi być jawny i pojedynczy; nazwa bazy i użytkownik są również wymagane, aby nie odziedziczyć PGDATABASE/PGUSER. Dla połączenia zdalnego wymagane jest `sslmode=verify-full`, z zaufanym CA (`sslrootcert` albo właściwym magazynem libpq), czyli weryfikacją certyfikatu i nazwy hosta. `sslmode=disable` jest dopuszczalne tylko dla literalnego loopback lub dokładnego `localhost` w lokalnym laboratorium. Wartości `prefer`, `require` czy `verify-ca` nie zastępują zdalnego `verify-full`. Dodatkowe pola pozwalające zmienić politykę połączenia, np. `options`, `service`, `hostaddr` i `passfile`, są odrzucane.

Sekrety przechowuj w lokalnym `.env`/menedżerze sekretów, bez Git, argumentów procesu i publikacji DSN w logach. CLI migracji celowo nie ma opcji `--dsn`. Konfiguracja ukrywa DSN, a błędy API i migratora nie przekazują diagnostyki serwera zawierającej poświadczenia lub SQL.

Nowe endpointy wymagają właściciela: klucza bootstrap albo ważnej sesji konta `owner` z [M1.3](SECURITY-ACCESS.md). Pozostałe role i tokeny usługowe nie uzyskują tutaj dostępu, nawet jeżeli mają prawo czytać istniejący adapter AutoLogiki.

- Dla sesji `subject` to UUID zweryfikowanego konta SQLite. Backend pobiera go z tożsamości, nie z JSON, query ani dostarczonego JWT.
- Dla klucza bootstrap używany jest stały `BOOTSTRAP_SUBJECT`: `ad14c9a1-290b-588b-9ed7-2e94d7b6fe9e`, wyliczony przez UUIDv5 z `jarvis:local:bootstrap-owner`. Zmiana klucza nie tworzy nowej przestrzeni prywatnej. To stała przestrzeń tego mechanizmu bootstrap, nie identyfikator odczytany z hasła.
- Prywatne rekordy PostgreSQL są oddzielne dla każdego konta `owner` i dla bootstrap. Nie jest to dotychczasowy model SQLite: tam konta `owner` nadal współdzielą pamięć i rozmowy. Bootstrap nie otrzymuje automatycznego wglądu w prywatne rekordy innych kont PostgreSQL.

## Role SQL i RLS

`jarvis_runtime` musi być rolą `LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`, bez własności schematu/tabel, bez roli migratora i bez podwyższonych członkostw. Otrzymuje tylko członkostwo `authenticated`, a backend jawnie ustawia tę rolę na czas transakcji. Konto migratora jest odrębne; może tworzyć i aktualizować własny schemat `jarvis`, lecz jego DSN nie należy do aplikacji HTTP.

Migracja zakłada istnienie ról platformowych; nie tworzy ich i nie zmienia ich atrybutów. Uprawnienia w schemacie `jarvis` są jawne:

| Rola | Uprawnienia aplikacyjne |
| --- | --- |
| `PUBLIC`, `anon` | Brak dostępu do schematu, tabel, sekwencji i funkcji aplikacji. |
| `authenticated` | `USAGE` schematu; `SELECT` warsztatów i członkostw; `SELECT/INSERT/DELETE` rekordów; `UPDATE` wyłącznie `title`, `payload`, `revision`; `SELECT/INSERT` metadanych zdarzeń. Wykonanie `current_subject()` i `schema_version()`. Wszystkie operacje danych podlegają RLS. |
| `service_role` | Brak grantów aplikacyjnych. Nawet obecność `BYPASSRLS` w tej roli platformowej nie daje brakujących uprawnień do tabel/schematu. Nie jest poświadczeniem runtime. |
| `jarvis_runtime` | Nie jest właścicielem obiektów; korzysta z powyższych grantów dopiero przez `SET LOCAL ROLE authenticated`. Brak DDL i dostępu do historii migracji. |
| Migrator / administrator | Osobny kanał administracyjny. Właściciel obiektów zarządza migracjami; zaufany administrator przygotowuje warsztaty i członkostwa. Nie udostępniaj tych poświadczeń klientowi. |

`workshops`, `memberships`, `records` i `record_events` mają włączone oraz wymuszone RLS. Prywatny rekord (`workshop_id IS NULL`) widzi i zmienia tylko jego właściciel. Rekord warsztatowy widzi wyłącznie aktualny członek wskazanego warsztatu; zapis wymaga `can_write=true`. Samo utworzenie rekordu nie zachowuje dostępu po usunięciu członkostwa. Czytelnik nie może podnieść sobie praw ani dopisać członkostwa.

W każdej transakcji backend ustawia `SET LOCAL ROLE authenticated` oraz transakcyjne `request.jwt.claims` z `sub` zweryfikowanej tożsamości. Po zakończeniu/rollbacku kontekst nie powinien przechodzić do następnego żądania. Nazwa zmiennej nie oznacza, że API przyjmuje lub weryfikuje JWT Supabase: to wewnętrznie ustawiane dane sesji. Bez poprawnego subject reguły nie udostępniają rekordów. Posiadacz poświadczeń SQL runtime może sam ustawiać kontekst SQL, dlatego DSN pozostaje wyłącznie po stronie zaufanego backendu; nie jest poświadczeniem klienta ani przeglądarki.

Własność, warsztat, UUID i czas utworzenia rekordu są niezmienne. Aktualizacja musi zwiększyć rewizję dokładnie o jeden; dodatkowo API wymaga aktualnej rewizji klienta. `schema_version()` jest wąską funkcją `SECURITY DEFINER` ze stałym `search_path=pg_catalog`; zwraca numer, bez nazw plików i checksum migracji.

## Migracja i bootstrap wyłącznie w osobnym laboratorium

Poniższy przykład dotyczy **nowego, lokalnego klastra i bazy testowej**. Nie wykonuj go na produkcyjnym Supabase/AutoLogice. W istniejącej platformie role mogą już istnieć; nie nadpisuj ich ani nie traktuj tego przykładu jako procedury wdrożenia.

Administrator nowego klastra przygotowuje role; hasła ustawia przez interaktywne `\password` w `psql`, nie w pliku SQL ani historii powłoki:

```sql
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE ROLE jarvis_migrator LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE jarvis_runtime LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT authenticated TO jarvis_runtime;
CREATE DATABASE jarvis_lab;
GRANT CONNECT, CREATE ON DATABASE jarvis_lab TO jarvis_migrator;
GRANT CONNECT ON DATABASE jarvis_lab TO jarvis_runtime;
```

Po przełączeniu połączenia administracyjnego na `jarvis_lab` odbierz `PUBLIC` prawo tworzenia obiektów w schemacie `public`:

```sql
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

Przed zmianą istniejącej bazy zachowaj osobną kopię PostgreSQL i globalnych ról/grantów oraz dane potrzebne do jej odtworzenia. Kopia SQLite Core nie obejmuje PostgreSQL. W testach skrypt tworzy nową, jednorazową bazę, więc nie migruje danych użytkownika.

Ustaw `JARVIS_POSTGRES_MIGRATION_DSN` wyłącznie w środowisku procesu CLI, wskazując `jarvis_migrator` i `jarvis_lab`, a następnie wykonaj:

```sh
.venv/bin/python scripts/migrate_postgres.py
```

Migrator używa numerowanych plików `migrations/postgres/NNNN_nazwa.sql`, historii SHA-256 i transakcyjnej blokady advisory. Powtórzenie nie wykonuje już zastosowanych plików. Zmiana nazwy/checksum, usunięcie zastosowanego pliku lub błąd SQL przerywa operację; bieżąca transakcja wycofuje DDL i zapis wersji. Po zastosowaniu migracji nie edytuj jej w miejscu — dodawaj kolejną wersję. Nie ma automatycznej migracji w dół ani deklaracji ukończonego restore drill; pełne odtwarzanie i rollback operacyjny pozostają w M8.3.

Warsztaty i członkostwa nadaje osobno zaufany administrator przez SQL; API M1.4 nie ma endpointu nadawania sobie członkostw. Przykład po migracji, z placeholderem UUID konta wymagającym zastąpienia:

```sql
INSERT INTO jarvis.workshops(id, name)
VALUES ('00000000-0000-4000-8000-000000000101', 'Warsztat laboratoryjny');
INSERT INTO jarvis.memberships(workshop_id, user_id, can_write)
VALUES ('00000000-0000-4000-8000-000000000101', '<UUID_KONTA_OWNER>'::uuid, true);
```

UUID konta można odczytać przez `GET /api/v1/auth/me` po zalogowaniu. Dla klucza bootstrap użyj podanego wyżej `BOOTSTRAP_SUBJECT`, nie tekstu `owner-key`. Wymuszone RLS dotyczy także właściciela tabel. Migracja nadaje wyłącznie swojemu użytkownikowi osobne polityki administracyjne warsztatów i członkostw; dzięki temu migrator bez superuser/BYPASSRLS może je przygotować bez wyłączania RLS. Runtime nie otrzymuje członkostwa w roli migratora.

## HTTP CRUD i błędy

Prefiks zalecany: `/api/v1`; zgodny alias `/api` ma te same uprawnienia. Uwierzytelnienie: `X-Jarvis-Key: <TOKEN_SESJI_OWNER>` lub klucz bootstrap. Pole `owner_id`/`subject` nigdy nie jest argumentem klienta.

| Żądanie po prefiksie | Znaczenie |
| --- | --- |
| `GET /storage/status` | Jawne `disabled` lub gotowość magazynu i numer migracji. |
| `GET /storage/records?limit=50&offset=0` | Lista wszystkich rekordów widocznych przez RLS: własnych prywatnych oraz warsztatów z członkostwem. Stronicowanie: limit 1–200, offset 0–100000. |
| `GET /storage/records?workshop_id=<UUID>` | Lista wskazanego warsztatu, ograniczona RLS. |
| `POST /storage/records` | Utworzenie rekordu, `201`; opcjonalny `workshop_id`. |
| `GET /storage/records/<UUID>` | Odczyt widocznego rekordu. |
| `PATCH /storage/records/<UUID>` | Zmiana tytułu/payload przy zgodnej `revision`. |
| `DELETE /storage/records/<UUID>?revision=1` | Usunięcie przy zgodnej rewizji. |

Przykładowe treści żądań, bez poświadczeń i rzeczywistych danych:

```json
{"title":"Notatka laboratoryjna","payload":{"source":"synthetic"}}
```

```json
{"revision":0,"title":"Poprawiona notatka","payload":{"source":"synthetic","version":2}}
```

Rekord prywatny powstaje bez `workshop_id`. Rekord warsztatowy wymaga jego UUID i istniejącego członkostwa z prawem zapisu. Brak widoczności zwraca `404`, bez ujawniania istnienia cudzego rekordu; widoczny rekord bez prawa zapisu zwraca `403`, a nieaktualna rewizja `409`. Niepoprawny kontrakt to `422`; wyłączony/niedostępny magazyn to `503`. Pusty DSN nadal pozwala korzystać z dotychczasowych funkcji SQLite.

Metadane `created`/`updated`/`deleted` trafiają do PostgreSQL `record_events` **w tej samej transakcji co zmiana rekordu**. Zawierają UUID zdarzenia, subject, rodzaj, UUID rekordu i czas — bez tytułu, payload, hasła lub DSN. Usunięcie rekordu nie kasuje historii zdarzeń. To osobny audyt magazynu, nie drugi zapis transakcji do audytu SQLite. Nie ma publicznego endpointu eksportu tego audytu w M1.4.

## Powtarzalne sprawdzenie na bazie jednorazowej

Najpierw zainstaluj zależności projektu i uruchom lokalny Docker. Rekomendowana ścieżka sprawdzenia nie korzysta ze skonfigurowanych DSN aplikacji:

```sh
.venv/bin/python scripts/check_postgres.py --docker-host unix:///var/run/docker.sock
```

Na Windows odpowiednikiem jest `.venv\Scripts\python.exe scripts\check_postgres.py --docker-host npipe:////./pipe/docker_engine`. `--image` wybiera obraz (domyślnie `postgres:16-bookworm`); `--skip-pull` wymaga obrazu już dostępnego lokalnie; `--output <plik.json>` zapisuje oczyszczony raport dopiero po sprzątnięciu zasobów.

Skrypt tworzy kontener i wolumen o losowej nazwie/etykiecie, publikuje PostgreSQL na dynamicznym porcie `127.0.0.1`, generuje tymczasowe hasła i role testowe. Uruchamia prawdziwe testy migracji/RLS/repozytorium/API; pominięty test nie jest zaliczeniem. Sprawdza też trwałość syntetycznej wartości po restarcie i usuwa wyłącznie własne oznaczone zasoby. W tym izolowanym harnessie rolę migratora pełni administrator nowej bazy; nie oznacza to zgody na superusera w runtime. Zwykły `pytest` bez testowych DSN pomija scenariusze wymagające prawdziwego serwera — sam taki wynik nie potwierdza RLS.

Wyniki M1.4 są zapisywane w [planie i dzienniku](../JARVIS_MASTER_PLAN.md). Rzeczywisty raport: [postgres-m14.json](evals/postgres-m14.json),25 testów PASS/0skip, PostgreSQL16.15, restart i cleanup. To wynik lokalnego laboratorium, nie produkcji.

## Pozostające ograniczenia

Nie wdrożono produkcyjnego Supabase, logowania przez jego JWT ani bezpośredniego publicznego PostgREST do tych tabel. Nie ma migracji całego Core lub pamięci SQLite do PostgreSQL, pgvector z M3.3, nowego UI ani synchronizacji AutoLogiki. UUID warsztatów i członkostwa są obecnie zarządzane administracyjnie; nie są automatycznie odtwarzane z kont ani z danych innego systemu. Kopie, szyfrowanie i ćwiczenie odtworzenia PostgreSQL wymagają dalszej pracy M8.3. Test lokalnego Postgresa nie jest testem produkcyjnej platformy ani upoważnieniem do jej modyfikacji.

## Opcjonalna pamięć M3.3

Fundament schema1 pozostaje niezależny od funkcji pamięci pgvector. Ta funkcja ma osobną historię migracji1–2, opt-in API pamięci i odrębne sesje tekstowe PostgreSQL z prywatnym kontekstem AI. [Stan, instalacja rozszerzenia i dowody](POSTGRES-MEMORY.md). Runner --memory weryfikuje także25dotychczasowych testów M1.4; pełny etap M3.3 ma62testy rzeczywistego PG/API/0skip.
