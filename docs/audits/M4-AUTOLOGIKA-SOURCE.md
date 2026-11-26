# M4 — audyt źródeł 2026-10-29

Odczyt bez uruchamiania AutoLogiki i bez dostępu do bazy użytkownika. Lokalny HEAD: 515a655cf42491c87176a9bfeebc948b86e32971. Hash odczytanych plików określa dokładne bajty niezależnie od zmian roboczych:

- electron/main.cjs SHA256 d3dd8ebd3f9a8a1c52eef1a7d5e552bbfd53ffd4e58fd6115c059f6f762c538e, linie358–390: GET /api/orders i GET /api/order/{id}; szczegóły zawierają order, notes, diag, parts, payments. Lista max100 bez WYDANE. Współdzielony PIN, brak izolacji per klient.
- electron/db.cjs SHA256 02b3b710aea5bcf3eecc21b1d506c3554ec5d2f6688b78f3e6eb56e80e253bb2, linie662–669: diagnostics; linie925–931: order_qc.

Kontrakt HTTP zgodny z poprzednim audytem681f7f5. Nie rozszerzamy automatycznie zgodności całej bazy tylko na podstawie numeru wersji; odczyty snapshot wymagają obecności konkretnych tabel/kolumn. Produkcyjne połączenie, Supabase/RLS i zapisy NOT_RUN.

2026-11-06: ponowny odczyt db.cjs926–930 potwierdził order_qc i te same pola; SHA256 nadal02b3b710aea5bcf3eecc21b1d506c3554ec5d2f6688b78f3e6eb56e80e253bb2. Bez uruchamiania AutoLogiki.

2026-11-26 (0.13.0): ponowny odczyt Autologika-OS bcdc364770ace83675ee7c2c7e6967d15dcf1197 (2026-11-21). `electron/main.cjs` createMobileServer: GET `/api/orders` (orderSelect, `status!='WYDANE'`, LIMIT 100) i GET `/api/order/{id}` ({order, notes, diag, parts = job_part_orders + supplier, payments}) bez zmian kontraktu; serwer dodatkowo ma zapisy PATCH/PUT/POST (status, notatki, diagnostyka, przyjęcie) — JARVIS ich nie używa. `electron/db.cjs` SCHEMA_VERSION 18. `electron/job-part-workflow.cjs`: statusy DO_ZAMOWIENIA, ZAMOWIONE, W_DRODZE (blokujące → `wait_state=CZESCI`), ODEBRANE, ZAMONTOWANE, DO_ZWROTU, ZWROT_ZAKONCZONY, ANULOWANE. Serwer słucha na 0.0.0.0 (HTTP, PIN). Kontrakt sprawdzony harnessem `scripts/autologika_contract_harness.cjs` (prawdziwe migracje i SQL, dane syntetyczne); prawdziwa instalacja NOT_RUN. Repozytorium AutoLogiki nie było modyfikowane.
