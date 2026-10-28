# Przekazanie JARVIS OS 0.9.4

26.10.2026. **15/45 VERIFIED.** Nowy widok `#/changes` „Zmiany i zgody” pokazuje ostatnie100propozycji settings/automation/code, status, treść i osobny podgląd decyzji. Zatwierdzenie/odrzucenie/cofnięcie wymaga drugiego przycisku. Cofanie dotyczy zastosowanych ustawień i przypomnień. Zatwierdzenie opisu kodu prowadzi wyłącznie do review_required, bez wykonania i deploy.

Przed podglądem i decyzją ponowny odczyt propozycji, dla ustawień również bieżącej konfiguracji. Wykryta zmiana blokuje wysłanie; to preflight bez atomowego CAS. Backend pozostaje autorytetem409. Po niepewnym wyniku mutacji wymagane odświeżenie, bez autoretry. Prywatny stan usuwa401/keyedcredential/abortepoch. Treść i poprzednie ustawienia renderowane jako tekst. Zmiany kont/pamięci/pluginów zachowują własne moduły i zgody; lista propozycji nie udaje pełnego rejestru wszystkich zmian.

Accessibility: fokus nagłówka potwierdzenia, powrót do przycisku po anulowaniu i fokus wyniku. Sprawdzono w Chromium strukturę16widoków: pojedyncze main/h1, brak zduplikowanychID i etykiety pól; mobilne menu fokus/pułapkaTab/ShiftTab/Escape, fokus treści po wyborze. Poprawiono otwieranie menu po przejściu do mobilnego viewportu. Nie jest to kompletny audytWCAG, czytnika ekranu ani Safari.

PASS139testówUI, TypeScript/build; pełne pytest662/24skip87.79s, pipcheck/app.js/diff. RzeczywistyChromium/tempCore: osobna akceptacja ustawień i ich rzeczywisty rollback, kod→review_required, tekst/role/privacy/CSP oraz klawiatura i390px. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Dowody evals/control-m25.json/docker-m25.json/changes-desktop.png/changes-mobile.png.

CoreSQLite12/PG1 bez migracji. Windows/WSL2/Safari/iPhone/Android, czytnik ekranu, realne modele, sprzęt i CI NOT_RUN. PG=M1.4 bezpowtórki. ProdukcjaAutoLogika/Supabase bez zmian; lokalnecommitybezpush. NastępneM3.1: wspólna warstwa dostawcówLLM i kontrola kosztów. Historia: history/RAPORT-v0.9.3.md.

Najpierw pełny JARVIS_MASTER_PLAN.txt, identycznyMD iAGENTS. NastępneM3.1; każdezadanie kod/testy/README/obaplany/commit. Zewnętrzne usługi płatne/produkcja wymagają osobnej aktywacji. Pakowanie czystegoGit przez scripts/package_handoff.py i verify_handoff.py.

M3.1 IN_PROGRESS: jarvis/llm.py definiuje kontrakt i CostPolicyUSD/Decimal, tests/test_llm_cost.py18PASS. Pełna regresja680PASS/24skip69.28s, pipcheck PASS. To fundament bez adaptera cloud i bez podłączenia do istniejącego czatu; nie jest zamknięciemM3.1. Dalszy krok: adaptery, walidowana konfiguracja/sekrety/opt-in i integracja katalogu/chatu. Szczegóły: LLM-PROVIDERS.md.
