# Telefonia 0.6 — ustawienia i podgląd

## Ustalenia użytkownika

Numer warsztatu jest komórkowy w Play. Docelowo JARVIS odbiera od razu. Właściciel ma drugi numer do eskalacji. Przekazywanie wyłącznie przy kryzysie lub gdy klient ponawia żądanie kontaktu i odrzuca pomoc asystenta. Dostępność ustala właściciel w programie, w polskiej strefie czasowej. Kryzys nie obchodzi godzin ani DND. Właściciel powinien dostać wewnętrzne podsumowanie i zaakceptować połączenie przed połączeniem z klientem.

Uzgodniono także: aktywacja głosu hasłem lub przyciskiem, swobodna rozmowa kończona poleceniem lub po 30 sekundach ciszy oraz automatyczna pamięć według reguł prywatności. Te zachowania są wymaganiami kolejnych modułów — nie są implementacją wersji 0.6. Dotychczasowy upload głosowy i ręczne zapisy notatek nadal działają.

## Co działa

W Control Center otwórz **Telefonia**. Wpisz drugi numer właściciela i numer warsztatu w formacie +48…, ustaw dni/godziny, ewentualne wyjątki i DND. Ustawienia są lokalne, trwale zapisane w SQLite i dostępne wyłącznie właścicielowi. Nie wpisuj numeru właściciela w czacie ani repozytorium.

Domyślnie przekazywanie wyłączone, bez numerów i godzin. Nie zakładamy dni pracy. Włączenie reguł wymaga dwóch różnych numerów i przynajmniej jednego przedziału. Samo włączenie reguł NIE aktywuje operatora ani przekierowania w Play. Zakładka zawsze oznacza brak podłączonej telefonii.

Dni tygodnia mogą mieć kilka przerwanych przedziałów. Początek włącznie, koniec wyłącznie; 24:00 to koniec dnia. Przedział przez północ rozdziel na dwa dni. Puste dni są zamknięte. Urlop/święta to jawne zakresy dat włącznie; system nie pobiera automatycznie kalendarza świąt. Wyjątki blokują cały dzień, również kryzysy. Przedziały nie mogą się nakładać, a dzień nie może występować dwukrotnie.

DND ma dwa niezależne warianty: ręczne włączenie do odwołania albo termin z wygaśnięciem. Każdy z nich blokuje eskalacje. Termin wymaga jawnego offsetu; po wygaśnięciu blokada czasowa przestaje obowiązywać, bez potrzeby zadania harmonogramu. Ręczny DND nadal działa do odznaczenia.

Wersjonowanie ustawień zapobiega nadpisaniu zmian z innej karty (409: wczytaj ponownie). Audyt zapisuje numer rewizji, bez numerów telefonów. Numery są w lokalnej bazie i jej backupach; backupy trzeba chronić jak pozostałe dane warsztatu.

## Podgląd decyzji

Podgląd korzysta z ZAPISANYCH ustawień. Pusta chwila to teraz; inna chwila wymaga ISO 8601 z offsetem, np. `2026-10-28T10:00:00+01:00`. API zamienia ją na Europe/Warsaw. Nie używa strefy systemu ani przeglądarki. Zmiana czasu uwzględniona przez zoneinfo, baza tzdata przypięta jako fallback Windows. Przy powtórzonej godzinie jesienią oba wystąpienia należą do tego samego lokalnego przedziału. Godzina nieistniejąca wiosną nie występuje; podgląd zawsze wskazuje rzeczywistą chwilę z offsetem.

| Sytuacja | Decyzja przy aktywnych regułach |
|---|---|
| Rutynowa sprawa lub pierwsza prośba o właściciela | Kontynuuj obsługę |
| Kryzys / ponawiane żądanie, godziny i brak blokad | Kandydat do kontaktu: poproś właściciela o przyjęcie |
| Kryzys / ponawiane żądanie poza godzinami, DND lub urlop | Zapis i powiadomienie jako plan działania, bez telefonu |
| Właściciel nie odbiera | Docelowo prośba o oddzwonienie |

Podgląd zwraca wszystkie przyczyny blokady, lokalny czas i rewizję. Zawsze `preview_only=true`, `executed=false`, `notifications_sent=false`, `carrier_connected=false`. Nie tworzy zgłoszenia, nie wysyła powiadomienia i nie dzwoni. Wybór „kryzys” jest założeniem testu, nie wynikiem modelu analizującego rozmowę. Pole emergency_services_notice to przypomnienie o rozróżnieniu zagrożenia życia od kontaktu z właścicielem, nie automatyczny telefon na numer alarmowy.

## API

Wszystko wymaga klucza właściciela `X-Jarvis-Key`; tokeny usług odrzucane.

- GET `/api/telephony/settings` → revision, policy, mode=policy_preview.
- PUT `/api/telephony/settings` → `{revision,policy}`; atomowa aktualizacja przy zgodnej rewizji.
- POST `/api/telephony/preview` → `{at:null,situation:"crisis"}`; situation: routine, contact_requested, insistent, crisis.

Polityka: enabled, owner_number, workshop_number, timezone (tylko Europe/Warsaw), weekly `[ {weekday:0,windows:[{start:"08:00",end:"18:00"}]} ]`, exceptions `[{start:"2026-12-24",end:"2026-12-26",label:"Święta"}]`, dnd, dnd_until. Stałe fallbacki outside_hours=log_and_notify, no_answer=callback_request. Pełne schematy w `/api/schema`.

## Czego jeszcze nie ma

Przekierowania u operatora Play, numeru SIP/Twilio, webhooków połączeń, strumieniowego STT/TTS telefonicznego, klasyfikacji sytuacji przez model, oczekiwania klienta na linii, wewnętrznego podsumowania, akceptacji DTMF, rzeczywistego transferu, zapisu zgłoszeń i powiadomień wynikających z rozmowy, limitów kosztowych ani obsługi równoległych połączeń. Same numery nie uwierzytelniają właściciela; rozmówcy nie dostają uprawnień Core.

Następny etap: adapter laboratoryjny sesji telefonicznej, wydzielona rola recepcji, schemat zgłoszenia, kontrolowane przejścia stanów i testy zakończenia/eskalacji. Dopiero później podłączenie prawdziwego operatora. Nie dodajemy kodów przekierowania Play bez sprawdzenia oferty i numeru docelowego, nie zmieniamy telefonu użytkownika ani nie wykonujemy płatnych rozmów w tym etapie.
