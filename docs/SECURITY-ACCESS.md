# Dostęp i zabezpieczenia JARVIS OS

Stan: M1.3, Core 0.8.6, lokalna baza SQLite ze schematem 12. Opis dotyczy
backendu kont i sesji, istniejących tokenów usługowych oraz kontroli dostępu API.
Przykłady zawierają wyłącznie wartości demonstracyjne i symbole do zastąpienia.

## Pierwsze uruchomienie i klucz właściciela

1. Wygeneruj losowy klucz lokalnie, np. poleceniem
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Zapisz go jako `JARVIS_API_KEY` w lokalnym `.env` albo konfiguracji środowiska.
   Wartość musi mieć 24–256 znaków ASCII i nie może zaczynać się od `replace-`.
   Wygenerowanego klucza i `.env` nie dodawaj do Git.
3. Uruchom serwer lokalnie:

   ```sh
   .venv/bin/python -m uvicorn jarvis.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
   ```

4. Sprawdź `GET /ready`. Gotowość wymaga poprawnego klucza i dostępnej bazy ze
   schematem 12. `GET /health` potwierdza działanie procesu; sam nie potwierdza
   gotowości konfiguracji.
5. Użyj klucza w nagłówku `X-Jarvis-Key`, aby utworzyć pierwsze konto.

Klucz środowiskowy pozostaje wymagany po utworzeniu kont. Bez poprawnego
`JARVIS_API_KEY` logowanie i chronione API zwracają `503`; istniejące konta ani
sesje nie zastępują konfiguracji bootstrap. Zmiana klucza wymaga ponownego
uruchomienia procesu. To pełny dostęp właściciela, więc nie przekazuj go workerom.

Nie ma domyślnego użytkownika ani domyślnego hasła. Nazwa konta spełnia
`^[a-z][a-z0-9_.-]{2,63}$` (3–64 znaki), hasło ma 12–256 znaków. Konta tworzy
właściciel. Maksymalna liczba kont wynosi 256, łącznie z kontami wyłączonymi.

## Role, zakresy i prywatność

Backend rozpoznaje klucz właściciela, sesje kont i tokeny usługowe. Każdy z tych
sekretów jest przekazywany w `X-Jarvis-Key`; API nie używa ciasteczek logowania.

| Rola konta | Zakresy | Dostęp |
| --- | --- | --- |
| `owner` | `*` | Wszystkie chronione funkcje, także zarządzanie dostępem i dane prywatne. |
| `observer` | `status:read` | Status Core. |
| `home_reader` | `status:read`, `home:read` | Status oraz odczyt dozwolonych stanów Home Assistant. |
| `workshop_reader` | `status:read`, `workshop:read` | Status, odczyt zleceń i wybrane domeny snapshotu warsztatu. |
| `automation_runner` | `status:read`, `scheduler:tick` | Status oraz uruchomienie kroku lokalnego harmonogramu. |

Zakres `status:read` zwraca również ustawienia (`name`, `tone`, `model`), liczniki
rekordów, listę modeli i informację o trybie integracji. To świadomie udostępniony
podzbiór danych, który należy uwzględnić przy nadawaniu roli obserwatora.

`workshop_reader` może odczytywać `/autologika/readonly/orders`, pojedyncze
zlecenia, manifest `/autologika/snapshot` oraz domeny snapshotu `calendar`,
`orders`, `vehicles`, `parts`, `customers`. Domeny `finances`, `reports` i
`notifications` wymagają właściciela. Odczyt klientów może zawierać dane osobowe.
Nadanie roli nie włącza adaptera ani nie tworzy połączenia produkcyjnego;
wyłączona lub niepoprawnie skonfigurowana integracja nadal zwraca `503`.

Pamięć, rozmowy właściciela, konfiguracja recepcjonisty i telefonii, ustawienia,
audyt, kopie zapasowe oraz zarządzanie kontami i sekretami są dostępne wyłącznie
właścicielom. Konta nie tworzą oddzielnych przestrzeni danych: wszystkie konta
`owner` mają dostęp do tej samej pamięci, rozmów i konfiguracji JARVIS.
Pozostałe role nie mogą nadawać sobie dodatkowych uprawnień. Rola
`automation_runner` może wywołać krok harmonogramu, ale nie zarządza jego
konfiguracją; obecny krok tworzy lokalne powiadomienia bez żądań zewnętrznych.

Istniejące tokeny usługowe mają własną listę zakresów, bez roli konta. Właściciel
zarządza nimi przez `/security/tokens`. Dopuszczalne zakresy to `status:read`,
`scheduler:tick`, `home:read`, `plugins:read`, `plugins:invoke`, `messages:read`,
`messages:draft`; okres ważności to 1–8760 godzin (domyślnie 24). Pełny token jest
zwracany tylko przy utworzeniu, a w bazie pozostaje SHA256. Token usługowy nie
otrzymuje dostępu właściciela. `GET /auth/me` działa również dla takiego tokenu,
ale `POST /auth/logout` służy tylko do sesji kont i dla tokenu usługowego albo
klucza właściciela zwraca `409`.

## Endpointy i przykłady

Zalecany prefiks to `/api/v1`. Każdy poniższy endpoint ma także zgodny alias
`/api`, używany przez obecny interfejs i workery. Autoryzacja i stan bazy są
wspólne dla obu prefiksów. `Authorization: Bearer` nie zastępuje nagłówka
`X-Jarvis-Key`.

| Metoda i ścieżka po prefiksie | Wymagany dostęp | Wynik |
| --- | --- | --- |
| `POST /auth/login` | Bez klucza w żądaniu; poprawna konfiguracja bootstrap. | Sesja, jednorazowo pokazany token i dane konta. |
| `GET /auth/me` | Dowolna ważna tożsamość. | Identyfikator/rodzaj tożsamości, rola, zakresy, nazwa i termin ważności. |
| `POST /auth/logout` | Ważna sesja konta. | Unieważnia tę sesję. |
| `GET /security/users` | Właściciel. | Lista kont bez haseł i skrótów haseł. |
| `POST /security/users` | Właściciel. | Tworzy konto, `201`. |
| `PATCH /security/users/{uuid}` | Właściciel. | Zmienia rolę/aktywność przy zgodnej rewizji. |
| `GET /security/sessions` | Właściciel. | Metadane sesji bez tokenów i ich skrótów. |
| `DELETE /security/sessions/{uuid}` | Właściciel. | Unieważnia wskazaną sesję. |

Przykład utworzenia konta; hasło jest demonstracyjne i należy je zastąpić:

```http
POST /api/v1/security/users
Content-Type: application/json
X-Jarvis-Key: <KLUCZ_WLASCICIELA>

{"username":"operator.demo","password":"Demonstracyjne-haslo-do-zmiany","role":"observer"}
```

Odpowiedź `201`, z przykładowymi identyfikatorami i czasem Unix w sekundach:

```json
{
  "id": "00000000-0000-4000-8000-000000000001",
  "username": "operator.demo",
  "role": "observer",
  "enabled": true,
  "revision": 0,
  "created": 1800000000.0,
  "updated": 1800000000.0
}
```

Logowanie nie wymaga nagłówka z kluczem:

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username":"operator.demo","password":"Demonstracyjne-haslo-do-zmiany"}
```

```json
{
  "session_id": "00000000-0000-4000-8000-000000000002",
  "token": "<TOKEN_SESJI_POKAZANY_TYLKO_RAZ>",
  "expires_at": 1800003600.0,
  "user": {
    "id": "00000000-0000-4000-8000-000000000001",
    "username": "operator.demo",
    "role": "observer",
    "enabled": true,
    "revision": 0,
    "created": 1800000000.0,
    "updated": 1800000000.0
  }
}
```

Token sesji przekazuj jako `X-Jarvis-Key: <TOKEN_SESJI>` do `GET /api/v1/auth/me`,
`GET /api/v1/status` i pozostałych dozwolonych endpointów. Nie umieszczaj go
w adresie URL ani w treści notatki czy rozmowy.

Zmiana roli i wyłączenie konta mogą być jednym żądaniem:

```http
PATCH /api/v1/security/users/00000000-0000-4000-8000-000000000001
Content-Type: application/json
X-Jarvis-Key: <KLUCZ_WLASCICIELA>

{"revision":0,"role":"home_reader","enabled":false}
```

Wynik zawiera `revision: 1`; dotychczasowe sesje tego konta zostają unieważnione.
Nieaktualna rewizja zwraca `409`: odczytaj konto ponownie przed kolejną zmianą.
`enabled` musi być wartością JSON `true`/`false`, a rewizja liczbą całkowitą.
Nieznane pola żądania są odrzucane. Nie ma endpointu kasowania konta ani zmiany
hasła; konto można wyłączyć.

Wylogowanie: `POST /api/v1/auth/logout` z nagłówkiem sesji zwraca
`{"revoked":"00000000-0000-4000-8000-000000000002"}`. Właściciel może uzyskać
ten sam skutek przez `DELETE /api/v1/security/sessions/{session_id}`. Brak rekordu
daje `404`; ponowne unieważnienie istniejącego rekordu jest idempotentne.
Rekord może później zniknąć wskutek porządkowania sesji.

Brak/niepoprawny sekret daje `401`, brak wymaganego zakresu `403`, błędne dane
wejściowe `422`. Dla błędnego hasła, nieistniejącego poprawnie nazwanego konta
i konta wyłączonego logowanie zwraca identyczne `401 Invalid credentials`.

## Hasła i cykl życia sesji

Hasło jest przechowywane jako PBKDF2-HMAC-SHA256 z 600 000 iteracji i losową
32-bajtową solą na konto. Weryfikacja używa porównania stałoczasowego skrótu.
Nieistniejące i wyłączone konta przechodzą kosztowną weryfikację zastępczą,
aby uniknąć skróconej ścieżki obliczeń. Nie oznacza to gwarancji identycznego
czasu całego żądania sieciowego.

Sesja ma UUID i losowy, nieprzewidywalny token URL-safe wygenerowany z 32 bajtów
losowych danych. W bazie zapisuje się wyłącznie SHA256 tokenu, powiązanie z kontem,
czas utworzenia i wygaśnięcia oraz flagę unieważnienia. Lista kont ani lista sesji
nie ujawnia skrótów. Ponowne odczytanie tokenu z API nie jest możliwe.

Domyślny czas ważności to 60 minut, konfigurowany przez
`JARVIS_SESSION_MINUTES` w granicach 5–1440 minut. Termin jest stały: żądania nie
przedłużają sesji. Przy `teraz >= expires_at` sesja jest nieważna. Restart procesu
z zachowaniem bazy i poprawnym kluczem bootstrap zachowuje sesje; nie ma tokenów
odświeżających.

Na konto przypada najwyżej 16 aktywnych sesji. Kolejne udane logowanie unieważnia
najstarszą, aby zachować limit. Udane logowanie usuwa z bazy wygasłe i wcześniej
unieważnione sesje; lista sesji jest listą bieżących metadanych, nie pełną historią.
Nieudane logowanie nie zmienia kont ani sesji. Każda przyjęta zmiana roli lub
aktywności zwiększa rewizję i unieważnia wszystkie sesje konta. Przy każdym
żądaniu backend sprawdza aktualne konto, rolę, aktywność, wygaśnięcie i revokację.
Także zapis tej samej roli lub tej samej wartości `enabled` unieważnia sesje.

Zmiany kont, sesji i odpowiadające im zdarzenia audytu są wykonywane w transakcji
SQLite. Pliki bazy i backupów nadal zawierają dane prywatne; haszowanie sekretów
nie szyfruje całej bazy. Chroń je uprawnieniami systemu operacyjnego. Klucz
bootstrap i sekrety opcjonalnych integracji pozostają w lokalnej konfiguracji
środowiska, poza odpowiedziami API i repozytorium.

## Limity żądań i adres klienta

| Zmienna | Domyślnie | Dozwolona wartość |
| --- | --- | --- |
| `JARVIS_API_REQUESTS_PER_MINUTE` | `600` | Liczba całkowita 1–100000. |
| `JARVIS_LOGIN_ATTEMPTS_PER_MINUTE` | `10` | Liczba całkowita 1–1000. |
| `JARVIS_SESSION_MINUTES` | `60` | Liczba całkowita 5–1440. |

Budżet API obejmuje wszystkie żądania HTTP do `/api` i `/api/...`, w tym błędne,
nieautoryzowane i próby logowania. Logowanie ma dodatkowy budżet wspólny dla
`/api/auth/login` i `/api/v1/auth/login`, także z końcowym `/`. Nie można zwiększyć
budżetu przez zmianę prefiksu. Odrzucenie przez limit logowania również zużywa
pozostały budżet API. `OPTIONS`, `/health`, `/ready` i statyczny interfejs są poza
tymi limitami; `/api/ready` podlega limitowi API.

Liczniki mają stałe okna po 60 sekund od pierwszego żądania danego połączeniowego
adresu IP w oknie. Są wspólne dla kont z tego adresu i lokalne dla procesu.
Odpowiedź `429` zawiera `Retry-After` w sekundach oraz
`{"detail":"Rate limit exceeded"}`. Pamięć limitera ma najwyżej 4096 aktywnych
adresów; po zapełnieniu nowe adresy otrzymują `429` do zwolnienia miejsca po
wygaśnięciu okna. Brak adresu klienta oznacza jeden wspólny koszyk `unknown`.

Uvicorn musi działać z `--no-proxy-headers`, jak w Dockerfile i skrypcie startowym.
Limiter używa rzeczywistego peer IP z ASGI, nie przyjmuje samodzielnie
`X-Forwarded-For`, `Forwarded` ani `X-Real-IP`. Włączenie zaufania do nagłówków
proxy w serwerze zmienia tę podstawę. W obecnej konfiguracji klienci za wspólnym
proxy/NAT współdzielą budżet widocznego adresu. Wiele procesów lub instancji ma
oddzielne liczniki, a restart je zeruje; nie ma współdzielonego magazynu limitów.

## Jawna lista CORS

`JARVIS_CORS_ORIGINS` jest domyślnie puste. Interfejs serwowany przez ten sam
Core korzysta z tego samego origin i nie wymaga dopisania do listy. Dla osobnego
panelu wpisz dokładne originy rozdzielone przecinkami, np.:

```dotenv
JARVIS_CORS_ORIGINS=https://panel.example,http://127.0.0.1:5173
```

Dopuszczone są originy HTTPS oraz HTTP dla `localhost` i adresów loopback.
Konfiguracja odrzuca `*`, wildcardy domen, origin `null`, dane logowania w URL,
ścieżki inne niż `/`, query i fragment. Hosty i porty domyślne są normalizowane,
a duplikaty usuwane. Błędna konfiguracja zatrzymuje tworzenie aplikacji.

Dozwolone metody CORS: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`.
Dozwolone nagłówki: `Content-Type`, `X-Jarvis-Key`, `X-Jarvis-Call-Token`.
`allow_credentials=False`; sesje nie korzystają z cookies. Niedozwolony preflight
otrzymuje `400`. CORS kontroluje dostęp przeglądarki do odpowiedzi, a autoryzacja
nadal jest wymagana: rzeczywiste żądanie z obcego origin może zostać obsłużone
przez serwer, lecz nie otrzyma nagłówka zezwalającego na odczyt przez przeglądarkę.

## Aktor i ślad audytowy

Pole `actor` w szczegółach zdarzenia jest ustalane przez backend z tożsamości
żądania. Klient nie może ustawić go dodatkowym polem JSON. Format:

| Tożsamość | `actor` |
| --- | --- |
| Klucz środowiskowy właściciela | `owner_key:owner-key` |
| Sesja konta | `session:<UUID użytkownika>` |
| Token usługowy | `service:<UUID tokenu>` |
| Brak ważnej tożsamości | `anonymous` |
| Operacja poza kontekstem żądania | Domyślnie `system`. |

Zdarzenia kont i sesji to `identity.user_created`, `identity.user_changed`,
`identity.login`, `identity.logout`, `identity.session_revoked`. Typowe logowanie
bez nagłówka ma aktora `anonymous`, także gdy się powiedzie; sukces zawiera
`subject` z UUID zalogowanego konta. Nieudane logowanie zapisuje `success:false`
bez podanej nazwy i hasła. Audyt tej próby zostaje zapisany przed zwróceniem `401`.

Odmowy `401`/`403` dla dopasowanych tras zapisują dodatkowo `security.denied`
z metodą, szablonem trasy i statusem. Nie zapisują pełnego URL, query, nagłówka
z sekretem ani treści żądania. Dane haseł, tokenów i ich skrótów nie trafiają do
zdarzeń tożsamości. Walidacja odrzucona przed wykonaniem endpointu nie jest
zdarzeniem logowania. Odrzucenia `429` przez zewnętrzny limiter nie dochodzą do
audytu żądań. Historię przez `GET /api/v1/audit` (ostatnie 100 wpisów) czyta tylko
właściciel; porządkowanie tabeli sesji nie usuwa zdarzeń audytu.

## Migracja SQLite 11 → 12 i ograniczenia

Przy starcie istniejącej bazy ze schematem niższym niż 12 i tabelą `plugins`
Core najpierw wykonuje kopię przez SQLite Backup API do
`<katalog bazy>/backups/before-schema12-<uuid>.sqlite3`. Następnie dodaje
`identity_users`, `identity_sessions`, indeks sesji użytkownika i ustawia
`PRAGMA user_version=12`. Istniejące dane oraz tokeny usługowe pozostają dostępne;
nie powstają automatycznie konta. Nowa pusta baza jest inicjalizowana od razu
w schemacie 12. Kolejny start bazy 12 nie tworzy ponownie kopii migracyjnej.
Schemat nowszy niż 12 jest odrzucany. Backup jest lokalnym plikiem z danymi
prywatnymi, a nie eksportem do zewnętrznej usługi.

Zakres tego etapu obejmuje lokalne konta i API. Nie ma SSO, resetowania ani zmiany
hasła przez API, osobnego interfejsu logowania kont ani izolacji prywatnych danych
między właścicielami. Obecny interfejs korzysta z pola klucza i przechowuje sekret
w pamięci karty. Przycisk wylogowania czyści tę pamięć, ale nie wywołuje
`/auth/logout`: po wklejeniu tokenu sesji jego unieważnienie wymaga endpointu API
lub decyzji właściciela. Obsługa kont przez UI pozostaje kolejną pracą. Limity
działają tylko w jednym procesie i nie stanowią rozproszonej ochrony przed
przeciążeniem. CORS nie konfiguruje TLS serwera.

Testy tego zakresu korzystają z baz tymczasowych, danych syntetycznych oraz
lokalnego serwera TCP. Nie potwierdzają działania produkcyjnego AutoLogika OS,
Supabase, prawdziwego Home Assistant, urządzeń ani zewnętrznego dostawcy SSO.
Zmiany w produkcji i uruchomienie rzeczywistych integracji wymagają osobnej
zgody właściciela.
