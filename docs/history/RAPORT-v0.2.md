# JARVIS OS 0.2 — raport realizacji

22 października 2026. Przygotowano odrębny projekt, rozwijający przekazany starter 0.1. Audyt źródeł AutoLogiki wykonano na commicie `681f7f5ecf5a1e365022a9ac1cb22b6ff443262c`. Nie zmieniono produkcyjnego repozytorium, nie użyto jego bazy i nie uruchamiano żadnych urządzeń.

## Co jest gotowe

- Python/FastAPI Core, konfiguracja `.env`, trwała baza SQLite, walidacja żądań i autoryzacja kluczem właściciela.
- Responsywny Control Center: stan, rozmowa, integracje, pamięć, propozycje zmian, automatyzacje i audyt. Przycisk lokalnej kopii bazy.
- Rejestr pluginów: dodawanie manifestów, przełączanie, wywołanie testowe i blokowanie nieobsługiwanych transportów. MCP/OpenAPI to na tym etapie rejestracja, nie działające połączenie z zewnętrznymi serwerami.
- Jawne adaptery DEMO: AutoLogika we wszystkich 8 domenach, Home Assistant, MQTT/ESP32 jako symulowany kanał, n8n, Twilio i głos. Syntetyczne dane są oznaczone, a działania live zablokowane.
- Dodatkowy rzeczywisty czytnik AutoLogiki oparty na istniejących GET `/api/orders` i `/api/order/{id}`. Jest domyślnie wyłączony, wymaga adresu/PIN i ręcznego uruchomienia serwera mobilnego. W testach używa kontrolowanego transportu HTTP. Nie zweryfikowano połączenia z Twoją instalacją.
- Czat DEMO i klient lokalnego modelu Ollama; notatki długoterminowe dodawane/usuwane w panelu lub poleceniem „zapamiętaj …”. Ostatnie 10 notatek przekazywane do Ollama. Brak pełnej historii i wyszukiwania wektorowego.
- Zmiany imienia rozmową, tworzenie propozycji przypomnienia poleceniem „przypominaj co 60 minut: Sprawdź części”; zatwierdzanie/odrzucanie ustawień i automatyzacji oraz rollback. Propozycje kodu są opisami do przeglądu; brak automatycznej edycji lub wdrożenia kodu.
- Lokalny scheduler powiadomień, opcjonalny worker Docker, profil n8n, Dockerfile, skrypt startowy Windows i macierz CI Linux/Windows do przyszłego uruchomienia na GitHubie.
- Backup SQLite przez API wraz z SHA-256, instrukcja odtwarzania, healthcheck i audyt zdarzeń. Audyt nie jest odporny na modyfikację pliku przez administratora.

## Co jest zaplanowane, ale jeszcze nie działa

Pełne odczyty i zapisy domen AutoLogiki; transporty MCP/OpenAPI; instalacja kodu i konfiguracja sekretów pluginów; HA/MQTT/ESPHome na sprzęcie; wysyłanie WhatsApp i podpisane webhooki; połączenia WhatsApp; semantyczna pamięć i historia czatu; lokalne STT/TTS; workflow n8n i powiadomienia push; autonomiczne zmiany kodu z testami i rollbackiem; wielu użytkowników i scopes; automatyczny updater, szyfrowane kopie offsite i monitoring alertów. Wszystkie są ujęte w architekturze i etapach. Rejestracja manifestu ani symulacja nie oznacza wdrożenia tych funkcji.

Głos w panelu wykorzystuje opcjonalne mechanizmy przeglądarki/systemu, wymaga ręcznego kliknięcia i uprawnień. Nie zapewnia stałego nasłuchu w tle ani gwarancji pracy offline. Wygląd panelu nie został zweryfikowany zrzutem przeglądarki: w środowisku nie było Chromium, a próba pobrania została zablokowana/zwracała niepoprawne archiwum. Zasoby HTTP oraz składnię JS sprawdzono osobno.

## Wyniki weryfikacji

- **36 testów pytest — zaliczone**: autoryzacja fail-closed, osiem domen syntetycznych, cykl pluginów, brak transportu MCP/OpenAPI, blokady fizycznych skutków, pamięć i restart, parser rozmowy, propozycje/akceptacja/rollback oraz konflikty, scheduler bez duplikatów, integralność backupu, walidacja i prywatność audytu; adapter AutoLogiki: GET, PIN, blokada przekierowań i domyślne wyłączenie; Ollama: format żądania, kontekst i jawny błąd przy awarii.
- Sprawdzono składnię `app.js` przez Node i serwowanie HTML/CSS/JS przez TestClient. Uruchomiono proces Uvicorn lokalnie i sprawdzono odpowiedź health/status.
- Plik Compose sprawdzono jako YAML; **nie wykonano** builda obrazu, `docker compose config`, uruchomienia Dockera ani PowerShell na Windows. Definicja CI została dodana, lecz nie uruchomiona na GitHubie.
- Modele Ollama testowano przez kontrolowaną odpowiedź, bez rzeczywistego generowania na GPU/CPU. Twilio, HA, MQTT, n8n, iOS/Android i fizyczne urządzenia nie były podłączane.
- Zależności bezpośrednie są przypięte wersjami; brak pełnego locka i skanu CVE. Ostrzeżenie deprecacyjne w bibliotece testowej nie powoduje błędu. Nie jest to certyfikacja gotowości produkcyjnej.

## Konta, klucze i sprzęt

| Integracja | Co przygotować | Czy blokuje lokalny start |
|---|---|---|
| Core | Losowy JARVIS_API_KEY; skrypt generuje go lokalnie | Tak, klucz wymagany |
| AutoLogika odczyt | Uruchomiony serwer mobilny, jego PIN, adres i port; zgodność wersji | Nie |
| Ollama | Instalacja i pobrany model, pamięć RAM/VRAM; URL i nazwa modelu | Nie; DEMO działa bez modelu |
| Home Assistant | Instancja, token użytkownika o ograniczonym dostępie, entity_id i allowlista | Nie |
| MQTT / ESP32 | Broker, oddzielny użytkownik i ACL, firmware ESPHome, opis pinów i urządzeń | Nie |
| n8n | Lokalne konto właściciela, osobny encryption key, zatwierdzony workflow i aktualny obraz | Nie |
| WhatsApp Messaging | Twilio, Meta Business/WABA, sender, SID i sekrety, HTTPS webhook, zgody | Nie |
| WhatsApp Calling | Aktywacja Voice dla sendera, TwiML App, Meta Business Verification, odpowiedni limit i kraj numeru; zgody na połączenia | Nie |
| Zdalny telefon | Prywatny VPN/HTTPS, konfiguracja firewalla i urządzeń | Nie |
| Pełne zapisy AutoLogika | Najpierw zaakceptowany projekt mostu i osobna zgoda na zmianę repo | Nie |

Twilio: dokumentacja sprawdzona 22.10.2026 wymaga dla aktywacji Calling limitu minimum 2000 rozmów inicjowanych przez firmę na 24 h oraz weryfikacji Meta. Połączenia wychodzące wymagają osobnej zgody użytkownika. Nie ma gwarancji aktywacji nowego konta i nie zakładamy działania Calling w sandboxie. Szczegóły i źródło: `OPERACJE.md`.

## Co zrobić w środę — 28 października 2026

1. Rozpakuj projekt do nowego katalogu, obok AutoLogiki. Zainstaluj Python 3.12; Docker Desktop/WSL2 jest opcjonalny. Nie zastępuj plików AutoLogiki paczką JARVIS-a.
2. Uruchom `scripts/start.ps1`. Skrypt generuje sekret, tworzy venv, instaluje zależności i odpala testy. Otwórz panel pod http://127.0.0.1:8000 i wklej klucz z `.env`.
3. Sprawdź DEMO: rozmowę, zapis/usunięcie notatki, wyłączenie pluginu, propozycję zmiany imienia, odrzucenie/akceptację/rollback. Dodaj przypomnienie i uruchom scheduler. Utwórz kopię bazy i zanotuj jej SHA-256.
4. Zanotuj wersję zainstalowanej AutoLogiki i porównaj z audytem. Wykonaj jej własny backup. Ręcznie uruchom serwer mobilny i odczytaj PIN. Ustaw AUTOLOGIKA_READONLY_ENABLED, URL i PIN, zrestartuj Core. Sprawdź listę oraz szczegóły jednego testowego zlecenia. Porównaj total/final_price, płatności, pojazd i klienta z interfejsem AutoLogiki. Ograniczenie listy 100 i brak WYDANE jest zamierzone w istniejącym API.
5. Zainstaluj Ollama i model odpowiedni dla faktycznego RAM/VRAM. Wybierz model w panelu, porozmawiaj po polsku, sprawdź pamięć i zachowanie po zatrzymaniu Ollama. Adres hosta w Dockerze różni się od localhost.
6. Sprawdź PowerShell, Docker build/compose i restart z zachowaniem danych. Dla telefonu dopiero skonfiguruj prywatny dostęp HTTPS/VPN i sprawdź Safari/Chrome, mikrofon oraz syntezę. Domyślny localhost nie daje dostępu z telefonu.
7. Zbierz modele centrali bramy, świateł, listę urządzeń i stan Home Assistant. Uruchomienie bramy pozostaje osobnym zadaniem z osobnym potwierdzeniem. Pierwszy test domowy powinien dotyczyć odczytu czujnika.
8. Przygotuj Twilio/Meta, ale najpierw potwierdź wymagania Calling dla konta/numeru i koszty. Nie kupuj integracji tylko dlatego, że działa jej adapter DEMO.

Po zaliczeniu startu na Windows następny etap to pełny most AutoLogiki i lokalne AI. Nie trzeba wcześniej kupować hostingu ani płatnego modelu.
