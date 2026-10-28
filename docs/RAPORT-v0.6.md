# JARVIS OS 0.6 — raport etapu telefonii

22.10.2026. Dodano panel **Telefonia**, zapis ustawień i podgląd reguł eskalacji. To konfiguracja przyszłej telefonii, bez połączenia z operatorem. Poprzedni pełny raport wszystkich 11 obszarów: [0.5](RAPORT-v0.5.md); jego stan pozostałych modułów nadal obowiązuje.

Gotowe: osobny numer właściciela i warsztatu, grafik tygodniowy z wieloma przedziałami, urlopy/wyjątki, ręczny i czasowy DND, Europe/Warsaw, wyjaśnienie decyzji, walidacja numerów i konfliktów godzin, ochrona przed nadpisaniem ustawień z drugiej karty, audyt bez numerów. Schemat Core 6, backup przed migracją. Nowa zależność tzdata dostarcza strefy również na Windows.

Testy: 112 pytest na Pythonie 3.12, sprawdzenie JS i pip check. Nowe scenariusze: granice przedziałów, przerwy, koniec dnia, dwie jesienne godziny i przeskok wiosenny, DND/wygaśnięcie, urlop, nieuzasadniona eskalacja, walidacja konfiguracji, konflikt rewizji, restart, uprawnienia tokenów i migracja z 0.5 z kopią starych danych. Test DOM z działającym Core: zapis numerów/godzin, kryzys kwalifikujący do kontaktu i blokada DND. To nie test prawdziwej przeglądarki ani telefonu. Dwa istniejące ostrzeżenia zależności pozostają.

Wciąż wymagają przygotowania: operator/numery i aktywacja przekierowania Play; analiza żywej rozmowy, strumieniowy głos telefoniczny, transfer/akceptacja właściciela i zapis zgłoszeń. Nie wykonano połączeń, przekierowania ani powiadomień. Ustawienia można testować bez kont i kluczy operatora. Numer właściciela wpiszesz lokalnie w panelu.

Środa: uruchom projekt osobno na Windows/Pythonie 3.12, wykonaj testy, ustaw numer warsztatu i drugi numer, grafik oraz urlopy. Sprawdź podgląd w godzinach, poza nimi i z DND. Następnie wykonaj wcześniejszy plan z raportu 0.5 (kopia AutoLogiki, modele, rzeczywiste STT/TTS, Docker i telefon). Nie aktywuj przekierowania Play, dopóki docelowy moduł odbioru nie przejdzie testowego połączenia i nie będzie gotowej ścieżki awaryjnej.

Szczegóły, zapis zaakceptowanych preferencji i lista następnych prac: [Telefonia 0.6](TELEFONIA-v0.6.md).
