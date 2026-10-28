# Zadania AI z wieloma etapami — M3.5

Core0.10.4 udostępnia właścicielskie zadania z 1–4 jawnych etapów. Każdy etap korzysta z istniejącej pętli odczytów Ollama/OpenAI i ToolGateway. Poprzednie odpowiedzi trafiają do następnego etapu jako niezaufane dane; nie zmieniają praw, katalogu ani reguł. Plan pochodzi z żądania właściciela. Model nie tworzy harmonogramu, nie uruchamia kodu i nie wykonuje zapisów/sterowania. Zwykły czat, voice, prywatna pamięć PG i recepcja pozostają osobnymi ścieżkami.

Funkcja wymaga `JARVIS_TOOL_CHAT_ENABLED=true`, aktywnego wybranego dostawcy i lokalnie zatwierdzonych odczytów. Domyślnie jest wyłączona. Chmura wymaga dotychczasowej aktywacji i cen/budżetu; zadanie nie aktywuje konta ani nie instaluje modelu. Interfejs jest API; nie dodano osobnego panelu zadań.

## Żądania

Prefiks `/api/v1`, kompatybilny alias `/api`, uwierzytelnienie X-Jarvis-Key. Tylko aktualne konto owner lub klucz właściciela. Przypisanie do konta pochodzi z serwera; request nie przyjmuje owner/role/scope/session_id.

`POST /chat/tasks` zwraca202 z identyfikatorem i stanem. Przykład dla jawnie demonstracyjnego odczytu, bez sieci zewnętrznej:

```json
{
  "request_id": "a2f65be0-69b7-45a8-8bf9-c8f137e31c73",
  "model": "ollama",
  "tool_ids": ["mqtt.status"],
  "steps": [
    "Odczytaj demonstracyjny status MQTT i wskaż źródło.",
    "Podsumuj wynik i zaznacz, że nie sprawdzono fizycznych urządzeń."
  ]
}
```

Opcjonalny `model_name` musi należeć do katalogu. Backend przypina rozwiązany model podczas tworzenia; każdy etap ponownie waliduje jego dostępność. 1–8 unikalnych tool_ids, każde z dokładnym plugin.operation. Etap 1–8000znaków, plan łącznie do16000znaków. Puste/niepoprawnie zakodowane treści oraz dodatkowe pola są odrzucane przed I/O.

`GET /chat/tasks/{id}` zwraca status `queued/running/cancelling/completed/failed/cancelled`, liczniki etapów, fazę discovery/model/read, wyniki ukończonego zadania lub bezpieczny kod błędu.202 oznacza przyjęcie, nie ukończenie. Inne konto widzi404, odwołana sesja401. Nie pobiera automatycznie danych innych kont ani prywatnej historii. Wymagany jest identyfikator; nie ma wspólnej listy prywatnych zadań.

`POST /chat/tasks/{id}/cancel` zwraca202 i bieżący stan. Dla aktywnego zadania zgłasza anulowanie, przerywa oczekiwanie na model/odczyt, czyści wyniki i blokuje następne wywołania. `cancelling` oznacza trwające sprzątanie. Powtórne anulowanie zakończonego zadania zwraca jego rzeczywisty stan. Nie zmienia `completed` w fikcyjne `cancelled`. Anulowanie nie cofa wykonanych odczytów ani już wysłanego żądania do dostawcy; zdalna usługa może nadal je przetwarzać i naliczyć koszt. Nie ma automatycznego ponowienia.

## Limity i trwałość

- Dwa aktywne zadania i maksymalnie32rekordy na proces. Pętla ma wspólne dwa sloty z `/chat/tools`; przy braku miejsca kończy się429, bez kolejki i retry.
- Całe zadanie do180s; jeden etap do90s, maksymalnie4tury modelu i8odczytów. W całym planie najwyżej16tur i32odczyty; deadline może zakończyć przebieg wcześniej.
- Poprzednie odpowiedzi: do16000bajtów. Łączne zachowane wyniki:128KiB. Przekroczenie daje413, bez cichego obcięcia. Dotychczasowe limity schematów, argumentów, sieci i wyników narzędzi nadal obowiązują.
- Rezerwacja OpenAI przechodzi pomiędzy etapami. `JARVIS_OPENAI_MAX_REQUEST_USD` jest granicą rezerwacji **całego zadania**, nie każdego etapu osobno. Usage etapu zawiera jego tury i skumulowaną rezerwację; nie sumuj ponownie skumulowanych wartości. Jest to ostrożne oszacowanie, nie faktura. Nieudane/anulowane zadanie może mieć już płatne żądania mimo braku wyników.
- request_id zapewnia idempotencję per konto w okresie zachowania rekordu. Ten sam plan zwraca ten samid bez I/O; inny plan z tymUUID daje409. Po TTL lub restarcie pamięć identyfikatorów znika i ten sam UUID może rozpocząć nowe zadanie. Nie używaj ponowienia jako sprawdzenia statusu.
- Wszystkie plany/wyniki są w RAM jednego procesu. Wynik wygasa900s od zakończenia; odmowa dostępu i fizyczne usunięcie następują przy następnym odczycie/tworzeniu w rejestrze. Bez ruchu dane mogą pozostać w RAM do zamknięcia procesu. Brak trwałej kolejki, automatycznego wznowienia i współdzielenia między workerami. Uruchamiaj jeden worker; restart oznacza404 i nie dowodzi cofnięcia wcześniejszych odczytów.
- Lifespan aplikacji anuluje aktywne coroutine i czyści RAM. Token żądania pozostaje jedynie w wewnętrznej closure na czas zadania; nie trafia do API, audytu ani SQLite. Audyt przechowuje ID, stan i liczniki, bez tekstów/argumentów/wyników.

Autoryzacja konta, flagi/modelu i bieżąca konfiguracja pluginu są sprawdzane przed kolejnymi operacjami oraz po inferencji. ToolGateway sprawdza schemat i autoryzację także po ostatnim discovery MCP. Zmiana konfiguracji lub unieważnienie dostępu zatrzymuje przebieg; częściowe odpowiedzi są usuwane. Skuteczność przerwania zależy od współpracy transportu, dlatego nie obiecujemy natychmiastowego zatrzymania zdalnego procesu.

## Sprawdzenia

`tests/test_ai_tasks.py` sprawdza rzeczywistą pętlę i gateway z kontrolowanym dostawcą, wieloetapowość/provenance, idempotencję, izolację kont, odwołanie podczas modelu, budżet całego planu, zmianę pluginu, anulowanie w3fazach, capacity/TTL/timeout/shutdown i limity wyników.

`.venv/bin/python scripts/check_tool_chat.py --tasks --report docs/evals/ai-tasks-m35.json` uruchamia prawdziwy TCP Core, oba protokoły LLM i lokalne OpenAPI/MCP SDK: cztery kombinacje po2etapy, ponowienie bez dispatch i anulowanie podczas HTTP modelu przed odczytem. Runner korzysta z syntetycznych odpowiedzi, sekretów i danych; nie dowodzi jakości inferencji. Nie uruchamia produkcji AutoLogika/Supabase ani fizycznych urządzeń. Został dodany do istniejącego jobCI; wykonanie GitHub CI nie jest lokalnie deklarowane.
