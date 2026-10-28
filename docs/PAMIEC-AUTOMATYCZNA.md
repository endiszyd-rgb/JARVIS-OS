# R02 — ograniczona automatyczna pamięć

Tryb automatyczny jest opcjonalny. W panelu Pamięć wybierz auto i kategorie; domyślnie pozostaje manual. Ekstraktor `pl-declarations-v1` działa lokalnie i deterministycznie, bez modelu ani dodatkowej usługi. Obsługuje całe, krótkie deklaracje z poniższego zamkniętego katalogu. Nie rozumie dowolnych samodzielnych wypowiedzi. Inne wiadomości pomija, zamiast zgadywać fakty.

| Kategoria | Deklaracja | Dopuszczalne wartości |
|---|---|---|
| Preferencje | Preferuję/Wolę … odpowiedzi | krótkie, szczegółowe |
| Preferencje | Preferuję/Wolę odpowiedzi … | po polsku, po angielsku |
| Sprzęt | Używam … / Mój system to … | Windows 10, Windows 11, Linux, macOS |
| Sprzęt | Mój telefon ma system … | Android, iOS |
| Projekty | Pracuję nad projektem … / Rozwijam projekt … | JARVIS OS, AutoLogika OS |
| Decyzje | Zdecydowałem, że modele AI mają działać … | lokalnie |
| Decyzje | Zdecydowałem, że kopie zapasowe robimy … | codziennie, co tydzień |
| Sposób pracy | Preferuję/Wolę pracować … | etapami, nad jednym zadaniem naraz |

Wielkość liter, brak polskich znaków i jedna końcowa kropka są obsługiwane. Dopisane instrukcje, cytaty, pytania, negacje, hipotezy, nieznane nazwy, dane klientów, hasła i inne dodatkowe treści powodują pominięcie całej deklaracji. Treść notatki tworzy backend z katalogu; nie kopiuje dowolnej wartości z wypowiedzi ani odpowiedzi modelu. To ograniczenie formatu, nie ogólny semantyczny filtr danych prywatnych. Obsługa swobodnych projektów i sprzętu pozostaje przyszłym rozszerzeniem z osobną ewaluacją.

## Zapis i konflikty

Źródłem jest tylko bieżąca wypowiedź właściciela z prywatnego `/api/chat`. Odpowiedzi asystenta, wcześniejsza historia, recepcja, importy warsztatu i narzędzia nie uruchamiają ekstrakcji. Tura z `include_workshop_summary=true` jest wykluczona także wtedy, gdy jej tekst pasuje do katalogu.

Po udanej odpowiedzi zapis i zakończenie tury następują w jednej transakcji SQLite. Nieudana/stara tura albo błąd końcowego zapisu nie pozostawia częściowej pamięci. Rewizje polityki i pamięci są porównywane z początkiem tury. Zmiana ustawień, notatek lub usunięcie danych podczas generowania odpowiedzi powoduje pominięcie automatycznego zapisu, bez odwracania zmiany właściciela. Domyślnie analizujemy najwyżej 1000 notatek; większa pamięć wymaga rozszerzenia indeksu, a zapis jest pomijany.

Jeden klucz ma jedno automatyczne wspomnienie, np. `preferences.response_length`. Powtórzenie lub alias nie dodaje duplikatu. Inna wartość bez potwierdzenia zmiany jest konfliktem. Aby zastąpić wcześniejszą automatyczną wartość, użyj całej deklaracji z prefiksem **„Od teraz …”**, np. „Od teraz wolę szczegółowe odpowiedzi.”. Aktualizacja zachowuje poprzednią treść, rewizję i źródło w historii; odświeża FTS i usuwa nieaktualny embedding.

Ręcznie zapisane i poprawione notatki są chronione przed automatycznym nadpisaniem. Parser rozpoznaje również wspierane deklaracje w starych/ręcznych notatkach, aby wykryć ich duplikaty i konflikty. Nie rozpoznaje wszystkich sprzeczności ze swobodnym dawnym tekstem — taki przypadek wymaga ręcznej korekty. Katalog nie jest pełną realizacją całej pamięci osobistej opisanej w D07.

## Blokada, pochodzenie i usuwanie

Checkbox **„Tego nie zapamiętuj”** w Rozmowie wysyła `do_not_remember=true`. Blokuje automatyczny zapis i jawne polecenie „zapamiętaj”. Rozpoznawane frazy „nie zapamiętuj”, „nie pamiętaj”, „nie zapisuj” także blokują zapis. Checkbox i frazy nie usuwają już istniejących notatek ani historii rozmowy; historia jest odrębną funkcją.

Notatki automatyczne mają źródło `owner_auto`. Przycisk Źródła automatycznego zapisu pokazuje dopasowaną deklarację, wersję ekstraktora, identyfikator sesji/tury i rewizję. Dane otrzymuje wyłącznie właściciel przez `GET /api/memory/{id}/origins`. Ręczna korekta zachowuje historię i zmienia źródło na `owner_correction`.

Usunięcie notatki/retencja pamięci usuwa jej klucz, historię i pochodzenie. Restart nie skanuje rozmów i nie odtwarza skasowanej pamięci. Nowa, świadomie wysłana deklaracja może ponownie utworzyć notatkę. Usunięcie samej rozmowy pozostawia niezależnie zapisaną pamięć i jej krótkie źródło; `session_available=false` informuje, że pełnej rozmowy już nie ma. Starsze backupy mogą nadal zawierać dawne dane.

## Kontrakt i weryfikacja

Odpowiedź `/api/chat` ma pole `memory_capture`: wynik zapisu, aktualizacji, duplikatu lub przyczynę pominięcia. Panel wyświetla go po odpowiedzi. `/api/memory/policy` zwraca aktywność ograniczonego ekstraktora i jego nazwę. Domyślny manual, wyłączenie zapisu i wyłączone kategorie są respektowane.

Schemat Core 9 dodaje klucze faktów, pochodzenie, wyniki tur i licznik zmian pamięci. Przed migracją starej bazy powstaje `backups/before-schema9-*.sqlite3`. Test migracji 8→9 odczytuje backup i sprawdza zachowanie ręcznej treści i źródła.

Testy sprawdzają katalog i odrzucenia, brak pobierania faktów od asystenta/recepcji, źródła i restart, duplikaty, konflikty, aktualizację i ręczną ochronę, zmianę polityki i pamięci podczas odpowiedzi, rollback po wykonanym capture, FTS/embeddingi, retencję i usuwanie. Transport modelu jest kontrolowany, więc te testy nie są oceną jakości AI. Nie używają prawdziwych danych klientów.
