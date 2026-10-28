# Dobór projektów do JARVIS OS — 22.10.2026

Sprawdzono rzeczywiste README, licencje i wskazane pliki siedmiu płytkich klonów. Commity i SHA256 w `upstream-evidence.json`. To dobór komponentów, nie połączenie całego kodu tych projektów. Własny Core pozostaje miejscem uprawnień, zgód i audytu. Nie kopiujemy kodu GPL do Core; silniki głosu są osobnymi usługami. Licencja modelu i zbioru treningowego może różnić się od licencji programu.

| Projekt i źródło | Licencja kodu | Decyzja / stan |
|---|---|---|
| [Wyoming](https://github.com/OHF-Voice/wyoming) | MIT | Zintegrowano SDK 1.10.2: TCP JSONL/PCM, STT/TTS, limity i przypięcie IP. Protokół nie ma własnego uwierzytelniania ani TLS — tylko zaufana sieć. Notice w third_party. |
| [wyoming-faster-whisper](https://github.com/OHF-Voice/wyoming-faster-whisper) | MIT | Wybrany kandydat usługi STT, README i moduły sprawdzone. Nie uruchomiono inferencji. W README istnieje obraz rhasspy/wyoming-whisper; wersję/digest trzeba przypiąć po teście. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Zweryfikowane źródło/licencja upstream; silnik stojący za powyższą usługą, nie osobna biblioteka Core. |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | MIT | Zweryfikowana licencja upstream; alternatywa do benchmarku CPU/Windows, jeszcze bez adaptera. |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) | GPL-3.0 | Sprawdzono COPYING/README. Kandydat zewnętrznego TTS; nie dostarczamy kodu, binarek ani głosów. Głos polski wymaga osobnego sprawdzenia licencji i testu. Nie każdy Piper udostępnia Wyoming. |
| [openWakeWord](https://github.com/dscripka/openWakeWord) | Apache-2.0 kod; gotowe modele CC-BY-NC-SA-4.0 | Odroczono nasłuch. Ograniczenie NC gotowych modeli jest istotne dla warsztatu. Potrzebny właściwy model/licencja; niczego nie pobrano. |
| [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant) | Apache-2.0 | README i licencja sprawdzone. Kandydat satelity HA/ESPHome, nie adapter Wyoming Core; brak testu sprzętu i zgodności RPi. |
| [Mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | Sprawdzono repo/licencję. Nie instalujemy całego stosu ani domyślnego automatycznego wydobywania wspomnień. W 0.5 własna jawna pamięć + lokalne embeddingi. Wyniki reklamowe usługi nie są pomiarem tej instalacji. |
| [LangGraph](https://github.com/langchain-ai/langgraph) | MIT | Sprawdzono README/licencję. Kandydat trwałych przepływów i zatrzymań do zatwierdzania kodu. Nie wdrożono; dotychczasowe propozycje kodu są opisami. |
| [n8n](https://github.com/n8n-io/n8n) | Sustainable Use License; dodatkowe składniki enterprise | Już przygotowany profil Docker i szablon. To source-available, nie projekt OSI open source. Do własnych automatyzacji; dystrybucja/hosting komercyjny wymaga oceny warunków. |

Następny wybór silników po pomiarze jakości polskiego, opóźnienia i RAM/VRAM na rzeczywistym PC. Nie zakładamy kompatybilności starych GPU z aktualnym CUDA. Przegląd nie stanowi pełnego audytu bezpieczeństwa zależności.

## M2.1 — biblioteki panelu, 24.10.2026

Zainstalowane pakiety i ich metadane `package.json`: React/react-dom19.3.1 (MIT), lucide-react1.61.0 (ISC); notice używanych w panelu bibliotek w `third_party/`. Narzędzia build/test: Vite8.3.5 (MIT), TypeScript7.0.2 (Apache-2.0), Vitest5.0.5 (MIT). Wersje i integralność zależności zapisuje `frontend/package-lock.json`. To kontrola metadanych zainstalowanych pakietów i zachowanie notice, nie pełny skan zależności ani ocena licencji przyszłych modeli.
