# Analiza recepcji przez model — 0.8

## Rzeczywista implementacja i granice

Dodano opcjonalne wywołanie Ollama `/api/chat` z parametrem `format` zawierającym JSON Schema. Oficjalny opis mechanizmu: https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx (sprawdzone 22.10.2026). Core dodatkowo sam waliduje odpowiedź; zgodny JSON nie oznacza poprawnego rozumienia rozmowy.

To rozszerzenie właścicielskiego laboratorium, nie publiczny endpoint telefonu. Rozmowy na żywo, analiza audio, operator i rzeczywisty transfer nie są podłączone. Nie uruchomiono rzeczywistego modelu w tym środowisku. Testy używają kontrolowanego transportu HTTP i lokalnego serwera odpowiedzi, więc dowodzą działania protokołu i walidacji, a nie jakości polskiej inferencji.

## Konfiguracja

Wymagany Python3.12, lokalna/świadomie skonfigurowana usługa Ollama i już zainstalowany model wspierający odpowiedzi według schematu. Model musi być wpisany w OLLAMA_ALLOWED_MODELS. Brak automatycznego pobierania i instalowania modeli.

```
JARVIS_RECEPTION_AI_ENABLED=true
OLLAMA_RECEPTION_URL=http://127.0.0.1:11434
OLLAMA_RECEPTION_MODEL=qwen2.5:3b
OLLAMA_ALLOWED_MODELS=qwen2.5:3b
```

Przykładowa nazwa jest punktem konfiguracji, nie obietnicą odpowiedniej jakości na polskich rozmowach lub sprzęcie użytkownika. Dopasowanie RAM/VRAM i jakość należy ocenić. Modele z sufiksem :cloud są w tym module zabronione niezależnie od ustawienia osobistego czatu. URL to origin bez ścieżki, danych logowania i parametrów. Obowiązują sieciowa allowlista, przypięcie IP i brak przekierowań. Domyślnie loopback; dodatkowy adres jest świadomą konfiguracją operatora. Reverse proxy wskazane przez operatora może kierować dane dalej, więc sam brak :cloud nie jest dowodem całkowicie lokalnego przetwarzania.

W Dockerze localhost jest kontenerem. Użyj właściwego adresu hosta i jawnego CIDR w JARVIS_NETWORK_ALLOWLIST. Compose przekazuje trzy nowe zmienne. Nic nie aktywuje kont telekomunikacyjnych ani przekierowania Play.

## Przebieg

W Recepcja · laboratorium rozpocznij test, wpisz wypowiedź i wybierz „Analizuj wypowiedź przez AI”. Zwykły przycisk wypowiedzi nadal korzysta z haseł/scenariuszy 0.7. Tryby nie mieszają się automatycznie: awaria AI nie przechodzi po cichu do haseł.

Model otrzymuje do 10 ostatnich wiadomości, ograniczonych łącznie do 12000 znaków, i aktualną wypowiedź do 4000 znaków. Wiadomości są materiałem do analizy; nie są instrukcjami. Nie wysyła się osobistej pamięci/czatu, konfiguracji właściciela, numeru właściciela, wewnętrznego briefingu ani danych AutoLogiki. Treść klienta może sama zawierać dane osobowe — trafiają do skonfigurowanej usługi. Retencja/logi tej usługi wymagają osobnej konfiguracji.

Wynik modelu ma: kind (routine/contact_requested/insistent/crisis/unclear), confidence (low/medium/high), evidence i facts. Każdy dowód wskazuje message_index i dosłowny cytat z wypowiedzi klienta. Ocena inna niż routine/unclear wymaga dowodu z bieżącej wypowiedzi. Fakty name/phone/vehicle/issue/preferred_time muszą dosłownie występować w swoim cytacie. Nie akceptujemy parafraz, dopisywania numeru kraju, nieznanych pól, duplikatów tego samego pola ani cytatów z asystenta. Telefon można jedynie oczyścić ze spacji, nawiasów i myślników, jeśli pełne + i kraj są w źródle.

Sama zgodność cytatu nie dowodzi, że klient mówi prawdę ani że model właściwie zrozumiał negację, osobę lub kontekst. Nazwa „evidence checked” oznacza sprawdzenie pochodzenia tekstu, nie weryfikację faktu. Dane zgłoszenia nadal wymagają sprawdzenia przez człowieka. Błędne, ale dosłownie poparte interpretacje pozostają możliwe.

## Egzekwowanie przez backend

- Tylko confidence=high może zaproponować skuteczną klasyfikację lub automatycznie uzupełnić fakty. Medium/low → unclear i pytanie o doprecyzowanie. Wartość confidence to deklaracja modelu, nie skalibrowane prawdopodobieństwo.
- Jeśli model od razu mówi insistent, a nie było wcześniejszej rozpoznanej prośby, backend traktuje to jako pierwszą prośbę o właściciela. Drugie żądanie wymaga kontekstu i następnej oceny.
- Harmonogram/DND/urlopy i akceptacja właściciela są nadal poza modelem. Model nie ustala godzin ani numerów, nie zmienia polityki, nie wykonuje urządzeń i nie potwierdza ceny/rezerwacji.
- Przed inferencją odrzucane są stare rewizje, zakończone rozmowy i duplikaty. Dokładne ponowienie zakończonego zdarzenia zwraca stan bez kolejnej inferencji.
- Inferencja jest poza transakcją SQLite. Przy zapisie rewizja jest ponownie sprawdzana: jeśli w trakcie zakończono/zmieniono rozmowę, wynik odrzucany z 409.
- Wykorzystuje bieżącą politykę w momencie zapisu i ponownie przy przyjęciu właściciela. Zmiana DND podczas analizy nadal blokuje eskalację.
- Niepoprawny wynik/awaria/niekompletna odpowiedź → 502, limit całej analizy → 504; rozmowa pozostaje bez zmiany. Nie zapisujemy surowych błędów serwera modelu.

Analiza ma limit 65 s, odczyt 64 KiB i tekst odpowiedzi 24000 znaków; generacja ograniczona num_predict=1800, temperatura 0. Trwała historia recepcji zawiera zweryfikowane dowody i proponowaną ocenę; audyt nadal zawiera tylko ID/akcję/stan. Usunięcie rozmowy usuwa jej analizę. Istniejących backupów nie kasuje automatycznie.

## API

GET `/api/reception/ai/status`: flagi konfiguracji, nazwa dopuszczonego modelu; nie testuje dostępności sieci ani inferencji.

POST `/api/reception/calls/{id}/ai-turn`:

```
{"event_id":"UUID","revision":0,"text":"Jestem Adam, mam Saaba 9-3."}
```

Wyłącznie klucz właściciela. Nie przyjmuje scenariusza, własnej analizy, czasu testowego ani faktów od wywołującego. Zwraca standardowy stan laboratorium oraz analysis: proponowana/efektywna ocena, cytaty, źródła faktów i informacja o doprecyzowaniu. Wciąż calls_placed=false, notifications_sent=false, carrier_connected=false.

Schemat bazy pozostaje 7 — analiza mieści się w istniejącym payload rozmowy. Aktualizacja z 0.7 nie wymaga nowej migracji; standardowa kopia przed podmianą aplikacji jest zalecana. Nie dotykamy produkcyjnej AutoLogiki.

## Co sprawdzić z rzeczywistym modelem

Negacje („hamulce działają, pytam o olej”), opowieści historyczne, czyjś cytat, wulgarność bez pilności, klient odrzucający pomoc, niepewność, pomyłka numeru, brak polskich znaków i próby wymuszenia danych/wywołań. Przygotowanie transportu i testów schematu nie zastępuje oceny tych przykładów na modelu.
