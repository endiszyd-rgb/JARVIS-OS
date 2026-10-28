# Profile i historia pamięci — M3.4

Core0.10.3: wersjonowane profile i historia notatek, jawny pin profilu do sesji AI oraz panel React pamięci PostgreSQL.

## Migracja i uprawnienia

Opcjonalna funkcja pamięci otrzymała migration3 w migrations/postgres_memory/0003_versions_profiles.sql. PodstawaPG1/SQLite12 pozostają bez zmian; wcześniejsze0001/0002 zachowano. Migracja wymaga jawnego CLI `scripts/migrate_postgres.py --memory`, sekretu migratora i istniejącego przygotowania pgvector z [POSTGRES-MEMORY.md](POSTGRES-MEMORY.md). Nie wykonuje jej start Core ani API. Pamięć z feature1/2 nadal ma obsługę dotychczasowych operacji; nowe profile i historia wymagają3.

Tabele memory_versions, memory_profiles, memory_profile_versions i memory_profile_events mają FORCE RLS. Zakres jest prywatny albo jeden jawny workshop. Dostęp do historii zależy od bieżącego dostępu do jej rekordu. Czytelnik warsztatu widzi wspólny profil i jego wersje, lecz nie może go zmienić; utrata członkostwa odbiera dostęp autorowi. Prywatny profil jest odrębny dla konta owner i klucza bootstrap. Subject nie pochodzi z ciała żądania.

Migrujący użytkownik nie potrzebuje superuser/BYPASSRLS do tworzenia ani działania historii. Wąskie funkcje triggerowe SECURITY DEFINER ze stałym search_path=pg_catalog zapisują wyłącznie snapshot w jawnie wskazanej tabeli. Dla ich właściciela istnieje tylko odpowiednia polityka INSERT; runtime otrzymuje wyłącznie SELECT historii i nie może jej dopisywać, edytować ani kasować. EXECUTE funkcji triggerowych jest odebrane rolom aplikacyjnym; same wyzwalacze działają dla zweryfikowanych mutacji rodzica. SQL nie przyjmuje poleceń z treści profilu.

## API właściciela

Wymaga JARVIS_POSTGRES_MEMORY_ENABLED=true, ograniczonego DSN i jawnej migracji, tak jak wcześniejsze API pamięci. Brak aktywacji daje503 bez połączenia z PostgreSQL. Prefiks `/api/v1` lub alias`/api`:

| Trasa | Znaczenie |
| --- | --- |
| GET/storage/memory/profiles?workshop_id=UUID&limit=50&offset=0 | Domyślnie tylko prywatne profile; opcjonalnie dokładnie jeden warsztat, z RLS. |
| POST/storage/memory/profiles | name1–100znaków, instructions1–4000znaków, workshop_id?; nowa revision0, status201. |
| GET/storage/memory/profiles/{id} | Bieżący profil; obcy lub usunięty404. |
| PATCH/storage/memory/profiles/{id} | revision/name/instructions; brak aktualnej rewizji409, brak prawa zapisu403. |
| DELETE/storage/memory/profiles/{id}?revision=N | Usuwa profil i wszystkie zachowane treści jego wersji; metadane audytu pozostają. |
| GET/storage/memory/profiles/{id}/history | Wersje od najnowszej, limit1–100 i offset0–100000. |
| GET/storage/memory/{id}/history | Bieżąca revision i wersje notatki, z tym samym stronicowaniem. |

owner_id, role, subject i początkowa revision nie są polami tworzenia profilu. Zakres/własność/UUID/czas utworzenia profilu są niezmienne. Każda korekta zwiększa rewizję o1 i tworzy snapshot w tej samej transakcji. Zdarzenie profilu jest metadanymi, bez instrukcji; błąd audytu wycofuje zmianę i nową wersję.

## Co obejmuje historia

Nowe notatki i profile od migracji3 mają snapshot każdej zapisanej rewizji. W notatce uwzględnia to także zmianę indeksu, bo indeksowanie zwiększa jej revision. Wersje notatki zawierają treść, kategorię, deklarowane pochodzenie, hash, status indexed oraz oryginalny czas aktualizacji; nie zawierają surowego wektora. Profil zachowuje nazwę, instrukcje, rewizję i czas aktualizacji. captured_at wskazuje czas uchwycenia wersji.

Migracja nie odtwarza nieistniejących dawnych wersji. Dla notatki sprzed migracji3 pierwsza późniejsza edycja zachowuje jej bezpośrednio poprzedni stan i nowy stan. Jeszcze wcześniejszych rewizji nie wymyślamy ani nie kopiujemy z innego źródła. `history_before_feature3_available:false` informuje o braku pełnej historii sprzed tej migracji; lista versions może zawierać uchwycony przy pierwszej edycji poprzedni stan. Dla jeszcze nieedytowanej starej notatki historia może być pusta, a bieżąca treść pozostaje dostępna przez zwykły GET rekordu.

Usunięcie notatki lub profilu kaskadowo usuwa ich treści z tabel wersji. Pozostają wyłącznie metadane zdarzeń bez treści. Nie usuwa to automatycznie kopii backupowych ani dawnych odpowiedzi AI, które mogły już powtórzyć notatkę; bieżący kontekst takich rozmów jest chroniony ponowną walidacją źródeł zM3.3.

## Profil przypięty do rozmowy i panel

Migration4 dodaje nullable profile_id/profile_revision do memory_sessions oraz niezmienność przypięcia. Starsze sesje bez profilu nadal działają, także na feature2. Tworzenie sesji może zawierać `profile_ref:{"id":"UUID","revision":0}`. Bieżący profil musi być widoczny przez RLS i należeć do dokładnie tego samego zakresu. Kontrole następują przy tworzeniu, przygotowaniu tury, przed modelem, przed zapisem i odczycie historii. Korekta/usunięcie profilu daje409 i wymaga nowej sesji; sesję można nadal usunąć. Model otrzymuje instrukcje jako ograniczone preferencje stylu pod nadrzędnymi regułami; nie otrzymuje narzędzi ani uprawnień.

W React Pamięć → „Pamięć i profile PostgreSQL” osobny status poprzedza pobieranie danych; feature4 jest wymagane dla całego panelu. Domyślny zakres prywatny, opcjonalnie UUID warsztatu. Jawny odczyt, strony20rekordów, historia do100wersji, formularze CRUD zCAS, osobne potwierdzenie usunięcia. Wybór profilu i0–5notatek poprzedza nową rozmowę; dostawca/model konfiguracji serwera, zgoda cloud w każdej turze. Bieżąca sesja jest lokalnym wyborem tej karty; powrót do starych sesji dostępny przez API, nie przez listę w tym panelu. Przerwanie karty/timeout wymaga odczytu stanu, nie gwarantuje cofnięcia operacji. Błędy mutacji blokują ponowienie do odświeżenia.401/zmiana konta odrzuca prywatny stan i spóźnione odpowiedzi. SQLite działa na osobnej zakładce.

## Weryfikacja

`.venv/bin/python scripts/check_postgres.py --memory --browser --skip-pull` uruchamia izolowany DockerPG i opcjonalny prawdziwy Chromium/Playwright z zbudowanym frontendem. Wymaga lokalnego Chromium (`JARVIS_BROWSER_EXECUTABLE` może wskazać jego ścieżkę). Bez --browser kontroluje backend; zwykła regresja pomija chronione testy PG.76realnychPG/API/browser PASS/0skip, w tym upgrade1→2→4 ograniczonym migratorem i zachowanie wcześniejszych sesji.149UI,817pytest/75skip,build i nowyDocker PASS; evals/postgres-profiles-m34.json. Odpowiedzi HTTP modeli są syntetyczne. Realna inferencja, Windows i produkcja NOT_RUN.
