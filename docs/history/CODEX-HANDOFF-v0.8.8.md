# Przekazanie JARVIS OS0.8.8

Najpierw cały JARVIS_MASTER_PLAN.txt, identyczny MD i AGENTS.md.10/45 VERIFIED, M0 i M1 zakończone; następne M2.1 React+TS responsywny dashboard/nawigacja. Zachowaj istniejące15widoków i funkcje, dostarczaj etapami. Przed zadaniem IN_PROGRESS/plan/kryteria, po nim kod+testy+oba plany/status/README i commit. Każdy commit z README.

M1.5: ToolSpec/ToolGateway w tool_registry.py, wspólne invoke/discover oraz GET/tools bez sieci; plugins.py ma normalizedinputSchema i bounded schematy. Scope plugins:read/invoke, zweryfikowany Principal; reviewed_read_tools lokalne, remotehints nie nadają praw. DEMO tylko status lub8domen, sideeffectflags blokowane. Limity30s/4operacje/64KiBinput/1MiBresult, schema/argumentnodes512/depth16; regex/refs odrzucone. Starsze niezgodne config zwracają422 do przeglądu, owner może je odczytać/poprawić. Metadataaudit bez args/results, tokeny nie w logach. Digest nie jest przypięciem akceptacji wersji; LLMloop M3.2 nie wdrożony.

PASS657pytest/24skip(68.97s), pipcheck, app.js syntax, localhostMCP/OpenAPI przez realSDK, nowy Docker0.8.8/Compose/auth/restart/413/non-root/healthy/cleanup. Dowody docker-m15.json. 25realPGtestów M1.4 i Chromium M1.3 bez powtórki. ZewnętrznyCI/Windows/WSL2/produkcja/realne modele/sprzęt NOT_RUN.

CoreSQLite12 i opcjonalny Postgresmigration1, bez przeniesienia całego Core/pamięci. M1.3role/sesje/CORS/limity nadal aktywne; produkcja AutoLogika/Supabase bez zmian. Telefonia tekstowylab i głos półdupleks; żadnych realnych rozmów/wiadomości/urządzeń. Wszystkie45zadań i11obszarów zachowane. TOOLS/POSTGRES/SECURITY-ACCESS/API dokumentują granice.

Pakowanie scripts/package_handoff.py po commicie z czystego repo. Lokalne commity bez push. Historia: history/CODEX-HANDOFF-v0.8.7.md.
