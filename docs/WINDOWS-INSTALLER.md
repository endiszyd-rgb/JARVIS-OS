# JARVIS OS 0.11.0 — instalacja Windows

1. Uruchom `JARVIS-OS-0.11.0-Setup-x64.exe` na Windows 10/11 x64 (budowany przez workflow **Windows installer** w GitHub Actions: *Run workflow* → artefakt, albo tag `v0.11.0` → Release).
2. Zainstaluj dla swojego użytkownika. Python, biblioteki i gotowy panel są w paczce; nie instaluj osobno Node, Docker ani Pythona.
3. Uruchom skrót **JARVIS OS**. Otworzy się małe okno startowe oraz panel w domyślnej przeglądarce.
4. Kliknij **Kopiuj klucz dostępu**, w panelu wybierz **Klucz właściciela**, wklej klucz, zaznacz „Zapamiętaj klucz na tym komputerze” (tylko zaufane stanowisko) i zaloguj się. Kolejne uruchomienia logują się same.
5. Brama: widok **Brama** → konfiguracja sterownika; głos: widok **Głos** w Chrome/Edge (zgoda na mikrofon). Szczegóły: [BRAMA-I-GLOS.md](BRAMA-I-GLOS.md).
5. Obejrzyj Pulpit, Rozmowę, Ustawienia, Pamięć i pozostałe widoki. Domyślny model DEMO pozwala obejrzeć przepływ bez konta AI. Prawdziwe modele i integracje wymagają osobnej konfiguracji.

Serwer nasłuchuje wyłącznie na `127.0.0.1`, domyślnie na porcie 17321 (`JARVIS_PORT` w `.env`; gdy zajęty — wolny port). Nie otwiera portu w zaporze i nie uruchamia się automatycznie z Windows. Zamknięcie przeglądarki nie zatrzymuje serwera; zamknij okno startowe JARVIS, aby go zatrzymać. Nie uruchamiaj drugiej kopii z tym samym katalogiem danych.

## Dane i aktualizacja

Program: `%LOCALAPPDATA%\Programs\JARVIS OS`. Dane, baza, logi i osobisty klucz: `%LOCALAPPDATA%\JARVIS OS\data`. Przycisk w oknie startowym otwiera ten folder. Nie publikuj `.env` ani bazy. Klucz nie jest przekazywany w adresie strony, skrócie ani argumentach procesu.

Zamknij JARVIS przed aktualizacją. Instalator zastępuje pliki programu; dane są oddzielne. Deinstalacja przez Ustawienia Windows usuwa program i skróty, zachowuje dane. Aby całkowicie usunąć prywatne dane, po deinstalacji świadomie usuń własny katalog danych. Nigdy nie kopiuj tam produkcyjnej bazy AutoLogiki.

Pierwsze uruchomienie tworzy lokalną bazę i unikalny klucz. PostgreSQL/pgvector, modele Ollama, operator, urządzenia i usługi zewnętrzne nie są dołączone ani aktywowane. Panel pokazuje odpowiednie ograniczenia. M4 nie zostało rozpoczęte.

Instalator JARVIS nie jest podpisany certyfikatem wydawcy. Windows może pokazać ostrzeżenie o nieznanym wydawcy; sprawdź pochodzenie pliku i opublikowaną sumę SHA-256.

## Budowanie z kodu

Wymagane: Windows, Python 3.12, gotowe zależności frontend (`npm ci`), Node i kompilator [Inno Setup](https://jrsoftware.org/isinfo.php). Kompilator pobieraj z oficjalnego wydania i sprawdź podpis Authenticode. Budowa nie wymaga płatnej usługi.

```powershell
.venv\Scripts\python.exe scripts\build_windows_installer.py --runtime "C:\path\to\standalone-python-3.12" --compiler "C:\path\to\ISCC.exe" --output "C:\path\to\new-build-folder"
# lub pobierz runtime automatycznie (python-build-standalone, SHA-256 sprawdzane):
.venv\Scripts\python.exe scripts\build_windows_installer.py --download-runtime --compiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" --output "C:\path\to\new-build-folder"
```

Ten sam skrypt uruchamia `.github/workflows/windows-installer.yml` na `windows-latest` (choco innosetup, npm ci, szybki podzbiór pytest, build, smoke launchera z zainstalowanego runtime, artefakt; przy tagu `v*` tworzy Release z plikiem .exe i .sha256).

Skrypt wymaga nowego folderu wyniku, kopiuje runtime, instaluje produkcyjne zależności z requirements/lock, kompiluje UI i instalator oraz zapisuje SHA-256. Nie pakuje roboczej bazy, `.env`, node_modules ani `.venv`. Runtime i zależności są zawartością instalatora, nie repozytorium Git. Ich pliki licencji pozostają w paczce.

## Weryfikacja

Przed wydaniem sprawdź instalację do odrębnego folderu, uruchomienie z zainstalowanego runtime, autoryzowane API, assety panelu, ponowne uruchomienie i zachowanie klucza/bazy oraz deinstalację bez usuwania danych. `--smoke-test --data-dir <test-folder> --report <absolute-json-path>` umożliwia kontrolę launchera bez otwierania przeglądarki. Ten test nie jest weryfikacją fizycznych urządzeń ani jakości modeli.
