# M0.5 — zależności i strategia testów

Kolejność pracy wynika z planu M0–M8 i [grafu45zadań](../JARVIS_MASTER_DEPENDENCIES.json). Graf doprecyzowuje zależności implementacyjne, nie nadaje statusów ukończenia. Zwykle wybieramy pierwsze możliwe zadanie w kolejności ID; blokady zapisujemy, a prace niezależne kontynuujemy. DONE oznacza brak pełnej weryfikacji i nie zastępuje VERIFIED dla wymaganej zależności. Przy częściowo dostępnej podstawie trzeba jawnie podzielić kryteria/dowody zamiast samodzielnie pomijać zależność.

Przykłady: UI React M2.1 potrzebuje stabilnego API M1.1, nie konta Twilio. Pamięć pgvector M3.3 wymaga warstwy Postgres/RLS M1.4. Światła i workflow mogą wymagać późniejszego n8n; nie upoważnia to do uruchamiania urządzeń. Brak inspekcji bramy nie blokuje jej symulatora. External_gate wskazuje wymogi rzeczywistej aktywacji; lokalny adapter/mock/test pozostaje możliwy, ale nie dowodzi działania integracji na żywo.

## Poziomy dowodów

| Poziom | Narzędzie / zakres | Czego nie potwierdza |
|---|---|---|
| Stan planu | `python3 scripts/check_master_plan.py` —45ID, statusy, zgodneTXT/MD, graf bez cykli, zależności i podsumowanie | Nie ocenia semantycznie funkcji ani jakości AI |
| Backend | Python3.12, `.venv/bin/python -m pytest -q`, `pip check`; dane i bazy tymczasowe | Test kontrolowanego HTTP nie jest realną instalacją warsztatu |
| Kontrakty | `tests/test_autologika.py`, `tests/test_workshop.py`, lokalny MCP/OpenAPI | Bez zmian AutoLogiki i bez dowodu aktualności bazy właściciela |
| UI JS | `node --check` i `scripts/check_*.cjs` | Kontrolowany DOM nie jest Safari/Chrome |
| Przeglądarka | opcjonalne Playwright/Chromium; syntetyczne audio i usługi | Nie potwierdza modeli, mikrofonów, hałasu ani fizycznych telefonów |
| React/TS po M2 | typecheck, komponenty/a11y i produkcyjny build | Sam build nie potwierdza API ani mobilnego mikrofonu |
| Kontenery | Compose config, build, start na tymczasowym wolumenie, health/readiness i kontrolowany smoke | Linux Docker w chmurze nie dowodzi Windows/WSL2 |
| Postgres/RLS | osobny testowy Postgres i role/tokeny dwóch użytkowników, minimalne granty i próby przekroczenia granicy | Nie wolno uruchamiać migracji w produkcyjnym Supabase |
| Sprzęt/usługi | osobne jawne aktywacje, checklisty i dane właściciela | Symulator nie zastępuje inspekcji centrali/bramy ani kwalifikacji Twilio |

Pełna regresja jest wymagana po zmianach backendu; JS ma składnię i właściwe testy zachowania. Zmiana schematu: kopia, migracja istniejących danych, test rollback/restore. Nie pisz testów, które wyłącznie powtarzają implementację. Dla zmian dokumentacji wystarczy kontrola źródeł/linków/JSON i diff; nie przedstawiaj poprzednich testów jako uruchomionych ponownie.

CI opisuje Ubuntu/Windows, Python3.12 i Node22. Zewnętrzny job pozostaje NOT_RUN, dopóki nie odczytano rzeczywistego wyniku. Testy kont/API używają wyłączonych integracji i syntetycznych danych. Logi i artefakty nie zawierają kluczy, baz produkcyjnych ani treści klientów.

## Dostępne środowisko tej sesji

Potwierdzono Python3.12 w .venv, Node24.19/npm11.9 oraz Docker28.4/Compose2.40 z działającym daemonem. Nie zbudowano jeszcze kontenerów wM0.5; ta kontrola ma nastąpić wM1.2. Windows/WSL2, iPhone/Android i fizyczne urządzenia są NOT_RUN. Pakiety przeglądarkowe są opcjonalne i nie są wymogiem bazowego pytest.
