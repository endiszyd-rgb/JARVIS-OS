# JARVIS OS 0.4 — raport realizacji

22.10.2026. Kontynuacja projektu 0.3. Produkcyjne repozytorium AutoLogiki pozostaje niezmienione. Nie podłączono rzeczywistej bazy warsztatu, urządzeń domowych ani kont Twilio. Nie wysłano wiadomości i nie wykonano płatnych operacji.

## Nowe działające elementy

- **Trwałe rozmowy:** osobne sesje, tytuły, zapis po restarcie, historia w panelu, zmiana modelu, eksport JSON, usuwanie i ręczna retencja z podglądem.
- **Kontekst rozmowy:** ograniczona historia udanych wiadomości bieżącej sesji; brak mieszania rozmów; nieudane zapytania oznaczone i pomijane w kontekście. Blokada równoległych tur i odzyskiwanie stanu po przerwanym procesie.
- **Katalog modeli:** dostawca domyślny z ustawień, nazwa modelu per sesja i jawna allowlista. Katalog nie instaluje modeli. Nazwy :cloud wymagają dodatkowego włączenia; nie jest to weryfikacja architektury dowolnego modelu/proxy.
- **Most odczytu AutoLogiki na kopii:** osiem domen — terminarz, zlecenia, pojazdy, części, klienci, finanse, raporty i powiadomienia. Wykorzystuje potwierdzone tabele schematu 18, bez migracji i zapisów źródła. Nie dodano endpointów do produkcyjnej AutoLogiki.
- **Spójny import:** źródło wskazane ręcznie, otwarte read-only; SQLite backup API uwzględnia zatwierdzone dane WAL. Manifest, SHA-256 i kontrola integralności. Czytnik otwiera kopię immutable/mode=ro i blokuje inny schemat lub zmienioną kopię.
- **Warsztat w rozmowie:** jawny checkbox dołącza agregaty finansów/statusów i datę kopii, bez list klientów i VIN. Nie daje modelowi samodzielnego dostępu do narzędzi ani zapisów.
- **Panel:** rozwinięta Rozmowa oraz nowy widok AutoLogika · kopia. Łącznie 11 widoków. Syntetyczna baza warsztatu do samodzielnego testu bez PC warsztatu i kont.
- **Operacje:** migracja bazy Core do user_version=4 z kopią przed aktualizacją; istniejące notatki, pluginy i tokeny zachowane.

Moduły 0.3 pozostają: MCP Streamable HTTP i podzbiór OpenAPI GET, konfiguracja pluginów i reguły sieci, ograniczone tokeny, czytnik HA, podpisany inbox Twilio, szkice bez wysyłki, worker i szablon n8n. Istniejący klient serwera mobilnego AutoLogiki nadal wykonuje wyłącznie potwierdzone GET zleceń.

## Testy i ich granice

**83 testy pytest zaliczone** w Pythonie 3.12. Nowe testy obejmują trwałość i izolację sesji, rzeczywisty wybór nazwy modelu w żądaniu, blokadę modeli spoza listy, domyślne ustawienia, błąd modelu, równoległe żądania/usuwanie, odzyskiwanie starej blokady, retencję, ograniczenie kontekstu i brak dostępu historii przez token usługi.

Dla warsztatu sprawdzono każdą z ośmiu domen, brak zmian źródła/kopii przy odczycie, cenę końcową równą zero, brak podwójnego sumowania, różne miesiące zlecenia i płatności, tombstones, pięć rodzin powiadomień, limit listy, zły checksum, nieobsługiwany schemat, blokadę SQL zapisu i spójne kopiowanie danych z WAL oraz zamknięcie uchwytów SQLite przed atomową podmianą pliku (ważne dla Windows). Sprawdzono także jawne dołączanie agregatów do modelu i brak list klientów w tym kontekście.

Test DOM z działającym Core potwierdził tworzenie i wysłanie wiadomości, powrót do historii po zmianie zakładki, zmianę tytułu/usunięcie sesji oraz widok finansów kopii. Sprawdzono składnię JS, spójność zależności i diff. **Test DOM nie sprawdza wyglądu w rzeczywistej przeglądarce.** Jedno ostrzeżenie deprecacyjne zależności testowej pozostaje nieszkodliwe dla wyniku.

Nie sprawdzono jeszcze: Windows/PowerShell, Docker build i mountów, telefonu/mikrofonu, zainstalowanego n8n, generacji na rzeczywistym modelu, prawdziwej bazy AutoLogiki, konta Twilio, HA i fizycznych urządzeń. Modele były testowane kontrolowanym transportem HTTP. Integracyjny test MCP/OpenAPI nadal uruchamia osobny proces lokalnego serwera. Nie deklarujemy produkcyjnej gotowości ani pełnej zgodności wszystkich ekranów desktopu z podzbiorem snapshotu.

## Co wymaga kont, kluczy lub danych

| Funkcja | Potrzebne do rzeczywistego użycia |
|---|---|
| Core, sesje, DEMO, laboratorium | Tylko lokalny klucz JARVIS-a; skrypt go generuje |
| Rozmowa AI | Ollama i zainstalowany model wpisany na listę; zgodność RAM/VRAM do sprawdzenia na komputerze |
| Kopia AutoLogiki | Wskazany plik rzeczywistej bazy/backup schematu 18; bez API key |
| Istniejące API mobilne | Działająca AutoLogika, uruchomiony serwer, PIN i adres |
| MCP/OpenAPI | Serwer, sprawdzony kontrakt odczytu i ewentualny Bearer token |
| HA | Instancja, token, dozwolone entity_id i adres sieciowy |
| WhatsApp | Twilio/Meta, sender, Auth Token i publiczny webhook HTTPS; Calling nadal odrębnie |
| n8n/worker | Ograniczony token scheduler:tick; n8n także osobny klucz szyfrowania |

## Środa 28.10.2026

1. Rozpakuj projekt w osobnym katalogu, zachowaj .env i backup poprzedniej bazy Core. Uruchom scripts/start.ps1. Sprawdź wynik 83 testów i wersję 0.4 w /health.
2. Utwórz dwie rozmowy, sprawdź odrębny kontekst, restart, eksport oraz usuwanie. Ustaw rzeczywiste modele w OLLAMA_ALLOWED_MODELS; zainstaluj je oddzielnie i sprawdź rozmowę po polsku.
3. Uruchom generator i import syntetycznej bazy z README. Włącz snapshot, sprawdź osiem domen i miesiąc 2026-10 w finansach. Checkbox w rozmowie powinien przekazać tylko agregaty kopii.
4. W AutoLogice potwierdź wersję i wykonaj jej backup. Przy zatrzymanym Core zaimportuj jawnie wybrany plik schematu 18. Uruchom Core i porównaj dane jednego zlecenia, final_price, płatności, części oraz terminy. Snapshot nie aktualizuje się sam; odświeżaj go świadomie, przy zatrzymanym Core.
5. Dla podglądu na żywo nadal przetestuj istniejący serwer mobilny AutoLogiki i jego GET-y. Pełne zapisy wymagają osobno zaakceptowanego mostu usług domenowych, nie bezpośredniego SQL.
6. Następnie sprawdź lokalne laboratorium MCP/OpenAPI, tokeny, HA z jednym czujnikiem i n8n. Docker oraz dostęp telefonu przez prywatny HTTPS/VPN wymagają testu konfiguracji i mountów.
7. Na końcu przygotuj konta Twilio i przychodzący webhook. Wysyłka, Calling oraz sterowanie bramą pozostają osobnymi etapami; brama wymaga osobnego potwierdzenia i zabezpieczeń sprzętowych.

## Pozostały zakres projektu

Streaming odpowiedzi, lokalne STT/TTS i wake word, semantyczna pamięć, pełny most domen AutoLogiki i zapisy, MQTT/ESPHome, sterowanie światłem/scenami/bramą, wysyłka WhatsApp i Calling, rozszerzone automatyzacje, OAuth/stdio pluginów, samodzielne zmiany kodu z izolowanymi testami i wdrożeniem, OIDC/role pracowników, monitoring i szyfrowane kopie offsite. Wszystko pozostaje ujęte w ARCHITEKTURA.md; ta wersja nie odblokowuje tego przez zmianę flagi live.
