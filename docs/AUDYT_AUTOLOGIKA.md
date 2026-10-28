# Audyt źródeł AutoLogika OS

Data: 22.10.2026. Repozytorium: https://github.com/endiszyd-rgb/Autologika-OS
Commit: **681f7f5ecf5a1e365022a9ac1cb22b6ff443262c** (18.10.2026). Zakres: statyczny audyt punktów integracyjnych, nie pełny audyt bezpieczeństwa ani test działającej instalacji. Repozytorium sklonowano bez zmian. Nie wykonano instalacji zależności ani migracji AutoLogiki.

## Fakty potwierdzone kodem

`package.json`: aplikacja 1.1.1, Electron 34, React 18, Vite 6, better-sqlite3 11. Backend domenowy to moduły CommonJS oraz handlery IPC w `electron/main.cjs`. Renderer korzysta z `contextBridge` w `electron/preload.cjs`, przy `contextIsolation:true` i `nodeIntegration:false`. IPC nie jest automatycznie HTTP API dla Pythona.

`electron/db.cjs`: SCHEMA_VERSION=18; plik `autologika.db` w `app.getPath('userData')`, backupy w podfolderze `backups`. Dokładny katalog Windows trzeba odczytać z instalacji, nie zgadywać na podstawie nazwy produktu. Skrypt analityczny wykrył 57 unikalnych deklaracji CREATE TABLE IF NOT EXISTS i 262 handlery IPC. Wykaz deklaracji nie jest zrzutem aktualnej bazy; migracje dodają kolumny, indeksy i mechanizmy synchronizacji.

| Obszar | Potwierdzony kod/dane | Dostęp obecnym HTTP API |
|---|---|---|
| Terminarz | `appointments`, `work_resources`, `resource_unavailability`, `appointment_resources`; IPC `appointments:list/create/update/remove` | Brak pełnego terminarza |
| Zlecenia | `orders`, `order_items`, `order_notes`, `order_events`; IPC `orders:list/get/create/createComplete` i operacje cyklu życia | GET listy i szczegółów; istnieją też operacje zapisu |
| Pojazdy | `vehicles`, IPC `vehicles:list/profile/history/findByVin` | Dane pojazdu w zleceniu; brak osobnej listy pojazdów |
| Klienci | `customers`, IPC `customers:list/profile/create/update` | Dane klienta w zleceniu; brak osobnej listy klientów |
| Części | `job_part_orders`, `inventory_parts`, `order_repair_operations`, `repair_parts`, zdarzenia części; IPC `jobParts:*`, `inventory:*`, `repairs:*` | Części konkretnego zlecenia w szczegółach |
| Finanse | `payments`, `sales_refs`, `orders.final_price`; IPC `finance:analytics`, `payments:*`, `debtors:list` | Płatności konkretnego zlecenia; brak pełnego API analityki |
| Raporty | `dashboard:get`, `finance:analytics`, `worklog:productivity`, `bays:productivity`; obliczenia w kodzie | Brak ogólnego `/api/reports`; nie zakładamy osobnej tabeli reports |
| Powiadomienia | IPC `notifications:list` wylicza WAIT, REPLY, PART_LATE, APPROVAL, VEHICLE_FINDING | Brak ogólnego `/api/notifications`; nie zakładamy tabeli notifications |

## Istniejący serwer mobilny

`electron/main.cjs`, funkcje `createMobileServer`, `mobileAuthorized`, `loadRemoteConfig`. Domyślny port 8787, konfiguracja w `remote-access.json`, domyślnie `autoStart:false`. Serwer binduje `0.0.0.0`. Nie uruchamialiśmy go tutaj.

| Metoda | Trasa rzeczywistej AutoLogiki | Znaczenie |
|---|---|---|
| GET | `/health` | Publiczna kondycja serwera mobilnego |
| POST | `/api/login` | Sprawdzenie PIN; nie wydaje osobnego tokena sesji |
| GET | `/api/orders` | Maksymalnie 100 zleceń bez WYDANE, sortowanie opened_at DESC |
| GET | `/api/sync` | Czas serwera; to nie strumień synchronizacji danych |
| GET | `/api/order/{liczbowy_id}` | `{order,notes,diag,parts,payments}` |
| PATCH | `/api/order/{id}` | Zmiana statusu/oczekiwania; poza adapterem JARVIS-a |
| PUT | `/api/order/{id}/notes` | Zapis notatek; poza adapterem |
| PUT | `/api/order/{id}/diagnostics` | Zapis diagnozy; poza adapterem |
| POST | `/api/intake` | Przyjęcie; poza adapterem |

Autoryzacja chronionych tras: nagłówek `X-Autologika-Pin`. Brak TLS w tym serwerze, brak widocznego limitowania prób w badanym handlerze, PIN jest sekretem współdzielonym. W JARVIS-ie nie wystawiamy tego serwera publicznie i nie korzystamy z jego operacji zapisu. Stosować lokalny host/prywatną sieć z szyfrowanym transportem lub warstwę HTTPS/VPN. Przekierowania HTTP w adapterze są wyłączone, aby nie przekazywać PIN do innego hosta.

## Supabase i reguły spójności

`electron/cloud-sync.cjs` synchronizuje jawny SYNC_TABLES (m.in. customers, vehicles, orders, appointments, payments, job_part_orders) do **public.sync_records**. `cloud_schema_supabase.sql` definiuje `workshop_id`, `entity_type`, `cloud_id`, JSONB `payload`, `version`, `deleted_at`, `device_id` oraz unikalność `(workshop_id,entity_type,cloud_id)`. RLS wiąże `workshop_id` z `auth.uid()`. To nie osobne publiczne tabele Supabase `/orders` i `/vehicles`.

Synchronizacja obsługuje powiązania przez cloud_id, kolejkę, odświeżanie tokenów i konto właściciela. Bezpośrednie zapisy do sync_records mogą ominąć logikę domenową i prowadzić do konfliktów. JARVIS nie używa service-role key ani nie zapisuje do SQLite/Supabase AutoLogiki.

`electron/order-financials.cjs`: baza ceny = labor_hours × labor_rate + parts_sale + other_sale + diagnosis_fee − discount; cena finalna = COALESCE(final_price, baza). Wkład = cena finalna − (parts_cost + other_cost). Ten wkład nie jest pełnym zyskiem księgowym. Nie wolno ponownie sumować pozycji i nagłówka zlecenia ani mylić zapłat z przychodem.

`order-lifecycle.cjs`, `inventory-usage.cjs`, `repair-operations.cjs`, `quote-approval.cjs` i `closeout-automation.cjs` zawierają reguły edytowalności, ilości i akceptacji. Docelowy most zapisujący ma wywoływać te usługi, nie omijać ich SQL-em.

## Decyzja integracyjna

Teraz: istniejące API wyłącznie GET + pełne DEMO. Dalej: osobna propozycja mostu domenowego z uwierzytelnianiem i uprawnieniami, zatwierdzana przed jakąkolwiek zmianą AutoLogiki. Most powinien udostępnić brakujące domeny, stronicowanie, pełną synchronizację z tombstones, idempotency keys i strumień zdarzeń. Integracja ma identyfikować rekordy po cloud_id tam, gdzie to możliwe, a lokalne numery zawsze w kontekście konkretnej instalacji.

Podstawą ustaleń są pliki wymienione w `autologika-evidence.json`; zapisano ich SHA-256. Zdalny HEAD może zmienić się po audycie. Przed wdrożeniem porównać commit z wersją zainstalowaną na Windows i ponowić odpowiednie sprawdzenia.


## Rozszerzenie JARVIS 0.4 — lokalna kopia

Dodano po stronie JARVIS-a czytnik kopii SQLite schematu 18 dla ośmiu domen. Nie rozszerza on serwera mobilnego ani repozytorium AutoLogiki. Import wybiera jawnie źródło, używa mode=ro i SQLite backup API, a czytnik weryfikuje manifest/SHA-256. Odczyty raportów, finansów i pięciu rodzin powiadomień korzystają z potwierdzonych nazw tabel i reguły final_price, lecz stanowią udokumentowany podzbiór logiki desktopu. Mapowanie, filtry i ograniczenia opisano w ROZMOWY-I-WARSZTAT-v0.4.md; rzeczywistej bazy użytkownika nie użyto do testów.
