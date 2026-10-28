# JARVIS OS0.9.1 — M2.2

25.10.2026.12/45 VERIFIED. React pod /control/ ma właścicielskie rozmowy/sesje, wybór modelu, ustawienia przez propozycję i oddzielne zatwierdzenie oraz historię ostatnich100zdarzeń. Lista20sesji/historia100wiadomości, sesjevoice readonly. Legacy15widoków zachowane. CoreSQLite12/opcjonalnyPG1 bez migracji.

Wspólny apiRequest obsługuje jawne metody i95s dla czatu, zwykłe odczyty10s. Abort nie obiecuje zatrzymania backendu; przed wysłaniem wymagany odczyt active_turn i historii. Brak autoretry. Poprawiono obejście needsSync przez ponowny wybór tej samej sesji oraz czyszczenie danych przy zmianie credential; anulowane odczyty ignorują późny błąd. Wszystkie nowe widoki mają401/epoch/abortcleanup i ownergate. HTML/JSON wyświetlane jako tekst.

Ustawienia zawsze pełne name/tone/model. Podgląd nie aplikuje zmiany; osobna decyzja approve/reject, preflight wykrywa zaobserwowaną edycję. Nie zapewnia atomowego CAS. Modele to lista konfiguracyjna bez sondowania/instalacji, DEMO może wykonać lokalne polecenie pamięci/propozycji. Historia ma lokalny filtr i uczciwy limit100.

PASS: pełne pytest662/24skip (74.97s), pipcheck, app.js syntax;40testówUI (11.59s), typecheck/productionbuild. RzeczywistyChromium: trwała rozmowa/reload, model, escapedHTML, voice readonly, proposalapprove/reject, audit, role/privacy/CSP/logout/revoke/401; wszystkie3widoki390px bezoverflow. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Dowody docs/evals/control-m22.json, docker-m22.json i4PNG. Testy lifecycle/API wykorzystują kontrolowane odpowiedzi; inferencja modeli nie była uruchamiana.

Windows/WSL2/Safari/iPhone/Android/realne modele/sprzęt/CI NOT_RUN. PG25testów=M1.4, starszy browser głosu/transportu=M1.3, bezpowtórki. ProdukcjaAutoLogika/Supabase bez zmian; lokalny commit bezpush. NastępneM2.3. Historia: history/RAPORT-v0.9.0.md.
