Aktualizacja 2026-10-29: właściciel zlecił kontynuację M4 i dalszych etapów. To uchyla wcześniejszy STOP po M3; produkcja AutoLogika/Supabase, wydatki, operator i sprzęt pozostają wyłączone.

# JARVIS OS — zacznij tutaj

**To gotowy kod projektu do przejęcia, nie samo zlecenie stworzenia aplikacji od nowa.**

**Nowa instrukcja właściciela:** każdą sesję zacznij od aktualnego `JARVIS_MASTER_PLAN.txt` i dziennika [JARVIS_MASTER_PLAN.md](JARVIS_MASTER_PLAN.md). Plan 45 zadań ma pierwszeństwo przed wcześniejszą kolejką R01–R07. Plik został pobrany z repozytorium. TXT i MD mają identyczny aktualny stan; wybieraj zadania M0–M8 zgodnie z ich zależnościami. Starsza kolejka poniżej jest historyczna.

Pakiet: aplikacja **0.10.4**, przekazanie `0.10.4-handoff.1`, 27.10.2026. **20/45 VERIFIED; całe M3 zakończone. STOP przed M4 zgodnie z właścicielem.** SQLite12, PGfoundation1, opcjonalna pamięć feature4. PASS843pytest/75skip,76realnePG/API/Chromium/0skip; typecheck/build i nowyDockerPASS.149UI=M3.4 bezpowtórki. ZadaniaAI RAM-only bezrestartresume; brak aktywacji operatora/sprzętu/produkcji.

## Pierwsze kroki Codexa

1. Przeczytaj **AGENTS.md** — uprawnienia, zakres i wymagane sprawdzenia.
2. Przeczytaj **PROJECT_STATUS.json** — aktualny stan, mapa kodu i lista 11 obszarów. Status jest opisem dostarczonego snapshotu, nie automatyczną oceną przyszłych zmian.
3. Przeczytaj **docs/DECISIONS.md** i **docs/NEXT_TASKS.md**. Nie pytaj ponownie o zatwierdzone preferencje. R01–R07 opisują historyczny zakres; bieżący zakres M3 jest ukończony. Nie rozpoczynaj M4 bez nowego polecenia właściciela.
4. Przed zmianami uruchom `python3 scripts/verify_handoff.py`, jeśli w importowanej paczce jest HANDOFF-MANIFEST.json.
5. Uruchom `python3.12 scripts/cloud_setup.py`. Bazowy wynik to 843 PASS / 75 skip bez specjalnego PG/browser; testy PG uruchamia scripts/check_postgres.py. Sprawdź, pip check oraz sprawdzenie JS, jeśli Node jest dostępny. Brak Node oznacza brak tego sprawdzenia, nie jego zaliczenie.
6. Zachowaj STOP po M3; przed nową pracą sprawdź aktualne polecenie właściciela oraz plan; ograniczona pamięć, półdupleksowa rozmowa głosowa i laboratoryjny transport telefonii z panelem są już dostarczone. Jakość realnych modeli i sprzętu R03 pozostaje do sprawdzenia. Aktualizuj raport i stan, podaj faktycznie wykonane sprawdzenia. Potem przejdź do następnego możliwego zadania w ramach zleconej sesji.

Nie deklaruj nowej wersji jako „w pełni działającego Jarvisa” tylko dlatego, że testy jednostkowe przeszły.

## Jeżeli repozytorium zawiera tylko ZIP

Użyj **osobnego repozytorium JARVIS-OS**. ZIP ma teraz układ płaski: AGENTS.md, requirements.txt i jarvis/ są bezpośrednio na najwyższym poziomie. Najpierw obejrzyj listę plików, odrzuć ścieżki absolutne, `..` i symlinki, następnie rozpakuj do pustego katalogu roboczego; zachowaj istniejące .git. Nie nadpisuj innych zmienionych plików repo bez sprawdzenia konfliktów. Starsze wydania miały folder opakowujący JARVIS-OS/ — niniejszy go nie ma.

Po imporcie pliki projektu mają znajdować się w głównym katalogu repo, nie wewnątrz kolejnego JARVIS-OS/. Sprawdź manifest i testy przed pierwszą zmianą. Nie uruchamiaj kodu z .env lub rzeczywistymi danymi użytkownika. Paczka nie zawiera sekretów, baz, środowiska .venv, modeli ani historii .git.

## Mapa dokumentacji

| Potrzeba | Plik |
|---|---|
| Gotowa treść pierwszego zadania | PROMPT_CODEX.md |
| Reguły pracy i granice uprawnień | AGENTS.md |
| Stan maszynowy i mapa modułów | PROJECT_STATUS.json |
| Wszystkie zaakceptowane decyzje | docs/DECISIONS.md |
| Kolejka zadań i kryteria odbioru | docs/NEXT_TASKS.md |
| Bieżący wynik etapu i ograniczenia | docs/RAPORT.md |
| Pełny kontekst przejęcia | docs/CODEX-HANDOFF.md |
| Instalacja, uruchamianie, środowisko | README.md, .env.example, compose.yaml |
| Kontrakty API i architektura | docs/API.md, docs/ARCHITEKTURA.md |
| Transport klient/właściciel i ręczne komendy | docs/TRANSPORT-TELEFONII.md |
| Faktyczny audyt AutoLogiki | docs/AUDYT_AUTOLOGIKA.md, docs/autologika-evidence.json |
| Ograniczenia najnowszej analizy AI | docs/ANALIZA-RECEPCJI-v0.8.md |

Dokumenty z numerem starej wersji są historią/wyjaśnieniem danego modułu. Bieżącą prawdę ustalaj z kodu, PROJECT_STATUS i aktualnego raportu. Przy rozbieżności najpierw sprawdź implementację i testy, popraw status; nie dopowiadaj brakujących funkcji.

## Dostępne i niedostępne środowisko

Można pracować bez kont: API, DEMO, SQLite, testy, laboratoria, panel, walidacja i narzędzia ewaluacji. Rzeczywiste AI wymaga osobnej Ollamy i modelu; test kontrolowanego HTTP nie jest testem inferencji. Brak Windows, mikrofonów, Play, Twilio, Home Assistant i urządzeń nie blokuje przygotowania kodu/laboratoriów, ale blokuje deklarowanie testu integracji na żywo.

Użytkownik ma sam sprawdzić sprzęt po powrocie w środę **28.10.2026**. Nie obiecuj nieprzerwanej pracy w tle poza rzeczywiście uruchomionym zadaniem. Nie twórz automatyzacji/reminderów tylko na podstawie tego terminu.
