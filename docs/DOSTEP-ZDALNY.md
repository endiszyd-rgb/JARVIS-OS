# Dostęp zdalny, 2FA, rola operatora i kamery (0.12.0)

Cel: otworzyć bramę, wydać komendę głosową i zobaczyć kamery z telefonu **spoza warsztatu**, bez wystawiania komputera warsztatowego do internetu.

```
telefon (przeglądarka / PWA)
   │  HTTPS
   ▼
Cloudflare (lub Tailscale)  ──►  cloudflared na PC warsztatowym  ──►  JARVIS 127.0.0.1:17321
                                                                     ├─ brama (Tuya / HTTP / HA)
                                                                     ├─ go2rtc 127.0.0.1:1984 ──► kamery / rejestrator (RTSP)
                                                                     └─ kopia AutoLogiki (części)
```

JARVIS dalej słucha tylko na `127.0.0.1`. Ruch z internetu wchodzi wyłącznie przez tunel uruchomiony na tym samym komputerze; router nie wymaga przekierowania portów.

## Zasady bezpieczeństwa (wymuszane przez serwer)

| Sytuacja | Wynik |
|---|---|
| Żądanie z tunelu, `JARVIS_REMOTE_ACCESS=false` (domyślnie) | **403** dla wszystkiego oprócz `/health` i podpisanych webhooków — przypadkowo uruchomiony tunel nic nie odsłania |
| Żądanie z tunelu, `JARVIS_REMOTE_ACCESS=true` | panel `/control/` i logowanie dostępne; każde inne API wymaga **sesji konta otwartej z kodem 2FA** |
| Klucz właściciela lub token usługowy z tunelu | **403** zawsze — działają tylko lokalnie |
| Konto bez 2FA z tunelu | może się zalogować, ale API odpowiada 403 „requires two-factor” |
| Lokalnie (`127.0.0.1`, `localhost`) | bez zmian: klucz właściciela, konta, tokeny |

Żądanie jest „zdalne”, gdy ma nagłówki dodawane przez tunel/proxy (`CF-Connecting-IP`, `X-Forwarded-For`, `Forwarded`, …) albo — przy włączonym dostępie zdalnym — gdy nazwa hosta nie jest na liście `JARVIS_LOCAL_HOSTS` (domyślnie `127.0.0.1,localhost,::1`). Limit logowań (`JARVIS_LOGIN_ATTEMPTS_PER_MINUTE`) liczony jest osobno dla każdego adresu klienta podanego przez Cloudflare (`CF-Connecting-IP`, zaufany tylko gdy połączenie przychodzi z loopback).

Kod 2FA: TOTP (RFC 6238, 30 s, 6 cyfr) — Google/Microsoft Authenticator, Aegis, 1Password, Hasła w iPhonie. Ten sam kod nie zadziała drugi raz (ochrona przed powtórzeniem). 8 kodów zapasowych jednorazowych, przechowywanych jako SHA‑256. Sekret TOTP jest zapisany w lokalnej bazie SQLite (potrzebny do weryfikacji) — chroń plik bazy i kopie zapasowe tak jak klucz właściciela.

## Krok po kroku

### 1. Konta (lokalnie, na PC warsztatowym)

1. Zaloguj się kluczem właściciela → **Bezpieczeństwo** → *Utwórz konto*:
   - `endi` z rolą **Właściciel** — Twoje konto do telefonu,
   - np. `mechanik` z rolą **Operator** — pracownik: tylko brama, głos (komendy) i kamery, bez ustawień, pamięci i rozmów z AI.
2. Wyloguj się, zaloguj na konto `endi` → **Moje konto** → *Włącz 2FA* → zeskanuj QR → wpisz kod → **zapisz kody zapasowe**.
3. Pracownik robi to samo na swoim koncie (najlepiej przy Tobie, na komputerze warsztatowym).

Zgubiony telefon: właściciel w **Bezpieczeństwo** klika *Resetuj 2FA konta …* (odwołuje też wszystkie sesje tego konta).

### 2. Tunel — wariant A: Cloudflare Tunnel (własna domena, np. `jarvis.nitropoint.pl`)

Wymaga darmowego konta Cloudflare i domeny obsługiwanej przez Cloudflare (DNS).

```powershell
winget install --id Cloudflare.cloudflared
cloudflared tunnel login
cloudflared tunnel create jarvis
cloudflared tunnel route dns jarvis jarvis.nitropoint.pl
```

`%USERPROFILE%\.cloudflared\config.yml`:

```yaml
tunnel: jarvis
credentials-file: C:\Users\<użytkownik>\.cloudflared\<ID-tunelu>.json
ingress:
  - hostname: jarvis.nitropoint.pl
    service: http://127.0.0.1:17321
  - service: http_status:404
```

```powershell
cloudflared service install   # uruchamianie z Windows
```

Zalecane dodatkowo (darmowe): **Cloudflare Access** z regułą „tylko mój e‑mail” przed całą domeną — druga bramka logowania jeszcze przed JARVIS.

### 2. Tunel — wariant B: Tailscale (bez domeny, tylko Twoje urządzenia)

Zainstaluj Tailscale na PC warsztatowym i telefonie, zaloguj tym samym kontem. Na PC: `tailscale serve --bg 17321` → panel pod `https://<nazwa-pc>.<tailnet>.ts.net/control/`. Ruch nie wychodzi do publicznego internetu; Tailscale dodaje nagłówki `Tailscale-User-Login`, więc JARVIS traktuje go jako zdalny (2FA wymagane).

### 3. Włącz dostęp zdalny w JARVIS

W `.env` (katalog danych instalacji) dopisz i uruchom JARVIS ponownie:

```
JARVIS_REMOTE_ACCESS=true
JARVIS_SESSION_MINUTES=60
```

Sprawdź z telefonu (dane komórkowe, nie Wi‑Fi warsztatu): `https://jarvis.nitropoint.pl/control/` → logowanie kontem + kod 2FA. Logowanie kluczem właściciela przez tunel ma odpowiedzieć „Dostęp spoza warsztatu wymaga konta z włączonym 2FA”.

### 3a. Face ID zamiast hasła i kodu (passkey)

Na telefonie, przez tunel: zaloguj się raz hasłem + kodem 2FA → **Moje konto** → *Face ID / Touch ID* → *Dodaj to urządzenie*. Od teraz na ekranie logowania wystarczy *Zaloguj przez Face ID / klucz dostępu*. Klucz jest przypisany do domeny (np. `jarvis.nitropoint.pl`); na komputerze w warsztacie dodaj osobny klucz, otwierając panel przez `http://localhost:17321` (przeglądarki nie obsługują kluczy pod `127.0.0.1`). Zgubiony telefon: właściciel → **Bezpieczeństwo** → *Resetuj 2FA* (usuwa też klucze i sesje).

### 4. Aplikacja na telefonie (PWA)

Chrome (Android): menu ⋮ → *Dodaj do ekranu głównego*. Safari (iPhone): *Udostępnij* → *Do ekranu początkowego*. Ikona JARVIS otwiera panel pełnoekranowo, ze skrótami Brama / Głos / Kamery. Brak trybu offline — każde polecenie idzie przez serwer i jego uprawnienia.

Rozpoznawanie mowy w przeglądarce: Chrome na Androidzie działa; Safari na iPhonie bywa niestabilne — przyciski *Otwórz/Zamknij bramę* w widoku Głos i Brama działają zawsze.

### 5. Kamery (od 0.18.0: wbudowany go2rtc)

Instalator JARVIS zawiera [go2rtc](https://github.com/AlexxIT/go2rtc) v1.9.14 (MIT) i FFmpeg (build LGPL z BtbN/FFmpeg-Builds) w folderze `tools`. JARVIS sam uruchamia go2rtc w tle — tylko na `127.0.0.1:1984`, z wyłączonym serwerem RTSP — i pisze jego konfigurację z kamer ustawionych w panelu. Plik `go2rtc.yaml` i dziennik `go2rtc.log` leżą w folderze danych (`dane\go2rtc`) i zawierają hasła kamer / sekret chmury Tuya — nie wysyłaj ich nikomu.

**Ustawienia → Kamery → Dodaj kamerę**:

- **Setti / Tuya (Device ID)** — wpisz Device ID kamery z iot.tuya.com (*Devices → All Devices*) i kliknij **Sprawdź kamerę**: JARVIS pobiera z chmury nazwę i UID właściciela (potrzebny go2rtc). Działa przez ten sam projekt Tuya co brama (Access ID/Secret z *Ustawienia → Brama → Setti / Tuya przez chmurę*), więc kamery muszą być na tym samym koncie aplikacji co brama, a okres IoT Core musi być aktywny (obraz idzie przez chmurę Tuya, inaczej niż brama lokalna). Domyślnie jakość SD (mniej danych na telefonie); „Wysoka jakość (HD)” przy kamerze.
- **Kamera IP / rejestrator (RTSP)** — adres z hasłem, np. `rtsp://admin:HASLO@192.168.1.64:554/Streaming/Channels/102` (Hikvision, podstrumień) albo `rtsp://admin:HASLO@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1` (Dahua). Po zapisaniu adres nie jest pokazywany („zapisany ✓”).

Zapisz — go2rtc uruchamia się / restartuje sam; stan („go2rtc działa”, brakujące dane) widać nad listą kamer. Podgląd: widok **Kamery**, klatki JPEG odświeżane co `refresh_ms` (domyślnie 1 s) — działa przez tunel i na słabym LTE; to nie jest płynne wideo.

**Własny go2rtc (zaawansowane):** *Więcej opcji → Używam własnego go2rtc* — wtedy jak przed 0.18.0: adres go2rtc i nazwy strumieni z jego `go2rtc.yaml` (adres musi być w `JARVIS_NETWORK_ALLOWLIST`). Konfiguracje zapisane przed 0.18.0 zostają w tym trybie.

Ograniczenia: kamery Setti nie były testowane z prawdziwym sprzętem — jeśli obraz się nie pokazuje, zajrzyj do `dane\go2rtc\go2rtc.log` albo otwórz http://127.0.0.1:1984 na komputerze warsztatowym (panel go2rtc pokazuje strumienie i błędy).

### 6. Komendy głosowe

| Zdanie | Kto | Co robi |
|---|---|---|
| „Jarvis, otwórz / zamknij bramę”, „brama stop”, „stan bramy” | właściciel, operator | brama (z potwierdzeniem „tak”, jeśli włączone) |
| „Jarvis, co trzeba zamówić?”, „jakie części są w drodze?” | właściciel (i konta z `workshop:read`) | odczyt z kopii AutoLogiki: braki poniżej stanu minimalnego + zamówienia, które nie dotarły |

Operator używa `/api/v1/voice/command` — tylko parser poleceń, bez modelu AI i bez pamięci.

## Ograniczenia (stan 0.12.0)

- Tunel, Cloudflare Access, Tailscale, prawdziwe kamery/go2rtc i telefon **nie były testowane** w tej sesji — testy używają symulowanych nagłówków tunelu i atrapy go2rtc.
- Części pochodzą z **kopii** AutoLogiki (snapshot), nie na żywo; statusy zamówień rozpoznawane po nazwach (`ZAMOWIONE` itp.) — nieznany status liczy się jako „w drodze”.
- Brak WebRTC/płynnego wideo; brak powiadomień push.
- Sesje otwarte przed włączeniem 2FA nie działają zdalnie — zaloguj się ponownie z kodem.
