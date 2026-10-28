# Konfiguracja modułów 0.3

## Pluginy: od manifestu do odczytu

1. W Integracjach zarejestruj manifest `{id,name,protocol,description}`. Protocol to `mcp` albo `openapi`; `demo` pozostaje symulacją.
2. Otwórz Konfiguracja. Ustaw endpoint, opcjonalnie `secret_env`, oraz `reviewed_read_tools` — dokładne nazwy narzędzi/operationId, które wcześniej sprawdziłeś jako odczyty. Dla OpenAPI podaj schemat w polu `openapi`.
3. Zapisz. Plugin zostaje wyłączony przy każdym zapisie konfiguracji. Włącz go po przeglądzie.
4. Wybierz Odkryj narzędzia, następnie wywołaj odczyt z argumentami JSON. Odkrywanie MCP łączy się z serwerem, OpenAPI korzysta z lokalnego schematu.

Przykłady działają z `examples/lab_server.py` bez kont i urządzeń. MCP obsługuje Streamable HTTP przez SDK 1.30; nie obsługuje uruchamiania lokalnych serwerów stdio, instalacji obcego kodu ani interaktywnego OAuth. W celu autoryzacji można wskazać zmienną `.env` np. `JARVIS_PLUGIN_SECRET_WEATHER`; Core odczytuje jej wartość i wysyła jako Bearer. W bazie i panelu przechowywana jest wyłącznie nazwa zmiennej. W Dockerze należy jawnie przekazać taką zmienną do usługi Core.

Obsługa OpenAPI jest celowo ograniczona: wersje 3.x, GET z unikalnym operationId, skalarne parametry path/query. Bez requestBody, `$ref`, `$dynamicRef`, `$recursiveRef`, tablic parametrów, plików, callbacków, arbitralnych nagłówków, cookie auth i pobierania schematu z URL. Pole servers nie ustala celu — decyduje endpoint skonfigurowany przez właściciela. Operacje zapisu są pomijane. Walidacja argumentów i blokady traversal odbywają się przed HTTP. Schematy bardziej złożone wymagają późniejszego rozszerzenia importera, a nie obejścia blokad.

**Read-only jest lokalną oceną właściciela, nie gwarancją zachowania obcego serwera.** Nazwa narzędzia, metoda GET i adnotacja MCP nie wystarczają jako dowód. Nie dodawaj do listy narzędzi sterujących domem, wysyłających wiadomości ani zmieniających finanse. Model nie nadaje tej listy i nie ma ścieżki do wywołania pluginu przez czat. Wyłączenie blokuje kolejne żądania; już rozpoczęte odczyty nie są anulowane.

## Sieć

`JARVIS_NETWORK_ALLOWLIST` domyślnie dopuszcza wyłącznie loopback (`127.0.0.0/8,::1/128`) dla nowych adapterów HA/MCP/OpenAPI. Dla konkretnej usługi LAN dodaj jej adres, np. `192.168.1.50/32`, zamiast całej sieci, jeżeli to możliwe. Brak wpisu powoduje odmowę połączenia. To ustawienie nie obejmuje dotychczasowych klientów Ollama i AutoLogiki — ich adresy nadal konfiguruje właściciel osobno.

Warstwa HTTP sprawdza origin, rozwiązuje DNS, weryfikuje wszystkie zwrócone adresy i łączy się z wybranym dozwolonym IP. Zachowuje Host i nazwę TLS/SNI do weryfikacji certyfikatu. Blokuje przejścia na inny origin i przekierowania, adresy link-local/unspecified/multicast oraz znane adresy metadata. Nie wyłącza walidacji certyfikatu. Odpowiedzi mają limit 1 MiB, połączenia timeout, sesja MCP całościowy timeout 25 s. Usługi z większymi odpowiedziami wymagają świadomego rozszerzenia limitów. HTTP w LAN nie szyfruje tokenów; dla dostępu poza zaufanym lokalnym środowiskiem używaj HTTPS.

## Tokeny dostępu

Panel Dostęp i tokeny pokazuje listę tokenów (bez sekretów), tworzy je i cofa. Sekret jest pokazywany raz. Baza przechowuje jego SHA-256, datę ważności, nazwę i zakresy. Token właściciela pozostaje w `.env` i jako jedyny może zmieniać konfigurację, akceptować propozycje i wydawać nowe tokeny. Utracony token zastąp nowym; istniejący cofnij.

| Zakres | Dopuszczone działanie |
|---|---|
| `status:read` | Stan i liczniki |
| `scheduler:tick` | Sprawdzenie terminów lokalnych przypomnień |
| `home:read` | Odczyt encji HA z globalnej allowlisty |
| `plugins:read` | Lista pluginów i discovery włączonych transportów |
| `plugins:invoke` | Wywołanie odczytów pluginów z list właściciela |
| `messages:read` | Odczyt inboxu i szkiców WhatsApp |
| `messages:draft` | Utworzenie niewysyłanego szkicu |

To wciąż jeden właściciel i tokeny usług, nie konta wielu pracowników ani OIDC. `plugins:invoke` obejmuje wszystkie włączone, lokalnie sprawdzone odczyty; nie jest per-plugin/per-record. Backup bazy zawiera także skróty ważnych tokenów. Po odtworzeniu starej kopii zweryfikuj i ponownie cofnij tokeny unieważnione po dacie tej kopii.

Dla workera i n8n wystarczy `scheduler:tick`. Worker czyta JARVIS_SCHEDULER_TOKEN; nie stosuje klucza właściciela jako fallback. Szablon workflow n8n pozostaje nieaktywny; przypisz HTTP Header Auth i sprawdź import w swojej wersji przed aktywacją. Uruchamianie workera i n8n jednocześnie nie powinno duplikować powiadomień: tick serializuje transakcję i przesuwa next_run.

## Home Assistant

W `.env`:

```dotenv
HA_READONLY_ENABLED=true
HA_URL=http://192.168.1.50:8123
HA_TOKEN=TU_TOKEN_HA
HA_ALLOWED_ENTITIES=sensor.workshop_temperature,binary_sensor.gate_closed
JARVIS_NETWORK_ALLOWLIST=127.0.0.0/8,::1/128,192.168.1.50/32
```

Po zmianie zrestartuj Core. Panel Dom i czujniki wyświetla tylko dozwolone encje. API ma GET listy i GET konkretnej encji. Nie ma trasy wywołującej `/api/services` i nie ma konfiguracji odblokowującej fizyczne komendy. Zasięg uprawnień tokenu samego HA należy ograniczyć po stronie HA; filtr Core nie zmienia jego uprawnień w źródłowym systemie.

## Twilio WhatsApp: odbiór, bez wysyłki

Skonfiguruj zatwierdzony sender albo środowisko Messaging Sandbox zgodnie z dokumentacją konta. Sandbox wiadomości nie oznacza Calling. W `.env`:

```dotenv
TWILIO_WEBHOOK_ENABLED=true
TWILIO_PUBLIC_ORIGIN=https://twoj-adres.example
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+48...
WHATSAPP_ALLOWED_SENDERS=whatsapp:+48...
```

Dokładny URL webhooka w Twilio: `https://twoj-adres.example/webhooks/twilio/whatsapp`, POST form-urlencoded, bez query string. Sekret podpisu to Auth Token konta, nie dowolny API secret. Reverse proxy ma wystawić tylko ten webhook; nie udostępniaj publicznie panelu i całego Core w obecnym MVP. Publiczny adres walidacji jest ustalony w konfiguracji, a nie wyliczany z Host/X-Forwarded-Host.

Podpis weryfikuje oficjalny RequestValidator Twilio na wszystkich polach formularza. Sprawdzane są AccountSid, odbiorca, allowlista nadawców i format MessageSid. Nie pobieramy załączników; puste Body może oznaczać wiadomość multimedialną, której treści nie obsługujemy w 0.3. Endpoint obsługuje wiadomości przychodzące, nie jest uniwersalnym handlerem statusów, zgód Calling czy innych produktów Twilio.

MessageSid jest kluczem deduplikacji w osobnej tabeli receipts. Usunięcie treści z inboxu nie usuwa receipt, więc ponowne dostarczenie nie przywróci wiadomości. Audyt nie przechowuje treści wiadomości. Treści są jawne w lokalnej bazie i jej backupach. Nie ma automatycznych odpowiedzi, wykonywania poleceń, wysyłki ani połączeń. Endpoint oddaje pusty TwiML Response. Szkice powstają w panelu/API i można je usunąć; nie istnieje endpoint send.

Nie wdrażamy publicznego webhooka w tej turze i nie aktywujemy kont. Wymagania Calling pozostają w OPERACJE.md i nie są omijane przez ten moduł.

## Źródła techniczne sprawdzone 22.10.2026

- Oficjalny MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk — kod zainstalowanej, przypiętej wersji 1.30.0 i testy sesji Streamable HTTP.
- OpenAPI: https://spec.openapis.org/oas/v3.1.1.html — struktura operationId, paths i parametrów; implementacja obsługuje opisany powyżej podzbiór.
- Home Assistant REST: https://contributors.home-assistant.io/core/internals/rest-api/ — GET stanów i Bearer token.
- Twilio Security: https://www.twilio.com/docs/usage/security — podpisy i oficjalny walidator.
