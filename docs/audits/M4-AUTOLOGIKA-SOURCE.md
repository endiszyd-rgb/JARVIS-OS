# M4 — audyt źródeł 2026-10-29

Odczyt bez uruchamiania AutoLogiki i bez dostępu do bazy użytkownika. Lokalny HEAD: 515a655cf42491c87176a9bfeebc948b86e32971. Hash odczytanych plików określa dokładne bajty niezależnie od zmian roboczych:

- electron/main.cjs SHA256 d3dd8ebd3f9a8a1c52eef1a7d5e552bbfd53ffd4e58fd6115c059f6f762c538e, linie358–390: GET /api/orders i GET /api/order/{id}; szczegóły zawierają order, notes, diag, parts, payments. Lista max100 bez WYDANE. Współdzielony PIN, brak izolacji per klient.
- electron/db.cjs SHA256 02b3b710aea5bcf3eecc21b1d506c3554ec5d2f6688b78f3e6eb56e80e253bb2, linie662–669: diagnostics; linie925–931: order_qc.

Kontrakt HTTP zgodny z poprzednim audytem681f7f5. Nie rozszerzamy automatycznie zgodności całej bazy tylko na podstawie numeru wersji; odczyty snapshot wymagają obecności konkretnych tabel/kolumn. Produkcyjne połączenie, Supabase/RLS i zapisy NOT_RUN.
