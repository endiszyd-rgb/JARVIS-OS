# JARVIS OS 0.5 — stan realizacji

22.10.2026. Pakiet rozwija działające 0.4; historia raportu w RAPORT-v0.4.md. Produkcyjne AutoLogika OS pozostaje bez zmian. Projekt jest lokalnym MVP, nie kompletnym systemem produkcyjnym.

## Co dodano

- Adapter głosu Wyoming 1.10.2: jawny upload WAV do STT, edytowalna transkrypcja, TTS do pliku WAV. Panel „Głos lokalny”, bez nasłuchu w tle i automatycznego wykonywania rozpoznanych poleceń. Silniki działają osobno.
- Wyszukiwanie ręcznie zapisanych wspomnień: lokalny FTS5 lub fallback tokenowy; opcjonalne embeddingi przez Ollama, ranking hybrydowy RRF, indeksowanie po 20 notatek. Izolacja wersji/modelu i usuwanie wektorów z notatką. Wyniki wyszukiwania nie są jeszcze automatycznym kontekstem rozmów.
- Ograniczenie wielkości ciał żądań przed parsowaniem, również przy transmisji fragmentami. Weryfikacja lokalnych endpointów Wyoming, przypięcie IP i ograniczenia rozmiarów zdarzeń/dźwięku. Audyt głosu nie przechowuje transkrypcji.
- Migracja bazy Core do schematu 5, kopia przed zmianą. Dodatkowe zmienne .env i Compose. Przegląd rzeczywistych repozytoriów/licencji z commitami i sumami plików.

## Wszystkie obszary projektu

| Obszar | Gotowe w pakiecie | Kolejne prace |
|---|---|---|
| Core Python | API, lokalna SQLite, migracje, uwierzytelnianie | Wielu użytkowników, wdrożenie produkcyjne |
| AutoLogika | Audyt rzeczywistego kodu; readonly API zleceń; snapshot ośmiu domen | Test prawdziwej bazy i zgodności danych; zapis/synchronizacja wymaga odrębnego projektu |
| AI i pamięć | Sesje, historia, wybór modeli Ollama, notatki, wyszukiwanie, adapter głosu | Rzeczywiste silniki, mikrofon, dobór modelu i sposób zapamiętywania |
| WhatsApp | Walidowany webhook Twilio, deduplikacja, inbox, szkice | Wysyłka, onboarding kont; Calling dopiero po weryfikacji dostępności/uprawnień Twilio/Meta |
| Dom/ESP32/MQTT | DEMO, realny odczyt HA na allowliście | MQTT, provisioning ESP32, sceny i osobne zgody na bramę; brak fizycznego sterowania |
| n8n | Profil Compose, przykład workflow, ograniczony token, scheduler lokalny | Uruchomienie i rzeczywiste workflow |
| Pluginy | MCP Streamable HTTP i ograniczony OpenAPI GET, konfiguracja/wyłączanie | Rozszerzenia protokołów, uprawnienia do kontrolowanych zapisów |
| Zmiany przez rozmowę | Propozycje ustawień/automatyzacji, zatwierdzanie i cofanie | Kod pozostaje opisem; brak automatycznych patchy, testów sandbox i rollbacku kodu |
| Control Center | 12 widoków, API rzeczywistych modułów i DEMO | Test wyglądu/przeglądarki, dopracowanie UX |
| Windows/telefony | Skrypt PowerShell, responsywny web panel | Test Windows, iOS/Android, HTTPS i bezpieczny dostęp zdalny |
| Operacje | Tokeny z zakresami, audyt, backup, kontrola sieci, health | Monitoring/alerty, próby odtworzenia, podpisywanie aktualizacji, instalator |

## Dowody i granice testów

93 testy pytest zaliczone na Pythonie 3.12, test składni JS i pip check. Nowe testy obejmują rzeczywisty lokalny TCP Wyoming z syntetyczną transkrypcją/PCM, błędny/truncated WAV, rozmiary HTTP, blokadę publicznego endpointu, limit zdarzeń, wyszukiwanie FTS, indeksowanie, rozdzielenie przestrzeni modeli, kasowanie i awarię usługi. Test hybrydowy używa kontrolowanych embeddingów, a nie rzeczywistego modelu. Dwa ostrzeżenia deprecacyjne zależności (Starlette, audioop); wymagany Python 3.12.

Test DOM z działającym Core sprawdził ekran statusu głosu, zapis i wyszukiwanie notatki oraz czytelny błąd przy wyłączonych embeddingach. Nie jest to test wyglądu, odtwarzania audio ani mikrofonu. Rzeczywiste STT/TTS, Ollama, Windows, Docker, telefony, HA, MQTT, n8n, konta Twilio i prawdziwe dane warsztatu pozostają niesprawdzone. Nie wykonano działań fizycznych ani wysyłki wiadomości. Zewnętrzne modele nie zostały pobrane.

## Konta, klucze i dane

Core, testy, sesje i lokalne wyszukiwanie: bez płatnych kont, tylko wygenerowany lokalnie klucz właściciela. AI/embeddingi: zainstalowana Ollama i jawnie wskazane modele z odpowiednimi licencjami. Głos: osobne lokalne usługi Wyoming i polski model STT/głos TTS; usługi nie wymagają kont z założenia, konkretna dystrybucja może mieć własne warunki. AutoLogika: rzeczywisty backup schematu 18 albo adres/PIN serwera mobilnego. HA: adres, token i lista encji. Twilio: konto, Auth Token, SID, nadawca WhatsApp, HTTPS i dozwoleni nadawcy; użycie może być płatne.

WhatsApp Business Calling nie jest aktywowany przez ten projekt. Wymaga obsługi na konkretnym koncie/numerze i rynku, uprawnień oraz spełnienia aktualnych warunków Twilio/Meta, w tym warunków inicjowania połączeń. Nie zakładamy, że Sandbox lub zwykły numer zapewnia Calling. Szczegóły wcześniejszej weryfikacji i linki w dokumentacji 0.3; ponowna weryfikacja przed wdrożeniem.

## Środa 28.10 — kolejność uruchomienia

1. W osobnym katalogu zainstaluj Python 3.12 i uruchom scripts/start.ps1. Zachowaj lokalny .env/klucz. Sprawdź DEMO i testy; nie nadpisuj AutoLogiki.
2. Zrób backup AutoLogiki, wskaż kopię skryptowi import_autologika.py. Porównaj kilka zleceń, finanse, terminarz i części z aplikacją. Nie zapisuj do źródła.
3. Uruchom Ollamę, wybierz model zgodny z RAM/VRAM, przetestuj po polsku i sprawdź historię. Osobno wybierz model embeddingów; zindeksuj przykładowe notatki.
4. Uruchom STT/TTS w osobnych środowiskach. Wgraj krótki WAV z polską mową; sprawdź jakość i czas odpowiedzi. Odtwórz TTS. Nie włączaj ciągłego nasłuchu przed decyzją o sposobie aktywacji.
5. Sprawdź Docker i mapowanie host.docker.internal/allowlisty. Włącz wyłącznie odczyt wybranych czujników HA. Potem n8n z tokenem scheduler:tick.
6. Sprawdź dostęp panelu z telefonu przez zaufaną sieć/HTTPS. Nie wystawiaj surowych portów Core/Wyoming w Internecie. Sprawdź odtworzenie backupu na osobnej bazie.
7. Dopiero po testach kont skonfiguruj webhook Twilio. Osobno ustal zasady wysyłki i Calling. Fizyczna brama oraz inne wrażliwe urządzenia nadal wymagają oddzielnego potwierdzenia.

Instrukcje szczegółowe: GLOS-I-PAMIEC-v0.5.md, OPEN-SOURCE.md, OPERACJE.md oraz raport 0.4. Najbliższe decyzje użytkownika: aktywacja głosu i sposób zatwierdzania pamięci.
