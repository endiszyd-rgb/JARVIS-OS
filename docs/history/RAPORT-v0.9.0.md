# JARVIS OS0.9.0 — M2.1

24.10.2026.11/45 VERIFIED. M2.1 dostarcza rzeczywisty React/TypeScript/Vite pod /control/, z pulpitem, widokiem System i responsywną nawigacją. Dotychczasowy panel / zachowuje15widoków; przeniesienie rozmów/pluginów/pozostałych funkcji jest M2.2–M2.4. Backend nadalSQLite12 + opcjonalnyPGmigration1.

Frontend ma konta/klucz bootstrap, stan sesji wyłącznie w pamięci, czyszczenie hasła/klucza po próbie, logout sesji przezAPI, cleanup po401 i epoch/AbortController przeciw spóźnionym odpowiedziom. Pulpit opiera się na /api/v1/status oraz publicznych health/ready. Ograniczone role nie odpytują właścicielskich endpointów. Liczniki to wszystkie rekordy, gotowość wyłącznie Core, bez fikcyjnych danych o modelach/CPU/sprzęcie.

control_ui.py serwuje index i płaskie assets z blokadą traversalu/symlinków. Main traktuje UI jako publiczne bez lookupDB po starym nagłówku, zachowuje CSP bez unsafe-inline. Docker ma etap Node22 budujący UI; npm i pip korzystają z optionalCAsecret. Finalny obraz kopiuje dist i notice, bez node_modules. Git/dockerignore, cloud_setup, jobCI i check_docker z testemHTML/JS/CSS zaktualizowane. Źródła i lockfile frontend w Git, dist/node_modules pominięte. NoticeReact/react-dom/lucide zachowane wthird_party, metadane licencji wOPEN-SOURCE.

PASS662pytest/24skip(62.48s), w tym5testówtraversal/missingbuild/missingDB; pipcheck i app.js syntax. Frontend npmci108pakietów,10komponentówPASS(4.83s), typecheck+VitebuildPASS. Build: JS249.17kB/CSS20.85kB, bezsourcemaps. Początkowytypecheck wymagał korekty nieobsługiwanego exact wtypachtestowych; finalPASS. Poprawiono i przetestowano skiplink zachowujący System oraz fokus po wyborze mobilnego menu.

RzeczywistyChromium ztymczasowymCore: key/account/wrongpasswordclear, faktycznycount2, serverlogout/revocation, zewnętrzneodwołanie→401cleanup, observerbezprivateAPI, tokenybezDOM/URLquery/localStorage/sessionStorage/cookies, CSP/JS/CSS i klawiatura/focus PASS.390px/document390. Zrzuty obejrzane; control-m21.json + control-desktop/mobile.png. NowyDocker/Compose PASS: controlassets,health/ready/auth/restart/persistence/413/non-root/healthy/cleanup; docker-m21.json. Wszystkieintegracjewfixturewyłączone.

Windows/WSL2/Safari/iPhone/Android/realne modele/sprzęt/GitHubCI NOT_RUN. Istniejące25realPGtestów M1.4 bezpowtórki; stare Chromiumgłos/transport=M1.3. Brak nowegoportu rozmów/pluginów/pozostałych widoków/PWA. Lokalnycommitbezpush, produkcjaAutoLogika/Supabase bez zmian. NastępneM2.2. Historia: history/RAPORT-v0.8.8.md.
