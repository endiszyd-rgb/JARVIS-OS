# Kontrolowana pętla odczytów — M3.2

Core 0.10.1 ma osobne API `POST /api/v1/chat/tools` (także `/api/chat/tools`). Zwykły `/chat`, czat React i rozmowa głosowa nadal nie uruchamiają narzędzi. Nowy przepływ jest dostępny przez API; nie dodano przełącznika w GUI. Nie wymaga zmiany schematu SQLite12 ani PostgreSQL1.

## Uruchomienie i kontrakt

Domyślnie `JARVIS_TOOL_CHAT_ENABLED=false`. Właściciel może ustawić `true` w konfiguracji serwera; Compose przekazuje tę wartość. Endpoint wymaga aktualnego klucza właściciela lub sesji konta owner. Token usługi z `plugins:invoke` nie daje dostępu do rozmowy właściciela. Kanały klientów i voice nie korzystają z tego API.

Właściciel wybiera od jednego do ośmiu unikalnych ID z rejestru. `GET /api/v1/tools` pokazuje katalog lokalny bez sieci; dla MCP jawne `GET /api/v1/plugins/{id}/tools` wykonuje discovery. Przykładowe ciało dla lokalnego modelu Ollama obsługującego function calling:

```json
{
  "message": "Odczytaj wybrany status; zaznacz, jeśli wynik jest demonstracyjny.",
  "model": "ollama",
  "tool_ids": ["mqtt.status"]
}
```

`model_name` jest opcjonalne i musi należeć do skonfigurowanej allowlisty modeli. `mqtt.status` to syntetyczny adapter DEMO, bez połączenia z brokerem. Rzeczywiste odczyty wymagają skonfigurowanego, włączonego pluginu OpenAPI/MCP i lokalnie zatwierdzonej operacji. Wskazanie ID narzędzia MCP w tym żądaniu upoważnia do ograniczonego discovery właśnie tego pluginu; lista jest sprawdzana ponownie przed wykonaniem. Nie ma instalowania kodu ani przeszukiwania innych pluginów.

Dla OpenAI wybór `model: "openai"` dodatkowo wymaga wszystkich przełączników, klucza, cen i budżetu z [LLM-PROVIDERS.md](LLM-PROVIDERS.md). Wybór chmury wysyła do dostawcy treść tego żądania, opisy i schematy wybranych narzędzi oraz ich wyniki. Nie dołączamy prywatnej pamięci, ustawień, sekretów, historii zwykłego czatu ani podsumowania warsztatu. Właściciel może sam zawrzeć dane prywatne w pytaniu lub wybrać odczyt zwracający takie dane — należy uwzględnić to przy wyborze dostawcy. `store:false` nie stanowi obietnicy zerowej retencji po stronie usługi.

Odpowiedź zawiera `reply`, dostawcę/model, liczbę tur, metadane wykonanych wywołań (`id`, `tool_id`, `protocol`, `schema_digest`) i `usage.turns`. `private_memory_attached:false` oraz `history_saved:false` opisują tę odrębną, nietrwałą rozmowę. Nie dopisujemy jej do sesji ani automatycznej pamięci. Audyt zapisuje aktora, nazwy zatwierdzonych operacji, statusy i liczniki/koszty, bez treści pytania, argumentów i wyników. Odpowiedź modelu jest tekstem wygenerowanym, a nie dowodem wykonania działania; potwierdzeniem odczytów są metadane i audyt.

## Granice wykonania

- Maksymalnie 4 odpowiedzi dostawcy i 8 wywołań narzędzi na żądanie. Czwarta odpowiedź musi kończyć rozmowę tekstem; kolejne narzędzia nie zostaną wykonane.
- Dwie równoległe rozmowy na proces, bez kolejki; zajęte miejsca zwracają429. Całość, łącznie z discovery, ma timeout90s. Poszczególne transporty zachowują własne krótsze granice i zwalniają zasoby po anulowaniu.
- Do256KiB serializowanego kontekstu wraz z opisami/schematami przed kolejnym żądaniem LLM; wynik pojedynczego narzędzia do32KiB w kontekście. Zbyt duży wynik kończy pętlę bez wysyłania go modelowi. Gateway nadal ogranicza odpowiedź transportu do1MiB.
- Argumenty do64KiB,512węzłów i głębokości16, sprawdzane według serwerowego JSON Schema. Schematy zachowują ograniczenia rejestru (m.in. bez refs i regex). Cała lista wywołań modelu jest walidowana przed pierwszym dispatch z tej listy.
- Model dostaje wyłącznie aliasy wybranych narzędzi. Nie może przekazać Principal, roli, scope, nowego endpointu ani listy zezwoleń. Nieznany alias, dodatkowe pola struktury, wadliwe argumenty lub powtórzone ID kończą pętlę przed wykonaniem listy. Unikalność ID dotyczy jednego przebiegu; nie jest semantyczną deduplikacją odczytów.
- Backend ponownie sprawdza aktualną sesję/rolę, aktywację funkcji i allowlistę modelu przed kolejnymi krokami oraz przed zwrotem odpowiedzi. Przed wykonaniem ponownie czyta stan pluginu i porównuje konfigurację z wybraną na początku. Gateway sprawdza autoryzację, zatwierdzenie odczytu i schemat; transport MCP porównuje też ostatni odkryty schemat i ponawia kontrolę uprawnień po discovery, przed `call_tool`.
- Wynik trafia do modelu jako rola `tool`, z opakowaniem `untrusted_tool_data`. Wstrzyknięte w nim `role:system`, instrukcje lub wywołania są wyłącznie danymi. Następna propozycja modelu podlega tym samym ograniczeniom. Ochrona uprawnień nie polega na samym system prompt.

Nie ma zapisu, sterowania fizycznego, wykonywania kodu, wysyłania wiadomości, automatycznej akceptacji propozycji ani autoretry/fallbacku. Lokalnie zatwierdzony odczyt MCP wymaga zaufania do zachowania serwera; adnotacje i hash schematu nie dowodzą braku skutków ubocznych. Kontrole są wykonywane przed wysłaniem operacji, lecz nie mogą wycofać już wysłanego odczytu ani atomowo zablokować zdalnej usługi na czas zmiany lokalnych uprawnień. Przy błędzie późniejszego kroku wcześniejsze odczyty pozostają w audycie.

## Koszt i błędy

OpenAI rezerwuje przed każdą odpowiedzią koszt pełnego obsługiwanego kontekstu400000tokenów plus limit wyjścia. Suma tych rezerwacji dla całej pętli musi mieścić się w `JARVIS_OPENAI_MAX_REQUEST_USD`; ta sama wartość nadal ogranicza pojedynczy zwykły request. Przykładowo przy cenach0.75/4.50USD za1M i wyjściu1024tokeny rezerwacja jednej odpowiedzi wynosi0.304608USD, dwóch0.609216USD. Są to przykładowe ceny konfiguracyjne, nie automatycznie ustalony cennik.

Limit może ostrożnie odmówić krótkiej rozmowy. Nie jest budżetem dziennym, wspólnym limitem równoległych przebiegów ani weryfikacją faktury. Wcześniejsze żądania mogą być naliczone także wtedy, gdy kolejny krok zostanie odrzucony. Usage pochodzi z raportu dostawcy, `billing_verified:false`. Ollama `:cloud` jest blokowana; brak przypisanej ceny nie oznacza darmowego wykonania chmurowego.

401/403 oznaczają brak aktualnej tożsamości/zgody lub przekroczenie budżetu,409 zmianę konfiguracji/schematu lub koniec limitu tur,413 zbyt duży kontekst,422 wadliwy kontrakt wejściowy,429 zajęte miejsca,502 wadliwą odpowiedź/plan/wynik,504 timeout. Nie ponawiamy automatycznie. To API jednego przebiegu, bez trwałego joba, wznowienia i klucza idempotencji. Odłączenie klienta HTTP nie jest potwierdzeniem anulowania serwera; ponowne wysłanie jest nowym przebiegiem.

## Weryfikacja i ograniczenia

`tests/test_tool_plan.py`, `test_tool_chat.py`, `test_network_query.py` oraz dodatkowe testy transportów sprawdzają schematy, pełne listy, injection, replay/limity, cofnięcie sesji, zmianę konfiguracji/schematu, brak uprawnień z tokena usługi, timeout/cancel/capacity i prywatność. `scripts/check_tool_chat.py` uruchamia rzeczywiste lokalne TCP Core, syntetyczne protokoły Ollama/OpenAI oraz OpenAPI i oficjalny SDK MCP. Cztery kombinacje dostawca×protokół wykonują odczyt i drugą turę; dodatkowy atak jest odrzucany przed wykonaniem całej listy. Raport: [tool-chat-m32.json](evals/tool-chat-m32.json).

Testy protokołów korzystają z syntetycznych odpowiedzi. Prawdziwa inferencja i jakość wyboru narzędzi, konto OpenAI, odporność samego tekstu modelu na dowolne manipulacje, urządzenia i produkcja pozostają NOT_RUN. Nie obiecujemy pełnego rozwiązania prompt injection na podstawie poprawnej izolacji uprawnień. Nowy przepływ nie dodaje przycisków do React, głosu ani kanału recepcji.

Oficjalne kontrakty sprawdzone26.10.2026: [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling), [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling). OpenAI ma argumenty JSON-string i `tool_call_id`; Ollama obiekt argumentów i `tool_name`, obsługujemy opcjonalne `type:function`/`function.index`. Brak streamingu i automatycznego pobierania modeli.
