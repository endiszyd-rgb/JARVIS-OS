# M0.5 — checklista Windows11/WSL2 i odbioru

Szczegółowy build, bezpieczne .env i uruchomienie kontenera: [DOCKER-WINDOWS.md](DOCKER-WINDOWS.md).

To instrukcja przygotowania i przyszłego odbioru, nie protokół wykonanego testu Windows. Wszystkie kroki sprzętowe są obecnie NOT_RUN. Kod i testy można budować w chmurze bez dostępu do lokalnego PC.

## Przygotowanie

1. Zachowaj produkcyjną AutoLogikę i jej dane bez zmian. JARVIS rozpakuj do osobnego katalogu z aktualnej paczki; przed pierwszą zmianą sprawdź manifest. Nie kopiuj cudzej `.env` ani baz do repozytorium.
2. Dla trybu Python zainstaluj Python3.12 i uruchom `scripts/start.ps1` w PowerShell. Wymóg3.12 dotyczy Wyoming/audioop. Sprawdź, że klucz został wygenerowany lokalnie, a integracje pozostają wyłączone. Nigdy nie przesyłaj klucza w screenach/logach/Git.
3. Dla Docker zainstaluj Docker Desktop i WSL2, zrestartuj jeśli wymagane, sprawdź `wsl --status`, `docker version`, `docker compose version`. Nie zakładaj, że działający CLI oznacza gotowy daemon.
4. Utwórz `.env` na podstawie `.env.example`, ustaw losowy klucz właściciela. Początkowo wszystkie zewnętrzne integracje są false. `docker compose config --quiet` sprawdza konfigurację; unikaj drukowania całej rozwiniętej konfiguracji z sekretami.
5. Uruchom lokalny Core według README. Compose nasłuchuje127.0.0.1:8000 i nie udostępnia panelu automatycznie telefonowi. Nie otwieraj portów routera. Dla telefonu przygotuj prywatny HTTPS/VPN i świadomą regułę firewalla.

## Odbiór po przygotowaniu

- [ ] Health procesu i gotowość API (po M1.1), autoryzacja, brak wejścia z błędnym kluczem.
- [ ] Utwórz syntetyczną notatkę i rozmowę; restart zachowuje dane. Backup ma poprawny hash; restore drill wyłącznie na osobnej testowej bazie.
- [ ] Ustawienia modeli/instrukcji, wybór modelu i jawne błędy niedostępnego providera; bez automatycznego pobierania modeli lub płatnych wywołań.
- [ ] Głos po przycisku: zgoda mikrofonu, STT/review/TTS, przerwanie/koniec, nawigacja/wylogowanie zwalnia zasoby. Osobno pomiar hałasu i jakości modeli; test syntetyczny nie wystarcza.
- [ ] iPhone Safari i Android Chrome: układ, logowanie/wylogowanie, obrót ekranu i zgody; HTTPS dla mikrofonu. PWA instalacja dopiero po wdrożeniu M8.1, bez obietnicy stałego nasłuchu iOS w tle.
- [ ] Recepcja/transport laboratoryjny: osobne kanały, briefing prywatny, pierwsza prośba, godziny/DND, odmowa/timeout i brak drugiej próby. Nie aktywuj Play/operatora.
- [ ] MQTT/HA po ich wdrożeniu: najpierw odczyt syntetyczny i świeżość danych. Brama pozostaje bez fizycznego wykonania; wymaga osobnej inspekcji i zgody.
- [ ] Zapisz datę UTC, wersję/commit, OS/przeglądarkę, komendy, wyniki PASS/FAIL/NOT_RUN i ograniczenia w planie. Nie zamieniaj odhaczonych pozycji z dokumentu w wynik testów.

Do kontenerowego `host.docker.internal` trzeba świadomie dobrać adresy/allowlistę. Sekrety pluginów wymagają jawnej konfiguracji; nie wpisuj całej podsieci tylko po to, aby test przeszedł. Nie uruchamiaj migracji Supabase ani operacji zapisu AutoLogiki w ramach tej checklisty.
