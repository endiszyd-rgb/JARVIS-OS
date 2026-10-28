# Przekazanie JARVIS OS 0.8.3

Zacznij od 00_START_HERE.md, AGENTS.md, PROJECT_STATUS.json, docs/DECISIONS.md i docs/NEXT_TASKS.md. To istniejący projekt. Następne zadanie: R04 — interfejs transportu telefonii i laboratorium, bez aktywacji operatora. Nie zmieniaj produkcyjnej AutoLogiki. Wszystkie 11 obszarów i zaakceptowane decyzje pozostają w zakresie.

R01: 30 syntetycznych rozmów PL, runner, raporty; jakość prawdziwego modelu recepcji niesprawdzona. R02: ograniczona pamięć deklaracji pl-declarations-v1, źródła, korekty, deduplikacja i jawne zastąpienie; swobodna ekstrakcja nadal przyszła. R03: ręczna rozmowa półdupleksowa PCM→Wyoming STT→review→osobny czat voice→TTS, zwalnianie zasobów i test Chromium z syntetycznym mikrofonem/usługami.

Core schema10; migracja tworzy backup i oznacza dotychczasowe historie jako text. Voice nie może przejąć text, wykonywać parsera ani zapisywać pamięci. Domyślny review transkrypcji jest włączony; auto-send osobno eksperymentalny. Kod i ograniczenia: docs/ROZMOWA-GLOSOWA.md. Prawdziwe modele/sprzęt, hałas, wake-word, pełny dupleks i prywatne wyjście nie są sprawdzone lub wykonane.

Sprawdzenia: 229 pytest na Python 3.12, pip check, składnia JS, kontrolowane testy JS i rzeczywista Chromium z syntetycznym mikrofonem. Browser test jest opcjonalny: node scripts/check_voice_browser.cjs (wymaga Playwright/przeglądarki); nie oznacza testu inferencji lub fizycznego sprzętu. Dokładny wynik i granice: docs/RAPORT.md. Windows/Docker/GitHub CI nie wykonane w tej sesji. Workflow przygotowano do kontroli JS, nie przedstawiać YAML jako wykonanego CI.

Pracuj autonomicznie na danych syntetycznych. Każdy commit musi zawierać aktualizację README z zakresem, wykonanymi sprawdzeniami i ograniczeniami. Nie deklaruj bezterminowej pracy w tle; zapisuj konkretny etap i stan. Przed pierwszą edycją nowo rozpakowanej paczki sprawdź manifest. Po edycji stary manifest jest historycznym checksumem; scripts/package_handoff.py tworzy nowy z czystego, zapisanego repo. Zmiany w tej sesji są lokalne, bez push na GitHub.

Pełny poprzedni kontekst zachowano w docs/history/CODEX-HANDOFF-v0.8.2.md. Zatwierdzone decyzje: docs/DECISIONS.md; aktualny maszynowy stan: PROJECT_STATUS.json.
