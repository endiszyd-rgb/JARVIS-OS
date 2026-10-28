# Aktualizacja 0.8.3

Połączono ręczną sesję z PCM/STT/czatem/TTS. Bieżące uruchomienie, zachowanie i ograniczenia: [ROZMOWA-GLOSOWA.md](ROZMOWA-GLOSOWA.md). Poniżej historia etapu 0.8.2, który sam jeszcze nie miał całego przepływu.

# R03 — sterowanie sesją i cykl mikrofonu, laboratorium

Panel Głos lokalny ma osobny test ręcznej sesji mikrofonu. Mikrofon otwiera się dopiero po przycisku **Uruchom mikrofon** i zgodzie przeglądarki. Domyślna cisza wynosi 30 sekund, zakres 1–300 sekund. Zakończenie, anulowanie, wyjście z widoku, wylogowanie i `pagehide` zwalniają ścieżki mikrofonu oraz zatrzymują odtwarzanie z widoku. Późna odpowiedź na prośbę o mikrofon po anulowaniu natychmiast zamyka otrzymane ścieżki.

**To laboratorium cyklu zasobów, nie gotowa rozmowa głosowa.** Nie podłączono jeszcze wykrywania mowy, segmentacji i strumienia mikrofon→STT→czat→TTS. Przycisk „Zgłoś aktywność · test” ręcznie resetuje licznik ciszy. Mówienie samo w sobie nie resetuje go w tym etapie. Istniejący upload WAV i synteza Wyoming pozostają osobną funkcją; nie oznaczają działania sesji na żywo. Nie ma wake-word ani nasłuchu przed przyciskiem. Rzeczywisty test przeglądarki, uprawnień i sprzętu pozostaje do wykonania.

## Stan serwera

Endpointy wymagają pełnego klucza właściciela; tokeny usług nie mają dostępu.

- POST `/api/voice/sessions` — tworzy idle; opcjonalne silence_seconds, domyślnie 30.
- GET `/api/voice/sessions/{id}` — bieżący stan i pozostałe czasy.
- POST `/api/voice/sessions/{id}/events` — event_id UUID, oczekiwana revision, action. Configure wymaga silence_seconds.

Stany: idle → listening → processing → speaking → listening. Akcje activate/activity/process/speak/complete/resume/interrupt/end/cancel/configure są sprawdzane przez backend. Przerwanie kończy fazę mówienia i wraca do słuchania. End/cancel wracają do idle; kolejna ręczna aktywacja rozpoczyna nowy cykl. Konfigurację ciszy zmienia się tylko w idle. Nieaktualna rewizja lub niepoprawne przejście daje 409. Replay tego samego event_id zwraca aktualny stan i rewizję potwierdzonego zdarzenia; nie wznawia zakończonego mikrofonu. Zmiana danych przy tym samym event_id jest konfliktem.

Stan jest **procesowy, nietrwały**. Restart usuwa sesje audio. W wielu workerach potrzebny byłby wspólny magazyn albo kierowanie danej sesji do jednego procesu; ten etap jest przeznaczony dla lokalnego pojedynczego Core. Maksymalnie 128 sesji i 128 potwierdzeń na sesję. Nie zapisujemy dźwięku w bazie ani nie tworzymy wpisów recepcji czy pamięci.

Wygaśnięcie jest liczone zegarem monotonicznym przy odczycie/zdarzeniu lub sweep: cisza w listening, do 120 sekund processing/speaking oraz do 15 minut aktywacji. Po wygaśnięciu stan jest idle, później jest usuwany po co najmniej 5 minutach bezczynności/odczytów. Serwer nie ma w tym etapie wątku odliczającego i sam nie kontroluje mikrofonu klienta.

## Kontroler przeglądarki

`JarvisAudioSession` w audio_client.js używa uwierzytelnionego API i getUserMedia. Publiczne operacje obejmują start/activity/process/speak/complete/resume/interrupt/stop/cancel/dispose. Przetwarzanie i mówienie zwalniają mikrofon; powrót do listening pobiera go ponownie tylko dla nadal aktywnej sesji. Stop/cancel/dispose zwalniają lokalne zasoby natychmiast, niezależnie od powodzenia żądania do serwera.

Polling oraz lokalny watchdog mają oddzielny cykl. Błąd API, lokalny czas ciszy/fazy/całej aktywacji kończy sesję i zamyka mikrofon nawet przy zawieszonym żądaniu. Żądania pollingu nie są stosowane w stos; przejścia mają blokadę równoległych wywołań. Anulowanie unieważnia oczekujące operacje, aby późna odpowiedź nie mogła ponownie otworzyć mikrofonu.

Lokalne timery JavaScript podlegają ograniczeniom karty/przeglądarki i nie gwarantują twardego terminu w zawieszonym procesie. Użytkownik może zawsze odebrać uprawnienie mikrofonu w przeglądarce. Do praktycznego użycia potrzebny jest bezpieczny kontekst (localhost lub HTTPS), obsługa getUserMedia i test na docelowym urządzeniu.

## Weryfikacja

Testy backendu używają kontrolowanego zegara: granica ciszy, aktywność, przerwanie, fazy, lifetime, anulowanie/reaktywacja, replay/stare rewizje, izolacja sesji, ograniczenia magazynu i restart. Test prawdziwego create_app sprawdza uprawnienia właściciela oraz brak zmian w pamięci i recepcji.

`node scripts/check_audio_client.cjs` sprawdza kontroler z kontrolowanym mikrofonem/API/zegarem. `node scripts/check_voice_ui.cjs` sprawdza podłączenie przycisku, nawigacji, wylogowania i pagehide z kontrolerem testowym. Nie są to testy rzeczywistej przeglądarki, mikrofonu, słyszalnego dźwięku ani inferencji.

Następne zadanie R03: połączyć ręczną sesję z przechwytywaniem WAV/segmentacją, jawną transkrypcją i odtwarzaniem, sprawdzić opóźnienia, echo i hałas. Wake-word wymaga późniejszej oceny modelu i licencji; prywatne wyjście i satelity dom/warsztat pozostają w zakresie.
