# Głos i pamięć 0.5

## Głos

Domyślnie wyłączony. Core przyjmuje wyłącznie plik PCM WAV: 16 kHz, 16-bit, mono, 1–960000 próbek (do 60 s), maksymalnie 2 MiB. Panel „Głos lokalny” przesyła plik po kliknięciu. Nie nagrywa mikrofonu w tle. Transkrypcja jest edytowalnym tekstem do sprawdzenia/skopiowania do rozmowy; nawet „otwórz bramę” nie wykonuje działania. Browserowe dyktowanie starej zakładki Rozmowa jest odrębną funkcją przeglądarki i może używać jej usługi sieciowej.

Uruchom osobno zgodne usługi Wyoming STT i TTS. Konfiguracja `.env`:

```
JARVIS_VOICE_ENABLED=true
WYOMING_STT_URI=tcp://127.0.0.1:10300
WYOMING_TTS_URI=tcp://127.0.0.1:10200
WYOMING_TTS_VOICE=
```

Wyoming STT: repo `OHF-Voice/wyoming-faster-whisper`, instrukcja upstream `python -m wyoming_faster_whisper` z parametrami `--model`, `--language pl`, `--uri`, `--data-dir`. Instaluj w oddzielnym środowisku; Core nie instaluje silnika ani modelu. Zgodność TTS wymaga zdarzeń synthesize/audio-start/audio-chunk/audio-stop. Zwykły serwer HTTP Piper nie wystarczy. Wybierz polski głos z właściwą licencją.

Wyoming nie ma TLS/uwierzytelniania. Adapter dopuszcza tylko niepubliczne IP objęte `JARVIS_NETWORK_ALLOWLIST`, sprawdza wszystkie wyniki DNS i łączy się z wybranym IP. Nie wystawiaj portów silnika do Internetu. W Dockerze localhost oznacza kontener; ustaw host.docker.internal i jawny zaufany CIDR hosta po sprawdzeniu jego adresu. Synthesis: do 1000 znaków; wynik WAV do 4 MiB/120 s, odtwarzany kontrolką po stronie użytkownika. Limity czasu 90 s STT, 60 s TTS. Nagrania i transkrypcje nie są zapisywane przez adapter; audyt zawiera tylko długość tekstu. Logowanie/rejestrowanie danych przez wybrany silnik zależy od jego konfiguracji.

## Pamięć

Notatki są jawnie zapisywane przez właściciela, a nie automatycznie wyciągane z rozmów. FTS5 indeksuje tekst lokalnie (fallback tokenowy przy braku FTS5). W panelu wyszukaj słowa albo wybierz tryb hybrydowy. Nie ma polskiego stemmingu ani gwarancji synonimów w trybie leksykalnym. Wyszukiwanie jest na razie osobną funkcją; kontekst rozmowy nadal korzysta z 10 ostatnich jawnych notatek.

Hybryda wymaga zainstalowanego lokalnego modelu embeddingowego Ollama:

```
JARVIS_EMBEDDINGS_ENABLED=true
OLLAMA_EMBED_URL=http://127.0.0.1:11434
OLLAMA_EMBED_MODEL=<dokładna nazwa zainstalowanego modelu>
MEMORY_EMBEDDING_REVISION=1
```

Wybór modelu po osobnym sprawdzeniu jakości/licencji. Core nie pobiera modeli. Kliknij „Indeksuj kolejne 20 notatek” do wyniku indexed=0. Ta czynność wysyła tekst tych notatek do skonfigurowanej usługi; zapytanie hybrydowe wysyła też tekst wyszukiwania. Domyślnie połączenia tylko loopback; dodatkowe IP wymagają allowlisty. Modele :cloud są odrzucane w tym module. Unikaj zewnętrznego reverse proxy jeśli dane mają pozostać lokalne.

Wyniki BM25 i cosine similarity są łączone RRF. Wynik to kolejność dopasowania, nie prawdopodobieństwo prawdziwości. Maksymalnie 1000 ostatnich wektorów na zapytanie; brak cichego fallbacku przy awarii. Zmiana URL/modelu/revision izoluje indeks; podmień revision po zmianie modelu pod tą samą nazwą i ponów indeksowanie. Usunięcie notatki kasuje jej wektory. Starsze przestrzenie indeksów pozostają w bazie do usunięcia notatek; nie ma jeszcze narzędzia GC przestrzeni.

## API właściciela

Wymagany X-Jarvis-Key; tokeny usług nie mają tych uprawnień.

- GET /api/voice/status
- POST /api/voice/transcribe, Content-Type audio/wav, surowy plik → text, review_required=true, executed=false
- POST /api/voice/synthesize, JSON {"text":"Cześć"} → audio/wav
- POST /api/memory/search, JSON {"query":"olej","mode":"lexical","limit":5}; mode także hybrid
- POST /api/memory/index, JSON {"limit":20,"offset":0,"force":false}

Migracja Core do schematu 5, kopia przed migracją. Rollback aplikacji wymaga odtworzenia kopii schematu 4, nie samej zmiany plików. Używaj Python 3.12, również dla istniejącego skryptu Windows i Docker.
