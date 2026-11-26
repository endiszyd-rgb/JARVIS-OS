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

### 5. Kamery przez go2rtc

JARVIS nie łączy się z kamerami bezpośrednio. Na PC warsztatowym uruchom [go2rtc](https://github.com/AlexxIT/go2rtc) (jeden plik `go2rtc.exe`) z `go2rtc.yaml`:

```yaml
api:
  listen: "127.0.0.1:1984"      # tylko lokalnie — nie wystawiaj go2rtc przez tunel
streams:
  nvr_ch1: rtsp://admin:HASLO@192.168.1.64:554/Streaming/Channels/102   # Hikvision, kanał 1, substream
  nvr_ch2: rtsp://admin:HASLO@192.168.1.64:554/Streaming/Channels/202
  # Dahua: rtsp://admin:HASLO@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1
```

#### Kamery Setti (Setti+, ekosystem Tuya)

Kamery Setti działają w chmurze Tuya i zwykle nie mają RTSP. go2rtc od wersji **1.9.13** ma źródło `tuya`:

- **Tuya Smart API** (prościej): w go2rtc (http://127.0.0.1:1984) *Add → Tuya* → region + e-mail i hasło konta **Tuya Smart**. Konta Smart Life i aplikacji OEM (Setti+) nie są obsługiwane — kamery trzeba usunąć z aplikacji Setti+ i dodać w aplikacji Tuya Smart.
- **Tuya Cloud API** (bez przenoszenia kamer, jeśli konto Setti+ da się powiązać z projektem Tuya IoT — tym samym co dla sterownika bramy): w `go2rtc.yaml`

```yaml
streams:
  kamera_zewn: tuya://openapi.tuyaeu.com?device_id=ID_KAMERY&uid=UID&client_id=ACCESS_ID&client_secret=ACCESS_SECRET&resolution=sd
  kamera_wewn: tuya://openapi.tuyaeu.com?device_id=ID_KAMERY_2&uid=UID&client_id=ACCESS_ID&client_secret=ACCESS_SECRET&resolution=sd
```

Podgląd klatek z kamer Tuya wymaga **ffmpeg** obok go2rtc (go2rtc dekoduje obraz do JPEG). W JARVIS dodaj kamery `zewnetrzna` → strumień `kamera_zewn` i `wewnetrzna` → `kamera_wewn`. Nie testowane na kamerach Setti — jeśli go2rtc nie pokaże obrazu, sprawdź podgląd w samym go2rtc, zanim szukasz problemu w JARVIS.

Hasła kamer zostają w `go2rtc.yaml`; JARVIS zna tylko nazwy strumieni. W panelu: **Zaawansowane → Ustawienia → Kamery** → adres `http://127.0.0.1:1984`, dodaj kamery (identyfikator, nazwa, strumień `nvr_ch1`). Podgląd to klatki JPEG odświeżane co `refresh_ms` (domyślnie 1 s) — działa przez każdy tunel i na słabym LTE; to nie jest płynne wideo. Używaj substreamów (niższa rozdzielczość).

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
