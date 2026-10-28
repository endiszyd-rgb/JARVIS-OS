# Przekazanie JARVIS OS0.8.6

Zacznij od całego JARVIS_MASTER_PLAN.txt, identycznego MD i AGENTS.md. M0.1–M0.5 i M1.1–M1.3 VERIFIED,8/45. Następne M1.4 PostgreSQL/Supabase/migracje/RLS. Ustaw IN_PROGRESS przed implementacją, po każdym zadaniu oba plany/status/README i commit. Każdy commit musi zawierać README. Nie pomijaj istniejących modułów przy zmianie warstwy bazy.

Core FastAPI0.8.6/SQLite12. M1.3 dodało identity.py, security_api.py, security_limits.py: lokalne konta/role i hasła PBKDF2, sesje z odwołaniem i hashowanym tokenem, limity peerAPI/login dla obu aliasów, jawny CORS, kontekstaktora w audycie. Bootstrapkey wymagany nawet po utworzeniu kont. Zmiana roli lub wyłączenie odwołuje sesje. Właściciele współdzielą prywatne dane instalacji. Role ograniczone opisane w SECURITY-ACCESS.md; bez SSO/resetu hasła/UIkont. Limity perproces, nie rozproszone. Dostarczony Uvicorn wyłącza proxyheaders; test rzeczywistegoTCP chroni tę właściwość. Backup migracji before-schema12-* zachowuje schema11. Wszystkie stare dane i tokeny nadal obsługiwane.

PASS453pytest/60.37s, pip check,7JSsyntax/8kontrolowanych skryptów, rzeczywisty Chromium syntetyczny głosu/transportu390px, nowy LinuxDockerbuild/izolowanyCompose/restart/auth/413/non-root/healthy/cleanup. Docker dowody docs/evals/docker-m13.json. Windows/WSL2/GitHubCI/realne modele/sprzęt NOT_RUN. /api/v1 i zgodne/api współdzielą router i stan, /ready sprawdza klucz i schema12 bez sieci. Szczegóły w RAPORT/API/SECURITY-ACCESS i planie.

Produkcja AutoLogika/Supabase bez zmian; osobna zgoda wymagana. Dopuszczalne lokalne syntetyczne testy Postgres w izolowanym kontenerze. Głos nadal ręczny półdupleks z review, transport tekstowylab bez operatora i automatycznego dispatch. AutoLogika wyłącznie potwierdzony readonlyGET/snapshot. Brak sekretów/baz/modeli w Git. Wszystkie11obszarów i45zadań pozostają w zakresie.

Pakowanie scripts/package_handoff.py tylko z czystego repo po commicie; manifest opisuje dostarczone bajty, nie przyszły kod. Commity lokalne bez push. Historia: history/CODEX-HANDOFF-v0.8.5.md.
