# Brama warsztatu i komendy głosowe — 0.11.0 (2026-11-13)

Właściciel zlecił 2026-11-13 realne sterowanie bramą na Wi‑Fi z poziomu aplikacji i komendą głosową. Ten dokument opisuje, co zostało dostarczone, jak to skonfigurować i czego **nie** zweryfikowano.

## Co działa

| Element | Stan |
|---|---|
| Symulator bramy (M5.4): stany, czas ruchu, stop, cooldown, potwierdzenie, dziennik | VERIFIED — `tests/test_gate.py` |
| Sterownik **HTTP** (Shelly / Tasmota / ESPHome / własne ESP) | VERIFIED na lokalnym serwerze testowym; prawdziwy sterownik NOT_RUN |
| Sterownik **Tuya / Smart Life** (Tuya IoT OpenAPI, podpis HMAC‑SHA256) | DONE — implementacja według dokumentacji Tuya; rzeczywiste konto NOT_RUN |
| Sterownik **Home Assistant** (usługa `cover.*`/`switch.*` na jednej encji) | DONE — kontrakt REST HA; rzeczywista instalacja NOT_RUN |
| Komendy głosowe w przeglądarce (Chrome/Edge, słowo aktywujące) | VERIFIED w testach jsdom z syntetycznym `SpeechRecognition`; mikrofon na stanowisku NOT_RUN |
| Komendy głosowe Wyoming (przytrzymaj i mów) | DONE — reużywa `/voice/transcribe` i `/voice/synthesize`; wymaga uruchomionych usług Wyoming |
| Parser intencji PL (`jarvis/intents.py`) | VERIFIED — deterministyczny, model nigdy nie wykonuje urządzeń |

## Bezpieczeństwo i granice

- Tylko właściciel (klucz lub konto `owner`) może wysłać polecenie. Tokeny usługowe i role odczytu nie mają dostępu; każde polecenie trafia do `audit` (`gate.command` / `gate.failed`) oraz do tabeli `gate_events` (ostatnie 500).
- Cooldown (domyślnie 3 s) odrzuca szybkie powtórzenia; przy zasięgu głosowym chroni przed „podwójnym” poleceniem.
- Opcjonalne potwierdzenie: serwer wydaje jednorazowy token ważny 12 s; dla innej akcji lub po czasie token nie działa. W rozmowie i głosie potwierdzeniem jest „tak”, odwołaniem „nie”.
- Sekrety (hasło HTTP, Tuya Access Secret, token HA) są przechowywane w lokalnej bazie `device_config`, nie wracają do panelu ani audytu; puste pole przy zapisie zachowuje poprzednią wartość. Dostęp do pliku bazy to dostęp do sekretów — chroń katalog danych.
- Sterownik HTTP i HA łączą się tylko z adresami z `JARVIS_NETWORK_ALLOWLIST` (DNS przypięty do IP, bez przekierowań, limit 1 MiB, 15 s). Tuya Cloud łączy się z wybranym endpointem `openapi.tuya*.com` przez internet; to jedyny sterownik wychodzący poza LAN.
- Model językowy nie uruchamia bramy: intencje rozpoznaje stały parser po stronie Core, a jego wejściem jest wyłącznie tekst właściciela.
- Fizyczne zabezpieczenia bramy (fotokomórki, krańcówki, wyłącznik ręczny) pozostają po stronie centrali. JARVIS nie ma czujnika stanu, jeśli sterownik go nie udostępnia; wtedy stan to ostatnie wysłane polecenie po `travel_seconds`.

## Konfiguracja z poziomu aplikacji

Widok **Brama** → *Konfiguracja sterownika* → *Edytuj*. Zapis wymaga zgodnej rewizji (409 przy równoległej zmianie). *Testuj połączenie* odczytuje stan bez poruszania bramą.

### Brama na Smart Life / Tuya (najczęstszy przypadek „sterownik Wi‑Fi z aplikacji”)

1. Załóż konto na https://iot.tuya.com → *Cloud* → *Create Cloud Project* (Industry: Smart Home, Data Center: **Central Europe**).
2. W projekcie: *Devices* → *Link Tuya App Account* → zeskanuj kod aplikacją Smart Life/Tuya Smart. Brama pojawi się na liście z **Device ID**.
3. *Overview* → skopiuj **Access ID/Client ID** i **Access Secret**.
4. *Devices* → *Device Debugging* → sprawdź kody funkcji (`switch_1`, czasem `switch`, `control` z wartościami `open/close/stop`, `doorcontact_state` jako czujnik).
5. W JARVIS wybierz sterownik *Tuya / Smart Life*, wpisz region, Access ID, Access Secret, Device ID oraz kody. Dla sterownika z jednym przekaźnikiem impulsowym zaznacz *Brama impulsowa*.
6. *Zapisz*, potem *Testuj połączenie*. Błąd `Tuya error 1106` oznacza brak powiązania urządzenia z projektem; `1004` — zły podpis/sekret; `28841105` — nieaktywna subskrypcja API w projekcie (włącz *IoT Core* w *Service API*).

Alternatywa bez chmury: wgranie Tasmota/ESPHome na sterownik ESP (jeśli jest na ESP8266/ESP32) i użycie sterownika HTTP.

### Shelly / Tasmota / ESPHome (sterownik HTTP)

- Shelly 1/Plus: `http://IP/relay/0?turn=on` (impuls: ustaw w Shelly *auto‑off* 0.5–1 s). Stan: `http://IP/relay/0` z fragmentem `"ison":true`.
- Tasmota: `http://IP/cm?cmnd=Power%20On`, `.../Power%20Off`, stan `http://IP/cm?cmnd=Power` z fragmentem `"POWER":"ON"`.
- Dodaj podsieć sterownika do `JARVIS_NETWORK_ALLOWLIST` w `.env` (np. `127.0.0.0/8,::1/128,192.168.1.0/24`) i uruchom JARVIS ponownie.

### Home Assistant

Encja `cover.*` lub `switch.*`, usługi domyślne `cover.open_cover/close_cover/stop_cover`. Dla przełącznika impulsowego: `switch.turn_on` jako otwarcie i *Brama impulsowa*. Puste URL/token używają `HA_URL`/`HA_TOKEN` z `.env`.

## Komendy głosowe

Widok **Głos**. Silnik *Przeglądarka* używa rozpoznawania mowy Chrome/Edge (dźwięk przetwarza usługa mowy przeglądarki; wymaga internetu i zgody na mikrofon dla `http://127.0.0.1:17321`). Włącz nasłuch raz; nasłuch wznawia się automatycznie po przerwach.

- „**Jarvis, otwórz bramę**”, „Jarvis, zamknij bramę”, „Jarvis, brama stop”, „Jarvis, jaki jest stan bramy”.
- Samo „Jarvis” → odpowiedź „Słucham.” i 8 s na polecenie.
- Przy włączonym potwierdzeniu JARVIS pyta „Otworzyć bramę?” — odpowiedz „tak” lub „nie” (12 s).
- Zdania niezwiązane z urządzeniami są ignorowane, chyba że włączysz *Wysyłaj inne zdania do modelu AI*; wtedy trafiają do zwykłej rozmowy głosowej (bez pamięci, jak dotychczas).
- Silnik *Wyoming*: przycisk *Przytrzymaj i mów*; nagranie 16 kHz WAV trafia do `/api/v1/voice/transcribe`, odpowiedź czyta `/api/v1/voice/synthesize`. Wymaga `JARVIS_VOICE_ENABLED=true` i usług STT/TTS.

Odpowiedzi są czytane przez `speechSynthesis` (głos polski Windows, jeśli zainstalowany) lub Wyoming TTS.

## API

- `GET /api/v1/devices/gate` — stan, zamaskowana konfiguracja, rewizja, 20 ostatnich zdarzeń.
- `POST /api/v1/devices/gate/command` `{action: open|close|stop|status, source: panel|voice|api, confirm_token?}` → `executed` | `confirmation_required` | 429 cooldown | 501/502/503.
- `POST /api/v1/devices/gate/test` — odczyt stanu bez ruchu.
- `GET/PUT /api/v1/devices/gate/config` — `{revision, config}`; sekrety maskowane.
- `GET/PUT /api/v1/config/voice` — preferencje głosu właściciela.
- `POST /api/v1/chat` z `input_mode: voice` lub tekstem rozpoznaje intencje bramy przed modelem; odpowiedź ma `model: parser` i pole `device`.

Schemat SQLite pozostaje 12: dodano tabele `device_config` i `gate_events` przez `CREATE TABLE IF NOT EXISTS` (bez migracji danych; starsza baza otwiera się bez zmian).

## Weryfikacja 2026-11-13

`tests/test_gate.py` (26): intencje, symulator, cooldown, potwierdzenie, maskowanie sekretów, lokalny przekaźnik HTTP, odmowa poza allowlistą, rozmowa/głos, konfiguracja głosu. Frontend: `GatePanel.test.tsx` (5) i `VoicePanel.test.tsx` (6). Rzeczywisty Chrome headless: logowanie z zapamiętanym kluczem, Brama/Głos/Pulpit, 390 px. **Rzeczywista brama, konto Tuya, instalacja HA, mikrofon i Windows: NOT_RUN** — do sprawdzenia przez właściciela na warsztacie (patrz `docs/PLAN-ROZWOJU.md`, etap 0).
