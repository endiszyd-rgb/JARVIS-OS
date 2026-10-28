# JARVIS OS 0.8.4 — transport telefonii w laboratorium

22.10.2026. R04 dostarcza trwały kontrakt adaptera i transport laboratoryjny na SQLite. Kanały klienta, właściciela i systemu mają osobne typy komend; publiczna projekcja klienta zawiera wyłącznie stan oraz dostarczone wiadomości. Token ograniczony do jednej rozmowy ma skrót w bazie, wygasa i może zostać obrócony przez właściciela. Klucz właściciela nie uwierzytelnia kanału klienta.

Prywatna oferta musi zostać dostarczona przed akceptacją. Zgoda dotyczy aktualnej próby i tworzy oczekującą komendę mostu, dostarczaną osobno. Backend sprawdza bieżące godziny, urlop i DND przy akceptacji oraz przed mostem. Jedna próba kontaktu, ograniczenia czasu/tur/zdarzeń i symulowanego kosztu są egzekwowane przez serwer. Odmowa, brak odpowiedzi, timeout lub awaria kończą próbę bez ponawiania; powstaje zgłoszenie bez obietnicy terminu. Czas pochodzi z serwera. Powtórzone zdarzenie nie tworzy drugiej komendy, a odtworzenie po terminie nie reaktywuje mostu.

Recepcja, zgłoszenia, zdarzenia, audyt i komendy uczestniczą w tej samej transakcji. Migracja 10→11 tworzy before-schema11-*.sqlite3; testy zachowują stare rozmowy recepcji, notatki, politykę i historie voice. Restart wznawia zapisany stan bez ponownego dostarczenia. Stare właścicielskie akcje recepcji nie mogą modyfikować rozmowy powiązanej z transportem.

Control Center ma nowy widok Transport · laboratorium: osobne karty właściciela, klienta i komend, ręczne tworzenie/odświeżanie/dostarczanie, obrót tokenu, decyzje, rozłączenie i usuwanie zakończonego testu. Token pozostaje w pamięci panelu, jest usuwany przy nawigacji/wylogowaniu; spóźnione odpowiedzi nie odbudowują widoku. Usunięcie czyści dane recepcji i unieważnia token. Poprawiono mobilną szerokość selektora oraz aktualizowanie jego etykiety. Cały Control Center nadal jest stroną właściciela; nie przekazuj jej klucza klientowi.

## Wykonane sprawdzenia

- **276 testów pytest na Python 3.12**, pip check; migracja, restart, izolacja, limity, timeouty, DND, awarie, rewizje/idempotencja, współbieżność i rollback.
- Składnia 7 plików JS; 6 kontrolowanych testów panelu transportu. Dotychczasowe testy pamięci/głosu pozostają zielone: 12 cyklu audio, 10 PCM, 18 przepływu rozmowy oraz testy paneli i sprzątania.
- Rzeczywisty Chromium/Playwright: pełny przebieg klient→prywatna oferta→zgoda→osobne dostarczenie mostu→rozłączenie; 13 żądań klienta bez klucza właściciela, ścisłe pola publiczne, brak tokenu w DOM/storage/URL, usunięcie i odpowiedź 401 dla starego tokenu, nawigacja/wylogowanie. Widok mobilny 390 px, szerokość dokumentu 390 px, brak poziomego przepełnienia. Tymczasowa baza i syntetyczne dane, bez operatora.
- Ponownie Chromium głosu: 2 tury, 3 STT i 2 TTS na kontrolowanych usługach i syntetycznym mikrofonie; 3 tracki ended, 3 konteksty closed. To rzeczywiste lokalne protokoły, bez inferencji modeli.
- Walidacja 30 syntetycznych przypadków reception-pl-v1.0.0 bez inferencji. Workflow CI i setup rozszerzono o panel transportu; GitHub CI nie uruchomiono.

## Ograniczenia i następny etap

To transport tekstowy laboratorium, z trzema zamkniętymi frazami testowymi zamiast ogólnego rozumienia rozmowy. Adapter niczego nie wysyła przez sieć. Nie ma PSTN/SIP, telefonicznego audio, aktywnego operatora, płatnych rozmów ani powiadomień. Komendy wymagają ręcznego dispatch, a terminy są rozliczane przy odczycie/zdarzeniu; nie ma workera działającego w tle. Przed rzeczywistym adapterem potrzebne są oddzielna aktywacja, autoryzacja webhooków i projekt niezawodnego dostarczania skutków zewnętrznych. Szczegóły: [TRANSPORT-TELEFONII.md](TRANSPORT-TELEFONII.md).

Jakość prawdziwych modeli, fizyczny sprzęt, hałas, Windows, telefony i Docker pozostają niesprawdzone. R03 nie ma wake-word, głosowego barge-in, pełnego dupleksu ani prywatnego wyjścia. Produkcyjna AutoLogika pozostała bez zmian. Następne zadanie: R05 — odczyt czujników i laboratorium MQTT. Wszystkie 11 obszarów zachowano w PROJECT_STATUS.json. Zmiany lokalne, bez push. Każdy commit zawiera README. Poprzedni raport: [history/RAPORT-v0.8.3.md](history/RAPORT-v0.8.3.md).
