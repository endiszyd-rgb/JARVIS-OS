# JARVIS OS — plan rozwoju (od 0.11.0, 2026-11-13)

Plan operacyjny właściciela: co robić po kolei, żeby JARVIS był codziennie używany na warsztacie, a nie tylko przechodził testy. Uzupełnia (nie zastępuje) `JARVIS_MASTER_PLAN.md` — każdy punkt mapuje się na zadania M5–M8. Kolejność jest celowa: najpierw jedna rzecz działająca fizycznie, potem rozszerzanie.

## Etap 0 — Uruchomienie na warsztacie (ten tydzień)

Cel: „Jarvis, otwórz bramę” działa na PC warsztatowym.

1. Zbuduj instalator: GitHub → *Actions* → *Windows installer* → *Run workflow* (lub `git tag v0.11.0 && git push --tags` — wtedy plik trafi do *Releases*). Pobierz `JARVIS-OS-0.11.0-Setup-x64.exe` i sprawdź SHA‑256.
2. Zainstaluj, uruchom skrót, w Chrome/Edge zaloguj kluczem właściciela z zaznaczonym „Zapamiętaj klucz na tym komputerze”. Od teraz panel loguje się sam (`http://127.0.0.1:17321/control/`).
3. Ustal, co steruje bramą (naklejka na sterowniku / aplikacja w telefonie): Smart Life/Tuya → sekcja Tuya w `docs/BRAMA-I-GLOS.md`; Shelly/Tasmota → sterownik HTTP; Home Assistant → sterownik HA.
4. Widok *Brama* → konfiguracja → *Testuj połączenie* (bez ruchu) → *Otwórz* z panelu stojąc przy bramie. Dopiero potem głos.
5. Widok *Głos* → *Włącz nasłuch* → zezwól na mikrofon → „Jarvis, otwórz bramę”. Jeśli brama ma czujnik stanu, wpisz kod/URL stanu, żeby „jaki jest stan bramy” mówił prawdę.
6. Zdecyduj o potwierdzeniu: na warsztacie z ludźmi przy bramie włącz *Wymagaj potwierdzenia*; w zamkniętym pomieszczeniu wyłącz.
7. Zapisz wynik w `JARVIS_MASTER_PLAN.md` (M5.5 → VERIFIED tylko po realnym teście) — to zamyka granicę „symulator ≠ sprzęt”.

Ryzyka: Tuya Cloud wymaga internetu i aktywnej subskrypcji *IoT Core* (darmowy trial odnawiany ręcznie); rozpoznawanie mowy Chrome wymaga internetu. Plan B dla obu: ESP/Tasmota po HTTP + Wyoming lokalnie.

## Etap 1 — Głos, który nie wymaga chmury (2–3 tygodnie)

Mapuje się na M7.3 i część M5.2.

- Pakiet „Wyoming lokalnie” w instalatorze: osobna opcja instalacji `faster-whisper` (model `small` PL) i `piper` (głos `pl_PL-gosia`), uruchamiane jako usługi obok JARVIS; w panelu *Głos* automatyczny wybór silnika, gdy usługi są dostępne.
- Słowo aktywujące offline: `openWakeWord` (ONNX, CPU) jako mikro‑serwis zamiast ciągłego nasłuchu Chrome; panel pokazuje poziom RMS i ostatnie wyzwolenie.
- Streaming STT i przerywanie (barge‑in) — dopiero po stabilnym push‑to‑talk; mierz opóźnienie „koniec mowy → impuls bramy” (cel < 1,5 s lokalnie).
- Satelita głosowy: ESP32‑S3 + mikrofon (ESPHome voice assistant) przy bramie wjazdowej, łączony tym samym protokołem Wyoming → wykonuje polecenia przez JARVIS, nie bezpośrednio.

## Etap 2 — Urządzenia warsztatu (M5.2, M5.3, M6.3)

- Katalog urządzeń w bazie (`devices`): typ, sterownik, uprawnienia, czujnik stanu; brama staje się pierwszym wpisem, a `/devices/gate` aliasem.
- MQTT/Mosquitto w `compose.yaml` + sterownik `mqtt` (publish komend, subskrypcja stanu, reconnect, ostatnia wiadomość ze znacznikiem czasu). ESPHome dla oświetlenia hali, czujnika otwarcia bramy, temperatury i kompresora.
- Reguły: „zamknij bramę 20:00, jeśli otwarta”, „światło hali on przy otwarciu bramy po zmroku”, „alert gdy brama otwarta > 15 min”. Każda reguła jako propozycja → zatwierdzenie → zapis z rollbackiem (istniejący mechanizm *Zmiany i zgody*).
- Powiadomienia: lokalna kolejka → Windows toast / WhatsApp (po M7.2) z linkiem do panelu.

## Etap 3 — Warsztat i AutoLogika (M4.4, M4.5, M6.2)

- Odblokowanie zapisów do AutoLogiki po kontrakcie per operacja (notatka, zadanie, wycena) z izolacją klientów — warunek: podpisana lista endpointów i test na kopii produkcji.
- Poranny raport głosowy: „Jarvis, co dziś?” → zlecenia na dziś, części do odbioru, opóźnienia; źródło: snapshot AutoLogiki, potem live read‑only.
- Dyktowanie notatek do zlecenia głosem (STT → podgląd → zatwierdzenie w panelu) — największa oszczędność czasu mechanika.

## Etap 4 — Interfejs i wdrożenie (M8.1, M8.5)

- PWA: manifest, ikona, tryb pełnoekranowy na tablecie przy stanowisku; dostęp z telefonu po LAN przez HTTPS (`mkcert`) i konto z rolą `operator` (nowa rola: tylko brama + głos, bez ustawień).
- Konsolidacja dwóch paneli: przeniesienie laboratoriów głosu/recepcji/transportu ze starego `/ui` do React, a następnie usunięcie `jarvis/app.js`.
- Instalator: podpis kodu (certyfikat OV lub self‑signed + instrukcja), autostart z Windows (zadanie harmonogramu, opcja w launcherze), tray‑ikona zamiast okna Tk, automatyczne sprawdzanie nowej wersji z GitHub Releases i aktualizacja z zachowaniem danych.
- Ustawienia instalacji z aplikacji: edycja `.env` (modele Ollama, allowlista sieci, Wyoming) przez panel z podglądem i restartem serwera z launchera — dziś zmienia się to ręcznie.

## Etap 4a — Dostęp z telefonu spoza warsztatu (0.12.0, kod gotowy)

Zrobione w kodzie 2026-11-26 (M8.1 IN_PROGRESS): 2FA TOTP, rola `operator`, polityka tunelu, kamery przez go2rtc, komenda „co trzeba zamówić”, PWA. Do zrobienia przez właściciela, po Etapie 0:

1. Konto `endi` (Właściciel) + 2FA w widoku *Moje konto*; konto pracownika z rolą *Operator* + 2FA.
2. Cloudflare Tunnel (`jarvis.nitropoint.pl`) albo Tailscale — `docs/DOSTEP-ZDALNY.md`; w `.env` `JARVIS_REMOTE_ACCESS=true`.
3. Test z telefonu na danych komórkowych: logowanie z kodem, „Otwórz” w widoku Brama, komenda głosowa, PWA na ekranie głównym.
4. go2rtc z rejestratorem (substreamy) → widok *Kamery*.

Następnie: WebRTC dla płynnego wideo (go2rtc), powiadomienia push o otwarciu bramy, części na żywo po kontrakcie AutoLogiki.

## Etap 4b — AutoLogika na żywo (0.13.0, kod gotowy)

W AutoLogice: Ustawienia → włącz serwer mobilny (zapamiętaj PIN). W JARVIS: Zaawansowane → Ustawienia → *AutoLogika* → `http://127.0.0.1:8787` + PIN → *Zapisz i sprawdź połączenie*. Potem „Jarvis, co dziś?”. Dalej: raport poranny o stałej godzinie, logowanie Face ID (passkeys), tryb warsztatowy (jeden ekran).

## Etap 5 — Telefonia i klienci (M7.1, M7.2, M7.4, M7.5)

- WhatsApp Business (Twilio): wysyłka po weryfikacji konta; przyjmowanie zgłoszeń z podsumowaniem do właściciela; brak automatycznego potwierdzania terminów/cen (zasada z AGENTS.md).
- Recepcja telefoniczna: po potwierdzeniu dostępności Business Calling; do tego czasu SIP/GSM przez osobny adapter.

## Etap 6 — Stabilizacja i bezpieczeństwo (M8.2–M8.4)

- Health‑checki urządzeń (ostatni kontakt, nieudane polecenia), retry z limitem, alert gdy sterownik bramy nie odpowiada.
- Backup/restore drill bazy i `.env` z launchera; test odtworzenia na czystej instalacji.
- E2E: Playwright na Windows z prawdziwym Chrome (logowanie, brama, głos z syntetycznym `SpeechRecognition`), skan sekretów w CI, pinned zależności.

## Zasady utrzymania

- Każda zmiana: testy + wpis w `JARVIS_MASTER_PLAN.md` + `CHANGELOG.md`; symulator nie zalicza sprzętu.
- Nowe sterowniki urządzeń dziedziczą ten sam model: konfiguracja w bazie z maskowaniem sekretów, allowlista sieci, cooldown, audyt, opcjonalne potwierdzenie.
- Model językowy nigdy nie wykonuje urządzeń bezpośrednio; wyłącznie parser intencji lub zatwierdzone narzędzia (`/chat/tools`).

## Kolejność na najbliższe sesje (propozycja)

| # | Zadanie | Plan | Czas |
|---|---|---|---|
| 1 | Etap 0 w całości — realna brama + głos na warsztacie | M5.5 VERIFIED | 1 dzień właściciela |
| 2 | Katalog urządzeń + sterownik MQTT + czujnik stanu bramy | M5.2 | 2–3 sesje |
| 3 | Wyoming w instalatorze (whisper + piper) i auto‑wybór silnika | M7.3 | 2 sesje |
| 4 | Reguły bramy/światła z zatwierdzeniem i powiadomienia lokalne | M6.3, M8.2 | 2 sesje |
| 5 | ~~PWA + rola `operator`~~ (0.12.0) — test właściciela przez tunel z 2FA | M8.1 | 1 dzień właściciela |
| 6 | Raport poranny i dyktowanie notatek (snapshot AutoLogiki) | M6.2 | 2 sesje |
| 7 | Tray + autostart + auto‑aktualizacja instalatora | M8.5 | 1–2 sesje |
