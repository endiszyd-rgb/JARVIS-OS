# Pamięć rozmowy PostgreSQL — M3.3

Core0.10.2 udostępnia osobną rozmowę tekstową właściciela z pamięcią krótkoterminową w PostgreSQL i jawnym wyborem notatek pamięci długoterminowej. Sesja należy do jednego konta i ma niezmienny zakres: prywatny albo jeden warsztat. Nawet inni członkowie tego warsztatu nie widzą tekstu tej sesji. Model i dostawca są przypisane podczas tworzenia; zmiana wymaga nowej sesji.

To osobna ścieżka od dotychczasowego `/chat` i jego interfejsów React/legacy. Nie importuje pamięci ani historii SQLite, nie uruchamia parsera ustawień lub automatycznego zapamiętywania. Nie podłącza voice, recepcji klientów ani tool-chat. Nie zapisuje prywatnych odpowiedzi PostgreSQL we wspólnej dla kont owner historii SQLite. Nowa ścieżka jest dostępna przez API; GUI pamięci PostgreSQL pozostaje pracą M3.4.

## Konfiguracja i migracja

Wymaga ograniczonego `JARVIS_POSTGRES_DSN`, `JARVIS_POSTGRES_MEMORY_ENABLED=true` oraz jawnej migracji pamięci do wersji2:

```sh
.venv/bin/python scripts/migrate_postgres.py --memory
```

Przy pierwszym uruchomieniu najpierw wykonaj przygotowanie oddzielnej bazy JARVIS, fundamentu migration1 i administracyjną instalację pgvector według [POSTGRES.md](POSTGRES.md) i [POSTGRES-MEMORY.md](POSTGRES-MEMORY.md). Runtime nie dostaje uprawnień administratora ani migratora. Start Core nie wykonuje DDL. Feature1 pozostaje obsługiwana dla wcześniejszego CRUD pamięci; nowe sesje wymagają feature2. SQLite schema12 i fundament PostgreSQL schema1 pozostają niezależne.

Migracja0002 dodaje memory_sessions, memory_turns i memory_session_events, z FORCE RLS i jawnymi grantami. Nie edytuje migracji0001. Test rzeczywistej bazy przeprowadza upgrade1→2 ograniczonym migratorem bez superuser/BYPASSRLS i sprawdza zachowanie treści, wektorów i wyszukiwania.

## Przepływ API

Prefiks zalecany `/api/v1`, zgodny alias `/api`. Wszystkie trasy wymagają aktualnego klucza bootstrap lub sesji konta owner. Subject bierze backend; JSON, numer klienta i wynik modelu nie mogą go ustawić. Token usługi z prawami pluginu nie daje tych uprawnień.

1. Pobierz notatki przez GET/storage/memory w wybranym zakresie albo wykonaj jawne semantic/search. Każda ma id i revision.
2. Utwórz sesję przez POST/storage/memory/conversations:

```json
{"model":"ollama","ttl_minutes":60}
```

Opcjonalne `model_name` musi być na allowliście. Opcjonalne `workshop_id` wybiera dokładnie jeden warsztat, którego jesteś aktualnym członkiem. Brak tego pola oznacza wyłącznie zakres prywatny. Model Ollama musi już być dostępny i obsługiwać zwykłe odpowiedzi tekstowe; API niczego nie pobiera.

3. Wyślij POST/storage/memory/conversations/{id}/turns z bieżącą rewizją sesji:

```json
{
  "revision":0,
  "message":"Uwzględnij wskazaną notatkę w odpowiedzi.",
  "memory_refs":[{"id":"00000000-0000-4000-8000-000000000001","revision":0}]
}
```

UUID w przykładzie jest placeholderem — zastąp go ID własnej notatki. Można jawnie wybrać0–5różnych notatek na turę. Muszą pasować do zakresu sesji oraz aktualnej rewizji; prywatna notatka nie może trafić do sesji warsztatowej. Nie ma automatycznego wyszukiwania ani ukrytego dołączania notatek w tej ścieżce. W kolejnych turach wolno pominąć memory_refs; wcześniejsze pomyślne wypowiedzi stanowią ograniczony kontekst.

4. Odpowiedź zawiera reply, model/model_name, session_id, nową revision, context_messages, wybrane memory_refs i usage. `history_storage:postgresql`, `sqlite_history_saved:false` i `automatic_memory_saved:false` wskazują rzeczywisty sposób zapisu.
5. GET/storage/memory/conversations/{id}/messages pokazuje ten sam ograniczony kontekst; GET/{id} i GET/storage/memory/conversations pokazują metadane. DELETE/{id}?revision=N usuwa własną sesję i jej tury przy zgodnej rewizji. Aktywna tura blokuje usunięcie; wygasłą sesję można usunąć, o ile nadal masz dostęp do jej zakresu.

Dla OpenAI dodatkowo wymagane są aktywacja, ceny i budżet z [LLM-PROVIDERS.md](LLM-PROVIDERS.md). Każdy POST/turns wymaga **`allow_cloud_context:true`**. Bez tego zwraca409 przed inferencją. Zgoda oznacza wysłanie pytania, ograniczonej historii tej sesji oraz jawnie wybranych notatek do dostawcy chmurowego. Konfiguracja `store:false` nie obiecuje zerowej retencji dostawcy. Ollama `:cloud` jest blokowana.

## Izolacja, źródła i uprawnienia

RLS filtruje sesje według właściciela i aktualnego członkostwa; warsztatowy tekst rozmowy pozostaje prywatny dla jej autora. Notatki warsztatowe nadal mogą czytać pozostali uprawnieni członkowie według M1.4/M3.3. Członkostwo tylko do odczytu wystarcza do prywatnej rozmowy o dostępnych notatkach; rozmowa nie zmienia danych warsztatu ani notatek.

Przed inferencją backend sprawdza bieżącą tożsamość, aktywację, allowlistę modelu, RLS i rewizje źródeł. Po odpowiedzi ponawia kontrole; bezpośrednio przed zapisem ponownie sprawdza tożsamość. Cofnięcie sesji/konta, usunięcie członkostwa, wygaśnięcie rozmowy albo zmiana/usunięcie użytego źródła powoduje odmowę zapisu i zwrotu tej odpowiedzi. Nie da się cofnąć danych już wysłanych do modelu; te kontrole nie stanowią rozproszonej transakcji między bazą, SQLite i dostawcą.

Każda zapisana tura zachowuje również referencje do źródeł użytych przez jej wcześniejszy kontekst. Dzięki temu po usunięciu oryginalnej tury z ograniczonego okna kontekstu wcześniejsza wiedza nie traci informacji o pochodzeniu. Aktualnie używane historyczne źródła są ponownie sprawdzane. Zmiana rewizji notatki (także przy indeksowaniu) wymaga nowej sesji, gdy poprzedni kontekst nadal od niej zależy. Maksymalnie20różnych źródeł może występować w zachowanym kontekście.

Pytania, notatki i odpowiedzi modelu są tekstem. Nie stają się Principal, instrukcjami SQL, uprawnieniami ani wykonywalnymi poleceniami. Modele w tym API nie dostają tools. Wynik może być błędny lub zmanipulowany; brak wykonania działań nie dowodzi odporności samego tekstu na dowolny prompt injection.

## Limity, czas i współbieżność

- TTL1–1440minut od utworzenia, domyślnie60; bez automatycznego przedłużania. Po wygaśnięciu metadane pozostają, ale RLS blokuje odczyt tur, API kontekstu zwraca410. TTL ogranicza użycie, nie jest fizycznym wymazaniem. Usunięcie sesji usuwa tury; metadane audytu pozostają. Retencja i pełne operacyjne odtwarzanie należą do dalszych etapów.
- Do32aktualnie widocznych aktywnych sesji na konto. Osobna blokada transakcyjna serializuje sprawdzenie limitu i utworzenie sesji. Po utracie członkostwa niewidoczne sesje nie są liczone do tego widocznego zbioru.
- Do64pomyślnych tur na sesję. Pytanie1–8000znaków; odpowiedź modelu1–32000. Unicode/blank/NUL są walidowane przed zapisem.
- Kontekst obejmuje maksymalnie10najnowszych pełnych par (20wiadomości) i16000znaków. Nie tniemy par w środku. Zbyt duża ostatnia para może pozostawić pusty kontekst; context_messages pokazuje faktycznie użyty rozmiar. Provider dodatkowo ogranicza serializowane wejście do256KiB.
- Do2równoległych żądań inferencji na proces; brak wolnego miejsca zwraca429, bez kolejki. Całość ma timeout90s, z ograniczonymi timeoutami SQL i HTTP. Dzierżawa jednej tury w bazie trwa120s i działa także pomiędzy procesami Core. Równoległa próba tej samej sesji dostaje409 przed modelem.
- Rewizja klienta i identyfikator dzierżawy muszą nadal pasować przy zapisie. Stara dzierżawa nie kończy nowej tury. Przerwanie podczas przygotowania synchronicznej transakcji czeka na jej rozstrzygnięcie i zwalnia uzyskaną dzierżawę. Przy niedostępności bazy lub utracie dostępu do zakresu działa ograniczone wygaśnięcie dzierżawy.
- Nie ma retry ani cichego fallbacku. Jedna tura wykonuje najwyżej jedno żądanie LLM. Budżet chmury ogranicza to żądanie, nie sumę64tur ani wszystkie równoległe rozmowy. Rezerwacja pełnego kontekstu, usage i billing_verified:false zachowują reguły M3.1.

Nieudana/przerwana inferencja nie dopisuje częściowej pary do historii. Zapis pary, zwiększenie rewizji i metadane zdarzenia są atomowe w PostgreSQL; błąd audytu wycofuje wszystko. Samo zerwanie HTTP lub timeout klienta nie potwierdza zatrzymania serwera — operacja mogła już zostać zatwierdzona. Przed powtórzeniem pobierz aktualną rewizję i kontekst; zgodność rewizji zapobiega ponownemu wykonaniu już zatwierdzonej tury.

Metadane audytu zawierają subject, session_id, event, revision i czas, bez pytania, odpowiedzi lub treści notatek. Tury przechowują pytanie/odpowiedź i referencje pamięci, ale nie kopiują surowych notatek ani sekretów serwera. Odpowiedź modelu może oczywiście powtórzyć treść wybranej notatki; dlatego historia ma takie same granice konta i zakresu. Nie czyścimy automatycznie dawnych wygenerowanych tekstów po usunięciu notatki; aktualny kontekst z nieaktualnymi referencjami jest blokowany.

## Wykonane sprawdzenia

Testy test_postgres_context.py i test_postgres_context_integration.py obejmują limity i kompletne pary, trwałość, RLS dwóch kont/warsztatów, brak dostępu innych członków do tekstu sesji, leases/replay/revision/expiry, quota, atomic audit i kaskadowe usuwanie. Sprawdzono również upgradefeature1→2 ograniczonym migratorem, zachowanie wektorów, zmianę notatek, cofnięcie sesji i członkostwa podczas inferencji oraz timeout podczas przygotowania dzierżawy.

Testy protokołów używają rzeczywistych lokalnych Ollama/OpenAI HTTP z syntetycznymi odpowiedziami i rzeczywistej bazy. Dodatkowa ścieżka uruchamia prawdziwy port HTTP Core: utworzenie notatki → lokalny HTTP embedding → indeks/pgvector/search → sesja → dwie tury modelu → odczyt historii → odrzucenie obcego konta → korekta źródła → odmowa kolejnej inferencji → usunięcie sesji. Raport runnera: [postgres-memory-m33.json](evals/postgres-memory-m33.json).

Prawdziwa inferencja/jakość modeli, rzeczywiste konto chmurowe, GUI nowej pamięci, Windows/WSL2 i urządzenia pozostają NOT_RUN. Produkcja AutoLogika/Supabase nie jest używana.

## M3.4 — profile sesji i panel pamięci PostgreSQL

Core0.10.3/feature4: tworzenie /storage/memory/conversations przyjmuje opcjonalny profile_ref z id i revision. Profil jest niezmiennie przypięty do nowej sesji; aktualny RLS/scope/revision sprawdzane przedLLM i zapisem. Korekta/usunięcie profilu:409, nowa sesja. React Pamięć ma osobną zakładkę PG: CRUD/history/CAS, potwierdzenie usunięcia, wybór profilu/notatek i osobna rozmowa z cloudzgodą per tura. Szczegóły POSTGRES-PROFILES.md; brak wspólnej historii zeSQLite.
