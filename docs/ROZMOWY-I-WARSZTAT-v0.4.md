# Rozmowy i odczyt kopii warsztatu — 0.4

## Sesje rozmów

Czat zapisuje wiadomości w bazie JARVIS-a. Każda sesja ma własny tytuł, dostawcę i nazwę modelu. Panel pozwala utworzyć sesję, wrócić do niej, zmienić tytuł, wyeksportować JSON lub usunąć ją z aktywnej bazy. W panelu lista obejmuje ostatnie 50 sesji i ostatnie 100 wiadomości wybranej sesji; API ma stronicowanie. Zwykłe stare wywołanie POST /api/chat bez session_id nadal działa — tworzy nową sesję i zwraca jej identyfikator.

Do modelu trafiają: instrukcja systemowa, do 10 jawnych notatek, ograniczony ogon udanych wiadomości tej samej sesji oraz bieżące pytanie. Ogon ma maksymalnie 20 wiadomości i 24 000 znaków; nie jest to limit tokenów ani semantyczne streszczenie. Wiadomości innych sesji, nieudane żądania i wiadomości w toku nie są dodawane do tego ogona. Jawne notatki pozostają wspólne dla właściciela; sesje nie są odseparowanymi kontami użytkowników. Zmiana modelu w istniejącej sesji zachowuje jej historię.

Jedna sesja przyjmuje jedno aktywne żądanie. Drugie równoległe otrzyma 409. Limit czasu całej odpowiedzi wynosi 90 s, a blokada przerwanego procesu może zostać odzyskana po 180 s przy kolejnym żądaniu. Nieudana wiadomość pozostaje oznaczona failed, bez wymyślonej odpowiedzi modelu. Usuwanie podczas aktywnego żądania jest blokowane. Nie dodano streamingu odpowiedzi, trwałej kolejki ani automatycznych ponowień — ręczne ponowienie to nowa wiadomość.

Usunięcie sesji usuwa jej wiadomości logicznie z aktywnej bazy. Nie czyści starszych backupów, eksportów ani wolnych stron pliku SQLite. Audyt przechowuje identyfikatory i zdarzenia, bez treści rozmowy. Backup Core zawiera historię. Ograniczone tokeny usług z 0.3 nie mają dostępu do historii.

Retencja jest ręczna: POST /api/chat/retention z `{days:30,dry_run:true}` pokazuje liczbę nieaktywnych sesji starszych według updated. Dopiero dry_run=false usuwa je. Nie uruchamiamy automatycznego kasowania. Sesje z blokadą active_turn są pomijane; stara blokada jest odzyskiwana przy nowej wiadomości lub można usunąć taką sesję po 180 s.

## Wybór modeli

```dotenv
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_ALLOWED_MODELS=qwen2.5:3b,nazwa-twojego-drugiego-modelu
JARVIS_ALLOW_CLOUD_MODELS=false
```

Lista /api/models jest katalogiem skonfigurowanym przez właściciela. Nie sprawdza instalacji, nie pobiera modeli i nie weryfikuje możliwości sprzętu. Model musi być dostępny w Twoim serwerze Ollama. Brak modelu lub awaria serwera daje jawny błąd; nie udajemy odpowiedzi AI przez cichy fallback do DEMO. Nazwa spoza listy jest blokowana przed HTTP.

Nazwy kończące się `:cloud` są ukryte i blokowane, dopóki właściciel nie doda ich do listy oraz nie ustawi JARVIS_ALLOW_CLOUD_MODELS=true. To dodatkowy bezpiecznik dla tak nazwanych modeli, nie dowód, że dowolny inny alias lub pośredniczący serwer działa offline. Właściciel odpowiada za wybór zaufanego serwera/modelu. Model chmurowy otrzyma przekazany kontekst tak samo jak lokalny — zwróć uwagę na notatki, historię i dołączone dane warsztatu.

Pole model w zatwierdzanych ustawieniach jest domyślnym dostawcą nowych sesji, a wybrana nazwa jest zapisywana w sesji. Katalog i nazwy konfiguruje się w .env i stosuje po restarcie. DEMO pozostaje jawnym, deterministycznym trybem testowym.

## Snapshot AutoLogiki

Nowy most jest czytnikiem **kopii lokalnej**, a nie dodatkowym istniejącym API AutoLogiki. Nie zmieniono produkcyjnego repozytorium i nie dodano do niego endpointów. Nadal działa też osobny klient istniejącego serwera mobilnego GET /api/orders i /api/order/{id}.

Potwierdzony kontrakt kopii: schemat SQLite user_version=18 z commitu 681f7f5. Inne wersje wymagają osobnego audytu i są blokowane. Nie uruchamiamy migracji AutoLogiki. Oryginalną bazę wybierasz jawnie w środę; kod nie szuka jej automatycznie po katalogach Windows.

Przy zatrzymanym Core utwórz kopię:

```powershell
.\.venv\Scripts\python.exe .\scripts\import_autologika.py --source "C:\dokladna\sciezka\autologika.db"
```

Można wskazać aktualny backup wykonany przez AutoLogikę zamiast aktywnej bazy. Źródło jest otwierane mode=ro, a SQLite backup API wykonuje spójną kopię także danych zatwierdzonych w WAL. Nie kopiuj ręcznie samego pliku aktywnej bazy z pominięciem WAL. Skrypt nie zapisuje rekordów ani nie checkpointuje źródła; SQLite może korzystać z istniejących plików współdzielonych WAL/SHM. Kopia ma limit wykonania 30 s i test integralności.

Powstają `data/autologika/workshop.snapshot.sqlite3` oraz `workshop.snapshot.json` z datą, kontraktem i SHA-256. Sekrety synchronizacji mogą znajdować się w pełnej bazie źródłowej, dlatego nie udostępniaj kopii innym osobom. API pokazuje tylko jawnie wybrane tabele/kolumny domenowe, a nie app_settings, sync_meta ani dowolny SQL.

W .env ustaw:

```dotenv
AUTOLOGIKA_SNAPSHOT_ENABLED=true
AUTOLOGIKA_SNAPSHOT_PATH=data/autologika/workshop.snapshot.sqlite3
```

Uruchom Core ponownie. Zakładka AutoLogika · kopia pokazuje datę kopii i tryb snapshot_readonly. Każdy odczyt sprawdza SHA-256 i otwiera plik immutable+mode=ro, z query_only oraz limitem czasu zapytań. Odświeżanie kopii wykonuj przy zatrzymanym Core, aby podmiana pliku i manifestu nie kolidowała z odczytem. To nie synchronizacja na żywo. Domyślny backup bazy JARVIS-a nie obejmuje plików snapshotu; zachowaj oba osobno, jeżeli są potrzebne.

## Osiem domen

| Domena | Dane odczytywane z potwierdzonych tabel | Zakres |
|---|---|---|
| calendar | appointments | Wizyty, terminy, stanowisko, status |
| orders | orders | Zlecenia, oczekiwanie, termin, cena i koszty zmienne |
| vehicles | vehicles | Marka/model, VIN, właściciel-ID, przebieg |
| parts | job_part_orders, inventory_parts, repair_parts | Osobne kolekcje zamówień, magazynu i części operacji; nie sumujemy ich jako jednego stanu |
| customers | customers | Wybrane dane kontaktowe i firma |
| finances | orders, payments | Wartości, wkład, płatności i należności |
| reports | orders | Liczby statusów wszystkich nieusuniętych zleceń, także WYDANE |
| notifications | orders, communications, job_part_orders, approvals, vehicle_findings, vehicles | Rodziny WAIT, REPLY, PART_LATE, APPROVAL, VEHICLE_FINDING |

Listy mają limit 1–200 i offset. Części są stronicowane osobno dla każdej kolekcji. To użyteczny podzbiór odczytu, nie pełny odpowiednik ekranów, profili, wykresów i logiki IPC AutoLogiki. Brak wymaganej tabeli lub kolumny blokuje domenę zamiast podstawiania wymyślonych danych. Tombstones deleted_at są pomijane tam, gdzie kolumna istnieje; przy porównywaniu desktopu uwzględnij różnice filtrów. W raporcie 0.4 i testach wskazano ten zakres.

Cena jest liczona jak w audytowanym order-financials.cjs: COALESCE(final_price, labor_hours×labor_rate + parts_sale + other_sale + diagnosis_fee − discount). Cena końcowa 0 pozostaje 0. Wkład to cena minus parts_cost i other_cost, **nie pełny zysk księgowy**. Wartość zleceń i należności są grupowane według opened_at w wybranym miesiącu, płatności według paid_at. Płatność w październiku za wrześniowe zlecenie jest październikową płatnością, ale nie październikowym zleceniem.

Powiadomienia są wyliczane teraz na danych kopii, używając czasu SQLite UTC. Mogą różnić się od desktopu w szczegółach prezentacji, filtrach, strefie czasu i dostępie do bieżących zmian. Nie wysyłają wiadomości i nie zmieniają statusów.

## Podsumowanie warsztatu w rozmowie

Checkbox „Dołącz podsumowanie kopii warsztatu…” jest domyślnie wyłączony. Gdy go zaznaczysz, Core dołączy tylko statusowe agregaty reports i finances oraz datę kopii — bez list klientów, telefonów i VIN. API: include_workshop_summary=true, opcjonalnie workshop_month=YYYY-MM. DEMO może wtedy pokazać deterministyczne podsumowanie, a Ollama otrzyma dane jako opisany kontekst offline.

Ta opcja nie odblokowuje narzędzi ani zapisów. Model nie pobiera sam danych klienta. Treść odpowiedzi wykorzystująca agregaty zostaje w historii i może być kontekstem kolejnych pytań tej sesji, także po zmianie modelu. Wyłączenie checkboxa nie usuwa wcześniej przekazanych danych z historii. Załóż nową sesję lub usuń historię, gdy chcesz oddzielić taki kontekst.

## Laboratorium bez PC warsztatu

```bash
python -m examples.workshop_fixture
python scripts/import_autologika.py --source data/lab/autologika-fixture.db
```

Następnie włącz snapshot w .env i uruchom Core. Dane są syntetyczne; status snapshot_readonly opisuje sposób odczytu, nie pochodzenie danych. Nazwy w laboratorium jawnie wskazują DEMO/SYNTHETIC. Nie nadpisuj tą bazą AutoLogiki. Generator odmawia nadpisania istniejącego pliku. W Dockerze import na hoście nie przenosi automatycznie kopii do nazwanego wolumenu — trzeba zamontować parę plików read-only i wskazać ścieżkę widoczną w kontenerze, z prawami odczytu dla UID 10001. Ten krok pozostaje do testu Windows/Docker; na pierwszy test użyj lokalnego Pythona.

## Źródła

- Rzeczywisty kod AutoLogiki i SHA plików: AUDYT_AUTOLOGIKA.md oraz autologika-evidence.json.
- Ollama chat/messages: https://docs.ollama.com/api/chat i https://github.com/ollama/ollama/blob/main/docs/api.md — API konwersacji.
- SQLite URI mode=ro/immutable: https://www.sqlite.org/uri.html — właściwości otwierania pliku.
