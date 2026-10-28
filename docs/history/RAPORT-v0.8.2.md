# Stan 0.8.2 — pamięć i sesje mikrofonu, 22.10.2026

Dostarczono R02 w ograniczonym zakresie: automatyczna pamięć pl-declarations-v1 rozpoznaje jednoznaczne całe deklaracje z zamkniętego katalogu. Zapis po udanej odpowiedzi jest atomowy z zakończeniem tury. Są źródła, deduplikacja, jawne zastąpienie, ochrona ręcznych korekt, opt-out wiadomości i blokada po zmianie polityki/pamięci. Domyślny tryb pozostaje manual. Nie ma ogólnej ekstrakcji swobodnych faktów ani semantycznego filtra dowolnych prywatnych treści. Szczegóły: PAMIEC-AUTOMATYCZNA.md.

R03: API stanów i laboratorium cyklu mikrofonu — ręczna aktywacja, cisza30s regulowana, przerwanie/anulowanie, polling i lokalny watchdog, sprzątanie przy nawigacji/wylogowaniu. Stan procesowy, jeden lokalny Core. Ciągłe przechwytywanie/segmentacja, STT→czat→TTS i automatyczne wykrywanie aktywności mowy nadal niepodłączone. Szczegóły: SESJE-AUDIO.md.

Migracja 8→9 tworzy kopię przed zmianą i zachowuje ręczne notatki. Weryfikacja: 213 testów Python3.12; pip check; JS syntax; 10 testów kontrolera audio z kontrolowanym mikrofonem/API/zegarem; kontrolowany DOM/API panelu pamięci, opt-out czatu i sprzątanie widoku głosu. Testy obejmują rollback po capture, równoległe zmiany, FTS/embeddingi, izolację recepcji i blokadę tokenów usług. R01: 30 przypadków nadal przechodzi walidację zestawu.

Nie wykonano testu rzeczywistego modelu, przeglądarki, mikrofonu, Windows, Dockera ani operatora. Nie aktywowano żadnych integracji ani urządzeń. Repo AutoLogiki pozostaje niezmienione. Zmiany i paczka przekazania są lokalne; nie wykonano push na GitHub. Bieżące zadanie: R03 integracja mikrofonu z przetwarzaniem mowy.

Poniżej historia poprzednich etapów; bieżącą prawdę opisuje powyższy stan i PROJECT_STATUS.json.

---

# Stan 0.8.1 — R01 i R02 część 1, 22.10.2026

R01 dostarczone: 30 syntetycznych rozmów, CLI, raporty i 9 testów HTTP. Jakość rzeczywistego modelu niesprawdzona (Ollama niedostępna).

R02 część 1 dostarczona: odrębna polityka, źródła, panel, korekty z historią i rewizjami, blokada zapisu, jawna retencja. Migracja Core 7→8 z kopią i testem. Automatyczna ekstrakcja pozostaje nieaktywna; następny etap to ekstrakcja, wykluczenia i deduplikacja. Instrukcje: PAMIEC-POLITYKA.md i EWALUACJA-RECEPCJI.md.

Weryfikacja: 164 testy Python 3.12, pip check, składnia JS i kontrolowany DOM/API panelu pamięci. Brak testów rzeczywistego AI, Windows, Dockera, sprzętu, operatora i prawdziwej przeglądarki. Produkcyjnej AutoLogiki nie zmieniono. Zmiany zapisane w lokalnym repo; nie wypchnięte na GitHub.

---

# Przejęcie w Cloud — R01, 22.10.2026

Pobrano ZIP z osobnego repo JARVIS-OS, sprawdzono manifest 81 plików i wykonano bazowe 147 testów Python 3.12. Zaimportowano źródła w katalogu głównym lokalnego repo, zachowując historię GitHub. Zmiany nie zostały wypchnięte na GitHub.

R01: 30 syntetycznych przypadków, runner `python -m jarvis.reception_eval`, walidacja bez modelu, raporty JSON/Markdown i rozróżnianie środowiska, schematu, dowodów, intencji, faktów i nadmiernej eskalacji. Szczegóły: EWALUACJA-RECEPCJI.md. Raport kontrolowanego HTTP: 11 zaliczonych i 19 niezaliczonych przypadków dla stałej odpowiedzi routine; nie jest to pomiar AI.

Sprawdzenia po zmianie: 156 testów pytest, pip check, node --check jarvis/app.js. Jakość rzeczywistego modelu niesprawdzona: brak Ollamy/usługi lokalnej. Windows, Docker, sprzęt, operator i test przeglądarki nie były wykonane w tej sesji. Schemat pozostaje 7. Następne zadanie: R02.

---

# JARVIS OS 0.8 — przekazanie 0.8-handoff.1

22.10.2026. Dodano opcjonalną analizę wypowiedzi klienta przez Ollama JSON Schema. Nie podłączono operatora, rzeczywistych rozmów, fizycznych urządzeń ani produkcyjnej bazy warsztatu. Nie uruchomiono jeszcze środowiska Codex Cloud i nie utworzono osobnego zdalnego repozytorium.

Działający kod: endpoint AI-turn, wybór modelu na allowliście, ograniczony kontekst, sprawdzenie dosłownych dowodów/faktów, high→propozycja klasyfikacji i uzupełnienie danych, low/medium→doprecyzowanie, backendowa bramka pierwszej prośby, egzekwowanie aktualnej dostępności, idempotencja, ochrona przed zapisem starego wyniku po zmianie rozmowy. Panel pokazuje ocenę oraz dowody i umożliwia wybór reguł testowych albo AI. Awaria AI nie przechodzi do heurystyki bez wiedzy użytkownika.

147 testów pytest przeszło na Pythonie3.12. Nowe testy: format żądania/model/schemat, brak pamięci osobistej w kontekście, zmyślone cytaty i fakty, nieznane pola/polecenia, niepewność, duplikaty, stare rewizje, zmiany podczas inferencji, bramka pierwszego żądania, brak dostępu tokenem usługi, sanitacja błędu i blokada modeli :cloud. Testy używają kontrolowanego HTTP, nie modelu AI. Test panel→Core→lokalny kontrolowany serwer HTTP sprawdził analizę, uzupełnienie samochodu/imienia i wyświetlenie oceny. Zweryfikowano pip check i składnię JS. To nadal nie pomiar jakości modelu, test Windows, Dockera, prawdziwej przeglądarki lub telefonu.

Przygotowano AGENTS.md, docs/CODEX-HANDOFF.md z całością wymagań i planem, oraz scripts/cloud_setup.py. Skrypt tworzy środowisko Python3.12, instaluje przypięte zależności i wykonuje testy/checki. Sprawdzono jego wykonanie lokalnie; nie oznacza to wykonania w Codex Cloud. Schemat pozostaje7, bez nowej migracji z 0.7.

Do użycia AI potrzebujesz uruchomionej Ollamy i zainstalowanego odpowiedniego modelu. Domyślnie funkcja wyłączona; trzy nowe zmienne w .env.example/Compose. Potrzebny jest rzeczywisty eval polskiej rozmowy, zanim moduł obsłuży klientów. Literalny cytat weryfikuje pochodzenie, a nie prawdziwość lub poprawne rozumienie. Deklarowana pewność modelu nie jest pomiarem statystycznym.

Do Codex Cloud potrzebne osobne repo JARVIS-OS na GitHub i środowisko powiązane z nim. ZIP zawiera instrukcję importu, przygotowania i kontynuacji. Nie używać produkcyjnego AutoLogika-OS jako miejsca importu. Oficjalnie nowe środowisko przygotowuje się w wersji web/desktop; mobile może korzystać z istniejącego. Cloud pomaga prowadzić zadania przy wyłączonym komputerze, ale nie zastąpi testów Windows/mikrofonu/operatora i nie uruchamia sam z siebie nieskończonego ciągu zadań do środy.

Na środę28.10: start Windows/Python3.12, testy, podgląd telefonii, laboratorium, prawdziwa Ollama i eval analizy, a następnie wcześniejsze testy snapshotu AutoLogiki, STT/TTS, Dockera i telefonów. Bez aktywacji Play do czasu gotowej integracji z fallbackiem. Pozostały zakres11modułów i wymagane konta w RAPORT-v0.5.md, aktualne priorytety w CODEX-HANDOFF.md.

Szczegóły nowego modułu: ANALIZA-RECEPCJI-v0.8.md. Testy jakości rzeczywistej inferencji, automatyczna pamięć, sesja audio/wake-word i telefonia na żywo pozostają do realizacji.

## Uporządkowane przejęcie projektu

Dodano 00_START_HERE.md, PROMPT_CODEX.md, PROJECT_STATUS.json, docs/DECISIONS.md i docs/NEXT_TASKS.md. Wyznaczono R01 (narzędzie ewaluacji polskiej recepcji) jako konkretne pierwsze zadanie z kryteriami odbioru. AGENTS wskazuje kolejność czytania. Skrypty package_handoff.py i verify_handoff.py tworzą/sprawdzają płaski ZIP z manifestem źródłowego commitu i sum plików. Nie zmieniono runtime aplikacji ani schematu.

Weryfikacja przekazania: pełne rozpakowanie do czystego katalogu, zgodność manifestu, wykrycie kontrolowanej zmiany pliku, bazowe147testów z rozpakowanego źródła, pip check i składnia JS. To test gotowości paczki, nie uruchomienie środowiska Codex Cloud ani realnych integracji. Pełny stan wszystkich modułów i granice dowodów znajdują się także w PROJECT_STATUS.json.
