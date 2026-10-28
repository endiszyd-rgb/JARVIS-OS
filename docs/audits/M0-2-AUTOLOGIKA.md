# M0.2 — audyt źródeł AutoLogika OS

Audyt statyczny publicznego `endiszyd-rgb/Autologika-OS`, wykonany 2026-10-22 UTC. Zbadany commit: **`681f7f5ecf5a1e365022a9ac1cb22b6ff443262c`**, zgodny z HEAD potwierdzonym przez `git ls-remote` i wcześniejszym manifestem. Odczytano osobny checkout w `/tmp/autologika-M0-2-inspection`; jego `git status --porcelain` pozostał pusty. Nie uruchamiano kodu AutoLogiki, instalatorów, testów, migracji SQL ani żądań do produkcji. Produkcyjny system i Supabase nie były zmieniane.

[Dowody maszynowe i SHA-256](M0-2-evidence.json) zawierają 17 przypiętych plików, w tym **8/8 identycznych hashy** względem [wcześniejszego manifestu](../autologika-evidence.json). Numery linii poniżej dotyczą wyłącznie wskazanego commitu; pełny adres każdego pliku znajduje się w JSON. Raport uzupełnia [wcześniejszy audyt](../AUDYT_AUTOLOGIKA.md), nie stanowi potwierdzenia bieżącego wdrożenia.

## Struktura i backend

`package.json:3–45` deklaruje aplikację 1.1.1, Electron 34, React 18, Vite 6 i better-sqlite3 11; punktem wejścia jest `electron/main.cjs`. `src/` zawiera interfejs React i modele widoków, `electron/` moduły domenowe oraz backend desktopowy, `supabase/` funkcję zatwierdzeń i migrację, `tests/` testy Node, `scripts/` audyty i próby Electron.

Główny interfejs domenowy to **IPC Electron**: statycznie znaleziono 262 deklaracje `ipcMain.handle`. `electron/preload.cjs:1–28` udostępnia `window.autologika` przez `contextBridge`, np. klientów, pojazdy, zlecenia, płatności, naprawy i powiadomienia. `electron/main.cjs:51` ustawia `contextIsolation:true`, `nodeIntegration:false`. Te operacje nie są automatycznie zdalnymi endpointami HTTP.

## Modele lokalne i migracje

`electron/db.cjs:9–11` określa SQLite **schema 18**, bazę `userData/autologika.db` i katalog `backups`. `:18–25,44–48` tworzy kopię przed migracją istniejącej starszej bazy, a `:77–154` wykonuje kolejne migracje w transakcjach wraz z `PRAGMA user_version`. Statyczna lista obejmuje 57 unikalnych nazw `CREATE TABLE IF NOT EXISTS`; pełny wykaz zapisano w JSON. To inwentaryzacja źródła, nie odczyt bazy produkcyjnej.

| Obszar | Potwierdzone tabele / logika | Dowód |
| --- | --- | --- |
| Klient, pojazd, zlecenie | `customers`, `vehicles`, `orders` | `electron/db.cjs:639–661` |
| Diagnostyka i pozycje | `diagnostics`, `order_items` | `electron/db.cjs:662–687` |
| Terminarz i zasoby | `appointments`, `work_resources`, `resource_unavailability`, `appointment_resources` | `electron/db.cjs:318–346,709` |
| Części, płatności, QC | `job_part_orders`, `payments`, `order_qc` | `electron/db.cjs:801,855,926` |
| Finanse | kwota końcowa zastępuje bazę: roboczogodziny × stawka + sprzedaż części/inne + diagnoza − rabat; koszty obejmują części i inne | `electron/order-financials.cjs:1–3` |

Raportów i powiadomień nie należy przedstawiać jako rzekomych tabel lub ogólnych REST API. Istnieją obliczane operacje IPC, np. `finance:analytics` (`electron/main.cjs:466`), `appointments:list` (`:619`) i `notifications:list` (`:1078`). Wyliczona marża po kosztach części/innych nie dowodzi pełnego księgowego zysku.

## Faktyczny mobilny HTTP i auth

`electron/main.cjs:315–325` zapisuje `remote-access.json`; domyślnie port 8787, `autoStart:false`. Serwer tworzy `http.createServer` (`:362`) i nasłuchuje `0.0.0.0` (`:419`). Chronione trasy porównują wspólny nagłówek **`X-Autologika-Pin`** z PIN-em serwera (`:344,367`). Login sprawdza PIN i zwraca `{ok}`, bez tokenu sesji (`:366`). W tym handlerze nie znaleziono TLS, odrębnego zakresu odczytu ani limitera prób PIN; ewentualnych zabezpieczeń wdrożeniowych nie badano.

| Metoda i ścieżka | Zachowanie źródła | Linie `electron/main.cjs` |
| --- | --- | --- |
| `GET /`, `GET /app` | strona mobilna; publiczne | 364 |
| `GET /health` | `{ok:true,name:...}`; publiczne | 365 |
| `POST /api/login` | sprawdzenie `pin`; publiczna próba logowania | 366 |
| `GET /api/orders` | maksymalnie 100 zleceń o statusie innym niż `WYDANE`, `opened_at DESC` | 368 |
| `GET /api/sync` | wyłącznie `{ok:true,serverTime}`, nie synchronizacja rekordów | 369 |
| `GET /api/order/{id}` | `{order,notes,diag,parts,payments}`; 404 przy braku zlecenia | 370–380 |
| `PATCH /api/order/{id}` | zmiany statusu i `wait_state` z list dozwolonych | 382–387 |
| `PUT /api/order/{id}/notes` | zapis notatek przyjęcia/wydania/QC | 389–392 |
| `PUT /api/order/{id}/diagnostics` | zapis diagnostyki | 394–399 |
| `POST /api/intake` | transakcyjne utworzenie/odnalezienie klienta i pojazdu oraz utworzenie zlecenia | 401–415 |

Pozostałe ścieżki kończą się 404 (`:417`). Zapis jest tu opisany jako fakt źródłowy; **nie jest udostępniony ani autoryzowany do wykonania przez JARVIS w ramach audytu**.

## Supabase, auth i RLS

`electron/cloud-sync.cjs:15` określa `SYNC_TABLES`. Dane domenowe przesyłane są przede wszystkim jako JSONB w **`public.sync_records`**, z kluczem `(workshop_id,entity_type,cloud_id)` (`cloud_schema_supabase.sql:4–17`), a nie jako zakładane osobne chmurowe tabele zleceń i pojazdów. `cloud-sync.cjs:88` odtwarza relacje przez identyfikatory `cloud_id`; `:118,128` pokazuje zapis i stronicowany odczyt PostgREST.

Logowanie właściciela korzysta z Supabase Auth password grant (`cloud-sync.cjs:31`), a odświeżanie z refresh tokenu (`:35`). RLS `sync_records` jest włączone i ogranicza operacje roli `authenticated` warunkiem `workshop_id=auth.uid()` (`cloud_schema_supabase.sql:19–29`). Prywatny bucket `order-files` oraz reguły ścieżek właściciela są zadeklarowane w `:32–41`. Jest to wariant „jedno konto = jeden warsztat”; nie znaleziono w tym modelu odrębnej roli JARVIS z minimalnym zakresem odczytu. Źródłowy SQL nie potwierdza, że te polityki są wdrożone i skuteczne na produkcji.

Repo zawiera migrację **`supabase/migrations/20260925_remote_approval_2.sql`**: tabele linków i zdarzeń zatwierdzeń, RLS właściciela (`:20,63–70`), atomową funkcję `decide_customer_approval` z `SECURITY DEFINER` (`:99–138`), wycofanie jej wykonania z `public,anon,authenticated` i grant wyłącznie `service_role` (`:137–138`), prywatny bucket `approval-evidence` i odczyt właściciela (`:140–142`). Nie wykonywano tej migracji.

Odrębna funkcja Edge **`approval`** ma `verify_jwt=false` (`supabase/config.toml:1–2`). To publiczny przepływ zatwierdzenia kosztorysu z tokenem, nie ogólny interfejs biznesowy: `supabase/functions/approval/index.ts:14–29` weryfikuje stały origin i token oraz korzysta serwerowo z service role; `:33–52` sprawdza wygaśnięcie, oddaje ograniczoną projekcję dla `action=load` i waliduje zgodę/podpis/integralność przy `action=decide`; `:64` wywołuje atomowy RPC. Nie wolno utożsamiać braku JWT z brakiem innych kontroli ani przenosić klucza service role do JARVIS lub przeglądarki.

## Testy zadeklarowane a wykonane

Znaleziono **52 pliki `tests/*.test.cjs` / `*.test.mjs`**. `package.json:9–16` deklaruje testy Node, audyt połączeń UI, katalogu oraz osobne próby migracji, istniejącej bazy v18, UI i dokumentów przez Electron. Przykłady: `tests/database-migration.test.cjs:6–51` sprawdza migracje i ponowne ich wywołanie na bazie w pamięci; `tests/cloud-sync.test.cjs:6–108` obejmuje formaty czasu, mapowanie danych, powiązanie warsztatu i stronicowanie; `tests/remote-approval-security.test.cjs:17–43` sprawdza tekst źródeł RLS, storage, RPC i funkcji Edge. Te ostatnie asercje nie są testem skuteczności polityk na działającym Postgres.

`package.json:14` i `scripts/existing-db-v18-smoke.cjs:6–16` przewidują próbę na kopii istniejącej bazy. Workflow `.github/workflows/release.yml:13–43` deklaruje Windows/Node22, `npm test` i build. Sam zapis workflow nie dowodzi wyniku jego wykonania.

W ramach M0.2: **PASS** przypięty checkout, czysty katalog źródeł, weryfikacja 8/8 wcześniejszych SHA-256 i hashe 9 dodatkowych plików; **PASS** audyt statyczny. **NOT_RUN** upstream testy/build/Electron/Windows, instalacja zależności, runtime HTTP, SQL, integracja i skuteczność RLS na produkcji. Nie wykonywano testów JARVIS, ponieważ zmiany obejmują wyłącznie dwa dokumenty audytu i manifest dowodów.

## Granice i wnioski dla M0.3

Potwierdzone są desktopowe IPC, ograniczony mobilny HTTP i Supabase synchronizacji/zatwierdzeń. W mobilnym handlerze brak ogólnych tras HTTP terminarza, zasobów, klientów, pojazdów, raportów, analityki finansowej, powiadomień i QC; powiązane dane częściowo istnieją w domenie lokalnej lub szczegółach zlecenia. Nie znaleziono w zbadanych interfejsach kontraktu OpenAPI, dedykowanego API JARVIS ani poświadczenia mobilnego tylko do odczytu.

Następny kontrakt musi wskazać rzeczywisty transport i zakres danych dla każdej funkcji oraz jawnie oznaczyć luki. Bezpośredni zapis do tabel synchronizacji omijałby reguły domenowe i nie jest zatwierdzoną drogą integracji. Dostępność produkcji, wdrożone polityki, tożsamości warsztatów i dodatkowe interfejsy spoza publicznego źródła pozostają niezweryfikowane.
