# JARVIS OS 0.7 — recepcja laboratoryjna

22.10.2026. Możemy kontynuować przygotowania bez dostępu do PC użytkownika. Dodano działający tekstowy przebieg recepcji, który korzysta z ustawień telefonii 0.6. Nie ma połączenia z operatorem i nie aktywowano przekierowania Play.

Gotowe: osobna zakładka Recepcja · laboratorium, powitanie, zapis wypowiedzi i ręcznie podanych faktów, pierwsza prośba i naleganie, podgląd pilności, oczekiwanie na decyzję właściciela, akceptacja/odmowa/brak odpowiedzi w symulacji, powrót do recepcji, zakończenie oraz jedno trwałe zgłoszenie na rozmowę. Wewnętrzne podsumowanie jest oddzielone od treści klienta. Zapisana pilność nie znika po kolejnej spokojnej wypowiedzi.

Ochrona reguł: ponowne sprawdzenie aktualnego grafiku przy przyjęciu, brak ponawiania kontaktu po odmowie/nieodebraniu, transakcje i rewizje, idempotencja zdarzeń, ograniczenie długości rozmowy, właściciel jako jedyna rola API, audyt bez treści i numerów. Usunięcie kaskadowe rozmowy usuwa jej zgłoszenie i zdarzenia. Schemat bazy 7 z kopią przed migracją.

127 testów pytest przeszło w Pythonie 3.12. Nowe testy obejmują pełne ścieżki recepcji, pierwszą i ponowioną prośbę, blokady godzin/DND zmienione podczas oczekiwania, akceptację/odmowę/brak odpowiedzi, zapis zgłoszeń, brak osobistej pamięci/powiadomień, duplikaty zdarzeń, równoczesne zmiany, restart, usunięcie, limity i migrację z 0.6. Test DOM z działającym Core sprawdził rozpoczęcie, prośbę, naleganie, brak odpowiedzi, zakończenie i usunięcie. Sprawdzono składnię JS i pip check. To nie test prawdziwego telefonu, audio lub wyglądu przeglądarki.

Ważna granica: rozpoznawanie sytuacji używa uproszczonych haseł laboratoryjnych albo scenariusza wybranego przez właściciela. To nie jest jeszcze analiza znaczenia rozmowy przez AI; nie podłączamy jej do prawdziwych klientów. Fakty wprowadza się ręcznie. Nie ma rzeczywistego transferu, połączeń wychodzących, powiadomień recepcji, timerów operatora ani zapisów AutoLogiki. Numer właściciela i godziny można wpisać lokalnie w panelu. Konta/klucze operatora do laboratorium nie są potrzebne.

Na środę 28.10: uruchomić skrypt Windows/Python 3.12, testy, Telefonia i laboratorium na danych syntetycznych. Sprawdzić godziny, DND, odmowę i brak odpowiedzi. Potem plan pozostałych modułów z raportu 0.5: rzeczywisty snapshot AutoLogiki, modele, STT/TTS, Docker i telefon. Nadal nie uruchamiać przekierowania Play przed gotowym i sprawdzonym modułem odbioru oraz ścieżką awaryjną.

Pełny zakres 11 modułów i wymagane konta pozostają w RAPORT-v0.5.md; reguły dostępności w TELEFONIA-v0.6.md. Nowy moduł i dalsze prace opisuje RECEPCJA-v0.7.md. Aktywacja głosem, swobodny dialog audio i automatyczna pamięć według uzgodnionych reguł pozostają oddzielnymi kolejnymi modułami. Produkcyjne repozytorium AutoLogiki bez zmian, brak rzeczywistych połączeń i działań fizycznych.
