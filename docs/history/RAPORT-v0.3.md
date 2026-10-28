# JARVIS OS 0.3 — raport kontynuacji

22.10.2026. Rozwinięto poprzednią wersję 0.2. Nie zmieniono produkcyjnego repozytorium AutoLogiki i nie podłączono rzeczywistych urządzeń ani kont. Audyt AutoLogiki pozostaje oparty na commicie 681f7f5ecf5a1e365022a9ac1cb22b6ff443262c.

## Dostarczone moduły

| Moduł | Co wykonano w tej wersji | Co pozostaje |
|---|---|---|
| MCP | Oficjalny SDK 1.30, Streamable HTTP, inicjalizacja sesji, discovery i wywołania odczytów z lokalnej listy właściciela | OAuth, stdio w sandboxie, scopes per-plugin, szerokie testy zgodności dostawców |
| OpenAPI | Konfiguracja lokalnego schematu, podzbiór GET/operationId, walidacja parametrów i blokady ścieżek | Pełniejsza obsługa schematów, autoryzacji, paginacji i kontrolowanych zapisów |
| Bezpieczeństwo | Tokeny usług z zakresami, terminem i cofnięciem; hashe w bazie; kontrola IP/DNS/Host/SNI, brak przekierowań i limity | Konta pracowników, OIDC, vault, rate limiting, podpisy wydań, pełny audyt bezpieczeństwa |
| Home Assistant | Rzeczywisty klient odczytu stanów wskazanych encji i panel Dom | Test własnej instancji; MQTT/ESPHome i dopiero osobno potwierdzone sterowanie |
| WhatsApp | Oficjalny walidator podpisów Twilio, inbox, allowlisty, deduplikacja z receipt, kasowanie treści i szkice | Publiczne wdrożenie webhooka, załączniki, dostarczanie wiadomości, Calling i obsługa zgód |
| Control Center | Konfiguracja/odkrywanie/odczyt pluginów, zakładki Dom, WhatsApp i Dostęp; łącznie 10 widoków | Wizualna weryfikacja przeglądarek, telefonów i uprawnień mikrofonu |
| Automatyzacje | Worker używa osobnego scheduler:tick tokenu; gotowy nieaktywny szablon n8n do importu | Test zainstalowanego n8n, retry i push; workflow nie jest aktywowany automatycznie |
| Operacje | Kopia przed rozszerzeniem schematu 0.2→0.3, lock zależności, laboratorium bez kont | Windows/PowerShell, Docker build, skan CVE i kopie offsite |

Moduły poprzedniej wersji pozostają: Core, AutoLogika GET, DEMO wszystkich 8 domen warsztatu, rozmowa DEMO/Ollama, notatki długoterminowe, parser poleceń, propozycje/akceptacja/rollback, scheduler, backup, audyt i dokumentacja wszystkich 11 obszarów projektu. Pełne zapisy warsztatowe, historia rozmów, lokalne STT/TTS, fizyczne sterowanie i samodzielne zmiany kodu nadal wymagają kolejnych etapów. Kodowe propozycje w panelu pozostają opisami do przeglądu.

## Weryfikacja

**56 testów pytest — zaliczone w izolowanym Python 3.12.** Obejmują wcześniejsze 36 testów oraz tokeny, migrację z kopią, reguły sieci i DNS pinning, OpenAPI, oficjalną sesję MCP, lokalną ocenę uprawnień, filtrowanie HA, podpisy/odrzucenia/deduplikację WhatsApp, szkice bez wysyłki i usuwanie wiadomości.

Najważniejszy test integracyjny uruchamia **osobny proces serwera lokalnego** z prawdziwym MCP i REST. Następnie przechodzi przez Core: instalacja → konfiguracja → aktywacja → discovery → invoke. Komunikacja jest rzeczywistym HTTP na localhost. Wynik nadal ma oznaczenie synthetic_fixture, bo laboratorium nie reprezentuje czujnika fizycznego. Osobny test SDK działa na serwerze ASGI.

Test interfejsu DOM przez jsdom i działający Core sprawdził logowanie, wyczyszczenie pola klucza, wydanie ograniczonego tokenu, usunięcie jego widoku po zmianie zakładki, zapis/usunięcie szkicu, renderowanie wrogiego HTML jako tekstu, rejestrację i konfigurację pluginu oraz wylogowanie. To test zachowania, **nie renderowania wizualnego**. Sprawdzono także składnię JS, brak konfliktów zależności (`pip check`) i poprawność zmian (`git diff --check`). Jedno ostrzeżenie deprecacyjne w zależności testowej nie powoduje błędu.

**Nie sprawdzono:** fizycznej instalacji HA/AutoLogiki, konta Twilio, routingu publicznego HTTPS, rzeczywistego TLS end-to-end, serwerów MCP z OAuth, Docker build, PowerShell i Windows, n8n runtime, Safari/Chrome na telefonach oraz rozmowy z faktycznie uruchomionym modelem. Nie wysłano wiadomości i nie wykonano płatnych operacji.

## Konta, sekrety i konfiguracja

- Do startu Core i laboratorium nie są potrzebne konta. Potrzebny jest tylko lokalny klucz właściciela — generuje go start.ps1.
- MCP/OpenAPI wymagają adresu serwera, lokalnie sprawdzonych odczytów i ewentualnego Bearer tokenu wskazanego zmienną JARVIS_PLUGIN_SECRET_*. Domyślna sieć obejmuje tylko loopback.
- Home Assistant: własna instancja, token, allowlista entity_id i adresu sieciowego.
- WhatsApp: Twilio Account SID/Auth Token, skonfigurowany sender, dokładny publiczny adres HTTPS i allowlista numerów nadawców. Żadnego sekretu nie dodano do paczki.
- Calling nadal wymaga warunków Twilio/Meta opisanych w OPERACJE.md; wiadomości i webhook nie aktywują połączeń.
- n8n/worker: osobny token scheduler:tick, a n8n także encryption key i własne konto właściciela. Nie używaj klucza właściciela JARVIS-a w workflow.

## Środa 28.10.2026 — kolejność

1. Rozpakuj projekt osobno od AutoLogiki, przeczytaj README i uruchom scripts/start.ps1. Jeśli masz już dane 0.2, zatrzymaj poprzedni Core, zachowaj .env i kopię data; przed rozszerzeniem istniejącej bazy 0.3 zrobi dodatkowy backup. Nie kopiuj .venv z innego systemu.
2. Sprawdź 56 testów, panel, propozycję ustawień/rollback, pamięć i backup.
3. Uruchom laboratorium z README na porcie 8765. Zarejestruj MCP i OpenAPI przy użyciu plików examples/lab.*.config.json. Sprawdź discovery i odczyt temperatury. Ten etap nie potrzebuje kont.
4. Wydaj token scheduler:tick, sprawdź jego działanie i odmowę dostępu do ustawień, potem cofnij. Dla dalszej pracy utwórz osobny token i ustaw worker. n8n konfiguruj dopiero po sprawdzeniu jego wersji i importu nieaktywnego workflow.
5. Porównaj wersję AutoLogiki z audytem, wykonaj jej backup, uruchom jej istniejący serwer mobilny i przetestuj wyłącznie odczyt zlecenia z prawdziwym PIN-em.
6. Jeżeli HA już działa: wskaż jeden czujnik i jego adres /32 w allowliście. Sprawdź stan. Nie konfiguruj jeszcze sterowania bramą.
7. Zainstaluj Ollama/model; sprawdź polską rozmowę i notatki. Zdalny telefon uruchamiaj przez prywatny HTTPS/VPN. Zweryfikuj wygląd i mikrofon na iPhone/Android.
8. Dopiero po przygotowaniu Twilio i reverse proxy przetestuj przychodzącą wiadomość z własnego dozwolonego numeru, zły podpis i ponowne dostarczenie. Szkice mają pozostać niewysyłane. Nie wystawiaj publicznie całego panelu.

Następny etap: historia i kontekst rozmów oraz projekt pełnego mostu domen AutoLogiki. Moduły wymagające sprzętu i kont są gotowe do wskazanych testów konfiguracyjnych; ich działanie na Twojej instalacji nie zostało jeszcze potwierdzone.
