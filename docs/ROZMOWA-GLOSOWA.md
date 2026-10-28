# R03 — mikrofon → STT → czat → TTS

W panelu Głos lokalny jest ręcznie uruchamiana rozmowa przez mikrofon. Po wykryciu wypowiedzi przeglądarka tworzy WAV, wysyła go do istniejącego adaptera Wyoming STT, przekazuje sprawdzony tekst do osobnej sesji czatu i odtwarza odpowiedź przez Wyoming TTS. Po odtworzeniu ponownie otwiera mikrofon, bez powtarzania hasła. Nie ma jeszcze wake-word.

## Uruchomienie

Potrzebne są: Core na Python 3.12, przeglądarka obsługująca AudioWorklet/getUserMedia i bezpieczny kontekst (localhost lub HTTPS). Ustaw JARVIS_VOICE_ENABLED=true oraz rzeczywiste WYOMING_STT_URI i WYOMING_TTS_URI; oba serwisy muszą być dostępne w dozwolonej lokalnej/prywatnej sieci. Używane są dotychczasowe ograniczenia DNS/IP, formatu audio i długości. Kod nie instaluje silników ani modeli. Do odpowiedzi AI potrzebna jest skonfigurowana Ollama i model na allowliście; model DEMO daje jawną odpowiedź testową. Wybór modelu respektuje dotychczasową politykę Ollamy, w tym jawne zezwolenie na modele :cloud.

1. Połącz się kluczem właściciela, otwórz Głos lokalny i wybierz model.
2. Pozostaw domyślne „Sprawdzaj tekst przed wysłaniem”. Dobierz czas ciszy i próg głośności.
3. Kliknij Rozpocznij rozmowę głosową i zezwól na mikrofon.
4. Wypowiedz zdanie, a następnie zrób krótką pauzę. Po STT sprawdź/popraw tekst i wybierz Wyślij tekst albo Pomiń wypowiedź.
5. Po odpowiedzi sesja wraca do słuchania. Przerwij odpowiedź przyciskiem lub zakończ sesję.

Wyłączenie sprawdzania tekstu jest osobnym trybem eksperymentalnym: kolejne transkrypcje są automatycznie wysyłane po ręcznym uruchomieniu. Ustawienie jest zamrożone na czas aktywnej sesji. STT nadal może się mylić; review_required w odpowiedzi adaptera nie jest dowodem jakości. Domyślny tryb wymaga przeglądu każdej wypowiedzi.

Zakończenie rozpoznanymi słowami: „koniec rozmowy”, „zakończ rozmowę”, „stop Jarvis”, również bez polskich znaków. Musi to być cała wypowiedź. Skrót jest sprawdzany przed czatem, a także po ręcznej korekcie transkrypcji. Podczas czekania/odtwarzania zawsze działają przyciski zakończenia i anulowania.

## Nagrywanie, granice i zasoby

AudioWorklet odbiera próbki dopiero z ręcznie aktywowanego strumienia. Kod miesza kanały do mono, przelicza częstotliwość próbkowania do 16 kHz i koduje PCM16 WAV. Resampler stosuje prosty filtr uśredniający, nie jest rozwiązaniem studyjnym. Worklet ma ograniczone bufory i potwierdzenia odbioru; przeciążenie kończy sesję zamiast pomijać fragmenty nagrania i transkrybować niepełne dane.

Podział wypowiedzi jest heurystyką RMS: próg domyślnie0.015, co najmniej160 ms aktywnego dźwięku, koniec po700 ms poniżej progu, do 20 s na fragment i200 ms wcześniejszego dźwięku w buforze. Twardy limit kodera30 s mieści się w wymaganiach adaptera WAV. Ciągły hałas maszyn może zostać uznany za mowę; nie ma modelu odróżniającego głos od otoczenia. Próg można regulować w panelu.

Domyślny koniec po30 s ciszy, regulacja w panelu5–300s. Zakres1–4s w API jest przeznaczony do laboratorium, nie do rozmowy przez sieć. Aktywność ma ograniczoną częstotliwość, bez kolejki żądań. Przed przejściem do processing kończy się oczekujący heartbeat. Jedna wypowiedź jest przetwarzana naraz; nie buforujemy kolejnych wypowiedzi podczas modelu lub TTS. Osiągnięcie limitu20 s wysyła ten fragment i zamyka mikrofon na czas przetwarzania; dalsza część nieprzerwanej wypowiedzi nie jest wtedy nagrywana.

Mikrofon i graf audio są zamykane podczas przetwarzania i odtwarzania; wracają w listening. Chroni to przed nagrywaniem własnej odpowiedzi, ale oznacza brak głosowego przerywania podczas speaking. Przerwanie przyciskiem zatrzymuje playback i ponownie otwiera mikrofon. Nie ma jeszcze pełnodupleksowej redukcji echa, satelitów dom/warsztat ani kierowania na prywatny głośnik.

Zegar klienta i serwera nadal ogranicza ciszę, fazy i całe15 min aktywacji. Wspólny budżet rozpoznawanie→przegląd→czat→synteza wynosi do 110 s, poniżej120 s fazy serwera. Odtwarzanie ma osobny limit do 110 s. Oczekiwanie na konfigurację mikrofonu/AudioWorklet jest ograniczone. Odpowiedź tekstowa pozostaje pełna; TTS odczytuje najwyżej1000 znaków i panel jawnie sygnalizuje skrót.

Anulowanie, nawigacja, wylogowanie i pagehide zwalniają tracki, kontekst, bufory, timery i URL nagrania. Oczekujące operacje dostają abort; spóźnione wyniki i callbacki poprzedniego capture nie mogą wznowić sesji. Przerwane żądania nie są automatycznie ponawiane. Timer JavaScript nie gwarantuje twardego terminu w całkowicie zawieszonej przeglądarce. Audio autoplay lub AudioContext może wymagać dodatkowej zgody przeglądarki; błąd kończy sesję.

## Tekst, prywatność i uprawnienia

Klucz właściciela uwierzytelnia API. Sam dźwięk, tekst „Jarvis” ani identyfikator sesji nie uwierzytelniają osoby. Transkrypcja ma input_mode=voice i do_not_remember=true. Backend niezależnie wymusza:

- Brak parsera zmian ustawień, przypomnień i jawnego „zapamiętaj”.
- Brak automatycznego zapisu pamięci nawet po zmianie flag klienta.
- Brak dołączania osobistych notatek i podsumowania warsztatu do kontekstu głosowego.
- Oddzielną, trwałą historię voice, której nie można połączyć z historią text przez podmianę input_mode. Tokeny usług nie mają dostępu.

Migracja schematu 9→10 tworzy kopię before-schema10-*.sqlite3. Dotychczasowe rozmowy zachowują dane i są oznaczone text. Nowe sesje mają trwały tryb text/voice; metadata usuwają się z sesją. Rozmowę voice można obejrzeć w panelu Rozmowa i kontynuować wpisanym tekstem w tym samym ograniczonym trybie. Aby użyć parsera tekstowego, utwórz nową sesję text.

Surowe audio jest przetwarzane w ograniczonych buforach i przekazywane skonfigurowanym usługom STT/TTS; Core nie zapisuje plików audio. Tekst zaakceptowany lub wysłany w trybie automatycznym trafia do zwykłej historii czatu. Pominięta transkrypcja pozostaje tylko w bieżącym panelu. Zamykanie fetch nie cofa tury już otrzymanej lub zapisanej na serwerze. Zasady przechowywania danych w zewnętrznych silnikach zależą od ich osobnej konfiguracji.

## Dowody i pozostałe sprawdzenia

Testy deterministyczne obejmują kodowanie i resampling, podział mowy/ciszy, limity, backpressure, zamknięcie i opóźnione uruchomienie grafu; przepływ wielu tur, ręczny przegląd, przerwanie i anulowanie każdej fazy, brak powtórek i izolację sesji; blokadę parserów/pamięci i migrację10. Osobny test generuje WAV w JavaScript i przepuszcza dwie tury przez rzeczywiste lokalne transporty Core/HTTP/Wyoming z kontrolowanymi odpowiedziami. To nie jest inferencja.

Opcjonalne sprawdzenie Chromium z Playwright i syntetycznym mikrofonem: node scripts/check_voice_browser.cjs. Wymaga zainstalowanego Playwright i przeglądarki; skrypt nie przedstawia braku przeglądarki jako zaliczenia. Test fizycznego mikrofonu, głośnika, hałasu, modelu STT/AI/TTS, Windows i telefonów pozostaje odbiorem na docelowym sprzęcie.

Wykonany test Chromium: dwa zaakceptowane teksty (pierwszy poprawiony), dwie odpowiedzi i trzeci rozpoznany skrót kończący. Wszystkie 3 tracki były ended i wszystkie 3 AudioContext closed. Bez błędów strony/konsoli. To dowód działania przeglądarkowej ścieżki z syntetycznymi usługami, nie ocena rozpoznawania naturalnej mowy lub inferencji modelu.
