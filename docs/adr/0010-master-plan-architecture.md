# ADR010 — przyjęcie planu M0–M8 bez zastępowania istniejącego kodu

Data: 2026-10-22. Status: przyjęta decyzja implementacyjna na podstawie nadrzędnego polecenia właściciela. Zadanie M0.4. Rozszerza historyczne ADR001/005; nie twierdzi, że docelowe technologie są już wdrożone.

## Kontekst i decyzja

JARVIS jest osobnym repozytorium `endiszyd-rgb/JARVIS-OS`, z własnym `.git`, kodem Python w jarvis/, testami w tests/, skryptami w scripts/, dokumentacją i przykładowymi integracjami. Repo zawiera działające źródła po imporcie ZIP-a i lokalne commity; nie tworzymy drugiego startera ani nie przenosimy zmian do AutoLogika-OS. Zostaje modułowy monolit z wydzielonymi adapterami i testami, rozwijany w tym monorepo.

Plan M0–M8 określa cel: FastAPI, React/TypeScript i oddzielny Postgres/Supabase JARVIS. Obecne SQLite/schema11 oraz statyczny panel JS pozostają działającą ścieżką przejściową. M1 wprowadza wersjonowane API, gotowość, konfigurację i dostęp; M1.4 ma dostarczyć osobną warstwę Postgres/RLS z migracją i testami. M2 dodaje frontend React/TS korzystający z API. Nie oznaczamy starego JS jako React ani SQLite jako Postgres. Migracje muszą zachować pamięć, rozmowy, polityki i odbiór laboratoryjny.

Nie kopiujemy backendu Electron ani schematu Supabase AutoLogiki do JARVIS. Potwierdzone kontrakty pozostają adapterami tylko do odczytu; brakujące operacje mają mock i jawny status. Instalacja/deploy rzeczywistej instancji Supabase wymaga osobnej zgody. Pliki migracji i izolowane testy lokalnego Postgresa można przygotować bez modyfikowania usługi produkcyjnej.

## Zaufanie i dostęp

- Główna autoryzacja jest po stronie backendu; tekst klienta/modelu oraz manifest pluginu nie przyznają praw. Role, sesje, RLS i limity M1.3/M1.4 muszą być sprawdzone przed udostępnieniem współpracownikom.
- Sekrety w środowisku/menedżerze sekretów; tokeny ograniczone zakresem/czasem i bez surowych wartości w logach. Klucz właściciela nie trafia do klienta, webhooka ani workera.
- Prywatna pamięć, dane warsztatu i klient recepcji pozostają rozdzielone. Przekazanie rozmowy wymaga bieżącej dostępności i osobnej zgody; caller ID nie uwierzytelnia właściciela.
- Wrażliwe akcje: podgląd konkretnej operacji, niezależne potwierdzenie, TTL i jednokrotność, audyt i ograniczenia urządzenia. Dla bramy lokalny STOP/czujniki/zabezpieczenia centrali są niezależne od AI. Symulator nie dowodzi działania sprzętu.
- Żadnych zmian produkcji AutoLogika/Supabase, płatnych połączeń, publicznego wystawienia, deploya ani fizycznego sterowania z powodu testu kodu. M6.5 kończy się przeglądalnym branch/PR i testami, bez autonomicznego wdrożenia.

## Koszty i operacje

Preferujemy lokalne usługi/open source oraz istniejące biblioteki. Nie pobieramy automatycznie modeli ani nie uruchamiamy płatnych providerów. Każdy provider cloud powinien mieć jawne stawki/limity, wyłącznik i pomiar zużycia; bez potwierdzonej konfiguracji pozostaje wyłączony. Jednostki kosztu telefonii laboratoryjnej nie są kosztami operatora. Hosting, Twilio/Meta, energia i sprzęt nie są deklarowane jako darmowe. Licencje modeli i n8n trzeba sprawdzać oddzielnie od bibliotek.

Każda migracja ma kopię, test zachowania danych i plan odtworzenia. Każde zadanie ma status i dowody w obu identycznych plikach planu, README i commicie. Wykonane testy odróżniamy od NOT_RUN. Docelowe 45 zadań i wszystkie11obszarów pozostają w backlogu; wdrożenie etapowe nie usuwa zakresu.

## Weryfikacja decyzji

Sprawdzono lokalny root/remote repo JARVIS, istniejący modułowy układ oraz zgodność45identyfikatorów planu i obu jego kopii. `git diff --check`: PASS. Nowe testy aplikacji: NOT_RUN — wyłącznie decyzja architektoniczna, bez zmian runtime. Pełna bazowa regresja PASS276 została wykonana w M0.1. React/TS/Postgres/RLS oraz produkcyjny deploy pozostają zadaniami implementacyjnymi, nie wynikiem tej ADR.
