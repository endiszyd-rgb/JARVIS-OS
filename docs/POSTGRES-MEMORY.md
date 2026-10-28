# Pamięć PostgreSQL/pgvector — M3.3

Ten etap dostarcza repozytorium i jawne migracje pamięci długoterminowej, przetestowane na rzeczywistym, jednorazowym PostgreSQL16/pgvector0.8.2. **Działają API pamięci i odrębne prywatne sesje tekstowe z jawnym kontekstem AI.** Nowe sesje PostgreSQL nie korzystają ze wspólnej historii SQLite; GUI nowej pamięci pozostaje w M3.4. [Sesje i integracja AI](POSTGRES-CONTEXT.md). Dotychczasowa pamięć SQLite i rozmowy pozostają dostępne; nie importujemy ich automatycznie ani nie zmieniamy ich wspólnego dla właścicieli modelu dostępu.

`jarvis/postgres_memory.py` używa sprawdzanych transakcji PostgresStore z M1.4. Metody create/get/list/update/delete, prepare_index/index i semantic nie wykonują embeddingu, sieci HTTP ani DDL. Subject API pochodzi wyłącznie ze zweryfikowanej tożsamości backendu. Domyślne list/search obejmują tylko własne rekordy prywatne. Workshop wymaga jawnego UUID i aktualnego członkostwa; nie ma wyszukiwania sumującego wszystkie przestrzenie.

Pamięć ma treść, kategorię, jawne pochodzenie manual/session/import i source_id, rewizję, hash tekstu i opcjonalny embedding z namespace. Etykiety pochodzenia przekazane ręcznie nie stanowią dowodu autentycznej historii sesji. Treść ma do8000znaków. Wektory:1–4096skończonych składowych, dodatnia norma, normalizacja, namespace64hex. Wyszukiwanie cosine jest dokładnym skanem pgvector w dozwolonym zakresie, bez indeksu ANN i bez deklaracji skalowalności na dużych zbiorach. Filtruje namespace i wymiary; nie łączy odmiennych modeli. Wyniki nie zwracają surowego wektora.

RLS jest wymuszone. Prywatne rekordy widzi i zmienia wyłącznie subject właściciela. Członkowie widzą pamięć swojego warsztatu; zapis/index wymaga can_write. Usunięcie członkostwa odbiera dostęp także autorowi. Runtime nie może zmieniać owner/workshop ani wyłączać RLS. Rewizja rośnie dokładnie o1. Trigger wylicza SHA256 tekstu po stronie bazy i unieważnia wektor po korekcie treści. Zapis embeddingu wymaga aktualnej rewizji i hasha; prepare_index sprawdza odczyt i zapis przed przyszłym wysłaniem treści do lokalnego modelu. Po embeddingu ponownie obowiązuje RLS/revision, więc wynik dla zmienionego tekstu nie nadpisuje korekty. Metadane zdarzenia i mutacja zapisują się w tej samej transakcji; błąd audytu wycofuje mutację.

## Osobna, jawna migracja opcjonalnej funkcji

Podstawa PostgreSQL pozostaje przy migration1. Funkcja pamięci ma własne migracje1–2 w `migrations/postgres_memory` i własną historię `jarvis.memory_schema_migrations`; brak konieczności instalowania pgvector w instalacji używającej wyłącznie dotychczasowych rekordów. Obie historie korzystają z checksum, transakcji i tej samej blokady advisory. Podczas startu Core nie wykonuje żadnej z migracji.

Przed funkcją pamięci wymagane są fundament M1.4 i administracyjna instalacja pgvector w **osobnej bazie JARVIS**. Przygotowanie rozszerzenia wymaga odpowiednio uprawnionego administratora; migrator/runtime nie dostają superuser ani prawa instalacji rozszerzeń. Nie wykonuj poniższych poleceń na produkcji AutoLogiki/Supabase bez odrębnej zgody.

```sql
-- Administrator nowej bazy laboratoryjnej, po przygotowaniu ról z POSTGRES.md:
CREATE SCHEMA jarvis_extensions;
REVOKE ALL ON SCHEMA jarvis_extensions FROM PUBLIC, anon, authenticated, service_role;
CREATE EXTENSION vector WITH SCHEMA jarvis_extensions;
GRANT USAGE ON SCHEMA jarvis_extensions TO authenticated;
-- Osobny migrator również potrzebuje USAGE tego schematu do utworzenia kolumny.
GRANT USAGE ON SCHEMA jarvis_extensions TO jarvis_migrator;
```

Używając wyłącznie sekretu osobnego migratora w JARVIS_POSTGRES_MIGRATION_DSN (nie w argumentach procesu):

```sh
.venv/bin/python scripts/migrate_postgres.py
.venv/bin/python scripts/migrate_postgres.py --memory
```

Brak rozszerzenia/prerekwizytu albo zmieniony checksum przerywa i wycofuje migrację. Nie edytuj zastosowanych plików; dodaj kolejną wersję. `memory_schema_version()` zwraca tylko wersję funkcji, bez historii/checksum. Wszystkie konta HTTP nadal wymagają ograniczonego `jarvis_runtime` opisanego w [POSTGRES.md](POSTGRES.md); anon/service_role nie uzyskują dostępu do pamięci.

## Wykonane sprawdzenia

`python scripts/check_postgres.py --memory` tworzy wyłącznie nowy, oznaczony UUID kontener/wolumen i syntetyczne poświadczenia. Używa pgvector/pgvector:0.8.2-pg16, przygotowuje rozszerzenie jako administrator tej jednorazowej bazy i uruchamia istniejące testy M1.4 oraz nowe testy pamięci. Standardowy runner bez --memory nadal korzysta z postgres:16-bookworm.

PASS62testy rzeczywistej bazy/API/0skip:25regresji M1.4,13testów pamięci długoterminowej/API oraz24testy prywatnych sesji/kontekstu i protokołów. Migracje/RLS/private/workshop/read-only/revocation/cosine/namespace/dimensions/revision/invalidation/atomic-audit/grants/checksum/rollback sprawdzone. Kontener restartuje się z zachowaniem danych, a zasoby testowe są usuwane. Dowód: [postgres-memory-m33.json](evals/postgres-memory-m33.json).15nowych testów czystej walidacji sprawdza granice wejścia i wektorów;134PASS razem z konfiguracją M1.4.

Wstępne próby wykryły brak miejsca przy pobieraniu obrazu (odzyskano nieużywane obrazy/cache testów JARVIS), klamry regex w psycopg.SQL.format oraz niedopuszczalny w PostgreSQL generated expression z convert_to. Poprawiono je przed końcowym PASS; hash jest teraz wyliczany w triggerze. Żadna z nieudanych prób nie dotyczyła bazy użytkownika.

Kontekst krótkoterminowy i jawne dołączanie notatek do AI działają w osobnym API sesji: [POSTGRES-CONTEXT.md](POSTGRES-CONTEXT.md). M3.3 VERIFIED w zakresie kodu i kontrolowanych protokołów. Realna inferencja/jakość, konto chmurowe, dane użytkownika, produkcja, Windows i GUI nowej pamięci NOT_RUN.

## API właściciela — checkpoint M3.3

Domyślnie `JARVIS_POSTGRES_MEMORY_ENABLED=false`; flaga true wymaga skonfigurowanego ograniczonego DSN i wcześniej jawnie wykonanych migracji. Żaden endpoint nie instaluje pgvector. Standardowe health/ready nadal nie sondują opcjonalnej bazy. Flaga jest sprawdzana przy żądaniach; nie aktywuje embeddingu ani nie importuje danych. Tokeny usług i konta bez owner nie mają dostępu. Bootstrap ma własny stały subject, konta owner odrębne UUID zgodnie z M1.4.

Prefiks `/api/v1` lub zgodny `/api`:

| Trasa | Działanie |
| --- | --- |
| GET/storage/memory/status | disabled bez sieci albo jawny test funkcji/pgvector. |
| GET/storage/memory?workshop_id=UUID&limit=50&offset=0 | Domyślnie prywatne; opcjonalnie dokładnie jeden warsztat, bez sumowania zakresów. |
| POST/storage/memory | content, category?, source?, source_id?, workshop_id?;201 po trwałym zapisie. Bez owner_id/subject/wektora w żądaniu. |
| GET/storage/memory/{id} | RLS; obcy/nieobecny rekord404. |
| PATCH/storage/memory/{id} | revision oraz content/category/source/source_id; konflikt409. Zmiana treści usuwa stary embedding. |
| DELETE/storage/memory/{id}?revision=N | Usunięcie przy aktualnej rewizji. |
| POST/storage/memory/{id}/index | Body revision; przed I/O sprawdza odczyt i prawo zapisu, jawnie indeksuje jeden tekst. |
| POST/storage/memory/search | query, limit?1–30, workshop_id?; wyłącznie semantic, brak cichego fallbacku. |

Indeksowanie i wyszukiwanie wymagają również `JARVIS_EMBEDDINGS_ENABLED=true`, jawnego lokalnego OLLAMA_EMBED_MODEL oraz OLLAMA_EMBED_URL zgodnie z istniejącą konfiguracją recall. Nazwy :cloud (także wielkie litery) są blokowane. Sieć pozostaje przypięta do dozwolonego origin/IP. Odczyty/lista/CRUD nie wykonują embeddingu. Indeks wysyła wyłącznie treść wybranego rekordu, wyszukiwanie wyłącznie query właściciela. Brak chmurowego embeddingu i automatycznego indeksowania.

Po odpowiedzi modelu backend ponownie sprawdza aktywację i aktualną sesję właściciela; zapis dodatkowo wymaga niezmienionej rewizji/hasza i bieżącego RLS. Cofnięta sesja lub równoległa korekta nie zapisują embeddingu. Błąd dostawcy502 nie zmienia rekordu. Search zwraca tylko wyniki aktualnie widoczne w wybranym zakresie i namespace; nie dopisuje ich do czatu ani pamięci SQLite. Nie ma globalnego cache/querylogu z treścią. Zdarzenia pamięci są metadanymi w PostgreSQL, bez treści; nie są jeszcze nowym widokiem Activity w React.

Dodatkowe4testy rzeczywistego API/PG z prawdziwym lokalnym HTTP/api/embed i syntetycznymi wektorami sprawdzają CRUD/search/private/workshop, brak I/O przy braku praw/nieaktualnej rewizji oraz cofnięcie sesji/korektę podczas embeddingu. Testy granic API sprawdzają domyślne wyłączenie bez sieci, rolę, brak podszycia owner_id i zachowanie SQLite. Test protokołu embeddingu nie dowodzi inferencji modelu. Osobny jobCI postgres-memory przygotowuje ten sam izolowany runner; wykonanie GitHubCI pozostaje NOT_RUN.

## M3.4 w toku

Checkpointfeature3 dodaje historię i profile instrukcji; wcześniejszefeature1/2 są zachowane. Profile nie są jeszcze dołączane do kontekstu AI i nie mają nowego GUI. [Kontrakt i pozostałe prace](POSTGRES-PROFILES.md).
