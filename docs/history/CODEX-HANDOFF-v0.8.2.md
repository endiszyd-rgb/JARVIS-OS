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

## Aktualizacja przejęcia — R01

Źródła zaimportowane z ZIP do lokalnego repo z historią GitHub. Manifest sprawdzony przed edycją. Bazowe 147, obecnie 156 testów; pip check i JS poprawne. R01 wykonane, instrukcja EWALUACJA-RECEPCJI.md. Ollama niedostępna; jakość modelu niesprawdzona. Następne zadanie R02. Zmiany lokalne, nie wypchnięte. Historyczne informacje niżej opisują wcześniejszą paczkę.

# Przekazanie JARVIS OS do Codex Cloud

Stan aplikacji 0.8, paczka 0.8-handoff.1, 22.10.2026. To dokument przejęcia projektu, nie deklaracja utworzenia środowiska Cloud. Obecny kod nie jest jeszcze połączony z osobnym zdalnym repozytorium GitHub; nie wypchnięto zmian do produkcyjnej AutoLogiki.

Główna kolejność czytania jest teraz w 00_START_HERE.md. Jednoznaczna kolejka i kryteria odbioru: docs/NEXT_TASKS.md, zatwierdzone decyzje: docs/DECISIONS.md. Poniższy szerszy opis zachowuje kontekst; nie zastępuje aktualnej kolejki.

## Cel i uzgodnienia

JARVIS to osobisty modułowy asystent Andreasa Szydłowskiego oraz recepcja AutoLogiki. Użytkownik wraca do Windows w środę 28.10 i do tego czasu chce możliwie dużo działającego kodu, konfiguracji, testów i dokumentacji. Zezwolił na kontynuację prac bez proszenia o kolejną zgodę. Preferuje rozwiązania open source i niskie opłaty. Nie deklaruj gotowości modułów, które są symulacjami.

Produkcja AutoLogiki: https://github.com/endiszyd-rgb/Autologika-OS — tylko do odczytu, bez zmian bez osobnej zgody. Audyt kodu: commit 681f7f5ecf5a1e365022a9ac1cb22b6ff443262c, SQLite schema18. Istniejące API mobilne: potwierdzone GET /api/orders i GET /api/order/{id}. Nie zakładaj innych endpointów/tabel. Szczegóły audytu i dowody w docs/AUDYT_AUTOLOGIKA.md oraz autologika-evidence.json.

Wymagania osobiste: głos po przycisku i haśle Jarvis, swobodny dialog kończony słowem lub 30 s ciszy (regulowane), pamięć automatyczna według uzgodnionych zasad: preferencje/sprzęt/projekty/decyzje, źródło, możliwość korekty/usunięcia, bez automatycznego zapisu haseł/kluczy/danych płatniczych i prywatnych danych klientów. Te trzy funkcje nie są jeszcze wdrożone w pełni — obecne STT/TTS działa na plikach, pamięć zapisuje się ręcznie.

Telefonia: komórkowy numer warsztatu w Play, JARVIS ma odbierać od razu. Właściciel ma drugi numer. Eskalacja tylko kryzys lub klient ponawia żądanie kontaktu i odrzuca pomoc. Właściciel ustawia grafik, wyjątki, DND i numery w programie, Europe/Warsaw. Brak obchodzenia godzin dla kryzysów. Wewnętrzne podsumowanie i akceptacja właściciela przed zestawieniem. Po odmowie/braku odpowiedzi: pilna sprawa do oddzwonienia, bez nękania kolejnymi telefonami. Żadne przekierowanie Play ani operator nie są aktywowane.

## Co działa

1. Core FastAPI/SQLite, auth właściciela, ograniczone tokeny, audyt, backup, migracje (schema7).
2. Control Center: rozmowy/sesje/modele, pamięć, pluginy, propozycje zmian, scheduler, osiem domen snapshotu, HA, WhatsApp inbox/szkice, głos, telefonia i laboratorium recepcji.
3. Pluginy MCP Streamable HTTP przez oficjalny SDK i ograniczony OpenAPI GET, allowlista narzędzi/adresów, DNS→IP pinning, brak uruchamiania obcego kodu.
4. AutoLogika: rzeczywisty klient readonly mobilnego API oraz niezmienny snapshot schematu18 w 8 domenach. Brak zapisów/synchronizacji.
5. Ollama: trwały czat i jawna lista modeli. Pamięć: notatki, FTS5, opcjonalne embeddingi/RRF; brak automatycznej ekstrakcji wspomnień.
6. HA: odczyty wybranych encji. MQTT/ESP32 i sterowanie pozostają DEMO/przyszłą pracą.
7. Twilio: weryfikowany webhook WhatsApp, deduplikacja, skrzynka i niewysyłane szkice. Brak wysyłki/calling.
8. Wyoming: jawny upload WAV do STT i TTS do WAV, limity/formats, brak streamingu na żywo i wake-word.
9. Telefonia: polityka godzin/DND/urlopu, podgląd oraz trwałe laboratorium recepcji z rewizjami/idempotencją/prywatnym podsumowaniem/zgłoszeniami. Brak PSTN/SIP/WebRTC/transferu.
10. Nowe w 0.8: opcjonalna analiza recepcji przez Ollama JSON Schema, cytaty i walidacja faktów, brak narzędzi modelu, niepewność→doprecyzowanie, backend nadal egzekwuje reguły. Testowane kontrolowanym HTTP, nie rzeczywistą inferencją.
11. Docker/PowerShell, CI Linux/Windows, profil n8n i workflow przygotowane. Nie deklaruj uruchomienia Windows/Dockera/CI, dopóki ich nie wykonasz.

## Jak uruchomić w Cloud

Użyj osobnego, najlepiej prywatnego repozytorium **JARVIS-OS**. Produkcyjna AutoLogika nie jest miejscem importu plików JARVIS-a. Jeśli repo zawiera tylko otrzymany ZIP, pierwszym zadaniem ma być rozpakowanie jego płaskiej zawartości do katalogu głównego roboczego repo, bez nadpisywania .git i bez wnoszenia plików danych/sekretów. Po sprawdzeniu zaimportuj źródła jako commit. Można usunąć źródłowy ZIP z repo po udanym imporcie, aby nie wersjonować kolejnych paczek obok źródeł.

Utwórz środowisko Codex Cloud z tym repozytorium. Do tworzenia nowego środowiska oficjalny przewodnik wskazuje wersję web lub desktop; mobile pozwala wybrać istniejące środowisko. Codex przygotowuje zależności i sprawdza workflow, a po opublikowaniu środowiska każde zadanie dostaje osobne workspace. Przewodnik: https://learn.chatgpt.com/docs/cloud i https://learn.chatgpt.com/docs/environments/cloud-environments (sprawdzone 22.10.2026). Samo przeniesienie nie zapewnia bezterminowej pracy do środy: zadania muszą mieć konkretny zakres i wyniki, a kolejne etapy trzeba uruchamiać/kontynuować.

W środowisku musi być Python3.12 oraz dostęp do menedżera pakietów. Projekt nie zawiera modeli ani prawdziwych kluczy. Przygotowanie: `python3.12 scripts/cloud_setup.py`. Alternatywnie .venv + pip install -r requirements-dev.txt, pytest -q, pip check i node --check jarvis/app.js. AGENTS.md ma zasady projektu. Skrypt przygotowania testów wyłącza opcjonalne realne integracje i używa tymczasowej bazy.

## Polecenie początkowe do nowego zadania

Kontynuuj projekt JARVIS OS dla Andreasa. Jeśli repo zawiera JARVIS-OS.zip zamiast źródeł, najpierw bezpiecznie rozpakuj źródła do repo bez naruszania .git. Przeczytaj AGENTS.md, README.md, docs/RAPORT.md i docs/CODEX-HANDOFF.md. Zweryfikuj Python3.12, zależności i bazowe testy. Nie zmieniaj produkcyjnej AutoLogiki, nie uruchamiaj operatora, wysyłki ani urządzeń. Pracuj samodzielnie etapami bez pytań o pozwolenie na kontynuację, zapisuj postęp i testy. Najpierw potwierdź bazowe testy i wykonaj R01 z docs/NEXT_TASKS.md; potem realizuj następne niezablokowane zadania z tej kolejki. Dostarczaj rzeczywisty kod, nie same plany, i odróżniaj testy modelu/sprzętu od transportów kontrolowanych.

## Priorytety dalszych prac

1. Eval polskich rozmów recepcji: negacje, hipotetyczne sytuacje, cytaty, po naprawie, naleganie, rozmówca zły numer, niepewność, próby wydobycia kluczy/danych. Zweryfikuj na realnym lokalnym modelu, jeśli środowisko go udostępnia; inaczej przygotuj narzędzia ewaluacji i raportuj brak inferencji.
2. Ustawienia prywatnej pamięci i selektywna ekstrakcja w osobistym czacie, źródła, deduplikacja, korekty, zakaz pamięci, retencja. Dane klientów muszą pozostać w recepcji.
3. Sesja audio: przycisk, stany, cisza/koniec, anulowanie i przerwanie wypowiedzi; później wake-word z właściwą licencją modelu, satelity dom/warsztat i przełączanie prywatnego wyjścia.
4. Telefonia za interfejsem adaptera: laboratorium transportu na żywo, odrębne role caller/owner, oczekiwanie, briefing/akceptacja, fallback i limity kosztu. Dopiero potem wybrany operator/numer/Play i rzeczywiste testy właściciela. WhatsApp Business Calling wymaga osobnej weryfikacji aktualnych warunków Twilio/Meta i aktywacji.
5. MQTT/ESP32, powiadomienia i n8n z najmniejszymi zakresami, bez fizycznej bramy i wrażliwych akcji.
6. Przepływ proponowania kodu z testami, sandboxem i rollbackiem — dziś propozycje kodu są tylko opisem.
7. Monitoring, retencja, odtwarzanie backupów, aktualizacje, UX/telefon/HTTPS oraz Windows/Docker. Sprawdź działające CI po podłączeniu GitHub, a nie sam YAML.

Wszystkie 11 pierwotnych obszarów nadal obowiązuje. Nie przedstawiaj działającego MVP jako ukończonego pełnego JARVIS-a.
