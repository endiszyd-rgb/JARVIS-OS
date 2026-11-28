## 0.19.0 — pytania bez rąk: „Hej Siri, Jarvis” i odpowiedzi z internetu (2026-11-28)

- **Darmowy dostawca Groq (domyślny)**: *Dostawca AI* → „Groq — darmowy” (`groq/compound` z wbudowanym wyszukiwaniem i źródłami, albo Compound Mini; klucz `gsk_…` z console.groq.com bez karty, maskowany) albo „Claude — płatny, dokładniejszy”. Oba klucze można zapisać i przełączać; po wyczerpaniu darmowego limitu Groq JARVIS mówi o tym zamiast odpowiedzi (bez opłat). Konfiguracja z kluczem Claude zapisana wcześniej zostaje przy Claude.

- **`POST /api/v1/voice/ask`** — jedno pytanie głosem, jedna odpowiedź do przeczytania (`speech`, `sources`, `kind`). „Brama”, „otwórz/zamknij bramę”, „tak/nie” obsługuje lokalny parser jak dotąd (nigdy model); każde inne pytanie idzie do **Claude API z wyszukiwarką** (`jarvis/web_answer.py`, narzędzie `web_search_20250305`): krótka polska odpowiedź z wartością, jednostką, warunkami i nazwą źródła, linki źródeł w odpowiedzi, przyznanie się do rozbieżnych danych, dopytanie o model/silnik. Pamięć 3 ostatnich pytań z urządzenia przez 15 min („a dla Passata?”). Błędy wracają jako zdanie (HTTP 200), limit 15 pytań/min na urządzenie.
- **Ustawienia → Głos → Odpowiedzi z internetu**: włącznik, klucz Claude API (`sk-ant-…`, maskowany jak inne sekrety), model (Sonnet zalecany / Haiku / Opus), liczba wyszukiwań na pytanie, **pytanie testowe** z linkami do źródeł.
- **Moje konto → Telefon i Siri**: klucze telefonu (`identity_device_keys`, schemat **15** z kopią zapasową przed migracją) — tylko dla kont z 2FA, tworzone z sesji z kodem 2FA, pokazane raz (z adresem i instrukcją skrótu), SHA-256 w bazie, zakres wyłącznie pytania + brama (także dla właściciela), przez tunel tylko `/voice/ask` i `/devices/gate/command`; usuwane ręcznie oraz automatycznie przy resecie/wyłączeniu 2FA.
- Instrukcja krok po kroku ze skrótem iOS (Dyktuj tekst → Pobierz zawartość URL → Wartość słownika → Mów tekst): `docs/PYTANIA-BEZ-RAK.md`; decyzja: `docs/DECISIONS.md`.

Wykonane kontrole: `.venv/bin/python -m pytest -q` **1048 PASS / 76 skip** (nowe `tests/test_voice_ask.py`: Groq domyślny, odpowiedź Groq ze źródłami z `executed_tools`, limit i zły klucz Groq jako mowa, przełączanie dostawców z zachowaniem obu kluczy, stara konfiguracja przy Claude, maskowanie i walidacja klucza, odpowiedź z wyszukiwarki ze źródłami i kontekstem, wypowiadane błędy, kontynuacja `pause_turn`, klucz telefonu przez tunel tylko dla pytań i bramy, brak obejścia uprawnień właściciela, brak tokenu w bazie, odwołanie, wymóg 2FA i unieważnienie przy resecie 2FA, operator, migracja schematu 14→15 z kopią — API Groq i Anthropic zastąpione atrapami), `pip check` PASS, `node --check jarvis/app.js` PASS, vitest **189 PASS** (nowe: wybór dostawcy z Groq domyślnie, ukryte klucze, pytanie testowe, telefon i Siri), typecheck/build PASS; Chrome 390/1280 px: sekcja „Odpowiedzi z internetu”, 0 błędów konsoli.

Ograniczenia: **nie sprawdzone z prawdziwym kluczem Groq/Claude ani na iPhonie z Siri** (atrapy API). Groq (otwarte modele) bywa mniej precyzyjny niż Claude przy danych technicznych. Odpowiedzi to dane z internetu, nie dokumentacja producenta — przy ważnych połączeniach trzeba sprawdzić wartość. Klucz Claude jest płatny za użycie (limit ustawia się w console.anthropic.com); Groq ma dzienne limity darmowego planu. Skrót iOS trzeba złożyć ręcznie (Skróty nie importują niepodpisanych plików). Wpis zakresu w `AGENTS.md` zostawiony właścicielowi.

## 0.18.0 — kamery bez ręcznej konfiguracji: wbudowany go2rtc (2026-11-28)

- **go2rtc i FFmpeg w instalatorze** (`tools\go2rtc.exe` v1.9.14, MIT; `tools\ffmpeg.exe` — build LGPL z BtbN). Pobierane w CI z wydań GitHub i sprawdzane z SHA-256 podanym przez GitHub; wersje i sumy w `tools\THIRD-PARTY.txt` (`scripts/build_windows_installer.py`, workflow *Windows installer*).
- **JARVIS sam uruchamia go2rtc** (`jarvis/go2rtc.py`, `Manager`): proces w tle tylko na `127.0.0.1:1984`, bez serwera RTSP, konfiguracja `dane\go2rtc\go2rtc.yaml` generowana z kamer w panelu (jako JSON — bez możliwości wstrzyknięcia opcji), restart tylko przy zmianie, zatrzymanie przy zamknięciu JARVIS. Zmiana danych chmury Tuya w ustawieniach bramy też odświeża kamery. Launcher podaje ścieżki narzędzi (`JARVIS_GO2RTC_BIN`, `JARVIS_FFMPEG_BIN`).
- **Ustawienia → Kamery, nowy formularz**: *Dodaj kamerę* → rodzaj **Setti / Tuya (Device ID)** albo **Kamera IP / rejestrator (RTSP)**. Przy Setti przycisk **Sprawdź kamerę** pobiera z projektu Tuya (tego samego co brama) nazwę, stan online i UID właściciela (`POST /api/v1/cameras/tuya-info`, tylko właściciel). Adres RTSP z hasłem jest po zapisie ukryty („zapisany ✓”), tak jak sekrety bramy. Nad listą stan: „go2rtc działa” / czego brakuje. Opcja „Wysoka jakość (HD)”; „Więcej opcji”: odświeżanie i **własny go2rtc** (tryb jak przed 0.18.0 — istniejące konfiguracje zostają w nim).
- API: `GET/PUT /api/v1/cameras/config` zwraca `builtin` (`available`, `running`, `ffmpeg`, `problems`, `error`) i zamaskowane RTSP; konfiguracja kamery ma `mode` (`builtin`/`external`) i `source` (`tuya`/`rtsp`/`go2rtc`).
- Instrukcja: `docs/DOSTEP-ZDALNY.md` → „Kamery”; decyzja: `docs/DECISIONS.md`; budowanie: `docs/WINDOWS-INSTALLER.md`.

Wykonane kontrole: `.venv/bin/python -m pytest -q` **1034 PASS / 76 skip** (nowe `tests/test_cameras_builtin.py`: źródła Tuya/RTSP w wygenerowanym pliku, tylko 127.0.0.1, odrzucanie złych adresów, start/brak restartu/restart/stop procesu, brak go2rtc, API bez wycieku haseł, zapis maski, ramka z `src=<id>`, UID z chmury i odświeżenie po zmianie sekretu Tuya — proces go2rtc i chmura zastąpione atrapami; launcher: wykrywanie `tools`), `pip check` PASS, `node --check jarvis/app.js` PASS, vitest **186 PASS** (nowe: dodanie kamery Setti z „Sprawdź kamerę”, ukryty RTSP, komunikat o braku go2rtc), typecheck/build PASS; Chrome 390 px i 1280 px: formularz kamer (Setti z Device ID, RTSP, stan go2rtc), 0 błędów konsoli.

Ograniczenia: **prawdziwy go2rtc nie był uruchamiany w tej sesji** (środowisko nie pozwala uruchamiać pobranych programów) — sprawdzają go dopiero kroki CI na Windows (`-version` i informacyjny test RTSP → JPEG). Kamery Setti z prawdziwym sprzętem niesprawdzone; wymagają aktywnego IoT Core (obraz idzie przez chmurę Tuya). Instalator jest większy o go2rtc i FFmpeg. Gdy JARVIS zostanie zabity bez zamknięcia, go2rtc może zostać w tle do ponownego uruchomienia (instalator zamyka go przy aktualizacji).

## 0.17.0 — jeden przycisk „Brama” i „Jarvis, brama” (2026-11-27)

- **Jeden przycisk „Brama” zamiast Otwórz / Zamknij / Stop** dla sterowników impulsowych (Setti): każde naciśnięcie działa jak pilot — otwiera, zatrzymuje albo zamyka. Powód: u właściciela przyciski Otwórz i Zamknij działały na przemian, a bramę można zatrzymać w połowie, więc osobne przyciski wprowadzały w błąd. Włączenie: *Ustawienia → Brama* → **„Jeden przycisk „Brama” (jak pilot)”** (pole przeniesione na wierzch formularza, z podpowiedzią „?”) i **Sygnał przycisku Brama** (Włącz / Wyłącz) przy sterowniku Setti/Tuya.
- **Komenda głosowa „Jarvis, brama”** (też „rusz bramę”, „uruchom bramę”, „brama proszę”). Przy bramie jednoprzyciskowej „otwórz bramę” i „zamknij bramę” też wysyłają ten sam impuls. Przy bramie z osobnymi przyciskami „Jarvis, brama” wybiera następny ruch (otwarta → zamknij, inaczej → otwórz). Zdania typu „brama jest zepsuta” nie są poleceniem.
- Nowa akcja API `toggle` (`POST /api/v1/devices/gate/command`), stan `impulse` wyświetlany jako „ruszona” (po czasie ruchu wraca do „nieznany”, bo kierunek zna tylko czujnik krańcowy), potwierdzenie „Uruchomić bramę?”. Kafelek bramy na ekranie *Warsztat* i szybki przycisk w *Głos* też mają jeden przycisk „Brama”.

Także w tej wersji (przygotowane wcześniej jako 0.16.1, nie wydane osobno):

- Przy sterownikach *Setti / Tuya lokalnie* i *Setti / Tuya przez chmurę* jest nowe pole **„Jeden przycisk w sterowniku: „Otwórz” wysyła ten sam sygnał co „Zamknij””**. Po zaznaczeniu przycisk Otwórz (i komenda głosowa „otwórz bramę”) wysyła dokładnie ten sam sygnał (ta sama funkcja i wartość) co Zamknij. Powód: u właściciela przy bramie Setti działał tylko przycisk Zamknij (raz otwierał, raz zamykał), a Otwórz nic nie robił. Odznaczenie przywraca Otwórz = Włącz, Zamknij = Wyłącz.
- **Mikrofon w oknie programu**: skrót „JARVIS OS” przed otwarciem okna zapisuje w jego osobnym profilu (`dane\desktop-window`) zgodę na mikrofon tylko dla adresu JARVIS (`http://localhost:<port>`). Wcześniejsze „Blokuj” dla tego adresu zostaje zastąpione „Zezwalaj”; inne strony i zwykła przeglądarka bez zmian (`scripts/windows_launcher.py`, `allow_microphone`). Sprawdzone w Chrome: profil z tym wpisem → `navigator.permissions` = `granted`, czysty profil → `prompt`.
- W *Więcej opcji* można osobno wybrać **sygnał przycisku Otwórz / Zamknij** (Włącz / Wyłącz); inne wartości ustawione wcześniej są zachowane i pokazane jako „Inna wartość”.
- Instrukcja: `docs/BRAMA-I-GLOS.md`. Wartości otwarcia/zamknięcia były już w konfiguracji backendu; test sprawdza, że przy tym ustawieniu oba przyciski wysyłają `false` na DP 1.

Wykonane kontrole (cała wersja 0.17.0): `.venv/bin/python -m pytest -q` **1023 PASS / 76 skip** (nowe w `tests/test_gate_tuya_local.py`: jeden przycisk i impuls przez API, „Jarvis, brama” przez rozmowę głosową, następny ruch przy bramie dwuprzyciskowej, potwierdzenie „Uruchomić bramę?”, frazy komend; zgoda na mikrofon w `tests/test_windows_launcher.py`), `pip check` PASS, `node --check jarvis/app.js` PASS, vitest 184 PASS (nowe: przycisk Brama w widoku i kafelku, ustawienie jednego przycisku), typecheck/build PASS; Chrome 390 px (widok Brama) i 1280 px (Warsztat): jeden przycisk „Brama”, stan po naciśnięciu, 0 błędów konsoli poza oczekiwanymi 503 (AutoLogika nieskonfigurowana) i 429 (drugie naciśnięcie w czasie przerwy między poleceniami).

Ograniczenia: zgoda na mikrofon działa po zamknięciu i ponownym otwarciu okna programu (otwarty profil przeglądarka nadpisuje przy zamknięciu); w Edge na Windows nie sprawdzono w tej sesji. Mikrofon musi być też dozwolony w Windows (Ustawienia → Prywatność → Mikrofon → aplikacje klasyczne). JARVIS nie wie, w którą stronę ruszy brama przy sterowniku jednoprzyciskowym — stan „otwiera się / zamyka się” to tylko ostatni naciśnięty przycisk, dopóki sterownik nie ma czujnika krańcowego (pole „Numer funkcji stanu”).

## 0.16.0 — brama Setti/Tuya w sieci warsztatu, bez chmury (2026-11-27)

- **Nowy sterownik „Setti / Tuya lokalnie, bez chmury (zalecane)”** (`jarvis/gate.py`, `TuyaLocal`, biblioteka `tinytuya==1.21.1`): JARVIS łączy się ze sterownikiem bramy bezpośrednio przez Wi‑Fi warsztatu (TCP 6668, szyfrowanie kluczem lokalnym urządzenia). Brama działa bez internetu i nie przestaje działać, gdy wygaśnie okres próbny IoT Core albo Tuya wstrzyma centrum danych. Wersja protokołu „Automatycznie” próbuje 3.3 → 3.4 → 3.5 → 3.1 i zapamiętuje działającą; numery funkcji (DP) otwarcia/zamknięcia/stopu/czujnika w „Więcej opcji” (domyślnie 1 = `switch_1`).
- **„Znajdź w sieci”** (`POST /api/v1/devices/gate/tuya-local/scan`, tylko właściciel): ok. 8 s nasłuchu komunikatów Tuya w sieci lokalnej, lista adres IP · ID urządzenia · wersja; kliknięcie wpisuje dane, a przy urządzeniu z projektu chmury pojawia się „to Twoja brama”. Skan tylko słucha (nie łączy się z urządzeniami).
- **„Pobierz klucz z chmury Tuya”** (`POST /api/v1/devices/gate/tuya-local/key`, tylko właściciel): jednorazowo odczytuje klucz lokalny przez zapisany wcześniej projekt chmury (Access ID/Secret). Potem chmura nie jest już potrzebna.
- Dozwolone są tylko adresy prywatne (192.168.x.x, 10.x.x.x, 172.16–31.x.x); adresy publiczne, loopback, link-local i nazwy hostów są odrzucane (422). Klucz lokalny jest maskowany jak inne sekrety (decyzja w `docs/DECISIONS.md`).
- **Zapisany sekret nie wygląda już na „ucięty”**: pola Access Secret / klucz lokalny / hasło / token po zapisie są puste z napisem „zapisany ✓ — wpisz nowy tylko, aby zmienić” zamiast 8 kropek.
- **Błędy Tuya po polsku z kolejnym krokiem** zamiast „Nie udało się wykonać żądania”: np. `28841107` → jak przywrócić centrum danych Central Europe, `28841101` → Extend Trial Period, `1004` → zły Access Secret, `914` (lokalnie) → zły klucz lokalny albo wersja protokołu, brak odpowiedzi → sprawdź adres IP.
- Instrukcja krok po kroku: `docs/BRAMA-I-GLOS.md` → „Setti / Tuya w sieci warsztatu — bez chmury”.

Wykonane kontrole: `.venv/bin/python -m pytest -q` **1008 PASS / 76 skip** (nowy `tests/test_gate_tuya_local.py` 14: tylko adresy LAN, auto‑wersja i zapamiętanie protokołu, podpowiedź przy złym kluczu, brama impulsowa, czujnik stanu, maskowanie klucza przez API, polecenie i test przez API, skan odrzuca adresy publiczne i złe ID, pobranie klucza z chmury i 409 bez danych chmury — urządzenie Tuya i chmura zastąpione atrapami); `pip check` PASS; `node --check jarvis/app.js` PASS; vitest **181 PASS** (nowe: przepływ „Znajdź w sieci → Pobierz klucz → Zapisz” bez pokazywania klucza, tłumaczenie błędów Tuya), typecheck/build PASS; Chrome 1280 px i 390 px: formularz, podpowiedź „?” przy kluczu lokalnym, 0 błędów konsoli.

Ograniczenia: **prawdziwy sterownik Setti nie był testowany** (brak sprzętu w sesji) — numery DP i wersja protokołu mogą wymagać korekty przy bramie. Skan LAN wymaga, by komputer z JARVIS był w tej samej sieci co sterownik; zapora Windows może zapytać o zgodę dla Pythona (UDP 6666/6667). Pobranie klucza wymaga jednorazowo aktywnego IoT Core w projekcie Tuya. Klucz lokalny zmienia się po ponownym dodaniu urządzenia w aplikacji.

## 0.15.0 — program desktopowy obok strony (2026-11-26)

- **JARVIS otwiera się jak zwykły program**: po uruchomieniu skrótu „JARVIS OS” panel pokazuje się w osobnym oknie aplikacji — bez paska adresu i kart, z własną ikoną na pasku zadań, od razu na ekranie *Warsztat*. Pod spodem to Microsoft Edge (albo Chrome) w trybie aplikacji z osobnym profilem (`dane\desktop-window`); dzięki temu w oknie działają mikrofon, rozpoznawanie mowy i Windows Hello (wbudowany WebView2 nie obsługuje rozpoznawania mowy). Gdy na komputerze nie ma Edge ani Chrome — otwiera się zwykła przeglądarka.
- **Strona działa równolegle** z tego samego serwera: w przeglądarce na tym komputerze (`http://localhost:17321/control/`, nowy skrót „JARVIS OS w przeglądarce” w menu Start) i na telefonie przez tunel. Zamknięcie okna programu nie wyłącza JARVIS; serwer zatrzymuje dopiero okno „JARVIS OS — serwer”.
- **Ponowne kliknięcie skrótu**, gdy JARVIS już działa, otwiera kolejne okno programu zamiast komunikatu „już uruchomiony”.
- **Autostart (opcja w instalatorze, domyślnie wyłączona)**: „Uruchamiaj JARVIS razem z Windows” — serwer startuje po zalogowaniu do Windows w tle (`--minimized`), więc brama, telefon i Face ID działają bez otwierania programu.
- Okno programu używa adresu `localhost` (nie `127.0.0.1`), więc logowanie Face ID / Windows Hello działa także w programie. Klucza ani haseł nie ma w poleceniu uruchomienia.

Wykonane kontrole: `tests/test_windows_launcher.py` 8 PASS lokalnie (wybór Edge → Chrome → przeglądarka, polecenie bez sekretów z `localhost`, ponowne użycie portu) + test tylko na Windows, który na runnerze CI sprawdza, że Edge/Chrome zostaje znaleziony; `scripts/check_windows_installer.py` przestawiony na okno programu. Interfejs bez zmian.

Ograniczenia: okno programu **nie było otwierane na prawdziwym pulpicie Windows** w tej sesji (CI sprawdza tylko instalację, serwer i znalezienie Edge). Okno programu ma osobny profil przeglądarki — przy pierwszym uruchomieniu trzeba zalogować się raz (najlepiej z „Zapamiętaj klucz na tym komputerze” albo przez Windows Hello).

## 0.14.2 — wszystkie ustawienia w jednym miejscu, podpowiedzi „?” (2026-11-26)

- **Zaawansowane → Ustawienia** ma teraz zakładki: *Brama*, *AutoLogika*, *Kamery*, *Głos*, *Asystent AI*. Konfiguracja zniknęła z widoków codziennych (Brama, Głos, Kamery, AutoLogika) — tam zostały tylko przyciski i podgląd oraz link „Ustawienia → …”. Adresy `#/settings/gate`, `#/settings/autologika`, `#/settings/cameras`, `#/settings/voice`, `#/settings/assistant` otwierają od razu właściwą zakładkę. *Bezpieczeństwo* (konta, tokeny, sesje) przeniesione do grupy *Zaawansowane*, zaraz pod *Ustawienia*.
- **Uproszczone formularze**: na wierzchu tylko to, co trzeba wpisać; reszta w zwijanym „Więcej opcji” / „Zachowanie bramy”. Brama: sterownik *Setti / Tuya* na pierwszym miejscu, prostsze nazwy (np. „Adres otwarcia”, „ID urządzenia”, „Pytaj „czy na pewno?” przed ruchem bramy”); kody Tuya, impuls, przerwa i czas ruchu schowane. Głos: słowo aktywujące, język, czytanie odpowiedzi; silnik i reszta w „Więcej opcji”.
- **Znak „?” przy każdym polu** (`frontend/src/components/HelpTip.tsx`): podpowiedź po najechaniu myszką, po przejściu klawiszem Tab albo po dotknięciu na telefonie; zawsze mieści się na ekranie; Esc ją zamyka. Podpowiedzi mówią, skąd wziąć wartość (np. Access ID z iot.tuya.com, PIN z AutoLogiki, nazwa strumienia z go2rtc).

Wykonane kontrole: **179 testów UI PASS** (nowe: zakładki i link do zakładki, podpowiedź „?” z rolą tooltip, brak konfiguracji w widoku Brama; testy formularzy przeniesione do nowych komponentów), typecheck/build PASS. Chrome 1280 px i 390 px: zakładki, Setti/Tuya → najechanie / dotknięcie „?” przy Access ID pokazuje podpowiedź w granicach ekranu, zakładka Kamery, 0 błędów konsoli. Backend bez zmian poza numerem wersji.

## 0.14.1 — porządki w interfejsie i kamery Setti (2026-11-26)

- **Menu w trzech grupach** zamiast 21 pozycji jedna pod drugą: *Na co dzień* (Warsztat, Brama, Kamery, Głos, AutoLogika, Rozmowa), *Konto* (Moje konto, Bezpieczeństwo) i zwinięte *Zaawansowane* (Pulpit, System, Ustawienia, Pamięć, Dom, Urządzenia, Automatyzacje, Powiadomienia, Telefonia, Pluginy, Zmiany, Historia działań). Grupa zaawansowana rozwija się sama, gdy otwarty jest jej widok. Usunięto zdublowaną pozycję „Logi” (ta sama historia co „Historia działań”; adres `#/logs` nadal działa).
- **Właściciel po zalogowaniu trafia na ekran „Warsztat”** (jak operator); pozostałe role — na Pulpit. Aplikacja z ekranu głównego telefonu (PWA) też otwiera Warsztat; skrót „Warsztat” w menu ikony.
- **Kamery Setti (Tuya)**: instrukcja w `docs/DOSTEP-ZDALNY.md` — go2rtc ≥ 1.9.13 ma źródło `tuya` (Tuya Smart API lub Tuya Cloud API z tym samym projektem co sterownik bramy); JARVIS bez zmian w kodzie pobiera klatki przez go2rtc.

Wykonane kontrole: **176 testów UI PASS** (nowy test grup menu; pomocnik logowania kluczem przechodzi teraz z Warsztatu na Pulpit), typecheck/build PASS; Chrome 1280 px i 390 px (menu mobilne): grupy, zwinięte Zaawansowane, przejście do Pulpitu, 0 błędów konsoli. Backend bez zmian poza numerem wersji (990 pytest PASS w 0.14.0).

Ograniczenia: kamery Setti przez go2rtc/Tuya **nie testowane** (brak sprzętu i konta); podgląd klatek z kamer Tuya wymaga ffmpeg obok go2rtc (dekodowanie WebRTC → JPEG).

## 0.14.0 — logowanie Face ID / Touch ID (passkeys) i ekran „Warsztat” (2026-11-26)

Na iPhonie sesja znika po zamknięciu aplikacji, więc logowanie hasłem i kodem 2FA za każdym razem było uciążliwe. Teraz:

- **„Zaloguj przez Face ID / klucz dostępu”** na ekranie logowania (na telefonie na samej górze). Klucz dostępu (passkey, WebAuthn) z weryfikacją użytkownika (Face ID, Touch ID, Windows Hello, PIN urządzenia) otwiera sesję liczoną jako dwuskładnikowa — działa też przez tunel spoza warsztatu.
- **Moje konto → Face ID / Touch ID / Windows Hello**: *Dodaj to urządzenie*, lista urządzeń (domena, ostatnie użycie), usuwanie. Konto z 2FA może dodać klucz tylko w sesji otwartej kodem 2FA. Właścicielski *Resetuj 2FA* usuwa też klucze (zgubiony telefon).
- Backend `jarvis/passkeys.py` (biblioteka `webauthn` 3.0.1 + zależności przypięte w `requirements.lock`): wyzwania jednorazowe 2 min w pamięci, wymagane UV, licznik podpisów, klucz przypisany do domeny (rp_id) — klucz z domeny tunelu nie zadziała pod innym adresem. Dozwolone adresy: `https://<domena tunelu>`, `http://localhost:<port>`, lista `JARVIS_PASSKEY_ORIGINS`. Przeglądarki nie pozwalają na klucze pod adresem IP (`127.0.0.1`) — lokalnie użyj `http://localhost:17321`. Logowanie kluczem objęte limitem prób jak hasło.
- Schemat SQLite **14**: tabela `identity_passkeys` (kopia `backups/before-schema14-*`).
- **Ekran „Warsztat”** (pierwsza pozycja menu; operator trafia tu od razu po zalogowaniu): duży przycisk *Dotknij i mów* (jednorazowe rozpoznanie mowy, odpowiedź czytana na głos), pole do wpisania polecenia, skróty *Co dziś? / Części / Stan bramy*, przyciski *Tak/Nie* przy potwierdzeniu bramy, kafel bramy, do 4 kamer i karta „Dziś w warsztacie”. Polecenia idą przez `/api/v1/voice/command` (tylko parser, bez modelu AI).

Wykonane kontrole: **990 pytest PASS / 75 skip** (nowe `tests/test_passkeys.py` 10 z programowym uwierzytelniaczem ES256: rejestracja, logowanie, ponowne użycie wyzwania, obcy klucz, inna domena, wymagane UV, wyłączone konto, reguły 2FA, pełna ścieżka telefonu przez tunel), pip check PASS, **175 testów UI PASS** (logowanie passkey, dodawanie urządzenia, ekran Warsztat), typecheck/build PASS. Chrome 1280 px i 390 px: ekran Warsztat z harnessem AutoLogiki — „Co dziś?”, kafel bramy, karta dnia, 0 błędów konsoli. **Chrome z wirtualnym uwierzytelniaczem WebAuthn (CDP)** na prawdziwym serwerze, 390 px: logowanie hasłem → Moje konto → *Dodaj to urządzenie* → wylogowanie → *Zaloguj przez Face ID* → pulpit; licznik podpisów 2, 0 błędów konsoli.

Ograniczenia: **prawdziwy iPhone/Face ID i Windows Hello NOT_RUN** (test tylko z wirtualnym uwierzytelniaczem Chrome). Klucz trzeba dodać osobno dla każdego adresu (domena tunelu, localhost). Wyzwania w pamięci jednego procesu — restart serwera w trakcie logowania wymaga ponowienia.

## 0.13.0 — AutoLogika OS na żywo: raport dnia i części (2026-11-26)

Właściciel używa desktopowej AutoLogiki OS. Ponowny audyt repozytorium Autologika-OS (bcdc364, 21.11.2026, 201 commitów po poprzednim audycie): serwer mobilny nadal udostępnia te same trasy GET `/api/orders` i `/api/order/{id}` (PIN w `X-Autologika-Pin`, port 8787), schemat bazy 18; statusy części pochodzą z `electron/job-part-workflow.cjs` (DO_ZAMOWIENIA / ZAMOWIONE / W_DRODZE …), a zlecenie z brakującymi częściami ma `wait_state=CZESCI`.

- **Połączenie ustawiane w panelu** (widok AutoLogika → *Połączenie z AutoLogiką*): adres i PIN serwera mobilnego, PIN maskowany i zachowywany przy ponownym zapisie, przycisk *Zapisz i sprawdź połączenie*. Zmienne `.env` działają jak dotąd jako zapas.
- **„Dziś w warsztacie”** (`GET /api/v1/autologika/today`, karta w widoku AutoLogika — odczyt na żądanie): termin dziś, gotowe do odbioru, czeka na klienta, po terminie, części do zamówienia i w drodze. Maksymalnie 1 + 15 zapytań GET; JARVIS nic nie zapisuje.
- **Głos / czat**: „Jarvis, co dziś?”, „jakie są zlecenia?”, „co jest gotowe?” → raport dnia; „co trzeba zamówić?” → części na żywo (gdy AutoLogika nie odpowiada — kopia). Operator nie ma dostępu do danych warsztatu.
- **Kontrakt**: `scripts/autologika_contract_harness.cjs` uruchamia prawdziwe migracje `db.cjs` (schemat 18) i prawdziwe zapytanie `orderSelect` z repozytorium AutoLogiki na danych syntetycznych; zrzuty odpowiedzi w `tests/fixtures/autologika_bcdc364/`.

Wykonane kontrole: **980 pytest PASS / 75 skip** (nowe `tests/test_autologika_live.py` 20), pip check PASS, `node --check jarvis/app.js` PASS, **172 testy UI PASS** (TodayCard 3), typecheck/build PASS. JARVIS uruchomiony przeciw harnessowi AutoLogiki przez HTTP: zapis połączenia, test (4 otwarte zlecenia), raport dnia, głos „co dziś” i „co trzeba zamówić” PASS; Chrome 390 px: karta „Dziś w warsztacie” z danymi, 0 błędów konsoli.

Ograniczenia: **prawdziwa instalacja AutoLogiki u właściciela NOT_RUN**. Serwer mobilny AutoLogiki musi być włączony (Ustawienia → serwer mobilny); lista z API pomija wydane i ma limit 100 zleceń; terminarz (wizyty) nie jest dostępny przez HTTP AutoLogiki. Serwer mobilny AutoLogiki słucha na wszystkich interfejsach (0.0.0.0) bez HTTPS i z 6‑cyfrowym PIN-em — w sieci warsztatu zalecane ograniczenie zapory Windows do 127.0.0.1/tabletu. Brak raportu porannego o stałej godzinie (M6.2 IN_PROGRESS).

## 0.12.0 — dostęp z telefonu: 2FA, rola operatora, kamery, PWA (2026-11-26)

Właściciel chciał używać JARVIS „jak strony”: zalogować się z telefonu spoza warsztatu i mieć komendy głosowe (brama), części do zamówienia i podgląd kamer. Zamiast osobnej strony rozbudowano Control Center:

- **2FA (TOTP)** — widok **Moje konto**: kod QR dla Google/Microsoft Authenticator, Aegis, iPhone; 8 jednorazowych kodów zapasowych (tylko SHA‑256 w bazie); ochrona przed ponownym użyciem kodu; pole „Kod 2FA” przy logowaniu; właściciel może zresetować 2FA konta w **Bezpieczeństwo** (`jarvis/totp.py`, `jarvis/identity.py`, `jarvis/security_api.py`).
- **Rola `operator`** — pracownik: brama (bez konfiguracji), komendy głosowe przez `/api/v1/voice/command` (tylko parser, bez AI i pamięci), kamery. Widoki Brama/Głos/Kamery/Moje konto.
- **Dostęp zdalny przez tunel** (`jarvis/remote_access.py`, `docs/DOSTEP-ZDALNY.md`): domyślnie każde żądanie z tunelu (nagłówki Cloudflare/proxy) dostaje 403; po `JARVIS_REMOTE_ACCESS=true` zdalnie działają tylko sesje kont otwarte z kodem 2FA — klucz właściciela i tokeny usługowe wyłącznie lokalnie. Limit logowań liczony per `CF-Connecting-IP`. Instrukcja Cloudflare Tunnel i Tailscale.
- **Kamery** (`jarvis/cameras.py`, widok **Kamery**): podgląd klatek JPEG przez lokalny go2rtc (hasła kamer tylko w go2rtc.yaml), allowlista sieci, limit 4 MiB / 8 s, konfiguracja w panelu; CSP `img-src 'self' blob: data:`.
- **Części głosem**: „Jarvis, co trzeba zamówić?” / „jakie części są w drodze?” — braki poniżej stanu minimalnego i niedostarczone zamówienia z kopii AutoLogiki (czat właściciela i `/voice/command`).
- **PWA**: manifest, ikony, skróty Brama/Głos/Kamery — „Dodaj do ekranu początkowego” (bez service workera, bez trybu offline).
- Schemat SQLite **13**: przebudowa `identity_users` (nowa rola w CHECK) z zachowaniem kont i sesji, tabela `identity_mfa`, kolumna `identity_sessions.mfa`; kopia `backups/before-schema13-*`.

Wykonane kontrole: **960 pytest PASS / 75 skip** (Python 3.12; nowe `tests/test_remote_access.py` 26, `tests/test_cameras.py` 12, `tests/test_control_ui.py` +2; test serwera z nagłówkami Forwarded zaktualizowany: 403 zamiast 200, limit 429 bez zmian), pip check PASS, `node --check jarvis/app.js` PASS, **169 testów UI PASS** (nowe: AccountPanel 3, CamerasPanel 3, App 2), typecheck/build PASS. Chrome headless (Linux) na prawdziwym serwerze z `JARVIS_REMOTE_ACCESS=true` i symulowanym nagłówkiem tunelu, 390 px: klucz właściciela odrzucony z komunikatem o 2FA, logowanie operatora bez kodu → prośba o kod, z kodem → pulpit; menu operatora tylko Pulpit/System/Głos/Brama/Kamery/Moje konto; „Otwórz” w symulatorze zapisane z aktorem `session:`; widok bez konfiguracji sterownika; manifest i ikony 200; kod QR 2FA i edytor kamer renderowane; 0 błędów konsoli.

Ograniczenia: **tunel Cloudflare/Tailscale, telefon, prawdziwe kamery/go2rtc, prawdziwa brama i Windows NOT_RUN**. Części pochodzą z kopii, nie na żywo; nieznany status zamówienia liczy się jako „w drodze”. Podgląd kamer to klatki (domyślnie 1/s), nie płynne wideo. Sekret TOTP leży w lokalnej bazie SQLite — chroń plik bazy i kopie. Sesje otwarte przed włączeniem 2FA nie działają zdalnie. M8.1 IN_PROGRESS (integracja z Android AutoLogika nadal po audycie).

## 0.11.0 — brama warsztatu i komendy głosowe (2026-11-13)

Właściciel zlecił realne sterowanie bramą Wi‑Fi z aplikacji i głosem. Dodano moduł `jarvis/gate.py` ze sterownikami **symulator / HTTP (Shelly, Tasmota, ESP) / Tuya‑Smart Life (chmura) / Home Assistant**, konfigurowanymi z widoku **Brama** (sekrety maskowane, rewizja, test połączenia bez ruchu bramy). Polecenia: tylko właściciel, cooldown, opcjonalne potwierdzenie jednorazowym tokenem (12 s), dziennik `gate_events` i audyt. Parser intencji PL (`jarvis/intents.py`) rozpoznaje „Jarvis, otwórz/zamknij bramę”, „brama stop”, „stan bramy”, „tak/nie” w rozmowie i głosie — model językowy nigdy nie wykonuje urządzeń. Nowy widok **Głos**: rozpoznawanie mowy Chrome/Edge ze słowem aktywującym (bez dodatkowych serwerów) lub Wyoming „przytrzymaj i mów”; odpowiedzi czytane na głos; ustawienia głosu z aplikacji (`/api/v1/config/voice`). Pulpit ma kafelek bramy; logowanie kluczem może zostać zapamiętane na zaufanym komputerze; launcher używa stałego portu 17321 i ma skrót do sterowania głosem. Instalator: nowy workflow `windows-installer.yml` (Windows runner, runtime python-build-standalone, Inno Setup, smoke launchera, artefakt/Release), skrypt budowy bez zaszytej nazwy wersji. Plan rozwoju: [docs/PLAN-ROZWOJU.md](docs/PLAN-ROZWOJU.md); instrukcja: [docs/BRAMA-I-GLOS.md](docs/BRAMA-I-GLOS.md).

Wykonane kontrole: **920 pytest PASS / 75 skip** (115.36 s; 26 nowych `tests/test_gate.py`), pip check PASS, **161 testów UI PASS** (GatePanel 5, VoicePanel 6), typecheck/build PASS, Chrome headless: logowanie z zapamiętanym kluczem, Brama/Głos/Pulpit/390 px PASS, launcher `--smoke-test` PASS (Linux). Schemat SQLite pozostaje 12 (nowe tabele `device_config`, `gate_events` przez IF NOT EXISTS).

Ograniczenia: **prawdziwy sterownik bramy, konto Tuya, instalacja HA, mikrofon i Windows NOT_RUN** — M5.4 VERIFIED (symulator), M5.5 DONE do czasu testu właściciela przy bramie (Etap 0 planu). Tuya Cloud i rozpoznawanie mowy przeglądarki wymagają internetu; sterownik HTTP/HA musi być w `JARVIS_NETWORK_ALLOWLIST`. Workflow instalatora nie był jeszcze uruchomiony na GitHub.

## M5.1 — odczyt Home Assistant (2026-11-06)

Dodano jednorazowy WebSocket auth/get_states obok REST i jawny wybór transportu w panelu Dom. Połączenia mają pinned DNS/IP, zakaz przekierowań, deadline, limit odpowiedzi i czterech sesji. Core zwraca wyłącznie dozwolone encje i bezpieczny podzbiór pól; ponownie sprawdza uprawnienia po odczycie WS. Nie dodano sterowania ani subskrypcji.

13 testów WebSocket/API PASS na rzeczywistym lokalnym serwerze z syntetycznymi odpowiedziami;10 testów panelu PASS, TypeScript/build/pip/JS PASS. Chrome/Core:85 żądań API,9 widoków390px, jawny wybór WS, role/CSP i zero outbound PASS. Pełna regresja: 893 pytest PASS /75skip/2warnings w256.52s; po dodaniu testu odwołania tokenu osobno13test_home_ws PASS,25test_master_plan PASS. Raport: docs/evals/m51-home.json.

**M5.1 BLOCKED dla realnej integracji**: konto HA i uprawnienia jego tokenu nie zostały zweryfikowane. Lokalna allowlista nie ogranicza tokenu upstream. Sprzęt NOT_RUN.23/45 VERIFIED bez zmian. Następny niezależny etap: laboratoryjna część M5.2 MQTT/status/reconnect. Instalator HUD3 nadal zawiera wcześniejszy M3. Instrukcja: [HOME-ASSISTANT.md](docs/HOME-ASSISTANT.md).

## M4.4 — laboratorium zapisów (2026-11-06)

Panel AutoLogika właściciela zawiera jawne laboratorium DEMO: notatka, zadanie, wycena w groszach i status syntetycznego DEMO-1. Podgląd before/after nie zmienia stanu. Osobne potwierdzenie wysyła digest dokładnej propozycji; CAS odrzuca nieaktualny stan, UUID eliminuje powtórny zapis, konta są odseparowane, odwołana sesja traci dostęp. Żadna ścieżka nie wywołuje adaptera AutoLogiki ani nie modyfikuje snapshotu.

Stan i dziennik metadanych są tylko w RAM pojedynczego procesu: restart lub30min bezczynności usuwa konto laboratoryjne (lazy cleanup), propozycje15min, max32konta/64propozycje na konto/512KiB podglądów na konto/32wpisy w kolekcji. To demonstracja polityki zapisów, nie trwały audyt ani produkcyjna integracja. Po błędzie sieci UI wymaga ponownego odczytu stanu, nie ponawia automatycznie decyzji.

M4.4 **BLOCKED dla realnych zapisów**: brak potwierdzonego bezpiecznego kontraktu wszystkich operacji (zwłaszcza zadań i wycen), izolacji klientów i autoryzacji produkcyjnych zmian. Nie deklarujemy ukończenia M4.4 ani RLS AutoLogiki. Backend źródeł został rozwinięty; instalator HUD3 nadal pochodzi z M3.

Wykonane kontrole:881pytest PASS/75skip282.69s;14nowych testów laboratorium,10testów panelu PASS; TypeScript/build/pip/JS PASS. Rzeczywisty Chrome/Core:4operacje z osobnym potwierdzeniem,390px,84żądań API,role/CSP/prywatność; zero outbound, źródło i snapshot bez zmian. Początkowy błąd etykiety select naprawiony przed finalnym testem.


## M4.3 — kontrola jakości z kopii (2026-11-06)

Dodano domenę qc dla audytowanej tabeli order_qc: kod/nazwa kontroli, stan0/1, notatka i daty. JOIN do nieusuniętych zleceń oraz paginacja wykluczają osierocone/usunięte rekordy. Brak tabeli lub wymaganych kolumn daje503 bez blokowania raportów. API i React udostępniają siedem domen workshop_reader; finanse, raporty i powiadomienia pozostają owner-only. To historia kopii, nie wykonanie kontroli ani potwierdzenie bezpieczeństwa pojazdu.

Nie dodano niepotwierdzonych tras AutoLogiki. Istniejące raporty finansowe są podzbiorem danych, wkład nie jest zyskiem księgowym, a powiadomienia są wyliczane z kopii. Produkcja, Supabase, synchronizacja i fizyczna kontrola pojazdu NOT_RUN. Instalator HUD3 pozostaje poprzednią wersją M3.

## M4.2 — diagnostyka i odczyty warsztatu (2026-10-29)

Kopia schema18 udostępnia dodatkową domenę diagnostics: objawy, DTC, pomiary, hipotezę, wnioski, zalecenia i czas. Odczyt przez GET /api/v1/autologika/snapshot/diagnostics ma paginację, pomija usunięte zlecenia i nie modyfikuje źródła. Brak tabeli/kolumn daje503; pozostałe domeny pozostają dostępne. Panel AutoLogika udostępnia diagnostykę właścicielowi i workshop_reader; finanse/raporty/powiadomienia nadal owner-only. Terminarz, pojazdy, klienci i części pozostają odczytami offline, nie wymyślonymi trasami live.

Testy backendu adapter/snapshot:39 PASS na syntetycznych danych. Produkcja i rzeczywista synchronizacja NOT_RUN.

## M4.1 — adapter AutoLogika (2026-10-29)

Właściciel autoryzował M4 i dalsze etapy. Adapter używa wyłącznie potwierdzonych GET /api/orders i /api/order/{id}; dodano limit odpowiedzi 2 MiB, całkowity deadline12s, kontrolę envelope i powiązania rekordów z order_id. GET /api/v1/autologika/capabilities wymaga workshop:read i pokazuje ograniczenia bez odpytywania usługi lub ujawniania konfiguracji. Audyt lokalnych źródeł: docs/audits/M4-AUTOLOGIKA-SOURCE.md. Brak awaryjnego przełączania live na DEMO.

Testy kontraktów i snapshot:36 PASS; pip check PASS. Produkcyjna AutoLogika/Supabase i realne urządzenia NOT_RUN. Schemat bazy i instalator HUD3 bez zmian; ten commit rozwija źródła backendu.

# Windows delivery 0.10.4 — 2026-10-28

- Samowystarczalny instalator x64, launcher lokalnego panelu i prywatny katalog danych.
- Odrębny test instalacji/reinstalacji/runtime/API/assets/GUI lifecycle/deinstalacji.
- Bez zmian API/migracji; M4 nie rozpoczęto.

## 0.10.4 — M3.5 i koniec M3, 2026-10-27

- Owner-only zadania1–4etapowe odczytu z postępem/cancel, idempotency, limitami i wspólnym budżetem. Aktualna tożsamość/config i cancellation także przy ostatnimdispatch.
- RAM-only/jedenworker/TTL900s, cleanupshutdown, brakautoreplay; wyniki modeli nie nadają uprawnień. Walidacja zadań nie odbija błędnych treści i nie powoduje Unicode500.
-843pytest/75skip,4genuine2-stepkombinacje26POST/12odczytów i cancel,76PG/API/Chromium,nowyDocker/typecheck/build PASS.149UI=M3.4 bezpowtórki. Realna inferencja/Windows/produkcja NOT_RUN.
-20/45VERIFIED, całeM3zakończone. STOP przedM4 zgodnie z właścicielem.

## 0.10.3 — M3.4, 2026-10-27

- Wersjonowane profile jawnie przypięte do sesjiAI, rewalidacja RLS/revision, bez nadawania uprawnień. Migration4 zachowuje wcześniejsze sesje.
- Panel React pamięci/profili: CRUD/history/CAS, potwierdzenie usunięcia, osobny zakres, jawny kontekstAI i cloudzgoda per tura, czyszczenie po401/zmianie konta.
-817pytest/75skip,149UI/typecheck/build,76realnePG/API/Chromium/0skip i nowyDocker PASS. Realna inferencja/Windows/sprzęt/CI NOT_RUN.19/45VERIFIED; następneM3.5, STOP przedM4.

## 0.10.2 — M3.3, 2026-10-26

- Pamięć PostgreSQL/pgvector i prywatne sesje tekstowe z jawnym kontekstem notatek: RLS per konto/zakres, TTL, limity i trwała dzierżawa tury, revision i atomowy audyt.
- Pochodzenie historycznych danych jest rewalidowane; zmiana źródła/revoke/membership/expiry blokuje starą odpowiedź. Brak zapisu prywatnych danychPG do wspólnej historiiSQLite, parsera, narzędzi i autozapamiętywania. Cloud wymaga jawnego potwierdzenia kontekstu w każdej turze.
- Osobna featuremigration2, zachowanie feature1 wektorów zweryfikowane ograniczonym migratorem.810pytest/61skip,62realnePG/API/0skip, genuineCoreTCP/embedding/LLM, nowyDocker/typecheck/buildPASS. Inferencja/GUI/Windows/sprzęt/CI NOT_RUN.18/45VERIFIED, następneM3.4.

## 0.10.1 — M3.2, 2026-10-26

- Osobne opt-in ownerAPI/chat/tools: pełna walidacja listy, wybór zatwierdzonych odczytów, aktualna autoryzacja/konfiguracja, pin schematu, limity i koszt całego przebiegu. Wyniki nie nadają uprawnień; bez pamięci prywatnej i historii tego przebiegu.
- Realne odczyty OpenAPI z query naprawione z zachowaniem origin/DNS/IP; kontrola schematu i sesji również po ostatnim discoveryMCP. Runner4kombinacji lokalnych protokołów dodany doCI.
-767pytest/24skip, typecheck/build, rzeczywistyTCP Core/LLM/OpenAPI/MCP SDK i nowyDockerPASS. Bez nowego GUI, inferencji, produkcji i aktywacji urządzeń.17/45VERIFIED; następneM3.3.

## 0.10.0 — M3.1, 2026-10-26

- Wspólny kontrakt i adaptery Ollama/OpenAI, integracja katalogu/sesji/czatu/ustawień i GUI, kontekst chmurowy jawnie oznaczony.
- Konfiguracja opt-in/SecretStr/cenyUSD i limit przed I/O, pełny kontekst jako granica kosztu, bounded I/O/no retries/no tools; usage bez udawania faktury.
-710pytest/24skip,141UI/typecheck/build, realny localhostHTTP/Chromium390px i nowyDocker/Compose PASS. Prawdziwe konto/inferencja/Windows/sprzęt/CI NOT_RUN.
-16/45 VERIFIED w zakresie implementacji/protokołów; następneM3.2.

## 0.9.4 — M2.5, 2026-10-26

- Wspólny przegląd propozycji z osobnymi decyzjami i rollback. Code→review_required bez wykonania; preflight bezCAS, brakautoretry.
- Fokus potwierdzenia/wyniku/anulowania, poprawka menu mobilnego; Chromium struktura16widoków i klawiatura390px PASS.
-139UI/typecheck/build,662pytest/24skip i nowyDocker/Compose PASS. PełnyWCAG/czytnik/Safari/Windows/sprzęt NOT_RUN.
-15/45 VERIFIED; następneM3.1.

## 0.9.3 — M2.4, 2026-10-26

- Dziewięć widoków modułów React i przewijana nawigacja; role home/workshop reader, owner-only dane prywatne.
- CRUD/polityka pamięci, zatwierdzane przypomnienia, lokalne powiadomienia, telefonia z rewizją i konta/sesje/tokeny.
-128UI i662pytest/24skip PASS, typecheck/build, actualChromium9widoków390px i Docker/Compose PASS. Usługi właściciela/sprzęt/Windows NOT_RUN.
-14/45 VERIFIED; następneM2.5.

## 0.9.2 — M2.3, 2026-10-25

- React Plugin Manager: status, manifesty, pełna konfiguracja, lokalne zatwierdzenia, enable/disable i jawny odczyt testowy. Brak ukrytych wywołań, sekret wyłącznie jako nazwaenv.
- PUT i40s dla discovery/invoke, ownergate i prywatny lifecycle. Konfiguracja wyłącza plugin; lokalny katalog nie udaje testu połączenia.
-662pytest/24skip,60UI/typecheck/build, rzeczywistyChromium/Core/localhostHTTP i nowyDocker/Compose PASS. Usługiwłaściciela/Windows/sprzęt/CI NOT_RUN.
-13/45 VERIFIED; oba plany/README/kod wtym samymcommicie, następneM2.4.

## 0.9.1 — M2.2, 2026-10-25

- React: rozmowy/sesje i wybór modelu, ustawienia z podglądem i osobnym zatwierdzeniem, historia ostatnich100zdarzeń. Ownergate, escapedtext,401/logoutcleanup; legacy15widoków zachowane.
- Chat95s, przerwanie oczekiwania wymaga synchronizacji; poprawiono powtórny wybórsesji i zmianę tożsamości. Settingspreflight niejest atomowym CAS.
-662pytest PASS/24skip,40UI/typecheck/build, rzeczywistyChromiumDEMO390px i nowyDocker/Compose PASS. Realnemodele/Windows/sprzęt/CI NOT_RUN.
-12/45 VERIFIED, następneM2.3. README i obaplany wtym samymcommicie.

## 0.9.0 — M2.1, 2026-10-24

- React/TypeScript Control Center pod /control/: login kontem/kluczem, rzeczywisty pulpit/System, responsive390px i nawigacja klawiaturowa. Legacy15widoków zachowane pod /.
- Bezpieczne assets/CSP, token tylko w pamięci, logoutserver/401/abort; DockerbudujeUI i sprawdzaHTML/JS/CSS, notice i lockfile zachowane.
-662pytest PASS/24skip,10komponentów/typecheck/build i actualChromium auth/privacy/roles/CSP/mobile PASS; nowyDocker/Compose PASS. Windows/urządzenia/produkcja/CI NOT_RUN.
-11/45 VERIFIED, oba plany/README i kod razem; następneM2.2.

## 0.8.8 — M1.5, 2026-10-24

- Wspólny rejestr i gateway DEMO/OpenAPI/MCP, wersjonowany katalog bez I/O i zachowany invoke; scope i lokalne zatwierdzenia.
- Schematy/argumenty/odpowiedzi i wykonanie ograniczone; timeout/cancel/capacity, audyt bez treści, zgodność starszej konfiguracji z bezpiecznym422.
-657pytest PASS/24skip, w tym realny localhostSDKlab; pipcheck/app.js/newDockerCompose PASS. PostgreSQL i Chromium nie powtarzano; produkcja/Windows/sprzęt/CI NOT_RUN.
-10/45 VERIFIED; oba dzienniki i README wraz z kodem, następne M2.1.

## 0.8.7 — M1.4, 2026-10-24

- Osobny opt-in PostgreSQL z migracją1, SHA256, blokadą, FORCE RLS i minimalnymi grantami; Core pozostaje SQLite12.
- Ograniczony runtime, transakcyjne claims, CRUD z rewizjami i atomowym audytem; API właścicielskie i wyraźny disabled.
-573pytest PASS/24skip bez PG; osobno25realPG PASS/0skip z migratorem bez superuser, restartem i cleanup. Pip check/app.js syntax i nowy LinuxDocker/Compose PASS. Supabase/Windows/sprzęt/CI NOT_RUN.
- Dokumentacja, oba plany i README razem z kodem; następne M1.5.

## 0.8.6 — M1.3, 2026-10-23

- Konta/role PBKDF2-SHA256, sesje TTL z hashowanym tokenem, odwołanie i rewizje; migracja11→12 z backupem.
- Wspólne limity obu API, osobny loginlimit, jawny CORS, actor i odmowy w audycie; uruchomienia Uvicorn bez zaufania do proxyheaders.
-453pytest, pip check, JS/Chromium syntetyczny i nowy LinuxDocker/Compose PASS. Windows/produkcja/sprzęt/realne modele/CI NOT_RUN. Brak SSO/resetu/UIlogowania; limity perproces.
- Oba plany, README i dokumentacja w tym samym commicie; następne M1.4.

## 0.8.5 — M1.2, 2026-10-23

- Dockerhealthcheck bada gotowość, Compose przekazuje zwalidowany timeout; opcjonalny publicznyCA przez BuildKitsecret bez warstw obrazu.
- Izolowany Compose smoke z wyłączonymi integracjami, osobnym wolumenem i ponownym odczytem dynamicznego portu po restarcie; build/auth/persistence/413/non-root/healthy/cleanup PASS.
- Instrukcja Windows11/WSL2 i osobny jobCI; natywne Windows/WSL2 i wykonanie GitHubCI NOT_RUN.353pytest pozostaje wynikiem M1.1, backend bez nowych zmian.

## 0.8.5 — 2026-10-23, M1.1

- Kanoniczne /api/v1 i zgodny /api z jednego routera, wszystkie moduły i wspólne stany/uprawnienia; zachowane limity JSON/WAV i podpisany webhook.
- Osobny /ready, walidowana konfiguracja środowiska Core, maskowany klucz i ograniczony odczyt lokalnej bazy; schema11 bez migracji.
-353testy Python, pip check, JS oraz regresja Chromium głosu/transportu PASS. Realne modele, sprzęt, Windows i Docker NOT_RUN.
- Plan/dziennik TXT/MD i README w tym samym commicie; następne M1.2.

## 0.8.4 — 2026-10-22, R04 transport laboratoryjny i panel

- Ścisły interfejs adaptera, osobne kanały i token klienta; trwałe zdarzenia/outbox i atomowość z recepcją, schema10→11 z backupem.
- Prywatna oferta, zgoda na bieżącą próbę, osobne dostarczenie mostu i ponowne sprawdzenie polityki; limity serwerowe, timeout/odmowa/awaria bez ponawiania.
- Nowy panel transportu, sprzątanie tokenu/stanu, usuwanie zakończonych testów i poprawka układu 390px/statusu listy.
- 276 pytest, pip check, składnia JS, 6 sprawdzeń panelu, pełna ścieżka Chromium z syntetycznymi danymi i regresja syntetycznego głosu. Setup/CI obejmują nowy panel; GitHub CI nie wykonano.
- Laboratorium tekstowe i zamknięte frazy testowe, ręczny dispatch i terminy przy odczycie/zdarzeniu. Bez operatora, PSTN/SIP, audio telefonicznego i realnej inferencji. README zaktualizowane w tym samym commicie.

## 0.8.3 — 2026-10-22, R03 ręczna rozmowa półdupleksowa

- AudioWorklet/PCM WAV i ograniczona segmentacja energii; STT→domyślny review→osobny czat voice→TTS, powrót do słuchania i komenda końca.
- Backend blokuje parsery i pamięć dla voice; schematu 9→10 oddziela historie z backupem i testem.
- Poprawki timerów natywnych z testu Chromium i wyścigów cancel/start; pełne sprzątanie zasobów.
- 229 testów Python; 12 + 10 + 18 kontrolowanych sprawdzeń audio JS; Chromium z syntetycznym mikrofonem i usługami: dwie tury, korekta, TTS, koniec, tracki/konteksty zamknięte.
- Realne modele/sprzęt, hałas, wake-word, pełny dupleks i prywatne wyjście nadal oczekujące. README zaktualizowane w tym samym commicie.

## 0.8.2 — 2026-10-22, R02 ograniczona pamięć / R03 laboratorium mikrofonu

- Zamknięte deklaracje pamięci pl-declarations-v1; domyślnie manual. Atomowy capture, źródła sesji/tury, opt-out, deduplikacja, jawna aktualizacja i ochrona ręcznych korekt.
- Migracja 8→9 z backupem i testem; wykrywanie zmian podczas odpowiedzi i pełny rollback.
- Sesje audio i ręczny kontroler mikrofonu z timeoutem, anulowaniem, sprzątaniem i testami zegara. Nie podłączono ciągłego STT/TTS ani wykrywania mowy/wake-word.
- 213 testów Python, 10 kontrolowanych testów JS audio oraz testy DOM/API. Realny sprzęt, przeglądarka i inferencja niesprawdzone.

## 0.8.1 — 2026-10-22, R02 część 1

- Osobna polityka pamięci, pochodzenie wpisów, korekty z rewizją i historią, jawna retencja i panel.
- Migracja schematu 7→8 z kopią. Blokada zapisu obejmuje ręczny czat i API.
- 8 nowych testów pamięci, łącznie 164. Kontrolowany DOM/API; brak testu rzeczywistej przeglądarki.
- Automatyczna ekstrakcja, wykluczenia podczas ekstrakcji i deduplikacja pozostają do wykonania.
- Pakowanie regeneruje manifest zamiast pakować stary manifest do jego własnej listy sum.

## 2026-10-22 — R01

- Import zweryfikowanego przekazania i 147 bazowych testów.
- Wersjonowane 30 syntetycznych rozmów PL, CLI ewaluacji, raport JSON/Markdown, odrębne błędy środowiska i jakości.
- 9 nowych testów przez kontrolowany HTTP; razem 156. Jakość rzeczywistego modelu niesprawdzona.

# Zmiany

## 0.8-handoff.1 — 22.10.2026

- Płaski ZIP z instrukcją startową, gotowym poleceniem, maszynowym statusem11obszarów, zatwierdzonymi decyzjami i kolejką z kryteriami odbioru.
- Powtarzalne pakowanie wyłącznie śledzonych plików i weryfikacja SHA256 dostarczonego źródła.
- Brak zmian zachowania aplikacji, wersja0.8.0/schema7. Bazowe147testów.

## 0.8.0 — 22.10.2026

- Opcjonalna analiza recepcji Ollama JSON Schema: pochodzenie cytatów/faktów, niepewność, granice uprawnień i kontrola rewizji.
- Panel analizy, model na allowliście, brak automatycznego przechodzenia do heurystyki przy awarii.
- Pakiet przekazania do Codex Cloud: AGENTS.md, dokument stanu i skrypt setup/checks.
- 147 testów, lokalny test HTTP i DOM; brak rzeczywistej inferencji i aktywowanej telefonii. Schemat bazy nadal7.

## 0.7.0 — 22.10.2026

- Laboratorium recepcji, stany rozmowy, oddzielne podsumowanie właściciela i zgłoszenia.
- Ponowna ocena dostępności przed akceptacją, obsługa odmowy i braku odpowiedzi, idempotencja i transakcje.
- Osobny panel, migracja Core 7, usuwanie danych rozmowy i 127 testów. Bez operatora, połączeń i klasyfikacji AI.

## 0.6.0 — 22.10.2026

- Panel Telefonia i API właściciela: tygodniowy grafik, urlop/wyjątki, DND, numery i podgląd eskalacji bez operatora.
- Europe/Warsaw z fallbackiem tzdata, rewizje ustawień, migracja do schematu 6 z backupem.
- 112 testów i test DOM z działającym Core; brak rzeczywistych rozmów.

## 0.5.0 — 22.10.2026

- Wyoming STT/TTS przez jawne pliki, lokalny FTS5 i opcjonalna pamięć hybrydowa przez Ollama.
- Przegląd repozytoriów i licencji, limity ciał HTTP i zdarzeń audio, schemat 5.
- 93 testy; rzeczywiste silniki i Windows nadal wymagają sprawdzenia.

## 0.4.0 — 22.10.2026

- Trwałe sesje i wiadomości, tytuły, eksport JSON, usuwanie kaskadowe oraz podgląd/aplikacja ręcznej retencji.
- Katalog nazw modeli z listy właściciela, faktyczny wybór modelu per sesja i respektowanie domyślnego dostawcy; brak automatycznego pobierania modeli.
- Ograniczony kontekst udanych wiadomości bieżącej sesji, blokada równoległych tur, zapis niepowodzeń i odzyskanie starej blokady.
- Most tylko do odczytu 8 domen z jawnie przygotowanej kopii schematu AutoLogiki 18; spójny import SQLite backup API, manifest i SHA-256, bez zmian repozytorium AutoLogiki.
- Raporty i finanse z kopii mogą być jawnie dołączone do rozmowy; bez automatycznego przekazywania list klientów.
- Zakładka AutoLogika · kopia, rozwinięty panel rozmów, syntetyczna baza warsztatu do testów i kopia przed migracją Core do schematu 4.
- 83 testy pytest oraz test zachowania nowych widoków DOM.

## 0.3.0 — 22.10.2026

- Transport MCP Streamable HTTP przez oficjalny Python SDK 1.30: inicjalizacja sesji, lista narzędzi i wywołania jawnie zatwierdzonych odczytów. Bez stdio i uruchamiania procesów pluginów.
- Ograniczony importer OpenAPI 3.x: GET, operationId, skalarne parametry path/query i walidacja; bez zewnętrznych referencji, requestBody, zapisów i automatycznego pobierania specyfikacji.
- Konfiguracja pluginów w panelu, sekrety wskazywane nazwą zmiennej .env. Zmiana konfiguracji wyłącza plugin do ponownego włączenia.
- Kontrola sieci: jawne zakresy IP, rozwiązywanie DNS z przypięciem IP, kontrola Host/SNI, blokada przekierowań oraz limit odpowiedzi.
- Ograniczone tokeny z terminem ważności i cofnięciem; sekret pokazywany tylko raz, w bazie SHA-256. Scheduler nie wymaga klucza właściciela.
- Czytnik Home Assistant: allowlista encji, tylko stany, bez usług sterujących.
- Twilio/WhatsApp: podpisany webhook, dokładny publiczny adres HTTPS, allowlista nadawców i konta, deduplikacja także po usunięciu wiadomości, inbox i niewysyłane szkice.
- Zakładki Dom, WhatsApp i Dostęp; laboratorium integracyjne bez kont; nieaktywny szablon workflow n8n; lock zależności i automatyczna kopia przed rozszerzeniem schematu 0.2 → 0.3.
- Testy obejmują pełną ścieżkę Core → osobny proces serwera MCP/OpenAPI na localhost.

## 0.2.0

Pierwszy Core i panel, audyt AutoLogiki, rzeczywisty adapter GET zleceń, DEMO integracji, pamięć/Ollama, propozycje i rollback, scheduler, backup oraz 36 testów. Raport historyczny: docs/history/RAPORT-v0.2.md.

## JARVIS HUD — 2026-10-29

Nowy cyjanowy interfejs: pulpit z animowanym rdzeniem prowadzącym do Systemu, telemetria z API, skrót rozmowy dla właściciela, motyw logowania i paneli. Animacje wyłączają się przy prefers-reduced-motion. Role i dotychczasowe funkcje zachowane; M4 nie rozpoczęto.

Wykonano: 149 testów UI PASS, TypeScript/build PASS, node --check jarvis/app.js PASS. Rzeczywisty Chrome + izolowany Core: logowanie, role, wylogowanie/unieważnienie, brak sekretów w storage/URL, CSP, klawiatura, radar i reduced-motion PASS; 390px bez overflow. Obejrzano zrzuty desktop/mobile. Backend bez zmian, pełnej regresji backendu nie powtarzano.

Instalator HUD: wydanie v0.10.4-windows.2, wersja pakietu 0.10.4.2 (Core nadal 0.10.4). Niepodpisany; modele i integracje nie są aktywowane.

## HUD 3 — spójny panel rozmów (2026-10-29)

Poprawiono cyjanowe zaznaczenie aktywnej trasy (aria-current), wybranej rozmowy, wiadomości i pól formularza. Zachowano kolory ostrzeżeń i błędów. Rozszerzono scripts/check_control_browser.cjs o rzeczywiste utworzenie sesji DEMO, wysłanie wiadomości i odczyt odpowiedzi oraz układ czatu przy 390px.

Wykonano: TypeScript/build PASS; node --check jarvis/app.js i check_control_browser.cjs PASS; Chrome z tymczasowym Core PASS (25 żądań API, auth/role/CSP/klawiatura/radar/reduced-motion/rozmowa/390px). Obejrzano docs/evals/control-hud-chat.png i control-hud-chat-mobile.png. Zmiana CSS nie zmienia backendu; 149 testów UI z poprzedniej dostawy nie powtarzano. M4 nie rozpoczęto.

Pakiet Windows 0.10.4.3 (Core 0.10.4): v0.10.4-windows.3. Instalacja na istniejącej kopii użytkownika NOT_RUN; dane i rejestracja pozostają nietknięte.
