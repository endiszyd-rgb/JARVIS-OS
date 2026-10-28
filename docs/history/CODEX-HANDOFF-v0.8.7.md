# Przekazanie JARVIS OS0.8.7

Najpierw cały JARVIS_MASTER_PLAN.txt, identyczny MD i AGENTS.md.9/45 VERIFIED (M0.1–M0.5,M1.1–M1.4), następne M1.5 rejestr narzędzi i polityki. Przed zadaniem IN_PROGRESS/plan/kryteria; po zadaniu kod, rzeczywiste testy, oba dzienniki/status/README i commit. Każdy commit z README. Nie projektuj istniejących modułów od początku.

Core0.8.7 nadal SQLite12; nowa opcjonalna warstwa PostgreSQL ma migrację1. postgres_migrations.py+SQL+CLI: SHA256/history/advisorylock/transactionrollback, bez DDL startup. postgres_store.py: jawny host/user/dbname, SecretStr i verify-full poza loopback, runtime exactjarvis_runtime bezsuper/BYPASS/INHERIT/DDL/ownership/extra memberships; SET LOCAL ROLE authenticated i claims transakcyjne. POSTGRES.md opisuje role/granty/RLS, osobnego migratora i provisioning warsztatów. M1.3 konta/sesje/limity nadal działają.

API /storage/status i records CRUD jest właścicielskie; subject wyłącznie ze zweryfikowanej sesjiUUID lub stałego bootstrapUUIDv5. PrivatePG peraccount różni się od nadal współdzielonych ownerdanych SQLite. Warsztaty wymagają osobnego członkostwa/can_write. PG audyt metadanych w tej samej TX coCRUD. Nie kopiuj DSN migratora do Core. BrakDSN=disabled; Coregotowość nie zależy od opcjonalnegoPG.

PASS573pytest/24skip(61.98s) bezPG; osobno25realPG/0skip w izolowanym Docker16.15, migracje/RLS/role/claims/revisions/auditrollback/limitedmigrator/restart/cleanup. Dowody postgres-m14.json. Pip check/app.js syntax PASS; nowy Docker0.8.7/Compose/auth/restart/413/non-root/healthy/cleanup PASS docker-m14.json. Chromium głos/transport z M1.3 bez powtórki. Windows/WSL2/realne modele/sprzęt/produkcja/GitHubCI NOT_RUN.

Supabase/AutoLogika produkcyjne bez zmian; testy lokalne z syntetycznymi danymi. M3.3 przeniesie pamięć/pgvector, M8.3 pełny restore drill; nie deklaruj ich na podstawie foundation. React/TS nie wdrożony. Telefonia nadal tekstowe lab/ręczny dispatch, głos półdupleks syntetycznie sprawdzony. Zachowaj wszystkie11obszarów i45zadań.

Pakuj scripts/package_handoff.py z czystego repo po commicie; manifest opisuje dostarczone bajty. Lokalne commity bez push. Historia: history/CODEX-HANDOFF-v0.8.6.md.
