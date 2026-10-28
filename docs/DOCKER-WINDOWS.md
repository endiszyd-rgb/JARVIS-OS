# M1.2 — Docker Compose, Windows11 i WSL2

Core można budować i testować na Linuksie w chmurze; komputer właściciela nie jest do tego potrzebny. Docelowe uruchomienie Windows ma osobny odbiór. W tej sesji nie deklarujemy testu Windows/WSL2, iPhone/Android ani sprzętu. Aktualne wyniki kontenera są w masterplanie.

## Przygotowanie Windows

Zainstaluj Docker Desktop z backendem WSL2, włącz wirtualizację i wykonaj wymagany restart. Sprawdź w PowerShell `wsl --status`, `docker version` i `docker compose version`. Potrzebny działający Linux Docker Engine, nie tylko CLI. Pracuj w osobnym katalogu JARVIS, bez bazy AutoLogiki. Do samego build/up nie jest wymagany lokalny Python, Node, model ani konto Twilio.

Utwórz `.env` z `.env.example`, jeżeli jeszcze go nie ma. Wstaw losowy klucz przynajmniej24znaki; nigdy nie używaj przykładowego placeholdera. Można utworzyć plik bez wypisywania klucza (PowerShell):

```powershell
if (Test-Path .env) { throw 'Plik .env istnieje — zachowaj jego ustawienia.' }
$jarvisRandom = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$jarvisBytes = New-Object byte[] 32
$jarvisRandom.GetBytes($jarvisBytes)
$jarvisRandom.Dispose()
$jarvisKey = [Convert]::ToBase64String($jarvisBytes)
$jarvisConfig = [IO.File]::ReadAllText((Join-Path (Get-Location) '.env.example')).Replace('replace-with-generated-secret', $jarvisKey)
[IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $jarvisConfig, (New-Object Text.UTF8Encoding($false)))
$jarvisKey = $null
$jarvisConfig = $null
```

Klucz pozostaje w pliku na lokalnym komputerze. Integracje pozostaw false. Nie kopiuj .env do Git, zgłoszenia ani zrzutu ekranu. Te polecenia są instrukcją, nie wynikiem wykonania PowerShell w tej sesji.

## Build i uruchomienie

```powershell
docker compose config --quiet
docker compose build core
docker compose up -d core
docker compose ps
curl.exe --fail http://127.0.0.1:8000/health
curl.exe --fail http://127.0.0.1:8000/ready
```

Otwórz http://127.0.0.1:8000. Klucz do panelu odczytaj lokalnie z .env; nie wpisuj go do adresu URL. Kontener działa jako UID10001, z wyłączonymi capabilities i no-new-privileges. Port jest ograniczony do loopback. Baza jest w nazwanym wolumenie `jarvis-data`, oddzielnym od AutoLogiki i plików źródłowych. Healthcheck używa `/ready`, więc niekompletna konfiguracja/baza nie zostaną uznane za zdrową usługę. Schemat12 i limit czasu połączenia pochodzą z Core; JARVIS_SQLITE_TIMEOUT_SECONDS jest jawnie przekazywany przez Compose.

`docker compose stop` zatrzymuje usługę. `docker compose down` usuwa kontenery/sieć, zachowując wolumen. **Nie używaj down --volumes dla własnych danych**. Nowa wersja wymaga backupu, build i ponownego utworzenia kontenera; procedura odtwarzania w OPERACJE.md. Zwykły restart testuje trwałość, nie stanowi backupu.

Scheduler i n8n są opcjonalnymi profilami i nie uruchamiają się wraz z samym core. Nie włączaj ich do testu bazowego. Model, Wyoming, HA i AutoLogika na hoście wymagają świadomie ustawionego host.docker.internal oraz wąskiej allowlisty. Brak tych usług nie blokuje gotowości lokalnego Core i nie oznacza ich przetestowania. Nie otwieraj portów routera; telefon wymaga osobnego prywatnego HTTPS/VPN i późniejszego odbioru.

## Powtarzalny test bez danych właściciela

`scripts/check_docker.py` używa tymczasowego pliku env z syntetycznym kluczem, losowej nazwy projektu Compose, dynamicznego portu127.0.0.1 i osobnego wolumenu. Uruchamia wyłącznie core, sprawdza API/auth/ready, nie-root, health, bodylimit oraz zachowanie notatki po restarcie. Na końcu usuwa tylko zasoby własnego projektu testowego. Nigdy nie korzysta z bazy/.env właściciela ani nie uruchamia profili n8n/automation. Odczyty loopback nie używają proxy. Test wymaga Python3 i Compose z obsługą !override (v2.24.4+).

```bash
python3 scripts/check_docker.py --image jarvis-m12-core:local
# Jeżeli obraz już zbudowano:
python3 scripts/check_docker.py --image jarvis-m12-core:local --skip-build
```

W zarządzanej chmurze sprawdź właściwy daemon i zachowaj konfigurację proxy/TLS/registry. Jeżeli pip potrzebuje CA sesji, przekaż publiczny bundle wyłącznie jako BuildKitsecret; Dockerfile wykrywa optional proxy_ca i ustawia PIP_CERT tylko w kroku instalacji. Certyfikat nie jest kopiowany do warstw obrazu, a TLS pozostaje włączone:

```bash
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t jarvis-m12-core:local .
python3 scripts/check_docker.py --image jarvis-m12-core:local --skip-build --docker-host unix:///var/run/docker.sock
# Albo build + test przez skrypt:
python3 scripts/check_docker.py --image jarvis-m12-core:local --ca-bundle /etc/ssl/certs/ca-certificates.crt
```

Na zwykłym komputerze z prawidłowym zaufaniem CA sekret nie jest potrzebny. Nie wyłączaj weryfikacji certyfikatów, aby ominąć błąd sieci. Wynik testu LinuxDocker nie jest wynikiem Windows, sprzętu, modeli, RLS ani operatora. Szczegółowy odbiór urządzeń: WINDOWS-CHECKLIST.md.

Opcjonalny PostgreSQL JARVIS ma osobną migrację i ograniczone poświadczenie runtime; nie jest uruchamiany przez domyślny Compose. Konfiguracja i izolowany test: [POSTGRES.md](POSTGRES.md).

Control Center React jest budowany razem z obrazem i dostępny pod `/control/`; dotychczasowy panel pozostaje pod `/`. Szczegóły: [CONTROL-CENTER.md](CONTROL-CENTER.md).
