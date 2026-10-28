# R01 — ewaluacja polskiej recepcji

Zestaw `evals/reception-pl-v1.json` (reception-pl-v1.0.0) zawiera 30 ręcznie określonych, syntetycznych przypadków. Obejmuje rutynę, pierwszą prośbę, naleganie z odmową pomocy, kryzys po naprawie, negację, cytaty, przeszłość, hipotezy, zdenerwowanie, pomyłkę numeru, brak znaków diakrytycznych, niepewność, telefony, korekty, fakty wyłącznie klienta oraz próby wymuszenia instrukcji, cen i rezerwacji.

Walidacja bez modelu (bez połączeń sieciowych):

```bash
.venv/bin/python -m jarvis.reception_eval --validate-only
```

Rzeczywisty pomiar wymaga już zainstalowanej Ollamy, lokalnego modelu na istniejącej allowliście i jawnie włączonej analizy. Runner nie instaluje modeli, nie rozszerza allowlisty i nie ładuje `.env` automatycznie. Przykład po ustawieniu dostępnego modelu w środowisku:

```bash
export JARVIS_RECEPTION_AI_ENABLED=true
export OLLAMA_ALLOWED_MODELS=qwen2.5:3b
export OLLAMA_RECEPTION_URL=http://127.0.0.1:11434
.venv/bin/python -m jarvis.reception_eval --model qwen2.5:3b --output data/evals/local-v1
```

Połączenie używa istniejącego `reception_ai.analyze` i transportu z kontrolą origin, IP/DNS, bez przekierowań, z timeoutem i limitem odpowiedzi. Runner nie tworzy aplikacji Core, bazy ani rozmów recepcji; wywołuje wyłącznie analizę. JSON Schema odrzuca pola akcji. Nie ma operatora, wysyłki, zapisów do warsztatu ani pobierania pamięci właściciela.

Raporty JSON/Markdown zawierają model, wersję zestawu, źródło, wynik każdego przypadku i liczniki. `environment_error` (konfiguracja, model niedostępny, HTTP, timeout, sieć) nie wchodzi do mianownika jakości. `invalid_schema` i `fabricated_evidence_or_fact` są odrzuceniami istniejącej analizy. Dalsza ocena rozróżnia intencję, nadmierną eskalację, niepewność oraz brakujące, błędne i zakazane fakty. Kod wyjścia: 0 — zaliczone; 1 — błędy jakości; 2 — błędy środowiska lub argumentów.

Oczekiwane fakty mają jawne, dopuszczalne dosłowne wartości i zakazane pola. Jest to rygorystyczny zestaw regresyjny, nie reprezentatywna statystyka rozmów produkcyjnych. Każda zmiana oczekiwań wymaga przeglądu i nowej wersji zestawu. Literalne pochodzenie nie dowodzi poprawności semantycznej, dlatego runner porównuje też pole i oczekiwaną wartość. Nie mierzy jakości swobodnych odpowiedzi klientowi: obecny interfejs analizatora zwraca wyłącznie klasyfikację i fakty. Nie mierzy faktycznej realizacji połączenia ani działania modelu na sprzęcie użytkownika.

`--source controlled_http` służy wyłącznie jawnym symulacjom. Źródło deklaruje uruchamiający; runner nie potrafi po samym protokole HTTP rozpoznać prawdziwej inferencji. Nie należy przedstawiać serwera fixture jako Ollamy. Raporty `docs/evals/controlled-http-v1.*` pochodzą z kontrolowanego serwera zwracającego zawsze routine bez faktów. Pokazują także oczekiwane porażki tej symulacji. `real_ai_passed=0`, współczynnik jakości AI jest null i jakość modelu pozostaje `unverified`.

W tym środowisku nie znaleziono polecenia Ollama ani usługi na 127.0.0.1:11434. **Jakość rzeczywistego modelu niesprawdzona.** Testy runnera używają rzeczywistego lokalnego serwera HTTP, w tym kontroli braku zapisów i blokady IP; nie są testami inferencji.
