# Przekazanie JARVIS OS 0.9.3

26.10.2026. **14/45 VERIFIED.** Dziewięć nowych widoków React: AutoLogika, Dom, Urządzenia, Automatyzacje, Pamięć, Telefonia, Powiadomienia, Bezpieczeństwo i Logi. Nawigacja15widoków przewija się na małych ekranach; legacy15widoków i laboratoria pozostają pod `/`.

AutoLogika czyta kopię ze źródłem/datą/SHA i paginacją50, trzy kolekcje części oraz osobny jawny odczyt usługi. Dom odpytuje dozwolone encje wyłącznie po przycisku. Urządzenia pokazują lokalne możliwości, bez fikcyjnego sterowania. Home reader otrzymuje tylko Dom, workshop reader pięć domen; finanse/raporty/powiadomienia warsztatu pozostają właścicielskie.

Pamięć: CRUD z rewizją korekty, historia/źródła na żądanie, polityka i osobny podgląd/wykonanie retencji. Retencja ponownie liczy dane, nie ma atomowego tokenu podglądu. Hybrid/index pozostają w legacy. Automatyzacje: pełna propozycja i osobne zatwierdzenie/odrzucenie, jawny lokalny tick. Powiadomienia: ostatnie100, bez wysyłki/push. Telefonia: numery/godziny/urlopy/DND z rewizją i podgląd zapisanych zasad bez operatora. Bezpieczeństwo: konta/role/aktywność z zatwierdzeniem, odwoływanie sesji/tokenów i sekret usługowy pokazany raz. Logi to ostatnie100zdarzeń audytu, bez logów systemu/Dockera.

PASS662pytest/24skip(62.62s), pipcheck/app.js;128UItests(46.44s), TypeScript/build. Rzeczywisty Chromium z tymczasowym Core:70żądań API, wszystkie9widoków390/390px, memoryCRUD/history, proposal→approval→ticknotification, politykaDND, konta/odwołanie sesji/token jednorazowy, role/prywatność/CSP. Termin przypomnienia zmieniono kontrolą wyłącznie testowego fixture. Źródłowa syntetyczna kopia i snapshot niezmienione; zero prób transportu zewnętrznego. NowyDocker/Compose build/assets/auth/restart/persistence/413/non-root/healthy/cleanup PASS. Dowody: evals/control-m24.json, docker-m24.json i11PNG; obejrzano pamięćdesktop i bezpieczeństwomobile.

Windows/WSL2/Safari/iPhone/Android, usługi właściciela, modele, sprzęt i CI: NOT_RUN. PG=M1.4, bezpowtórki. CoreSQLite12/PG1 bez migracji. ProdukcjaAutoLogika/Supabase bez zmian. Lokalnecommitybezpush. NastępneM2.5: wspólny przegląd zmian i zatwierdzeń oraz accessibility. Historia: history/RAPORT-v0.9.2.md.

Każdą sesję zacznij od pełnego JARVIS_MASTER_PLAN.txt, identycznegoMD iAGENTS. Każde zadanie kończ oboma planami/README i commitem. NastępneM2.5; nie omijaj osobnych zgód/revisions. Pakuj czystycommit przez scripts/package_handoff.py i sprawdź manifest.

M2.5 IN_PROGRESS: klient proposals/decide/rollback w features/changes i5testów PASS, typecheck PASS. Kolejny krok: właściwy panel przeglądu, osobne potwierdzenia i testy dostępności/klawiatury. M2.5 nie jest ukończone; nowe pełne testy/build/browser NOT_RUN.
