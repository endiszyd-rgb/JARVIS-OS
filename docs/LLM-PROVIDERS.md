# Dostawcy LLM — M3.1

Czat korzysta ze wspólnego kontraktu `Provider.complete` w `jarvis/llm.py` i adapterów `OllamaProvider`/`OpenAIProvider` w `jarvis/llm_providers.py`. DEMO i lokalny parser pozostają oddzielne. Model jest wybierany jawnie lub przez zatwierdzone ustawienia; nie ma cichego zastąpienia niedostępnego modelu przez DEMO.

## Konfiguracja

Ollama zachowuje `OLLAMA_URL`, `OLLAMA_MODEL` i `OLLAMA_ALLOWED_MODELS`. Wysyłane są wiadomości do `/api/chat`, `stream:false` i `options.num_predict`. Limit wyjścia `JARVIS_LLM_MAX_OUTPUT_TOKENS` domyślnie1024, zakres1–32768. Żądanie nie pobiera modeli. Nazwy `:cloud` mogą występować w starszych sesjach, ale ich wykonywanie jest zablokowane: płatna chmura ma osobny adapter z jawnymi cenami.

OpenAI wymaga równocześnie `JARVIS_ALLOW_CLOUD_MODELS=true` i `JARVIS_OPENAI_ENABLED=true`, lokalnie ustawionego `JARVIS_OPENAI_API_KEY`, dodatnich cen wejścia/wyjścia `JARVIS_OPENAI_INPUT_USD_PER_MILLION`/`JARVIS_OPENAI_OUTPUT_USD_PER_MILLION` oraz dodatniego limitu `JARVIS_OPENAI_MAX_REQUEST_USD`. W repo oba przełączniki pozostają wyłączone, ceny i sekret puste. Zmiana domyślnego dostawcy w panelu nie aktywuje konfiguracji ani nie potwierdza dostępności konta.

Obsługiwane są `gpt-5.4-mini-2026-03-17` (domyślny przypięty model) i alias `gpt-5.4-mini`. Inne modele wymagają przeglądu kontraktu, cen i limitów. `JARVIS_OPENAI_URL` domyślnie wskazuje dokładnie `https://api.openai.com`; inny zdalny origin jest odrzucany. HTTP na loopback jest dopuszczony do izolowanego laboratorium protokołu. Publiczne HTTPS zachowuje proxy i CA środowiska; przekierowania i automatyczne ponawianie są wyłączone. Nie udostępniaj sekretu w URL ani w interfejsie.

## Koszt i ograniczenia

Ceny podaje się jako `Decimal` w USD za milion tokenów. Przed otwarciem transportu adapter rezerwuje koszt **pełnego okna400000tokenów wejścia oraz skonfigurowanego limitu wyjścia**. To celowo ostrożna granica oparta na kontrakcie obsługiwanego modelu. Nie szacujemy tokenów z liczby znaków i nie używamy sieciowego zliczania przed odmową budżetu. Może to odrzucić krótkie zapytanie, którego faktyczny koszt byłby mniejszy.

Przykład rachunku, nie automatyczny cennik: dla stawek0.75/4.50USD i wyjścia1024 rezerwacja wynosi0.304608USD. Operator musi sam sprawdzić obowiązującą taryfę, podatki i warunki konta. `max_completion_tokens`, `n:1` oraz `service_tier:default` ograniczają pojedyncze żądanie; narzędzia i dodatkowe płatne funkcje nie są wysyłane. Nie jest to dzienny budżet konta ani kontrola sumy równoległych żądań. Wymagana jest zgodność usługi z opisanym kontraktem modelu.

Odpowiedź API ma `usage.input_tokens`, `output_tokens`, `estimated_cost_usd`, `reserved_cost_usd` oraz `billing_verified:false`. Koszt jest obliczony z raportu usługi i konfiguracji, bez weryfikacji rachunku. Nie traktuj go jako faktury. Brak/błędny raport użycia, nieobsługiwana struktura, przerwana generacja lub wywołanie narzędzia powodują502, bez automatycznego retry. Żądanie mogło już zostać rozliczone przez usługę. Limity: wejście256KiB/64wiadomości, odpowiedź1MiB i tekst32000znaków, transport60s, całe wywołanie czatu90s.

## Dane i dostęp

Wybór chmury w panelu pokazuje informację o wysłaniu kontekstu. Tekstowy czat zachowuje dotychczasową pamięć właściciela i ograniczoną historię sesji. Podsumowanie warsztatu jest dołączane tylko jawnie. Sesje voice pozostają osobne i bez pamięci osobistej/ustawiania zachowania. Recepcja i embeddingi pozostają na swoich dotychczasowych, lokalnych ścieżkach.

Wysyłamy `store:false`; ten parametr nie jest gwarancją zerowej retencji wszystkich danych po stronie dostawcy. Audyt lokalny zapisuje wyłącznie dostawcę, liczniki i wyliczony koszt, bez treści wejścia/odpowiedzi i sekretów. Klucz pozostaje po stronie serwera. Katalog modeli jest lokalny i nie wykonuje żądań ani pobierania modeli. W razie błędu tura jest oznaczana jako nieudana, zgodnie z dotychczasowym mechanizmem rozmów.

## Źródła i dowody

Kontrakty sprawdzone26.10.2026: [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Ollama Chat](https://docs.ollama.com/api/chat). Ceny nie są automatycznie synchronizowane.

Testy: `tests/test_llm_cost.py`, `tests/test_llm_providers.py`, komponentyReact i `scripts/check_llm_browser.cjs` z `browser_llm_fixture.py`. Laboratoria używają prawdziwego lokalnego HTTP oraz syntetycznych odpowiedzi i kluczy. Nie są testem inferencji ani konta OpenAI. Dowody bieżącego etapu są w masterplanie; realne płatne API i jakość modeli pozostają NOT_RUN.

## M3.2 — osobny kontrakt tool-calling

`complete` i zwykły/chat zachowują dotychczasowy tekstowy kontrakt. Nowe, domyślnie wyłączone/chat/tools używa oddzielnego adaptera tur i ToolGateway. Wybór OpenAI jawnie wysyła również opisy/schematy oraz wyniki wybranych odczytów. Nie dołącza prywatnej pamięci i nie zapisuje historii. Cały przebieg musi zmieścić sumę konserwatywnych rezerwacji kosztów w JARVIS_OPENAI_MAX_REQUEST_USD. Bez budżetu dziennego i rozliczania równoległych przebiegów. Szczegóły: [TOOL-CALLING.md](TOOL-CALLING.md).
