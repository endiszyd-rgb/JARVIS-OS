# R04 — trwały transport telefonii w laboratorium (0.8.4)

Ten etap łączy istniejącą recepcję z trwałą kolejką komunikatów i oddzielnymi kanałami klienta, właściciela oraz systemu. SQLite przechowuje stan rozmowy, potwierdzenia zdarzeń, oczekujące polecenia i wynik ich laboratoryjnego dostarczenia. `LabAdapter` jedynie sprawdza typy i zwraca potwierdzenie. Nie ma operatora, PSTN/SIP, rzeczywistych połączeń, SMS, powiadomień ani transferu audio. Pełne odpowiedzi stanu zachowują `carrier_connected=false`, `calls_placed=false` i `notifications_sent=false`.

## Panel i ręczny przebieg

Otwórz widok **Transport · laboratorium** w Control Center. Telefonia nadal ma osobną politykę godzin, DND, urlopów i numerów. Do scenariusza przekazania potrzebna jest włączona, kompletna polityka i bieżąca dostępność właściciela. Ustawienia nie aktywują Play ani operatora. Żadne domyślne godziny i rzeczywiste numery właściciela nie są narzucane.

1. Utwórz rozmowę laboratoryjną. Backend tworzy osobny rekord recepcji i zapisuje powitanie jako oczekujący komunikat klienta.
2. Użyj ręcznego dostarczenia kolejki, aby komunikaty zostały oznaczone jako dostarczone. Samo utworzenie lub wpisanie tekstu niczego nie dostarcza.
3. Wprowadź tekst w kanale klienta. Odpowiedź recepcji albo oczekiwanie na właściciela trafia do kolejki. Właściciel ma osobny widok oferty i podsumowania.
4. Dostarcz ofertę do właściciela. Akceptacja jest możliwa dopiero po tym kroku i wymaga identyfikatora bieżącej próby.
5. Akceptacja zapisuje zgodę i kolejkuje `bridge`; nie oznacza jeszcze połączenia. Kolejne ręczne dostarczenie ponownie sprawdza aktualną politykę oraz zgodę. Dopiero poprawne potwierdzenie adaptera przełącza stan na połączony laboratoryjnie.
6. Odmowa, brak odpowiedzi, upływ czasu, wyczerpanie budżetu albo błąd adaptera zapisują prośbę o oddzwonienie. Nie ma obietnicy godziny i drugiej próby kontaktu w tej rozmowie. Klient może kontynuować rozmowę recepcji lub się rozłączyć.
7. Po zakończeniu można usunąć rozmowę przyciskiem w panelu. Usunięcie trwale kasuje powiązane dane aktywnej bazy i natychmiast unieważnia token klienta; stare kopie zapasowe mogą zachować wcześniejszą zawartość.

Nie działa worker ani timer w tle dostarczający kolejkę. Czas jest sprawdzany przy odczycie/listowaniu lub zdarzeniu. Wygaśnięcie może więc zostać zapisane dopiero przy następnym żądaniu. Komunikat o fallbacku również wymaga późniejszego `dispatch`, aby pojawił się w dostarczonych wiadomościach klienta. Odświeżenie stanu nie jest wysłaniem wiadomości.

## Zamknięte scenariusze tekstowe

Transport nie używa heurystyki słów kluczowych starego laboratorium ani niesprawdzonej analizy AI. Rozpoznaje wyłącznie trzy całe wypowiedzi testowe:

| Tekst | Znaczenie w laboratorium |
|---|---|
| `Proszę o rozmowę z właścicielem` | Pierwsza prośba; recepcja proponuje pomoc, bez eskalacji. |
| `Ponownie proszę o właściciela i odrzucam pomoc asystenta` | Naleganie z odrzuceniem pomocy. Bez wcześniejszej prośby działa bramka pierwszego żądania; dopiero powtórzenie może uzasadnić ofertę. |
| `Po naprawie nie działają hamulce` | Test aktualnego kryzysu. Dostępność właściciela nadal obowiązuje. |

Porównanie ignoruje wielkość liter, polskie znaki, skrajne białe znaki i jedną końcową kropkę. Dodatkowe słowa, cytaty, negacje, hipotezy i inne wypowiedzi nie pasują do tych scenariuszy; recepcja prosi o doprecyzowanie. Samo powtórzenie pierwszej prośby nie dowodzi odrzucenia pomocy. Nie jest to ocena rozumienia polskiej mowy ani gotowy klasyfikator produkcyjny.

## Dwa rodzaje dostępu

Kanał właściciela wymaga `X-Jarvis-Key` z pełnym kluczem właściciela. Tokeny usług nie mają dostępu. Odpowiedzi zawierają stan wewnętrzny, limity, wynik polityki i kolejkę wszystkich kanałów. Kolejka właściciela może zawierać prywatny briefing oczekujący na dostarczenie; pole `owner_briefing` na szczycie odpowiedzi jest udostępniane dopiero po dostarczeniu oferty.

Kanał klienta wymaga osobnego nagłówka `X-Jarvis-Call-Token`. Sam klucz właściciela w tym żądaniu nie zastępuje tokenu rozmowy. Token jest związany z jednym ID rozmowy; numer telefonu ani treść wypowiedzi nie są uwierzytelnieniem. Klient nie może akceptować oferty, podawać czasu, ustawiać scenariusza, uzupełniać wewnętrznych faktów ani wywoływać poleceń właściciela.

Nowy token jest zwracany raz przez utworzenie rozmowy i raz po każdej rotacji. W SQLite pozostaje jego skrót SHA-256. Powtórzenie zdarzenia utworzenia/rotacji nie ujawnia tokenu ponownie (`caller_token=null`). Rotacja od razu unieważnia poprzedni token. Po zakończeniu czasu rozmowy token może jeszcze odczytać jej końcowy stan do `expires_at + 300 s` włącznie; później otrzymuje 401. Ta krótka karencja nie wznawia rozmowy i nie pozwala dopisywać tur do stanu ended. Usunięcie rekordu od razu usuwa również dostęp tokenem.

Publiczna projekcja ma wyłącznie `id`, `revision`, `state`, `messages`, `mode`, flagi braku rzeczywistych działań i `replayed`. `messages` zawiera tylko dostarczone komunikaty klienta jako `{id,text}`. Nie ma podsumowania, numeru właściciela, decyzji, kosztu, limitów, identyfikatora próby/zgody, notatek prywatnych, tokenu ani kolejki innych kanałów. `waiting_owner` i `bridge_pending` są widoczne jako `waiting`; `bridged_lab` jako `connected_lab`.

## API i payloady

Wszystkie identyfikatory tras rozmowy i `event_id`/`attempt_id` są UUID. Nieznane pola dają 422. `revision` jest aktualną rewizją transportu, nie wewnętrznej recepcji. API nie przyjmuje czasu testowego; używa świadomego strefy czasu zegara serwera i polityki Europe/Warsaw.

| Metoda i trasa | Dostęp / wynik |
|---|---|
| POST `/api/telephony/transport/calls` | Właściciel; tworzy rozmowę, HTTP 201. |
| GET `/api/telephony/transport/calls` | Właściciel; do 50 ostatnich rozmów, przy okazji sprawdza timeout. |
| GET `/api/telephony/transport/calls/{id}` | Właściciel; pełny stan i kolejka. |
| POST `/api/telephony/transport/calls/{id}/events` | Właściciel; dostarczenie, decyzja, zakończenie lub rotacja tokenu. |
| DELETE `/api/telephony/transport/calls/{id}` | Właściciel; usuwa tylko rozmowę już oznaczoną jako ended. |
| GET `/api/telephony/transport/caller/{id}` | Token rozmowy; ograniczona projekcja klienta. |
| POST `/api/telephony/transport/caller/{id}/events` | Token rozmowy; wyłącznie turn/hangup. |

Utworzenie wymaga `event_id`; `caller` jest opcjonalnym pełnym numerem z `+` i krajem albo pustym tekstem, a `limits` opcjonalnym obiektem. Odpowiedź jest stanem właściciela z jednorazowym `caller_token`.

```json
{
  "event_id": "51ad6ebc-1a5a-4db5-b23b-e59947e5d825",
  "caller": "",
  "limits": {
    "owner_wait_seconds": 30,
    "max_call_seconds": 600,
    "max_owner_attempts": 1,
    "max_simulated_cost_units": 2,
    "max_turns": 24
  }
}
```

Zdarzenie klienta wymaga `event_id`, `revision` i `action`. Dla `turn` tekst musi być niepusty, maksymalnie 4000 znaków. `hangup` wymaga pustego lub pominiętego `text`. Pola `at`, `scenario`, `facts`, `attempt_id` i akcje właściciela są niedozwolone.

```json
{
  "event_id": "10269d80-3cbd-4af6-897e-1c4268b607dd",
  "revision": 0,
  "action": "turn",
  "text": "Proszę o rozmowę z właścicielem"
}
```

Zdarzenie właściciela wymaga `event_id`, `revision`, `action`. Akcje to `dispatch`, `accept`, `decline`, `no_answer`, `finish`, `rotate_caller_token`. **Tylko** `accept`/`decline`/`no_answer` wymagają `attempt_id`, zgodnego z bieżącą dostarczoną ofertą. Pozostałe akcje nie przyjmują niepustego `attempt_id`. Opcjonalne `fail_next_owner=true` jest dozwolone tylko przy `dispatch` i symuluje jedną awarię najbliższego `offer` lub `bridge` w tym dostarczeniu. To parametr testowy właściciela, nie klienta.

```json
{
  "event_id": "590ef404-f336-4aac-b545-8c7d6555300c",
  "revision": 3,
  "action": "accept",
  "attempt_id": "e49456da-1885-4558-bf8e-32fd24ef1f7f"
}
```

Status 401 oznacza brak/niewłaściwy/wygasły token kanału; 403 niewystarczający token usługowy właściciela. 404 dotyczy nieistniejącej rozmowy na trasie właściciela; kanał klienta nie odróżnia nieistniejącego ID od niepoprawnego tokenu. 409 oznacza m.in. starą rewizję, zmianę treści pod istniejącym event_id, zły stan/ID próby albo limit. 422 oznacza niepoprawny schemat, UUID lub niedozwolone pole. Błąd dostarczenia laboratoryjnego jest trwałym stanem/fallbackiem, a nie dowodem kontaktu z operatorem.

## Limity i budżet

| Pole | Domyślnie | Zakres |
|---|---:|---|
| owner_wait_seconds |30 s|1–120 s|
| max_call_seconds |600 s|30–1800 s|
| max_owner_attempts |1|0–1|
| max_simulated_cost_units |2|0–10|
| max_turns |24|1–24|

Pola limitów są ścisłymi liczbami całkowitymi; wartości bool nie zastępują liczb. Próba i pierwsza jednostka budżetu są zużywane przy zakolejkowaniu oferty właścicielowi. Druga jednostka jest zużywana przy zaakceptowaniu i zakolejkowaniu bridge. Błąd, odmowa i timeout nie zwracają zużytego budżetu. Są to **jednostki symulacji**, nie cena, waluta, stawka ani rozliczenie operatora. Zero prób/budżetu nie wysyła oferty, a budżet 1 pozwala na ofertę, lecz nie bridge.

Termin oczekiwania powstaje przy utworzeniu próby i obejmuje także oczekiwanie na ręczne dostarczenie oraz bridge. Akceptacja nie rozpoczyna nowego czasu oczekiwania. Cała rozmowa ma niezależny maksymalny czas. Kryzys nie omija godzin, DND ani urlopu; bieżąca polityka jest sprawdzana przy zakwalifikowaniu oferty, akceptacji i dostarczaniu bridge.

Pozostałe granice: do 256 zachowanych rozmów, do 200 poleceń kolejki na rozmowę, limit 128 potwierdzeń zwykłych zdarzeń i do 20 poleceń w pojedynczym dispatch. Zdarzenia finish/hangup są wyłączone z tego limitu, aby nadal można było zakończyć rozmowę. Właściciel może usunąć ended, aby zwolnić miejsce; samo zakończenie nie usuwa historii. Jeśli rekord dopiero wygasł, najpierw odczytaj/odśwież jego stan albo zakończ go zdarzeniem.

## Trwałość, idempotencja i granica adaptera

Schemat 11 dodaje `transport_calls`, `transport_starts`, `transport_receipts`, `transport_outbox`. Migracja 10→11 tworzy kopię `backups/before-schema11-*.sqlite3` i zachowuje starszą recepcję, pamięć oraz ustawienia. Stany kolejki: pending, delivered, cancelled, failed. Restart nie cofa potwierdzonych dostarczeń ani nie zgaduje zgody właściciela. Po restarcie nadal potrzebny jest ręczny dispatch.

Start jest idempotentny według event_id. Zdarzenia są deduplikowane według rozmowy, kanału i event_id; ten sam ID z inną treścią jest konfliktem. Replay zwraca **bieżący** stan z `replayed=true`, nie dawną kopię odpowiedzi i nie ponawia dostarczenia. Ważna rotacja jest jednorazowa i nie wydaje na replay ponownie sekretu. Gwarancja dotyczy zachowanych rekordów; usunięcie rozmowy kasuje też jej receipt startu/zdarzeń.

Zgoda zapisuje identyfikator zdarzenia i bieżącej próby; adapter dostaje je w poleceniu bridge. Oddzielne typy poleceń pozwalają przekazać tekst tylko klientowi, ofertę/anulowanie tylko właścicielowi, a bridge/end tylko systemowi. `Ack` jest potwierdzeniem źródła lab i jawnie nie potwierdza wykonania rozmowy.

Zmiany recepcji, zgłoszenia oddzwonienia, transportu, kolejki, receiptu i audytu są wykonywane w tej samej transakcji SQLite. Nieoczekiwany błąd końcowego zapisu cofa je razem. Timeout jest odświeżany przed walidacją nowej akcji; jego aktualizacja pozostaje zapisana także wtedy, gdy spóźniona akcja dostanie 409. Zwykłe błędne akcje są cofane do savepointu bez częściowego wpisu.

Rozmowa związana z transportem nie może być zmieniana ani usunięta przez starsze właścicielskie trasy `/api/reception/calls/{id}/events`, `/ai-turn` i DELETE; otrzymują 409. Odczyt pozostaje właścicielski. Klient z tokenem rozmowy nie uzyskuje dostępu do żadnej starej trasy właściciela. Usunięcie zakończonej rozmowy transportu usuwa powiązaną recepcję, sprawy, kolejkę, potwierdzenia i skrót tokenu. Audyt zachowuje identyfikatory/akcje, bez treści klienta, telefonów i surowych tokenów.

Ten rollback jest możliwy, ponieważ obecny adapter jest czystym laboratoryjnym potwierdzeniem. Nie ustanawia transakcji z rzeczywistym operatorem i nie zapewnia zewnętrznego exactly-once. Przyszły adapter wymaga osobnego projektu workera, autoryzacji zdarzeń operatora, idempotencji i niejednoznacznych potwierdzeń, anulowania, limitów rzeczywistych kosztów oraz prywatnych kanałów audio. Nie jest zaimplementowany ani aktywowany. Play, numery, konta i połączenia pozostają poza uruchomieniem tego etapu.

## Weryfikacja

Testy sprawdzają oddzielne kanały/typy, ofertę przed zgodą, zgodę przed oddzielnym bridge, bieżące DND przed akceptacją i delivery, timeout bez drugiej próby, budżet 0/1, awarię offer/bridge, hangup anulujący oczekujące polecenia, ochronę starego laboratorium, tokeny/rotację/TTL, replay, współbieżność, rollback, restart i migrację. Wyniki całej bieżącej wersji znajdują się w README i RAPORT.md. Wydanie 0.8.4 zweryfikowano pełnym zestawem 276 testów Python oraz rzeczywistą przeglądarką Chromium: przebieg transportu, usunięcie zakończonej rozmowy i widok o szerokości 390 px. Przeszedł również przeglądarkowy test regresyjny głosu z syntetycznym mikrofonem. Test adaptera i UI nie jest testem operatora ani jakości AI.
