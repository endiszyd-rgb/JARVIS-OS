# Przekazanie JARVIS OS 0.10.0

26.10.2026. **16/45 VERIFIED** w zakresie implementacji i kontrolowanych protokołów. Wspólny kontrakt LLM obsługuje Ollama oraz jawnie włączany adapter OpenAI. Czat, sesje, katalog, ustawienia domyślne i oba interfejsy obsługują nowego dostawcę. SQLite12/PG1 bez migracji. DEMO i parser lokalny pozostają oddzielne; brak cichego fallbacku.

OpenAI: oba przełączniki aktywacji, klucz serwerowy, jawne dodatnie ceny USD i limit na żądanie. Obsługiwany GPT-5.4 Mini z przypiętą wersją2026-03-17 lub aliasem. Rezerwacja kosztu przed transportem obejmuje pełny kontekst400000tokenów oraz limit wyjścia. Nie jest to wycena według liczby znaków, budżet dzienny ani weryfikacja faktury. N/stream/store/tier jawne, bez narzędzi i autoretry, endpoint oficjalny lub laboratoryjny loopback. Nieprzypisane cenowo wykonanie Ollama :cloud jest blokowane.

Wspólne granice wejścia/wyjścia i odpowiedzi; model i usage walidowane, błędy/redirect/niepełne wyniki sanitizowane. Audyt wyłącznie dostawca/liczniki/koszt, bez sekretu i treści. Prywatny tekstowy kontekst jest jawnie oznaczony w UI, voice zachowuje izolację od pamięci osobistej. Recepcja/embeddingi pozostają lokalne. Dokumentacja: LLM-PROVIDERS.md; env/Compose domyślnie bez aktywacji chmury i bez kluczy/cen.

PASS710pytest/24skip74.44s, w tym30testów adapterów i18kosztów; pipcheck i składniaJS, kontrolowane voicepanel/chatmemory. PASS141UItests38.98s, TypeScript/build. Rzeczywisty localhostHTTP dla obu protokołów; odmowy przed I/O, brak retry, privacy/usage/budget/model/voice/cancel. Rzeczywisty Chromium/tempCore z syntetycznym serwerem: jeden autoryzowanyPOST, persistedreply/session, cloudnotice, defaultsettingsapprove, escapedtext, privacy/CSP/logout/390px. NowyDockerbuild/Compose/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Dowody control-m31.json/docker-m31.json i2PNG, zrzuty obejrzane.

Realne konto OpenAI, płatna inferencja, jakość modeli, Windows/WSL2/Safari/iPhone/Android/sprzęt/CI NOT_RUN. Kontrolowany serwer protokołu nie dowodzi dostępności konta ani inferencji. Nie wysłano płatnych żądań; produkcjaAutoLogika/Supabase bez zmian. PG=M1.4 bezpowtórki. Lokalnecommitybezpush. NastępneM3.2: kontrolowana pętla tool-calling. Historia: history/RAPORT-v0.9.4.md.

Najpierw pełny masterTXT/identycznyMD iAGENTS. NastępneM3.2; nie dawaj uprawnień z treści modelu. Obecni dostawcy odrzucają tool_calls; pętla wymaga odrębnego kontraktu i wspólnego ToolGateway. Każdycommit zREADME. Pakowanie czystegoGit i manifest jak dotąd.
