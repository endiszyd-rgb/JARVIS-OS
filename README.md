## 0.19.0 — pytania bez rąk: „Hej Siri, Jarvis” i odpowiedzi z internetu (2026-11-28)

- **`POST /api/v1/voice/ask`** — jedno pytanie głosem, jedna odpowiedź do przeczytania (`speech`, `sources`, `kind`). „Brama”, „otwórz/zamknij bramę”, „tak/nie” obsługuje lokalny parser jak dotąd (nigdy model); każde inne pytanie idzie do **Claude API z wyszukiwarką** (`jarvis/web_answer.py`, narzędzie `web_search_20250305`): krótka polska odpowiedź z wartością, jednostką, warunkami i nazwą źródła, linki źródeł w odpowiedzi, przyznanie się do rozbieżnych danych, dopytanie o model/silnik. Pamięć 3 ostatnich pytań z urządzenia przez 15 min („a dla Passata?”). Błędy wracają jako zdanie (HTTP 200), limit 15 pytań/min na urządzenie.
- **Ustawienia → Głos → Odpowiedzi z internetu**: włącznik, klucz Claude API (`sk-ant-…`, maskowany jak inne sekrety), model (Sonnet zalecany / Haiku / Opus), liczba wyszukiwań na pytanie, **pytanie testowe** z linkami do źródeł.
- **Moje konto → Telefon i Siri**: klucze telefonu (`identity_device_keys`, schemat **15** z kopią zapasową przed migracją) — tylko dla kont z 2FA, tworzone z sesji z kodem 2FA, pokazane raz (z adresem i instrukcją skrótu), SHA-256 w bazie, zakres wyłącznie pytania + brama (także dla właściciela), przez tunel tylko `/voice/ask` i `/devices/gate/command`; usuwane ręcznie oraz automatycznie przy resecie/wyłączeniu 2FA.
- Instrukcja krok po kroku ze skrótem iOS (Dyktuj tekst → Pobierz zawartość URL → Wartość słownika → Mów tekst): `docs/PYTANIA-BEZ-RAK.md`; decyzja: `docs/DECISIONS.md`.

Wykonane kontrole: `.venv/bin/python -m pytest -q` **1044 PASS / 76 skip** (nowe `tests/test_voice_ask.py`: maskowanie i walidacja klucza, odpowiedź z wyszukiwarki ze źródłami i kontekstem, wypowiadane błędy, kontynuacja `pause_turn`, klucz telefonu przez tunel tylko dla pytań i bramy, brak obejścia uprawnień właściciela, brak tokenu w bazie, odwołanie, wymóg 2FA i unieważnienie przy resecie 2FA, operator, migracja schematu 14→15 z kopią — API Anthropic zastąpione atrapą), `pip check` PASS, `node --check jarvis/app.js` PASS, vitest **189 PASS** (nowe: ustawienia odpowiedzi z internetu i pytanie testowe, telefon i Siri), typecheck/build PASS; Chrome 390/1280 px: sekcja „Odpowiedzi z internetu”, 0 błędów konsoli.

Ograniczenia: **nie sprawdzone z prawdziwym kluczem Claude ani na iPhonie z Siri** (atrapa API). Odpowiedzi to dane z internetu, nie dokumentacja producenta — przy ważnych połączeniach trzeba sprawdzić wartość. Klucz Claude jest płatny za użycie (limit ustawia się w console.anthropic.com). Skrót iOS trzeba złożyć ręcznie (Skróty nie importują niepodpisanych plików). Wpis zakresu w `AGENTS.md` zostawiony właścicielowi.

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

Weryfikacja M4.3 (2026-11-06): **867 pytest PASS /75skip**,240.74s; **10 testów panelu PASS**, typecheck/build/pip/JS PASS; rzeczywisty Chrome72API/9widoków390px/7domen warsztatowych PASS.23/45 VERIFIED; następne M4.4. Eksperyment OpenClaw zachowany na osobnym branchu.


## M4.3 — kontrola jakości z kopii (2026-11-06)

Dodano domenę qc dla audytowanej tabeli order_qc: kod/nazwa kontroli, stan0/1, notatka i daty. JOIN do nieusuniętych zleceń oraz paginacja wykluczają osierocone/usunięte rekordy. Brak tabeli lub wymaganych kolumn daje503 bez blokowania raportów. API i React udostępniają siedem domen workshop_reader; finanse, raporty i powiadomienia pozostają owner-only. To historia kopii, nie wykonanie kontroli ani potwierdzenie bezpieczeństwa pojazdu.

Nie dodano niepotwierdzonych tras AutoLogiki. Istniejące raporty finansowe są podzbiorem danych, wkład nie jest zyskiem księgowym, a powiadomienia są wyliczane z kopii. Produkcja, Supabase, synchronizacja i fizyczna kontrola pojazdu NOT_RUN. Instalator HUD3 pozostaje poprzednią wersją M3.
M4.2 VERIFIED 2026-11-06:39 testów adapter/snapshot PASS, pipcheck/typecheck/build PASS. Rzeczywisty Chrome/Core: sześć domen workshop_reader z diagnostyką, nine modules/390px, role/CSP i brak zewnętrznej sieci PASS; źródło i kopia bez zmian. Poprawiono przestarzałą asercję liczby domen8→9. Produkcja NOT_RUN.


## M4.2 — diagnostyka i odczyty warsztatu (2026-10-29)

Kopia schema18 udostępnia dodatkową domenę diagnostics: objawy, DTC, pomiary, hipotezę, wnioski, zalecenia i czas. Odczyt przez GET /api/v1/autologika/snapshot/diagnostics ma paginację, pomija usunięte zlecenia i nie modyfikuje źródła. Brak tabeli/kolumn daje503; pozostałe domeny pozostają dostępne. Panel AutoLogika udostępnia diagnostykę właścicielowi i workshop_reader; finanse/raporty/powiadomienia nadal owner-only. Terminarz, pojazdy, klienci i części pozostają odczytami offline, nie wymyślonymi trasami live.

Testy backendu adapter/snapshot:39 PASS na syntetycznych danych. Produkcja i rzeczywista synchronizacja NOT_RUN.
M4.1 pełna regresja: **861 PASS /75skip**,240.21s; pipcheckPASS.


## M4.1 — adapter AutoLogika (2026-10-29)

Właściciel autoryzował M4 i dalsze etapy. Adapter używa wyłącznie potwierdzonych GET /api/orders i /api/order/{id}; dodano limit odpowiedzi 2 MiB, całkowity deadline12s, kontrolę envelope i powiązania rekordów z order_id. GET /api/v1/autologika/capabilities wymaga workshop:read i pokazuje ograniczenia bez odpytywania usługi lub ujawniania konfiguracji. Audyt lokalnych źródeł: docs/audits/M4-AUTOLOGIKA-SOURCE.md. Brak awaryjnego przełączania live na DEMO.

Testy kontraktów i snapshot:36 PASS; pip check PASS. Produkcyjna AutoLogika/Supabase i realne urządzenia NOT_RUN. Schemat bazy i instalator HUD3 bez zmian; ten commit rozwija źródła backendu.

# JARVIS OS · 0.15.0

## Instalator Windows — obecna wersja M3

[Pobierz instalator i SHA-256](https://github.com/endiszyd-rgb/JARVIS-OS/releases/tag/v0.10.4-windows.1). Samowystarczalny `JARVIS-OS-0.10.4-Setup-x64.exe`: Windows 10/11 x64, instalacja dla bieżącego użytkownika, Python3.12/zależności i zbudowany panel React w paczce. Nie wymaga osobnego Dockera, Node ani Pythona. Skrót **JARVIS OS** uruchamia lokalny serwer i otwiera `/control/` w przeglądarce. W oknie startowym kliknij **Kopiuj klucz dostępu**, następnie w panelu wybierz **Klucz właściciela** i wklej klucz.

Dane i unikalny klucz są poza katalogiem programu; restart/aktualizacja/deinstalacja zachowują dane. Program nie startuje automatycznie z Windows. Zamknięcie okna startowego zatrzymuje serwer. [Instrukcja instalacji, konfiguracji, usuwania i budowania](docs/WINDOWS-INSTALLER.md). Instalator nie jest podpisany cyfrowo; do pobrania dołączona jest suma SHA-256.

To dystrybucja ukończonego M3 na nowe polecenie właściciela, bez rozpoczęcia integracji M4 ani deklaracji ukończenia M8. Pamięć SQLite i model DEMO działają lokalnie; PostgreSQL/pgvector i rzeczywiste modele są osobną konfiguracją, nie częścią instalatora. Operator i urządzenia nie są aktywowane.

Weryfikacja końcowej paczki: PASS instalacja/reinstalacja, rzeczywisty zainstalowany runtime/API/JS/CSS, restart i zachowanie bazy/klucza, Tk lifecycle (także natychmiastowe zamknięcie) oraz deinstalacja bez usuwania danych. Pełna regresja: **847 PASS / 75 skip (258.56 s)**; pip check i nowy build UI PASS. Testy konfiguracji:4 PASS. Szczegółowy dowód zainstalowanej paczki: [windows-installer-0104.json](docs/evals/windows-installer-0104.json). Sprawdzenie wizualne przez narzędzie Windows niedostępne (błąd inicjalizacji); test Tk weryfikuje cykl okna, przekazanie adresu przeglądarce i zatrzymanie.

**Plan nadrzędny:** [JARVIS_MASTER_PLAN.txt](JARVIS_MASTER_PLAN.txt) i identyczny [dziennik MD](JARVIS_MASTER_PLAN.md) zawierają 45 zadań M0–M8 oraz bieżący postęp. Plan pobrano z GitHub (źródło a8b5ee8); historyczna kolejka R01–R07 pozostaje materiałem pomocniczym. Po każdym zadaniu oba pliki, README i kod trafiają do tego samego commitu.

Bieżąca sesja planu:

| Zadanie | Zmiana | Weryfikacja |
|---|---|---|
| M0.1 | [Audyt stanu MVP i braków](docs/audits/M0-1-CURRENT-STATE.md), import planu | PASS276pytest, pip check, JS; bez testu produkcji |
| M0.2 | [Aktualny audyt AutoLogika](docs/audits/M0-2-AUTOLOGIKA.md) | PASS17hashy źródeł; upstream/Supabase NOT_RUN |
| M0.3 | [Potwierdzone kontrakty i braki](docs/contracts/AUTOLOGIKA.md) | PASS22testy readonly/snapshot; produkcja/RLS NOT_RUN |
| M0.4 | [ADR010 i osobny monorepo](docs/adr/0010-master-plan-architecture.md), bezpieczeństwo/koszty | PASS Git/root/45ID; runtime bez zmian |
| M0.5 | [Graf zależności](JARVIS_MASTER_DEPENDENCIES.json), walidator/CI, [strategia testów](docs/TEST-STRATEGY.md), [Windows checklist](docs/WINDOWS-CHECKLIST.md) | PASS301pytest (25walidatora), pip check, graf/TXT/MD; Windows i buildDocker NOT_RUN |
| M1.1 | Wspólne `/api/v1` i `/api`, publiczne `/ready`, walidacja konfiguracji Core i maskowany klucz | PASS353pytest, pip check, JS i oba Chromium syntetyczne; modele/sprzęt/Windows/Docker NOT_RUN |
| M1.2 | Docker HEALTHCHECK→ready, timeoutenv, BuildKitCAsecret, izolowany [Compose smoke](scripts/check_docker.py), [Windows/WSL2](docs/DOCKER-WINDOWS.md), jobCI | PASS rzeczywisty Linuxbuild/Compose/auth/restart/413/non-root/healthy/cleanup; Windows/WSL2 i GitHubCI NOT_RUN |
| M1.3 | Lokalne konta/role, sesje z odwołaniem, limity API/login, jawny CORS i audyt aktora; [instrukcja dostępu](docs/SECURITY-ACCESS.md) | PASS453pytest, pip check, JS, Chromium głos/transport i nowy Dockerbuild/Compose; Windows i produkcja NOT_RUN |
| M1.4 | Opcjonalny PostgreSQL: migracje/checksum, RLS, ograniczony runtime i API rekordów; [instrukcja](docs/POSTGRES.md) | PASS573pytest/24skip bez PG; osobno25 realnych testów PG/0skip, nowy Dockerbuild/Compose; Supabase i Windows NOT_RUN |
| M1.5 | Wspólny [rejestr i polityki narzędzi](docs/TOOLS.md), schematy DEMO/OpenAPI/MCP, bounded invoke i katalog bez sieci | PASS657pytest/24skip, realny localhost SDK MCP/OpenAPI i nowy Docker/Compose; produkcja i CI NOT_RUN |
| M2.1 | [React/TypeScript Control Center](docs/CONTROL-CENTER.md): pulpit, System, logowanie i układ mobilny pod `/control/` | PASS662pytest/24skip,10komponentów,typecheck/build,Chromium390px i nowyDocker/Compose; Windows i urządzenia NOT_RUN |
| M2.2 | Rozmowy/sesje i wybór modelu, ustawienia z osobnym zatwierdzeniem, ostatnie100 zdarzeń w React | PASS662pytest/24skip,40testówUI/typecheck/build, rzeczywistyChromiumDEMO390px i nowyDocker/Compose; modele i sprzęt NOT_RUN |
| M2.3 | Plugin Manager: status, manifesty, konfiguracja, zatwierdzone odczyty, enable/disable i jawny test transportu | PASS662pytest/24skip,60UI/typecheck/build, Chromium z prawdziwym lokalnym HTTP i Docker/Compose; usługi właściciela NOT_RUN |
| M2.4 | Dziewięć widoków modułów, role odczytu domu/warsztatu, pamięć/telefonia/bezpieczeństwo i lokalne przypomnienia | PASS662pytest/24skip,128UI/typecheck/build, Chromium9widoków390px i Docker/Compose; sprzęt/usługi właściciela NOT_RUN |
| M2.5 | Zmiany i zgody: podgląd, osobna decyzja, rollback; testy dostępności i klawiatury | PASS139UI/typecheck/build,662pytest/24skip,Chromium16widoków/390px i Docker; pełnyWCAG/czytnik/Safari NOT_RUN |
| M3.1 | Wspólni dostawcy Ollama/OpenAI, konfiguracja i kontrola kosztu przed I/O; integracja z czatem/GUI | PASS710pytest/24skip,141UI/build, rzeczywisty lokalny HTTP/Chromium/Docker; prawdziwe konto i inferencja NOT_RUN |
| M3.2 | Oddzielna pętla odczytów Ollama/OpenAI→ToolGateway: wybór narzędzi, schematy, limity, aktualna autoryzacja i koszt całego przebiegu | PASS767pytest/24skip, rzeczywisty TCP Core/oba protokoły/OpenAPI/MCP SDK, typecheck/build i Docker; inferencja NOT_RUN |
| M3.3 | Pamięć PG/pgvector i prywatne sesje AI: zakresy, TTL, rewizje/lease, jawny kontekst notatek | PASS810pytest/61skip,62realnePG/API/0skip, pełny TCP Core/embedding/LLM i nowyDocker; realna inferencja/GUI NOT_RUN |
| M3.4 | Profile przypięte do sesji AI, historia rewizji i panel pamięci PostgreSQL z CAS/RLS | PASS817pytest/75skip,149UI/build,76realnePG/API/Chromium,nowyDocker; inferencja NOT_RUN |
| M3.5 | [Wieloetapowe zadania AI](docs/AI-TASKS.md), status/cancel/idempotency i wspólny budżet | PASS843pytest/75skip,4genuine2-stepkombinacje,76PG/browser i nowyDocker/build; realna inferencja NOT_RUN |


**Przejęcie przez Codexa:** zacznij od [00_START_HERE.md](00_START_HERE.md), a gotowe zlecenie znajdziesz w [PROMPT_CODEX.md](PROMPT_CODEX.md). Maszynowy stan: [PROJECT_STATUS.json](PROJECT_STATUS.json). To istniejący projekt do rozwijania, nie szablon do napisania od nowa.


Osobisty, modułowy asystent dla Andreasa, zintegrowany z AutoLogika OS. Lokalny projekt Python/FastAPI + SQLite + Control Center. Rozwija starter 0.1 oraz wersje 0.2–0.3. **To nadal MVP** — wbudowane adaptery DEMO są oddzielone od rzeczywistych odczytów.

Aktualny stan: **20/45 VERIFIED; całe M3 ukończone. Zatrzymano pracę przed M4 zgodnie z poleceniem właściciela.** Szczegóły i ograniczenia w masterTXT/MD.

## Synchronizacja GitHub — 28.10.2026

Zaimportowano zweryfikowany snapshot 0.10.4 z manifestem źródła `5aba06cf52334454d65522a8fd4161c1a0cd1403` (379 plików). Import rozwija istniejącą historię `origin/main` od `a8b5ee8`; nie nadpisuje zdalnej historii. Dostarczony ZIP nie zawiera `.git`, a bundle nie jest dostępny: źródłowy hash dokumentuje pochodzenie, ale sam commit i jego lokalni przodkowie nie zostali odzyskani. Oryginalna paczka pozostaje bez zmian.

**Publikacja źródeł potwierdzona; B5 zamknięta.** Zwykły push do `origin/main` opublikował `8cf20683525bdaeb20192e604d2cf881ce4afb1f`; `git ls-remote` potwierdził identyczny zdalny HEAD. Bieżąca aktualizacja dokumentacji zapisuje ten dowód i zamyka blokadę. Świeże kontrole: 149 UI PASS, typecheck/build, protokoły zadań, pip check, JS i walidator planu PASS. Poprawiono trzy testy nieprzenośne na Windows; końcowa regresja backendu: **843 PASS / 75 skip / 0 FAIL (220.45 s)**. [Pełny raport przejęcia](docs/audits/GITHUB-SYNC-2026-10-28.md); wyniki etapów z 27.10 są historyczne. M4 i późniejsze etapy nie zostały rozpoczęte.

## Aktualny etap 0.10.4 — koniec M3

Właścicielskie API `/api/v1/chat/tasks` wykonuje1–4jawne etapy na dotychczasowej pętli odczytów. Ma status postępu, anulowanie, idempotencję per konto, limity czasu/RAM i wspólny budżet całego zadania. Każde wywołanie ponownie sprawdza uprawnienia i konfigurację, również przed ostatnim dispatch. Poprzednie wyniki są niezaufanymi danymi. Bez kodu, zapisów, sterowania i prywatnej pamięci w kontekście zadań. [Kontrakt i przykład](docs/AI-TASKS.md).

Zadania działają w pamięci jednego procesu. Wyniki wygasają900s po zakończeniu; RAM jest czyszczony przy kolejnym użyciu rejestru lub zamknięciu procesu. Nie ma trwałej kolejki ani automatycznego wznowienia po restarcie. Anulowanie nie cofa już wykonanych odczytów lub kosztu wysłanego żądania. Wyniki nieudanych/anulowanych przebiegów są czyszczone; audyt zawiera metadane. Funkcja jest opt-in i dostępna przez API, bez nowego panelu zadań.

Pamięć → „Pamięć i profile PostgreSQL” nadal obsługuje CRUD/history/CAS, potwierdzenie usunięcia oraz profil i0–5notatek do osobnej rozmowy. Profil/revision i zakres są stałe, zmiana źródła wymaga nowej sesji. Cloud wymaga zgody per tura. [Profile i GUI](docs/POSTGRES-PROFILES.md), [kontekst](docs/POSTGRES-CONTEXT.md). PGfeature4 wymaga jawnej migracji; SQLite12 i PGfoundation1 bez zmian.

**843pytest PASS/75skip (128.17s),76realnePG/API/Chromium PASS/0skip**, pipcheck/JSsyntax i nowy typecheck/build oraz Docker/Compose PASS.149UI=M3.4 bezpowtórki. [Dowód zadań](docs/evals/ai-tasks-m35.json):26POST modeli,6odczytówOpenAPI,6MCP; cztery kombinacje po dwa etapy i cancel przed odczytem. [PG/browser](docs/evals/postgres-m35.json), [Docker](docs/evals/docker-m35.json). Modele odpowiadają syntetycznie; realna inferencja/konto cloud, Windows/telefony/sprzęt/GitHubCI NOT_RUN. Publikację potwierdzono 28.10.2026; B5 zamknięta.

## Historia: checkpoint M3.4 przed ukończeniem

Dodano optional featuremigration3 oraz owner API profili instrukcji i historii notatek/profili. Zachowane wersje są odseparowane przez bieżące RLS; runtime nie może ich bezpośrednio zmieniać, a usunięcie rodzica usuwa również ich treści. Metadane audytu pozostają. [Zakres i ograniczenia](docs/POSTGRES-PROFILES.md).

**817pytest PASS/68skip** (103.40s), pipcheck i **69testów rzeczywistego PostgreSQL/API PASS/0skip**; [dowód](docs/evals/postgres-profiles-m34-foundation.json). Sprawdzono m.in. historię i CAS, private/workshop/read-only, atomowy rollback, usuwanie wersji oraz działanie triggerów ograniczonego migratora. Nowe profile są przechowywane, lecz nie są jeszcze przypinane do sesji AI ani dostępne w nowym GUI. **W tym historycznym checkpoincie M3.4 by?o IN_PROGRESS,18/45VERIFIED; obecnie M3.4 jest uko?czone, jak opisano powy?ej**. Docker/typecheck/build=M3.3, UI141/Chromium=M3.1 bez powtórki w tym checkpoincie; realna inferencja/Windows/produkcja NOT_RUN.

## Poprzedni etap 0.8.4 — transport telefonii i interfejs laboratorium

Nowa zakładka **Transport · laboratorium** rozdziela kanał klienta, prywatny briefing i decyzję właściciela oraz kolejkę komend symulacji. Można utworzyć rozmowę, przejść przez pierwszą prośbę/naleganie, dostarczyć briefing, przyjąć lub odrzucić kontakt, zasymulować most, rozłączyć i usunąć zakończony test. Poprawiono szerokość listy rozmów na małym ekranie i aktualizację jej statusu.

Backend zapisuje zdarzenia i komendy atomowo z recepcją. Ma rewizje, idempotencję, limity czasu/tur/prób i symulowanego kosztu. Akceptacja dotyczy bieżącej próby, wymaga dostarczonego briefingu i ponownie sprawdza godziny/DND/urlop; dostępność jest sprawdzana jeszcze raz przed mostem. Odmowa, timeout i awaria kończą próbę bez ponawiania. Token klienta daje dostęp tylko do jednej rozmowy, jest przechowywany jako skrót i nie zastępuje klucza właściciela. Migracja **10→11** tworzy kopię i zachowuje recepcję, pamięć oraz historie text/voice.

Komendy dostarcza się **ręcznie** przyciskiem „Dostarcz komendy · symulacja”. Terminy są rozliczane przy odczycie lub zdarzeniu, bez procesu działającego w tle. Klient przyjmuje tekst; laboratorium rozpoznaje tylko trzy pełne, jawne frazy testowe. Nie podłączono operatora, PSTN/SIP, telefonicznego audio ani realnej analizy AI do tego transportu. [Kontrakt, instrukcja i ograniczenia](docs/TRANSPORT-TELEFONII.md).

Sprawdzenia: **276 testów Python 3.12**, pip check, składnia 7 plików JS, 6 kontrolowanych sprawdzeń panelu transportu oraz regresja dotychczasowych testów JS. **Rzeczywisty Chromium** z tymczasową bazą i syntetycznymi danymi przeszedł pełną ścieżkę transportu, izolację żądań klienta, nawigację/wylogowanie i układ przy szerokości 390 px. Ponownie sprawdzono głos w Chromium z syntetycznym mikrofonem/usługami. To testy laboratorium, bez inferencji modeli, sprzętu i połączeń operatora; Windows, Docker i GitHub CI nie były uruchamiane.

R03 zachowuje ręczną rozmowę półdupleksową: AudioWorklet/PCM → Wyoming STT → domyślny przegląd transkrypcji → osobny czat voice → TTS. Głos nie wykonuje parsera ustawień ani zapisu pamięci. [Instrukcja](docs/ROZMOWA-GLOSOWA.md). Realne modele/sprzęt, hałas, wake-word, pełny dupleks i prywatne wyjście pozostają do sprawdzenia lub realizacji.

Historycznie wskazywano R05; obecnie obowiązuje **STOP po M3**, bez rozpoczęcia M4+. Wszystkie 11 obszarów pozostają w zakresie. Każdy commit zawiera aktualizację README z jego zmianami, wykonanymi sprawdzeniami i ograniczeniami. Zmiany lokalne, bez push na GitHub.

## Szybki start na Windows

Zainstaluj Python 3.12, rozpakuj projekt do osobnego katalogu i w PowerShell uruchom:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Skrypt tworzy `.venv`, generuje klucz właściciela w `.env`, instaluje przypięte zależności, uruchamia testy i Core. Otwórz http://127.0.0.1:8000 i wklej JARVIS_API_KEY. Klucz jest tylko w pamięci karty. Nie zastępuj plików AutoLogiki tym projektem.

Linux / ręcznie:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Wstaw wygenerowany klucz do JARVIS_API_KEY w .env.
python -m pytest -q
python -m uvicorn jarvis.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

`requirements.lock` przypina także zależności pośrednie; requirements.txt używa go jako constraints. Lock nie jest audytem bezpieczeństwa ani plikiem z hashami pakietów. Wersje sprawdzono razem w izolowanym środowisku Python 3.12.

## Co działa

| Moduł | Stan |
|---|---|
| Core i Control Center | Trwała baza, panel z 15 widokami (mobilnie sprawdzono ścieżkę transportu), health i audyt |
| MCP | Streamable HTTP: sesja, discovery i wywołania sprawdzonych odczytów przez oficjalny SDK; bez OAuth/stdio |
| OpenAPI | Obsługiwany podzbiór: GET, operationId, skalarne parametry, lokalny schemat bez $ref |
| Uprawnienia | Klucz właściciela i ograniczone tokeny z datą ważności, cofnięciem i przechowywaniem skrótu |
| Home Assistant | Rzeczywisty czytnik stanów jawnie wskazanych encji; bez sterowania |
| WhatsApp | Weryfikowany webhook Twilio, inbox, deduplikacja, szkice; bez wysyłki i Calling |
| AutoLogika | Audyt 681f7f5, istniejące GET zleceń i osobny czytnik 8 domen z przygotowanej kopii schematu 18; bez zapisów |
| Rozmowa i pamięć | DEMO/Ollama, katalog modeli, trwałe sesje i historia, kontekst sesji, eksport/usuwanie i ręczna retencja; jawne podsumowanie warsztatu |
| Zmiany rozmową | „zapamiętaj …”, „ustaw imię Jan”, „przypominaj co 60 minut: Sprawdź części”; propozycje, akceptacja i rollback |
| Telefonia | Grafik/DND/urlop, recepcja i oddzielny transport laboratoryjny z prywatnym briefingiem; bez operatora |
| Automatyzacje | Lokalny tick, worker, opcjonalny n8n i nieaktywny workflow do importu |
| Operacje | Kopie SQLite z SHA-256; kopia przed migracją do schematu 0.4, Docker i testy CI do uruchomienia |

Nie zaimplementowano komend do bramy/świateł ani wysyłania wiadomości WhatsApp. Od modelu nie zależą uprawnienia i zgody. Narzędzia MCP na liście właściciela muszą być wcześniej sprawdzone — sama adnotacja serwera `readOnlyHint` nie daje uprawnień i nie dowodzi braku skutków ubocznych.

## Test integracji bez kont i urządzeń

W drugim terminalu uruchom syntetyczne laboratorium:

```bash
python -m uvicorn examples.lab_server:app --host 127.0.0.1 --port 8765
```

W panelu Integracje zarejestruj plugin z protocol `mcp` albo `openapi`, otwórz Konfiguracja i użyj odpowiedniego pliku `examples/lab.*.config.json`. Zapis wyłącza plugin: przejrzyj konfigurację, włącz go, wybierz Odkryj narzędzia i wywołaj `read_temperature` z argumentami `{}`. To prawdziwy transport do lokalnego serwera, ale dane z niego są syntetyczne. Test automatyczny robi to samo z osobnym procesem serwera na losowym porcie.

## Rozmowy i kopia warsztatu

W Rozmowie utwórz osobną sesję, wybierz model z katalogu właściciela i wracaj do historii po restarcie. Historia nieudanych zapytań jest oznaczona; nie trafia do kontekstu modelu. Można zmienić tytuł, eksportować i usunąć sesję. Katalog definiuje OLLAMA_ALLOWED_MODELS — nie instaluje modeli. Modele z końcówką :cloud wymagają dodatkowego jawnego włączenia.

Bez dostępu do warsztatu przetestuj osiem domen na syntetycznej kopii:

```bash
python -m examples.workshop_fixture
python scripts/import_autologika.py --source data/lab/autologika-fixture.db
```

Ustaw AUTOLOGIKA_SNAPSHOT_ENABLED=true w .env i zrestartuj Core. Zakładka AutoLogika · kopia pokazuje dane offline. Dla finansów laboratorium wybierz miesiąc 2026-10. Przy zaznaczeniu checkboxa w rozmowie model otrzyma agregaty finansowe/statusowe i datę kopii, bez list klientów. Pełna instrukcja, ograniczenia i import rzeczywistej bazy w środę: docs/ROZMOWY-I-WARSZTAT-v0.4.md.

## Docker

Po ustawieniu klucza właściciela w `.env`:

```bash
docker compose config
docker compose up --build -d
```

Panel pozostaje na 127.0.0.1:8000. Dane są w `jarvis-data`. Nie używaj `down -v`, jeśli mają pozostać. Do workera utwórz w panelu token `scheduler:tick`, wpisz w `.env` jako JARVIS_SCHEDULER_TOKEN, następnie `docker compose --profile automation up --build -d`. Klucz właściciela nie jest przekazywany workerowi.

Dla n8n ustaw osobny N8N_ENCRYPTION_KEY i sprawdzony aktualny N8N_IMAGE, uruchom profil n8n. Zaimportuj `examples/n8n-tick.workflow.json`, przypisz w węźle HTTP poświadczenie Header Auth: `X-Jarvis-Key` z tokenem `scheduler:tick`. Workflow jest nieaktywny i wymaga sprawdzenia w zainstalowanej wersji n8n. n8n jest source-available; sprawdź licencję dla przyszłego hostowania komercyjnego.

W kontenerze `127.0.0.1` oznacza kontener. Dla usług Windows użyj `host.docker.internal` i dodaj jego **konkretny adres lub odpowiedni wąski zakres** do JARVIS_NETWORK_ALLOWLIST. Sekrety pluginów JARVIS_PLUGIN_SECRET_* wymagają jawnego przekazania w Compose override — nie są automatycznie eksportowane z pliku `.env` do kontenera.

## Dokumentacja

- `docs/RAPORT.md` — aktualny stan, testy, wymagane konta i plan na środę 28.10.
- `docs/ROZMOWY-I-WARSZTAT-v0.4.md` — historia, modele, retencja, kopia SQLite i zakres 8 domen.
- `docs/MODULY-v0.3.md` — konfiguracja MCP/OpenAPI, sieci, HA, tokenów i WhatsApp.
- `docs/AUDYT_AUTOLOGIKA.md` i `docs/autologika-evidence.json` — rzeczywisty kontrakt AutoLogiki, commit i dowody.
- `docs/ARCHITEKTURA.md` — plan wszystkich 11 obszarów i decyzje.
- `docs/API.md` — kontrakt aktualnego Core.
- `docs/OPERACJE.md` — backup/restore, aktualizacje, Windows i telefon.
- `CHANGELOG.md` — zmiany wersji, `docs/history/` — raport poprzedniej wersji.

Nie zmodyfikowano repozytorium produkcyjnego AutoLogiki. Nie podłączono rzeczywistej instalacji warsztatu, domu ani konta Twilio. Pełne zapisy AutoLogiki, fizyczne sterowanie i połączenia WhatsApp wymagają kolejnych etapów. Kopia SQLite nie daje synchronizacji na żywo ani pełnego parytetu z ekranami desktopu.

## Historia: nowe w 0.5

Panel „Głos lokalny”: jawny upload WAV i synteza przez zewnętrzne usługi Wyoming. Tekst wymaga sprawdzenia; nie wykonuje poleceń. Panel pamięci: FTS5 i opcjonalne hybrydowe wyszukiwanie przez lokalne embeddingi Ollama. Zapis pamięci nadal ręczny; wyszukiwarka nie zmienia automatycznie kontekstu rozmów.

Konfiguracja: [Głos i pamięć](docs/GLOS-I-PAMIEC-v0.5.md). Przegląd kodu/licencji projektów: [Przegląd repozytoriów](docs/OPEN-SOURCE.md). Bieżący stan i środowy plan: [raport](docs/RAPORT.md). Wymagany Python 3.12; Wyoming 1.10.2 korzysta z audioop, usuniętego w Pythonie 3.13.

## Historia: nowe w 0.6

Zakładka Telefonia: ustawienia godzin przekazywania do właściciela, numery, urlopy, DND i podgląd przyczyn decyzji. **Bez wykonywania rozmów** — konfiguracja nie aktywuje przekierowania Play. Instrukcja: [Telefonia](docs/TELEFONIA-v0.6.md). 112 testów pytest, schemat Core 6.

## Historia: nowe w 0.7

Recepcja · laboratorium: tekstowa rozmowa, pierwsza prośba i naleganie, oczekiwanie na właściciela, symulacja przyjęcia/odmowy/nieodebrania i trwałe zgłoszenia. **Bez operatora i analizy AI** — jawne reguły testowe, bez zapisu do AutoLogiki. [Instrukcja](docs/RECEPCJA-v0.7.md). 127 testów, schemat Core 7.

## Historia: nowe w 0.8 i Codex Cloud

Opcjonalna analiza recepcji przez Ollama z JSON Schema, cytatami i uzupełnianiem danych. **Integracja zaimplementowana, jakość rzeczywistego modelu niesprawdzona.** [Instrukcja](docs/ANALIZA-RECEPCJI-v0.8.md). 147 testów; schemat7.

Przeniesienie do osobnego repozytorium i kontynuacja: [CODEX-HANDOFF](docs/CODEX-HANDOFF.md), AGENTS.md i `python3.12 scripts/cloud_setup.py`. Pakiet nie został automatycznie wysłany na GitHub ani uruchomiony w Cloud.

## Paczka przekazania

ZIP ma pliki repo bezpośrednio w głównym katalogu. HANDOFF-MANIFEST.json zawiera commit źródłowy i SHA256 dostarczonych plików. Przed pierwszą zmianą: `python3 scripts/verify_handoff.py`. Po rozpoczęciu kodowania suma zmienionego pliku naturalnie się różni; manifest nie jest podpisem ani stałym testem CI. Historia .git, sekrety, bazy i modele nie są pakowane.

Ponowne utworzenie paczki z czystego, zapisanego repo: `python3 scripts/package_handoff.py --output ../JARVIS-OS.zip`. Nie pakuj ręcznie całego katalogu roboczego z danymi.

## Historia: nowe w 0.8.2

R02: [ograniczona automatyczna pamięć](docs/PAMIEC-AUTOMATYCZNA.md) rozpoznaje całe deklaracje z zamkniętego katalogu, zachowuje źródła, deduplikuje i chroni ręczne korekty. Domyślnie tryb manual. W Rozmowie jest checkbox „Tego nie zapamiętuj”. Nie ma swobodnej ekstrakcji z modelu.

R03: [sesje i laboratorium mikrofonu](docs/SESJE-AUDIO.md) — ręczna aktywacja, anulowanie, limity czasu, zwalnianie zasobów i API stanów. Ciągłe STT/czat/TTS, wykrywanie mowy i wake-word pozostają do podłączenia.

Core schema9 z kopią przed migracją; 213 testów Python, kontrolowane testy JS i walidacja 30 przypadków recepcji. Realne AI, przeglądarka, mikrofon i urządzenia nie były sprawdzone. Zmiany lokalne, bez push na GitHub.

## JARVIS HUD — 2026-10-29

Nowy cyjanowy interfejs: pulpit z animowanym rdzeniem prowadzącym do Systemu, telemetria z API, skrót rozmowy dla właściciela, motyw logowania i paneli. Animacje wyłączają się przy prefers-reduced-motion. Role i dotychczasowe funkcje zachowane; M4 nie rozpoczęto.

Wykonano: 149 testów UI PASS, TypeScript/build PASS, node --check jarvis/app.js PASS. Rzeczywisty Chrome + izolowany Core: logowanie, role, wylogowanie/unieważnienie, brak sekretów w storage/URL, CSP, klawiatura, radar i reduced-motion PASS; 390px bez overflow. Obejrzano zrzuty desktop/mobile. Backend bez zmian, pełnej regresji backendu nie powtarzano.

Instalator HUD: wydanie v0.10.4-windows.2, wersja pakietu 0.10.4.2 (Core nadal 0.10.4). Niepodpisany; modele i integracje nie są aktywowane.

Kontrola paczki HUD: kompilacja Inno Setup PASS; dołączony Python/Core/API/assets na izolowanych danych PASS (docs/evals/windows-hud-smoke.json); 4 testy launchera PASS. Instalacja/reinstalacja/deinstalacja nowego EXE NOT_RUN: wykryto istniejącą instalację użytkownika. Poprzednie testy instalacji nie są wynikiem nowej paczki. SHA256: e0d996551441e5b397dd147bc6f4353c75152affdff07271e5e86b9d737f4686.

## HUD 3 — spójny panel rozmów (2026-10-29)

Poprawiono cyjanowe zaznaczenie aktywnej trasy (aria-current), wybranej rozmowy, wiadomości i pól formularza. Zachowano kolory ostrzeżeń i błędów. Rozszerzono scripts/check_control_browser.cjs o rzeczywiste utworzenie sesji DEMO, wysłanie wiadomości i odczyt odpowiedzi oraz układ czatu przy 390px.

Wykonano: TypeScript/build PASS; node --check jarvis/app.js i check_control_browser.cjs PASS; Chrome z tymczasowym Core PASS (25 żądań API, auth/role/CSP/klawiatura/radar/reduced-motion/rozmowa/390px). Obejrzano docs/evals/control-hud-chat.png i control-hud-chat-mobile.png. Zmiana CSS nie zmienia backendu; 149 testów UI z poprzedniej dostawy nie powtarzano. M4 nie rozpoczęto.

Pakiet Windows 0.10.4.3 (Core 0.10.4): v0.10.4-windows.3. Instalacja na istniejącej kopii użytkownika NOT_RUN; dane i rejestracja pozostają nietknięte.

Wynik paczki HUD3: Inno Setup build PASS; Python 3.12.16/API/UI z paczki na izolowanych danych PASS (docs/evals/windows-hud3-smoke.json). Instalacja nowego EXE NOT_RUN — istniejąca instalacja użytkownika. SHA256: fe268664ad0ba001289e2d40abd286ea12cfa765cfbe6683c24971bb07d28442.
