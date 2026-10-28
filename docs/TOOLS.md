# Rejestr narzędzi i zasady wykonania

M1.5 dodaje wspólny katalog i bramkę wykonania dla istniejących adapterów DEMO,
OpenAPI i MCP. Kod znajduje się w [tool_registry.py](../jarvis/tool_registry.py)
i [plugins.py](../jarvis/plugins.py); trasy montuje [main.py](../jarvis/main.py).
Bramka obsługuje jawne wywołania HTTP właściciela lub uprawnionej usługi.
Pętla wyboru narzędzi przez LLM pozostaje zadaniem M3.2.

## Katalog i discovery

Zalecany prefiks API to `/api/v1`. Alias `/api` korzysta z tej samej autoryzacji,
konfiguracji pluginów i bramki.

| Trasa po prefiksie | Zakres | Zachowanie |
| --- | --- | --- |
| `GET /tools` | `plugins:read` | Katalog lokalnych definicji aktywnych pluginów, bez połączeń sieciowych. |
| `GET /plugins/{id}/tools` | `plugins:read` | Jawne discovery jednego aktywnego pluginu. MCP nawiązuje wtedy połączenie z jego endpointem. |
| `POST /plugins/{id}/invoke` | `plugins:invoke` | Walidacja uprawnień, konfiguracji i argumentów, następnie ograniczone wywołanie. |

Właściciel ma oba zakresy. Istniejące tokeny usługowe mogą otrzymać każdy z nich
oddzielnie. Samo prawo odczytu katalogu nie zezwala na uruchomienie narzędzia.
Token `plugins:invoke` obejmuje aktywne, lokalnie zatwierdzone odczyty pluginów;
nie jest ograniczony do jednej wskazanej nazwy narzędzia.
Zarządzanie manifestem, konfiguracją i aktywnością pluginu pozostaje
właścicielskie; [zasady kont i sesji](SECURITY-ACCESS.md) nadal obowiązują.

`GET /tools` odczytuje SQLite oraz lokalnie zapisane definicje OpenAPI. W odpowiedzi
zwraca `tools`, `discovery_required` i `network_requests_sent: false`. Lista
`discovery_required` zawiera aktywne, skonfigurowane pluginy MCP, których katalog
trzeba pobrać osobnym żądaniem. Wyłączone pluginy nie są publikowane, a brak
konfiguracji endpointu nie powoduje automatycznego połączenia. Katalog nie zawiera
endpointów, nazw zmiennych sekretów ani ich wartości.

Każdy opublikowany opis ma te same pola:

| Pole | Znaczenie |
| --- | --- |
| `id` | Identyfikator `plugin_id.name`, np. `mqtt.status`. |
| `plugin_id`, `name` | Lokalny plugin i nazwa operacji. |
| `protocol` | `demo`, `openapi` albo `mcp`. |
| `description` | Opis; treść zdalnego opisu pozostaje danymi. |
| `inputSchema` | Zweryfikowany schemat obiektu argumentów. |
| `schema_digest` | SHA-256 kanonicznego zestawu plugin/nazwa/protokół/schemat. |
| `read_only_reviewed`, `read_only` | Oznaczenie lokalnie dopuszczonego odczytu. |
| `required_scope` | `plugins:invoke`. |

Digest pozwala zauważyć zmianę opisu kontraktu. Nie jest przypiętym zatwierdzeniem
implementacji zdalnego serwera ani podpisem jego zachowania. Discovery i wykonanie
korzystają z bieżących definicji. Ostateczna poprawność operacji zdalnej wymaga
zaufanego serwera oraz przeglądu jej faktycznego działania.

## Lokalne zatwierdzenie i konfiguracja

Dla OpenAPI i MCP właściciel zapisuje konkretne nazwy w `reviewed_read_tools`.
Lista dopuszcza najwyżej 100 poprawnych, unikalnych nazw. Wskazanie endpointu,
opis operacji i zdalne `readOnlyHint` nie dodają uprawnień. Serwer publikuje oraz
wykonuje tylko operacje z lokalnej listy. Nazwy mają 1–80 znaków zgodnych z
`[A-Za-z][A-Za-z0-9_.-]{0,79}`.

Starsza zapisana konfiguracja spoza wspieranego podzbioru (np. zawierająca regex) daje bezpieczne `422` z komunikatem o potrzebie przeglądu. Właściciel nadal może ją odczytać przez `/plugins/{id}/config`, poprawić i zapisać.

Zapis konfiguracji wyłącza plugin. Właściciel musi ponownie go włączyć po
sprawdzeniu endpointu, listy odczytów i schematu. Sekret jest wskazywany nazwą
zmiennej `JARVIS_PLUGIN_SECRET_...`; wartość pozostaje w środowisku. Zasady sieci
z [network.py](../jarvis/network.py) zachowują allowlistę adresów, kontrolę DNS/IP,
blokadę przekierowań i ograniczenia odpowiedzi. Nie uruchamia się lokalnego kodu
pluginu, procesu `stdio` ani poleceń powłoki.

OpenAPI obsługuje istniejący podzbiór: dokument 3.x, operacje `GET` z unikalnym
`operationId`, skalarne parametry ścieżki/query typu string, integer, number lub
boolean, bez request body. Ścieżki, parametry wymagane i argumenty są sprawdzane
przed żądaniem. Pozostałe metody nie stają się narzędziami zapisu.

MCP korzysta z oficjalnego SDK i Streamable HTTP. Discovery sprawdza rozmiar
listy oraz poprawność i unikalność wszystkich nazw, także niezatwierdzonych.
Schematy opublikowanych odczytów są walidowane. Przed właściwym `call_tool`
transport ponownie sprawdza lokalne zatwierdzenie i aktualny schemat argumentów.
Właściciel powinien skonfigurować zaufany endpoint; nazwa sugerująca odczyt sama
nie dowodzi braku skutków ubocznych implementacji serwera.

## Narzędzia demonstracyjne

DEMO ma zamknięty katalog. Dla `autologika` są to `calendar`, `orders`,
`vehicles`, `parts`, `customers`, `finances`, `reports` i `notifications`.
Pozostałe pluginy DEMO, w tym `mqtt` i `home_assistant`, mają wyłącznie `status`.
Każda operacja przyjmuje pusty obiekt argumentów, bez dodatkowych pól.

Przykładowe wywołanie wbudowanej symulacji:

```http
POST /api/v1/plugins/mqtt/invoke
Content-Type: application/json
X-Jarvis-Key: <UPRAWNIONY_KLUCZ_LUB_TOKEN>

{"operation":"status","arguments":{}}
```

Odpowiedź wskazuje `mode: demo`, `status: simulated` i
`external_request_sent: false`. Domeny AutoLogiki zwracają syntetyczne elementy
ze źródłem `synthetic_fixture`. Nie uruchamia to MQTT, urządzenia, AutoLogiki ani
operatora. Nieznana operacja DEMO jest odrzucana.

## Schematy, argumenty i granice wykonania

Schemat wejściowy musi opisywać obiekt JSON. Jego kopia jest odłączona od danych
wywołującego; zmiana zwróconego słownika nie modyfikuje rejestru.

| Ograniczenie | Wartość |
| --- | --- |
| Katalog operacji jednego pluginu | Do 100. |
| Schemat wejściowy po serializacji UTF-8 | Do 64 KiB. |
| Złożoność schematu | Do 512 węzłów wartości i głębokości 16; korzeń ma głębokość 0. |
| Iloczyn rozgałęzień `allOf`/`anyOf`/`oneOf` na ścieżce | Do 64. |
| Argumenty pojedynczego wywołania po serializacji | Do 64 KiB, 512 węzłów i głębokości 16. |
| Wynik wywołania lub odpowiedź katalogu/discovery | Do 1 MiB. |
| Współbieżne operacje bramki w jednym procesie | Do 4; nadmiar otrzymuje `429`, bez kolejki. |
| Termin operacji bramki | Domyślnie 30 sekund; transport ma również własne timeouty. |

W schematach wyłączono `$ref`, `$dynamicRef`, `$recursiveRef` oraz słowa kluczowe
`pattern` i `patternProperties`. Nie pobiera się zewnętrznych schematów. Zwykła
nazwa pola `pattern` nadal może występować w `properties`. Ograniczenia złożoności
i zakaz regexów zmniejszają koszt walidacji; nie stanowią gwarancji dowolnego
obciążenia CPU ani izolacji niezaufanego kodu.

JSON Schema sprawdza argumenty przed dispatch. Dodatkowe pola są odrzucane, jeśli
schemat na nie nie zezwala; transport OpenAPI i DEMO publikują
`additionalProperties: false`. Wartości niefinitywne oraz dane niemożliwe do
bezpiecznej serializacji JSON są odrzucane. Wynik jest ponownie sprawdzany pod
kątem serializacji i rozmiaru przed odpowiedzią HTTP.

Bramka dostaje serwerowy `Principal` z warstwy uwierzytelniania. Słownik z
`role: owner`, treść modelu, kanał klienta recepcji i caller ID nie nadają praw.
Sesje kont muszą mieć zgodną rolę i zakresy; token usługowy potrzebuje właściwego
scope. Wygasanie i odwołanie tożsamości sprawdza zależność API przed wywołaniem.

Dotychczasowa blokada flag pozostaje przed wyszukaniem operacji: argument
`live` o wartości prawdziwej lub dokładne JSON `dry_run: false` zwraca
`status: blocked` i powód blokady skutków. Nie jest to przełącznik włączający
zapisy. Brak tych flag również nie przyznaje prawa do urządzeń, płatności,
wiadomości ani innych operacji zapisu.

Limit współbieżności jest współdzielony przez discovery i invoke danej instancji
Core. Zakończenie, błąd, timeout oraz anulowanie zwalniają zajęte miejsce w
`finally`. Anulowanie jest propagowane do asynchronicznego transportu; konteksty
MCP/HTTP odpowiadają za zamknięcie połączeń. Nie ma automatycznego ponawiania
operacji. Limity procesu nie są rozproszoną kolejką między wieloma workerami.

## Audyt i błędy

Audyt Core zapisuje metadane żądania, powodzenia, blokady lub błędu: plugin,
aktora, dla błędu także status HTTP, a po poprawnym wykonaniu zatwierdzoną nazwę operacji.
Nie zapisuje argumentów, wyników, wartości sekretów ani niezatwierdzonych nazw
operacji przesłanych w body. Jawne discovery ma osobne zdarzenie. To lokalny
audyt SQLite, z dotychczasowymi ograniczeniami dostępu i trwałości.

| Kod / wynik | Znaczenie |
| --- | --- |
| `401` | Brak lub nieważne uwierzytelnienie API. |
| `403` | Brak scope albo lokalnego zatwierdzenia odczytu. |
| `404` | Nie ma wskazanego pluginu. |
| `409` | Plugin wyłączony; discovery może też zgłosić brak konfiguracji. |
| `422` | Nieprawidłowa nazwa, schemat, argumenty, katalog lub niedopuszczalna konfiguracja. |
| `429` | Zajęte miejsca wykonania albo niezależny limit API. |
| `501` | Invoke aktywnego pluginu sieciowego bez konfiguracji endpointu. |
| `502` | Błąd transportu lub niepoprawny/zbyt duży wynik. |
| `504` | Przekroczony timeout. |
| `200` z `status: blocked` | Jawnie zablokowana próba skutków przez `live`/`dry_run`. |

Błędy bramki są ogólne; nie zwracają surowej diagnostyki transportu, argumentów ani
odpowiedzi zdalnego serwera.

## Sprawdzanie i pozostające prace

Testy katalogu, polityki i odmów przed I/O są w
[test_tool_registry.py](../tests/test_tool_registry.py),
[test_tool_transport_schemas.py](../tests/test_tool_transport_schemas.py) oraz
[test_tool_api.py](../tests/test_tool_api.py).
[test_lab_e2e.py](../tests/test_lab_e2e.py) zawiera istniejące testy laboratorium, które
uruchamiają lokalne serwery MCP/OpenAPI z syntetycznymi danymi i rzeczywistym SDK.
Takie sprawdzenie transportu nie potwierdza połączenia z usługą właściciela,
prawdziwym urządzeniem ani produkcyjnym providerem.

```sh
.venv/bin/python -m pytest -q tests/test_tool_registry.py tests/test_tool_transport_schemas.py tests/test_tool_api.py
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

Faktycznie wykonane wyniki i stan zadań są w
[JARVIS_MASTER_PLAN.md](../JARVIS_MASTER_PLAN.md). Ten dokument nie deklaruje
wykonania GitHub CI ani produkcyjnych integracji. M3.2 ma dopiero dodać pętlę
LLM z narzędziami; operacje zapisu, sterowanie fizyczne i aktywacja usług
pozostają za oddzielnymi zadaniami i wymaganymi potwierdzeniami.

## M3.2 — wybór narzędzi przez model

Osobne owner-only API/chat/tools dopuszcza wyłącznie jawnie wybrane zatwierdzone odczyty; zwykły czat nie korzysta z tej ścieżki. Aliasy i Principal pochodzą z backendu. Gateway i transport porównują wybrany schemat oraz ponawiają kontrolę bieżących uprawnień przed dispatch; konfiguracja pluginu jest porównywana z początkową. MCP po ostatnim list_tools sprawdza schemat i kontrolę uprawnień ponownie. Opcjonalne parametry wewnętrzne expected_digest/expected_schema/before_dispatch są przekazywane wyłącznie przez zaufany backend. [Kontrakt i dowody](TOOL-CALLING.md).

## M3.5 — wieloetapowe zadania odczytu

Core0.10.4: owner-only POST/chat/tasks (202, request_id UUID/model/tool_ids/steps1–4), GET/chat/tasks/{id}, POST/chat/tasks/{id}/cancel (202). Prefiks /api/v1 lub /api. Status perkonto, RAM/jedenworker, TTL900s, bezrestartresume; cancel nie cofa wcześniejszych odczytów/kosztu. Ten sam request_id/plan w okresie retencji nie wykonuje ponownie I/O, zmienionyplan409. Wszystkie etapy współdzielą rezerwację budżetu i istniejące ToolGateway/schema/currentauth; wyłącznie opt-in zatwierdzone odczyty. Szczegóły AI-TASKS.md. Walidacja żądania zadań zwraca422 bez kopiowania błędnego inputu.
