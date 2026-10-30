
## M4.2 — diagnostyka i odczyty warsztatu (2026-10-29)

Kopia schema18 udostępnia dodatkową domenę diagnostics: objawy, DTC, pomiary, hipotezę, wnioski, zalecenia i czas. Odczyt przez GET /api/v1/autologika/snapshot/diagnostics ma paginację, pomija usunięte zlecenia i nie modyfikuje źródła. Brak tabeli/kolumn daje503; pozostałe domeny pozostają dostępne. Panel AutoLogika udostępnia diagnostykę właścicielowi i workshop_reader; finanse/raporty/powiadomienia nadal owner-only. Terminarz, pojazdy, klienci i części pozostają odczytami offline, nie wymyślonymi trasami live.

Testy backendu adapter/snapshot:39 PASS na syntetycznych danych. Produkcja i rzeczywista synchronizacja NOT_RUN.
# M0.3 — potwierdzone interfejsy AutoLogika

Źródło: publiczny commit `681f7f5ecf5a1e365022a9ac1cb22b6ff443262c`, ponownie odczytany w M0.2. [Raport z liniami źródeł](../audits/M0-2-AUTOLOGIKA.md), [SHA-256](../audits/M0-2-evidence.json). To kontrakt źródłowy, bez połączenia z bazą użytkownika. [Rejestr maszynowy](autologika-http.json).

## Mobilny HTTP

`electron/main.cjs`, `createMobileServer`, `mobileAuthorized`. Domyślny port 8787, opcjonalny start, współdzielony nagłówek `X-Autologika-Pin`. POST login sprawdza PIN, nie wydaje tokenu sesji. Serwer nie ma własnego TLS; nie wystawiać go publicznie. ID zlecenia jest lokalnym dodatnim numerem konkretnej instalacji.

| Metoda i trasa | Faktyczny kontrakt | Dostęp JARVIS |
|---|---|---|
| GET `/health` | Publiczne `{ok,name}` serwera mobilnego | Nie jest odczytem danych warsztatu ani dowodem synchronizacji |
| POST `/api/login` | `{pin}` → `{ok}`, 200/401 | Nie używany; bez wydawania sesji |
| GET `/api/orders` | Tablica; status różny od WYDANE, opened_at DESC, LIMIT100 | Jedna z dwóch operacji adaptera readonly |
| GET `/api/order/{id}` | `{order,notes,diag,parts,payments}`; brak zlecenia404 | Druga operacja adaptera readonly |
| GET `/api/sync` | `{ok,serverTime}` | Zegar serwera, nie replikacja danych |
| PATCH `/api/order/{id}` | Status/wait_state i zdarzenie mobilne | Niedostępne w adapterze JARVIS |
| PUT `/api/order/{id}/notes` | Notatki przyjęcia/wydania/QC | Niedostępne w adapterze JARVIS |
| PUT `/api/order/{id}/diagnostics` | Pola diagnostyki zlecenia | Niedostępne w adapterze JARVIS |
| POST `/api/intake` | Przyjęcie klienta/pojazdu/zlecenia | Niedostępne w adapterze JARVIS |

`jarvis/autologika.py` wykonuje wyłącznie dwa wskazane GET-y, po jawnym włączeniu integracji. Waliduje origin i PIN, nie podąża za przekierowaniami, ogranicza timeout i sprawdza typ list/dict. Nie gwarantuje pełnego schematu każdej kolumny. Żaden test kontrolowanego HTTP nie potwierdza dostępności prawdziwej instalacji ani zgodności jej wersji z tym commitem.

## IPC, kopia offline i braki ośmiu domen

Electron IPC i `preload.cjs` są interfejsem desktopu, nie automatycznie REST dla Pythona. Nazwy tabel i operacji pochodzą z `db.cjs`, `main.cjs` i modułów domenowych wymienionych w dowodach. Nie tworzymy nowych tabel/endpoints w AutoLogice.

| Domena | Źródło i dostęp | Granica |
|---|---|---|
| Terminarz | appointments/zasoby i IPC; snapshot JARVIS calendar | Brak potwierdzonego pełnego HTTP terminarza |
| Zlecenia | orders/items/notes/events; HTTP lista/szczegóły i snapshot | Lista100 bez WYDANE nie jest pełnym eksportem |
| Pojazdy/klienci | vehicles/customers, IPC i snapshot | Brak osobnych list HTTP; dane częściowo w zleceniu |
| Części | job_part_orders/inventory i reguły domenowe; HTTP parts w zleceniu, snapshot | Brak pełnego API magazynu i operacji zapisu |
| Finanse | payments i order-financials; snapshot | Wkład = final_price − koszty części/inne, nie pełny zysk księgowy; nie podwajać sum pozycji i nagłówków |
| Raporty | dashboard/finance/worklog/bays IPC; podzbiór agregatów snapshot | Brak ogólnego `/api/reports` i założenia tabeli reports |
| Powiadomienia | notifications:list wylicza m.in. WAIT/REPLY/PART_LATE/APPROVAL/VEHICLE_FINDING; snapshot | Brak ogólnego `/api/notifications` i założenia tabeli notifications |
| Diagnostyka/QC | diagnostics w szczegółach HTTP i reguły desktopu | Nie stanowią osobnych kompletnych domen HTTP/snapshot JARVIS; M4 nadal wymaga pracy |

`jarvis/workshop.py` czyta jawnie przygotowaną kopię schema18 przez SQLite mode=ro i sprawdza manifest/hash. `scripts/import_autologika.py` korzysta z backup API; nie modyfikuje źródła. Domyślne dane DEMO są syntetyczne i jawnie oznaczone. Kopia offline nie daje synchronizacji ani prawa do publikacji danych klientów.

## Supabase i zapisy

Supabase synchronizuje ogólne `public.sync_records` z entity_type/cloud_id/payload i workshop_id powiązanym z auth.uid(); nie potwierdzono osobnych publicznych REST tabel orders/vehicles do użycia przez JARVIS. Obok istnieją tabele i Edge Functions zdalnych akceptacji z odrębnym tokenem oraz regułami. RLS/SQL opisano statycznie; nie wykonano testów uprawnień na działającej instancji.

Bezpośredni INSERT do sync_records lub SQLite ominąłby część usług domenowych, idempotencji i kontroli konfliktów. JARVIS nie ma service_role ani dostępu do produkcyjnego Supabase. Zapisy, most domenowy i funkcje nieobecne w HTTP pozostają w M4.4/M4.5, za osobną zgodą na zmiany po stronie AutoLogiki. Dostęp do danych nie jest zgodą na sterowanie urządzeniami.

Weryfikacja tego kontraktu: `.venv/bin/python -m pytest -q tests/test_autologika.py tests/test_workshop.py` — PASS22, kontrolowane HTTP i syntetyczna kopia. Produkcyjne dane/HTTP/Supabase/RLS: NOT_RUN. Nie wykonano zmian upstream.

## M4.1 — kontrakt obronny (2026-10-29)
Ponowny odczyt lokalnego electron/main.cjs (read-only) potwierdził dwie trasy. Adapter wymaga dodatnich unikalnych id (max100) i zgodnego order.id; notes/diag są obiektami, parts/payments listami rekordów tego samego order_id. Limit odpowiedzi 2MiB, timeout całkowity12s; redirect i błędy nie ujawniają treści ani PIN. GET /api/v1/autologika/capabilities wymaga workshop:read, nie wykonuje połączenia i ujawnia ograniczenia. Dane testowe są syntetyczne. Rzeczywiste połączenie z produkcją NOT_RUN.
