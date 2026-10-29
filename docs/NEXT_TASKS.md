# Historyczna kolejka R01–R07

Nowe polecenie 28.10: instalator bieżącego M3 dostarczony i zweryfikowany. Następny krok użytkownika: instalacja oraz odbiór interfejsu według WINDOWS-INSTALLER.md. Nie rozpoczynaj automatycznie M4 ani dawnej kolejki R05.

Od importu planu M0–M8 obowiązuje ../JARVIS_MASTER_PLAN.txt (identyczny dziennik MD). Ta wcześniejsza lista opisuje dostarczony zakres i zaległości; nie wybieraj z niej kolejności prac zamiast planu nadrzędnego.

M3.1–M3.5 ukończone. STOP przed M4 zgodnie z właścicielem; nie rozpoczynaj kolejnego etapu automatycznie w planie nadrzędnym. Poniższe opisy R01–R07 są historyczne. Wersja historycznego przekazania 0.8.4-handoff.1. R01 zaimplementowane; jakość rzeczywistego modelu nadal niesprawdzona. Następne zadanie: R05 — odczyt czujników i laboratorium MQTT. R04 dostarczono laboratoryjnie, bez operatora. Stan bieżący w PROJECT_STATUS.json; zamknięcie zadania wymaga kodu, dowodów i aktualizacji stanu. Te opisy są docelowymi wymaganiami — nie implementacją.

## R01 — ewaluacja polskiej recepcji (kod dostarczony)

Wykonano 30 przypadków, CLI, raporty i testy kontrolowanego HTTP. Instrukcja: EWALUACJA-RECEPCJI.md. Realny model pozostaje do sprawdzenia, nie blokuje R02.

**Problem:** walidacja JSON/cytatów i testy transportu nie mierzą jakości rozumienia polskiej rozmowy przez model.

**Kod wejściowy:** jarvis/reception_ai.py, jarvis/reception.py, jarvis/telephony.py, tests/test_reception_ai.py, docs/ANALIZA-RECEPCJI-v0.8.md.

**Dostarcz:** wersjonowany syntetyczny zestaw co najmniej 25 rozmów/przypadków, CLI runner i raport JSON/Markdown. Uwzględnij rutynę, pierwszą prośbę, naleganie z odrzuceniem pomocy, kryzys po naprawie, negację, cytat, przeszłość, hipotezę, zdenerwowanie bez kryzysu, pomyłkę numeru, brak polskich znaków, brak danych, błędny telefon i prompt injection. Oczekiwania muszą oceniać semantykę, wydobycie faktów i zakaz wykonania działań, nie tylko składnię.

**Kryteria odbioru:**

- Runner używa istniejącej analizy, jawnie wybranego modelu i bezpiecznej sieci; bez auto-pobierania modeli, operatora i danych klientów.
- Wynik rozróżnia błędny schemat, zmyślony cytat/fakt, niepewność, błędną intencję oraz niebezpieczną nadmierną eskalację. Pokazuje liczniki i konkretne niezaliczone przykłady, nazwę modelu, wersję zestawu i rzeczywiste źródło odpowiedzi.
- Jest tryb walidacji zestawu bez modelu. Błąd środowiska nie jest wynikiem jakości. Wyniki fixture/symulacji są wyraźnie oznaczone i nie są agregowane jako sukces rzeczywistego AI.
- Testy runnera na kontrolowanym serwerze obejmują sukces, błąd modelu, niepoprawną odpowiedź, raport i brak działań ubocznych. Nie kopiuj implementacji do asercji.
- Bazowe testy pozostają zielone. Realny eval tylko jeśli dostępna jest rzeczywista Ollama/model. W innym przypadku pozostaw „jakość niesprawdzona” i przejdź dalej.

## R02 — ustawienia i źródła pamięci osobistej (ograniczony zakres dostarczony)

Aktualizacja 0.8.2: atomowa automatyczna ekstrakcja zamkniętych deklaracji pl-declarations-v1, źródło sesji/tury, blokada per wiadomość, deduplikacja, jawne zastąpienie i ochrona ręcznych korekt. Migracja 8→9. Szczegóły: PAMIEC-AUTOMATYCZNA.md. Swobodna ekstrakcja i ogólna semantyczna walidacja prywatności pozostają przyszłym rozszerzeniem; nie są deklarowane jako gotowe. Poniżej poprzedni etap i pełne wymagania.

W 0.8.1 wdrożono osobną politykę, panel, źródła, historię korekt, rewizje, blokadę zapisu i jawną retencję; migracja 7→8 z backupem i testem. Szczegóły: PAMIEC-POLITYKA.md. Ten historyczny krok rozszerzono w 0.8.2 o zamkniętą ekstrakcję opisaną powyżej; domyślny tryb nadal manual.

Oddziel politykę pamięci od settings modelu i recepcji. Panel: auto/manual, kategorie, retencja, źródła, poprawianie/usuwanie, „nie pamiętaj”. Migracja zachowuje stare notatki jako manualne. Najpierw źródła i polityka, dopiero potem ograniczona ekstrakcja. Sekrety, dane płatnicze i dane klientów wykluczone. Ochrona przed duplikatami i fałszywym nadpisaniem; korekty mają historię/źródło. Testy obejmują blokadę zapisu, restart, usunięcie, stare dane, błędną ekstrakcję i izolację recepcji.

## R03 — sesja audio bez wake-word (kod półdupleksowy dostarczony)

Aktualizacja 0.8.3: AudioWorklet/PCM, heurystyka energii, Wyoming STT→domyślny review→osobna sesja voice→TTS; powrót do słuchania, anulowanie i przerwanie przyciskiem. Chromium z syntetycznym mikrofonem/usługami przeszedł dwie tury i komendę końca, zamykając wszystkie zasoby. 229 testów Python. Szczegóły: ROZMOWA-GLOSOWA.md. Rzeczywiste modele, sprzęt, hałas, wake-word, pełny dupleks i prywatne wyjście pozostają oczekujące; nie blokują laboratoryjnego R04. Poniżej wcześniejszy etap i pełne wymagania.

Historyczny etap 0.8.2: dostarczono warstwę stanów z zegarem, API właściciela i kontroler mikrofonu z testami zasobów. Dopiero 0.8.3 połączyło ręczny przepływ rozmowy opisany powyżej. Szczegóły: SESJE-AUDIO.md. Następny krok: segmentacja, automatyczna aktywność mowy i połączenie mikrofon→STT→czat→TTS. Testy sprzętu/przeglądarki oczekują.

Warstwa sesji: idle/listening/processing/speaking, ręczna aktywacja, zakończenie/anulowanie, regulowana cisza30s i przerwanie wypowiedzi. Testy zegara i izolacji sesji. Mikrofon przeglądarki ma działać tylko po aktywacji i zwalniać zasoby. Nie udawaj testu hardware przy fixture. Wake-word dopiero po ocenie licencji modelu oraz projektu lokalnego nasłuchu. Docelowo satelity dom/warsztat i prywatne wyjście, bez ujawniania finansów klientom.

## R04 — kontrakt transportu telefonii (laboratorium dostarczone)

Aktualizacja 0.8.4: trwała kolejka komend i zdarzeń, osobne tokeny/projekcje klienta i właściciela, zegar serwera, limity i jednorazowa akceptacja z ponowną oceną polityki, atomowość z recepcją oraz panel. Komendy są dostarczane ręcznie; terminy rozliczane przy odczycie/zdarzeniu, bez workera. Zamknięte frazy testowe zamiast ogólnego rozumienia rozmowy. 276 testów Python, 6 testów panelu i rzeczywisty Chromium na syntetycznych danych, także szerokość 390 px. Szczegóły: TRANSPORT-TELEFONII.md. PSTN/SIP, telefoniczne audio i realny adapter pozostają niezaimplementowane. Poniżej wymagania etapu.

Interfejs adaptera, oddzielne kanały klient/właściciel, idempotentne eventy, oczekiwanie, prywatny briefing, akceptacja, timeout i limity prób/kosztów. Najpierw transport laboratoryjny i pełne testy. Nie udostępniaj właścicielskiego obiektu recepcji klientowi. Rzeczywisty operator, zakup numeru, Play i transfer wymagają kont/konfiguracji i osobnego uruchomienia. Szkic adaptera nie jest działającym połączeniem.

## R05 — MQTT/ESP32/n8n i powiadomienia (następne)

Najpierw odczyt czujników i laboratorium brokera, rozróżnienie świeżych/starych danych, najmniejsze zakresy i mapowanie urządzeń. Powiadomienia mają docelowo godziny, priorytety i kanały, bez ukrytej wysyłki. Dom/brama pozostają za osobnymi zgodami. n8n sprawdź naprawdę, jeśli środowisko pozwala; sam profil Compose nie dowodzi działania.

## R06 — propozycje zmian kodu

Izolowany checkout, przeglądalny patch, testy, zatwierdzenie i rollback, brak wykonania kodu z treści rozmowy. Do czasu kompletnego przepływu zachowaj propozycje jako opis. Nie scalaj ani nie wdrażaj do produkcji poza autoryzacją.

## R07 — operacje i środowy odbiór

Retencja rozmów recepcji i analiz, odtwarzanie backupów na osobnej bazie, monitoring/alerty, aktualizacje, responsywny panel/HTTPS, Windows i Docker. Jeżeli Cloud ma dostęp do GitHub CI, sprawdź wynik wykonania, nie tylko YAML. Brak dostępu do sprzętu wpisz jako oczekujące, nie jako zaliczone.

## Wspólne warunki zamknięcia etapu

Kod działa na danych syntetycznych; brak regresji, prawdziwe sprawdzenia opisane; docs/RAPORT.md i PROJECT_STATUS.json zaktualizowane. Zachowaj pełen zakres11obszarów, konta i sprzęt jako jawne zależności. Zapisz zmiany do przeglądu/commitu. Kontynuuj najbliższe niezablokowane zadanie w ramach czasu sesji, zamiast pytać o zgodę na dalsze kodowanie.

2026-10-29: ocena interfejsu HUD przez właściciela. M4+ nadal wymaga osobnego polecenia.
