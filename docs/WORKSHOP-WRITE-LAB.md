## M4.4 — laboratorium zapisów (2026-11-06)

Panel AutoLogika właściciela zawiera jawne laboratorium DEMO: notatka, zadanie, wycena w groszach i status syntetycznego DEMO-1. Podgląd before/after nie zmienia stanu. Osobne potwierdzenie wysyła digest dokładnej propozycji; CAS odrzuca nieaktualny stan, UUID eliminuje powtórny zapis, konta są odseparowane, odwołana sesja traci dostęp. Żadna ścieżka nie wywołuje adaptera AutoLogiki ani nie modyfikuje snapshotu.

Stan i dziennik metadanych są tylko w RAM pojedynczego procesu: restart lub30min bezczynności usuwa konto laboratoryjne (lazy cleanup), propozycje15min, max32konta/64propozycje na konto/512KiB podglądów na konto/32wpisy w kolekcji. To demonstracja polityki zapisów, nie trwały audyt ani produkcyjna integracja. Po błędzie sieci UI wymaga ponownego odczytu stanu, nie ponawia automatycznie decyzji.

M4.4 **BLOCKED dla realnych zapisów**: brak potwierdzonego bezpiecznego kontraktu wszystkich operacji (zwłaszcza zadań i wycen), izolacji klientów i autoryzacji produkcyjnych zmian. Nie deklarujemy ukończenia M4.4 ani RLS AutoLogiki. Backend źródeł został rozwinięty; instalator HUD3 nadal pochodzi z M3.

Wykonane kontrole:881pytest PASS/75skip282.69s;14nowych testów laboratorium,10testów panelu PASS; TypeScript/build/pip/JS PASS. Rzeczywisty Chrome/Core:4operacje z osobnym potwierdzeniem,390px,84żądań API,role/CSP/prywatność; zero outbound, źródło i snapshot bez zmian. Początkowy błąd etykiety select naprawiony przed finalnym testem.

API owner-only (również alias /api):
- GET /api/v1/autologika/write-lab: własne syntetyczne zlecenie i ostatnie100metadanych zdarzeń.
- POST /api/v1/autologika/write-lab/proposals: request_id UUID,revision,operation note/task/quote/status,text; tylko quote wymaga amount_grosz.
- POST /api/v1/autologika/write-lab/proposals/{id}/decide: approve bool i digest podglądu. Identyczna decyzja jest idempotentna; inna409, obca/wygasła404.

Status applied_demo nigdy nie oznacza zapisu w AutoLogice. Brak routingu do produkcji, replikacji, rollbacku i wykonania zaplanowanego zadania. Kontrola wersji dotyczy wyłącznie stanu laboratoryjnego. Współdzielony klucz właściciela oznacza wspólną tożsamość owner-key; osobne konta mają osobne laboratoria. Przechowywanie danych klienta w laboratorium jest niepotrzebne; używaj danych syntetycznych.
