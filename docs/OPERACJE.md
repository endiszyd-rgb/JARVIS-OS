# Eksploatacja i testy na urządzeniach

## Backup i odtworzenie

Przycisk kopii wywołuje SQLite backup API do `data/backups/<uuid>.sqlite3` i zwraca SHA-256. Test automatyczny otwiera kopię, sprawdza `PRAGMA integrity_check` i zawartość notatki. Kopia jest jawna, lokalna i zawiera dane osobiste. Nie jest to kopia AutoLogiki, plików n8n ani `.env`. Kopia na tym samym dysku nie chroni przed utratą urządzenia.

Przed odtworzeniem zatrzymaj Core i scheduler. Zachowaj kopię bieżącej bazy i `.env`. Zweryfikuj SHA-256 i otwórz wybraną kopię poleceniem `sqlite3`/Python, sprawdzając integralność. Zastąp wyłącznie `JARVIS_DB` wybraną kopią; przy zatrzymanym procesie usuń stare pliki `jarvis.db-wal` i `jarvis.db-shm`, jeżeli pozostały. Uruchom serwer, sprawdź pamięć, ustawienia i propozycje. Zmiana schematu w kolejnych wersjach będzie wymagała wersjonowanych migracji; nie wracaj starszym kodem do nowszej bazy bez zgodnej kopii.

W Dockerze dane są w wolumenie `/app/data`. Do restore użyj zatrzymanych usług i jednorazowego kontenera z tym samym wolumenem lub eksportu `docker cp`. Nie kopiuj samego pliku aktywnej bazy SQLite z pominięciem WAL; skorzystaj z przycisku backupu. Przenieś kopię offsite i zaszyfruj ją narzędziem użytkownika przed produkcją.

## Aktualizacje

0.4 nie ma automatycznego updatera. Bezpieczny tryb: zapisz backup → zachowaj `.env` → testy nowej wersji w osobnym katalogu i kopii danych → zatrzymaj usługę → wymień kod → test health i działania → przy problemie odtwórz zgodny kod i backup. Propozycje kodu w panelu nie wdrażają zmian. Dalszy etap wprowadzi manifest wydania, hashe/signature, migracje, izolowane testy i rollback. `requirements.lock` przypina zależności bezpośrednie i pośrednie; nie ma hashów pakietów, a obraz Pythona nie jest przypięty digestem. Skan CVE jest wymagany przed produkcją. Przy przejściu z 0.2/0.3 do 0.4 Core tworzy kopię before-v0.4 przed rozszerzeniem schematu i ustawia PRAGMA user_version=4; schemat nowszy niż 4 blokuje start tej wersji. Rollback do starszego kodu wymaga zgodnej kopii.

## Telefon, głos, dostęp zdalny

Na komputerze testuj localhost. Dostęp z iPhone/Android wymaga uruchomienia serwera na interfejsie dostępnym przez prywatną sieć i konfiguracji firewalla, HTTPS lub VPN. Domyślny compose celowo nasłuchuje tylko 127.0.0.1; telefon nie połączy się z nim bez dodatkowej konfiguracji. Nie otwieraj portów routera dla obecnego MVP ani mobilnego serwera AutoLogiki.

Panel jest responsywny, ale nie jest natywną aplikacją i nie zawiera jeszcze PWA/service workera. Dyktowanie Web Speech zależy od Safari/Chrome, HTTPS i uprawnień mikrofonu; może przesyłać nagranie dostawcy przeglądarki. Synteza jest przez systemowy SpeechSynthesis. Alternatywa: dyktowanie klawiaturą telefonu. Lokalna transkrypcja, wake word i ciągły nasłuch w tle nie są wdrożone. iOS może zawieszać stronę w tle.

## Monitoring i ograniczenia bezpieczeństwa

Health procesu, Docker healthcheck i dziennik zdarzeń działają. Nie ma jeszcze pomiarów Prometheus, alertów push, rate limiting, identyfikacji wielu użytkowników, rotacji kluczy przez panel ani audytu odpornego na manipulację administratora pliku. Audyt nie zapisuje treści notatek/chatów; przechowuje rodzaj zdarzenia i identyfikatory, ale payload propozycji pozostaje w bazie. Ochrona przed dużym body sprawdza 64 KiB po odebraniu; nie zastępuje limitu reverse proxy na poziomie strumienia. Kopie i baza nie są szyfrowane przez aplikację.

Klucz właściciela zapewnia pełny dostęp. Nie stosuj go jako poświadczenia publicznego webhooka Twilio ani dla cudzych pluginów. W 0.3 n8n i worker używają osobnego tokenu scheduler:tick. Tworzy go właściciel w panelu; workflow pozostaje nieaktywny do sprawdzenia poświadczeń. To nie są konta wielu użytkowników ani pełne role pracownicze.

## WhatsApp i Calling — przygotowanie kont

Źródło sprawdzone 22.10.2026: https://www.twilio.com/docs/voice/whatsapp-business-calling

Wymagany jest zatwierdzony WhatsApp sender, powiązany WABA/Meta Business oraz konfiguracja TwiML Voice Application. Kraj numeru firmowego musi być obsługiwany — sprawdzić aktualną listę dla konkretnego numeru; nie zakładamy, że zwykły sandbox wiadomości aktywuje Calling. Aktualna dokumentacja wymaga Meta Business Verification oraz limitu co najmniej 2000 rozmów inicjowanych przez firmę w ruchomym okresie 24 h do aktywacji Calling. Bez spełnienia warunków nie można zapisać Voice Endpoint Configuration. Dla połączeń wychodzących dokumentacja wyklucza numery firmowe USA, Kanady, Egiptu, Nigerii, Turcji i Wietnamu. Polska nie jest na tej liście wyłączeń, co nie zastępuje weryfikacji konkretnego konta.

Połączenia wychodzące wymagają zgody użytkownika na połączenie; zgoda na wiadomości nie jest zgodą na dzwonienie. Należy obsłużyć webhook wyniku zgody, wygaśnięcie/cofnięcie, limity ponawiania i nieodebrane połączenia. Dokumentacja opisuje także callback permissions i różne okresy ważności; nie kodujemy ich jako stałej bez weryfikacji odpowiedzi dostawcy. Brak mostkowania WhatsApp do PSTN. Wymagane podpisy webhooków, deduplikacja, HTTPS, ograniczony koszt i logi bez sekretów. Rozmowy przychodzące i wychodzące nie są zaimplementowane w 0.3. Nie aktywowano kont i nie wykonano płatnych operacji.

Wersja 0.3 ma działający webhook wiadomości Twilio, inbox i szkice bez wysyłki. Opis konfiguracji, deduplikacji oraz zakresów tokenów znajduje się w MODULY-v0.3.md. Odtworzenie starszej kopii bazy może przywrócić ważność tokenu cofniętego później: po restore przejrzyj listę dostępu.


Wersja 0.4 zapisuje również historię rozmów i wybór modelu. Backup bazy Core zawiera te dane, ale nie zawiera osobnych plików snapshotu AutoLogiki. Usunięcie sesji nie usuwa starszych backupów i eksportów. Retencja ma osobny tryb podglądu i wykonania; bez wywołania właściciela nie kasuje danych. Import/odświeżanie kopii warsztatu wykonuj przy zatrzymanym Core. Szczegóły w ROZMOWY-I-WARSZTAT-v0.4.md.
