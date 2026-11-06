# Home Assistant — M5.1 (2026-11-06)

Adapter odczytuje stany przez REST lub jednorazową sesję WebSocket. Panel Dom wymaga jawnego wyboru i przycisku; zmiana transportu kasuje poprzedni wynik. Nie ma usług sterujących ani subskrypcji zdarzeń.

## Konfiguracja lokalna

W ignorowanym `.env` ustaw `HA_READONLY_ENABLED=true`, `HA_URL` (sam origin, preferowane HTTPS), `HA_TOKEN`, `HA_ALLOWED_ENTITIES` (lista entity_id oddzielona przecinkami, maksymalnie 100) i `JARVIS_NETWORK_ALLOWLIST` (dokładne adresy/CIDR serwera). Sekret pozostaje po stronie Core. Nie wklejaj go do panelu ani repozytorium. Wyłączenie integracji zwraca503 bez połączenia.

Użyj osobnego konta Home Assistant o najmniejszych uprawnieniach. **Lokalna lista encji nie ogranicza tokenu po stronie HA.** `get_states` otrzymuje stany dostępne kontu; Core filtruje wynik przed odpowiedzią. ACL rzeczywistego konta i instalacji trzeba sprawdzić osobno. Nie deklarujemy zweryfikowanego ograniczonego tokenu ani gotowości produkcyjnej M5.1.

## Kontrakt i granice

- GET `/api/v1/home/states` oraz `/api/v1/home/states/{entity}` — REST.
- GET `/api/v1/home/websocket/states` — auth_required → auth → auth_ok → get_states → zamknięcie; alias `/api` zachowany.
- Każda trasa wymaga `home:read`. WebSocket ponownie sprawdza autoryzację po odczycie, więc token odwołany podczas I/O nie otrzyma danych.
- DNS jest rozwiązywany przed połączeniem, wszystkie IP muszą być dozwolone; resolver łączy do tych adresów, zachowując host TLS. Brak przekierowań, proxy z otoczenia i cookies.
- Łączny deadline20s, odbiór WS5s, zamknięcie1s, maksymalnie4 sesje WS/proces (nadmiar429), wiadomość1MiB. REST również deadline20s/1MiB. Limit10000 rekordów wejściowych; duplikaty dozwolonej encji są odrzucane.
- Odpowiedź zawiera tylko entity_id, state, opcjonalny last_changed i friendly_name/unit_of_measurement. Pozostałe atrybuty nie opuszczają adaptera. Audit rejestruje licznik, nie token ani stany. Błąd transportu502 ma ogólny komunikat.
- Brak automatycznego reconnectu i zapisu; kolejny odczyt wymaga przycisku. Nie ma awaryjnego przełączania na DEMO.

## Weryfikacja

`tests/test_home_ws.py`: rzeczywisty lokalny aiohttp WebSocket z syntetycznym protokołem HA; sukces, auth_invalid, błędne id/result, JSON, limit rozmiaru, przekierowanie, timeout, adres spoza allowlisty, anulowanie i zwalnianie limitu, filtrowanie, auth/redakcja oraz odwołanie tokenu podczas I/O. To nie test instalacji Home Assistant.

`HomePanel.test.tsx`: jawny wybór transportu, brak automatycznych odczytów, czyszczenie wyniku i prywatność. `check_modules_browser.cjs`: rzeczywisty Chrome/Core, wyłączona integracja503, wybór WS i brak samoczynnego ruchu, role,390px.

Realne konto HA, jego ACL, urządzenia i usługi sterujące: NOT_RUN. M5.1 pozostaje BLOCKED dla realnej integracji; adapter i protokół przetestowane. Instalator HUD3 pozostaje wcześniejszą paczką M3.

## Źródła protokołu

Oficjalne [WebSocket API](https://contributors.home-assistant.io/core/internals/websocket-api/) i [REST API](https://contributors.home-assistant.io/core/internals/rest-api/), sprawdzone2026-11-06. Ograniczenia konta HA nie wynikają z samego użycia tokenu Bearer.
