# JARVIS OS 0.8.3 — ręczna rozmowa głosowa

22.10.2026. R03 połączono w przepływ półdupleksowy: mikrofon po przycisku → AudioWorklet/mono PCM16kHz WAV → segmentacja po energii → Wyoming STT → domyślny przegląd/poprawa tekstu → osobna sesja czatu voice → Wyoming TTS i odtworzenie → ponowne słuchanie. Dostępny osobny, eksperymentalny tryb automatycznego wysyłania. Koniec przyciskiem/komendą/ciszą, przerwanie odpowiedzi przyciskiem.

Mikrofon jest wyłączany w processing/speaking. Abort unieważnia spóźnione operacje, callbacki i wyniki; graf/tracki/URL/timery są sprzątane przy anulowaniu, nawigacji i wylogowaniu. Poprawiono natywne timery wykryte w Chromium oraz wyścigi natychmiastowego cancel/deferred start. Budżety i bufory są ograniczone; brak automatycznych ponowień.

Transkrypcja nie uruchamia parserów ustawień, przypomnień ani pamięci. Prywatne notatki i podsumowanie warsztatu nie są dołączane. Trwały input_mode oddziela historie text/voice. Schema9→10 tworzy kopię before-schema10 i zachowuje stare rozmowy jako text.

Weryfikacja: 229 testów Python 3.12; pip check; składnia6 plików JS; 12 kontrolowanych testów cyklu zasobów,10 PCM i 18 przepływu rozmowy, testy DOM/API. Dwie tury w testach przechodzą przez rzeczywiste lokalne transporty Wyoming/HTTP, WAV generowany jest koderem JS. Chromium/Playwright z syntetycznym plikiem mikrofonu i kontrolowanymi usługami przeszedł dwie sprawdzone wypowiedzi oraz komendę końca. Wszystkie 3 tracki i3 AudioContext zostały zamknięte. Testy nie używają rzeczywistych danych klientów.

Nadal niezweryfikowane: jakość rzeczywistych modeli STT/AI/TTS, fizyczny mikrofon/głośnik, hałas, Windows i telefony. Heurystyka energii może mylić maszyny z mową. Nie ma wake-word, głosowego barge-in, pełnego dupleksu, satelitów ani prywatnego wyjścia. Surowe audio nie jest zapisywane przez Core; zaakceptowany/automatycznie wysłany tekst trafia do historii. Abort klienta nie cofa tury już zapisanej na serwerze. Nie aktywowano operatora ani urządzeń i nie zmieniono produkcyjnej AutoLogiki.

Instrukcje i granice: ROZMOWA-GLOSOWA.md. Następne zadanie kodowe: R04, transport telefonii najpierw w laboratorium. Wszystkie 11 obszarów pozostają w PROJECT_STATUS.json i docs/NEXT_TASKS.md. Zmiany lokalne; nie wykonano push ani uruchomienia GitHub CI. Każdy commit zawiera aktualizację README.

Poprzedni raport zachowano w history/RAPORT-v0.8.2.md.
