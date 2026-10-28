# Aktualizacja 0.8.2

Dostarczono ograniczoną ekstrakcję deklaracji. Bieżące zachowanie i ograniczenia: [PAMIEC-AUTOMATYCZNA.md](PAMIEC-AUTOMATYCZNA.md). Domyślny tryb pozostaje ręczny. Poniższy opis dotyczy wcześniejszego etapu 0.8.1; migracja bieżąca prowadzi do schematu 9.

# R02 część 1 — polityka i pochodzenie pamięci

Osobne ustawienia pamięci nie zmieniają settings modelu ani polityki recepcji. Panel Pamięć pokazuje zgodę na zapis, tryb manual/auto, kategorie i limit retencji. **Auto jest zapisaną preferencją; automatyczna ekstrakcja nie jest aktywna.** Kolejny etap musi zaimplementować wykluczenia sekretów, danych płatniczych i klientów, deduplikację i bezpieczne zastępowanie faktów. Brak ekstrakcji nie jest zaliczeniem testów jej bezpieczeństwa.

Źródła są nadawane przez backend: legacy_manual (stare notatki), owner_manual (panel/API), owner_chat (jawne „zapamiętaj …”), owner_correction (korekta). Model ani klient recepcji nie mogą wybrać źródła. Wszystkie nowe endpointy wymagają uprawnień właściciela. Tryb auto nie zamienia ręcznych wpisów w automatyczne.

Schemat Core 8 dodaje osobne tabele polityki, źródeł i historii. Przed migracją starej bazy powstaje kopia `backups/before-schema8-*.sqlite3`; stare notatki i ich identyfikatory zostają zachowane. Nie nadpisujemy istniejącego pochodzenia przy restarcie. Manifest pierwotnego przekazania opisuje import; nowy ZIP dostaje nowy manifest.

- GET/PUT `/api/memory/policy`: polityka i rewizja; nieaktualny zapis → 409.
- POST `/api/memory`: ręczny wpis, opcjonalna kategoria; pochodzenie wybiera backend.
- GET `/api/memory`: wpisy z pochodzeniem, kategorią i rewizją.
- PUT `/api/memory/{id}`: tekst, kategoria i oczekiwana rewizja. Transakcja zachowuje poprzednią treść, zwiększa rewizję, aktualizuje FTS i usuwa stare embeddingi. Konflikt → 409.
- GET `/api/memory/{id}/history`: historia korekt; aktualna treść jest w liście notatek.
- DELETE `/api/memory/{id}`: usuwa również pochodzenie, historię, embeddingi i wpis indeksu z aktywnej bazy.
- POST `/api/memory/retention`: domyślnie dry_run=true; usuwa dopiero po jawnym żądaniu z false. Limit wieku liczymy od utworzenia notatki, nie od korekty. Pusty limit niczego nie usuwa.

Wyłączenie zapisu blokuje nowe ręczne wpisy i korekty, również komendę czatu. Odczyt istniejących notatek nadal działa. Frazy „nie zapamiętuj”, „nie pamiętaj”, „nie zapisuj” (również bez znaków diakrytycznych) blokują zapis danej notatki. Jest to konserwatywna blokada rozpoznawalnych fraz, nie pełne rozumienie wszystkich parafraz. Samo wysłanie takiej frazy nie usuwa dawnych danych ani historii rozmowy. Usuwanie i retencja są dostępne także przy wyłączonym zapisie. Kopie zapasowe zachowują wcześniejszą zawartość; osobna polityka backupów jest w R07.

Sprawdzenia: migracja z notatką schema7 i odczyt jej kopii przed migracją; restart bez ponownej migracji; osobne settings i konflikt rewizji; blokada zapisu w obu ścieżkach; źródła, korekta z historią, FTS i unieważnienie embeddingów; usuwanie z kaskadą; jawna retencja; izolacja od recepcji i brak uprawnień tokenu usługi. Panel sprawdzono przez `node scripts/check_memory_ui.cjs` z kontrolowanym DOM/API; nie jest to prawdziwa przeglądarka.
