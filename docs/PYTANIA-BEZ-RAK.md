# Pytania bez rąk: Siri + słuchawka (0.19.0)

Cel: przy aucie powiedzieć „Hej Siri, Jarvis”, zapytać o moment dokręcania albo powiedzieć „brama” i usłyszeć odpowiedź w słuchawce — bez odrywania się od pracy.

```
słuchawka BT ─ iPhone (Siri → skrót „Jarvis”) ─ Tailscale ─ JARVIS na PC warsztatowym
                                                            ├─ „brama”, „tak/nie” → sterownik bramy (lokalnie)
                                                            └─ inne pytania → Claude API + wyszukiwarka → odpowiedź + źródło
```

## 1. Odpowiedzi z internetu (komputer warsztatowy)

*Ustawienia → Głos → Odpowiedzi z internetu*:

1. Klucz z **console.anthropic.com** → *API Keys* → *Create Key* (`sk-ant-…`). W konsoli ustaw miesięczny limit wydatków. Każde pytanie to 1–3 wyszukiwania + odpowiedź modelu (rozliczane przez Anthropic za użycie).
2. Zaznacz „Odpowiadaj na pytania z internetu”, model **Claude Sonnet** (zalecany), *Zapisz*.
3. *Pytanie testowe* → np. „moment dokręcania kół Skoda Octavia 3” → odpowiedź i linki do źródeł.

JARVIS mówi krótko (do 3 zdań), po polsku, podaje wartość z jednostką i warunkami oraz źródło; gdy źródła się różnią albo brakuje modelu/silnika — mówi to albo dopytuje. Pamięta 3 ostatnie pytania z tego telefonu przez 15 minut („a dla Passata B8?”). **To dane z internetu, nie z dokumentacji producenta** — przy głowicy, zawieszeniu i hamulcach sprawdź wartość.

## 2. Klucz telefonu (na iPhonie, przez Tailscale)

Wymaga konta z 2FA (*Moje konto*) i Tailscale (instrukcja: [DOSTEP-ZDALNY.md](DOSTEP-ZDALNY.md)).

1. Na iPhonie otwórz panel przez adres Tailscale, zaloguj się (hasło + kod 2FA albo Face ID).
2. *Moje konto → Telefon i Siri* → nazwa „iPhone” → **Dodaj telefon**. Pokazuje się **adres** i **klucz** — tylko raz.
3. Klucz telefonu działa wyłącznie dla pytań (`/api/v1/voice/ask`) i bramy (`/api/v1/devices/gate/command`); nie otworzy ustawień, kamer, pamięci ani rozmów. Usunięcie telefonu w *Moje konto* albo reset/wyłączenie 2FA konta od razu go unieważnia. Klucz jest zapisany w bazie jako SHA-256.

## 3. Skrót „Jarvis” w aplikacji Skróty

1. **Skróty** → **+** → nazwa **Jarvis**.
2. **Dyktuj tekst** — język polski, „Przestań słuchać”: po przerwie.
3. **Pobierz zawartość URL** — adres z kroku 2, Metoda **POST**, Nagłówki: `X-Jarvis-Key` = klucz, Treść żądania **JSON**: `text` (Tekst) = *Dyktowany tekst*.
4. **Pobierz wartość ze słownika** — klucz `speech`, słownik = *Zawartość URL*.
5. **Mów tekst** — *Wartość słownika*.

Użycie: „Hej Siri, Jarvis” → (sygnał) → „moment dokręcania śrub koła Golf 7” albo „brama”. Przy włączonym „Pytaj czy na pewno” JARVIS odpowie „Uruchomić bramę? Powiedz tak” — wtedy jeszcze raz „Hej Siri, Jarvis” → „tak”.

Odpowiedź API: `{"speech": "...", "kind": "answer|command|error", "sources": [{"title","url"}]}`. Błędy (brak klucza, odrzucony klucz, brak internetu, limit 15 pytań/minutę) wracają jako zdanie do przeczytania (HTTP 200), żeby Siri zawsze coś powiedziała.

## Ograniczenia

- Nie testowane na prawdziwym iPhonie/Siri ani z prawdziwym kluczem Claude (testy z atrapą API Anthropic).
- Siri wymaga internetu w telefonie i włączonego Tailscale; komputer warsztatowy musi działać z JARVIS i Tailscale.
- Aplikacja Skróty nie pozwala zaimportować niepodpisanego pliku skrótu, dlatego skrót trzeba złożyć z 4 akcji (raz).
