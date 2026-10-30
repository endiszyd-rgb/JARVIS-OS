# Eksperyment OpenClaw + JARVIS

Stan: działający prototyp lokalny z 30.10.2026. To nie jest zamiennik obecnego JARVIS-a ani konfiguracja produkcyjna.

## Decyzja architektoniczna

- **OpenClaw** odpowiada za rozmowę, wybór modelu, panel i kanały.
- **JARVIS** pozostaje jedynym adapterem AutoLogiki i miejscem egzekwowania tożsamości, zakresów, odwołania dostępu oraz audytu.
- **Home Assistant** pozostaje warstwą urządzeń. Prototyp udostępnia tylko jeden odczyt stanu przez istniejący adapter JARVIS; nie ma wywołań usług ani sterowania.

JARVIS jest klientem MCP, ale nie udostępnia serwera MCP. Dlatego prototyp używa oficjalnego pluginu narzędzi OpenClaw i istniejącego lokalnego HTTP JARVIS. Nie dodano fikcyjnego MCP ani nowych tras AutoLogiki.

## Przypięte zależności i licencje

| Projekt | Przypięcie | Licencja | Użycie |
|---|---|---|---|
| OpenClaw | `v2026.10.7`, commit `157d8c2bc3ea2fa183afdc11088e69690bf8e64e`, npm `2026.10.7` | MIT | host pluginu i agenta |
| Node.js | `24.22.1`, Windows ZIP SHA-256 `d2046d28c2c3dcd211ac5145c0bf30e2047ef9dfb306693c8c6e2eccd8b95fa5` | Node.js license | runtime wymagany przez przypięty OpenClaw |
| Home Assistant Core | osobna instalacja operatora; nie jest vendoryzowany | Apache-2.0 | tylko istniejący REST state read JARVIS |

API pluginów OpenClaw jest oznaczone jako eksperymentalne, dlatego zarówno host, jak i peer dependency pluginu są przypięte dokładnie do `2026.10.7`. Źródła: [wydanie OpenClaw](https://github.com/openclaw/openclaw/releases/tag/v2026.10.7), [repozytorium i licencja OpenClaw](https://github.com/openclaw/openclaw), [oficjalne budowanie pluginów](https://docs.openclaw.ai/plugins/building-plugins), [manifest pluginu](https://docs.openclaw.ai/plugins/manifest), [Home Assistant Core](https://github.com/home-assistant/core).

## Powierzchnia pluginu

Plugin `integrations/openclaw/autologika-jarvis-plugin` rejestruje dokładnie dwa opcjonalne narzędzia:

1. `jarvis_workshop_orders` — `GET /api/v1/autologika/snapshot/orders`, maksymalnie 20 rekordów, bez danych klienta;
2. `jarvis_home_entity_state` — `GET /api/v1/home/states/{entity}`, tylko encja jawnie wpisana do allowlisty operatora.

Ograniczenia techniczne:

- jedynie `http://localhost`, `127.0.0.1` lub `::1`, bez ścieżki, userinfo, query i fragmentu;
- timeout 4 s i odpowiedź maksymalnie 256 KiB;
- osobne, wąskie i odwoływalne tokeny `workshop:read` oraz `home:read`;
- brak arbitralnego URL, metody, ścieżki i operacji;
- brak terminala, plików hosta, Docker socket, wiadomości, zakupów i sterowania urządzeniami;
- błędy nie zwracają body backendu ani sekretów;
- teksty z narzędzia są oznaczone `untrusted_tool_data` i nigdy nie są instrukcjami.

Konfiguracja używa profilu `minimal`, `alsoAllow` dla dwóch narzędzi, `toolSearch: false` i jawnych deny dla runtime, plików, wiadomości, urządzeń, automatyzacji, `gateway`, `session_status` i `presence`. Model nie przekazuje roli, konta ani warsztatu. Zakres pochodzi wyłącznie ze zweryfikowanego tokenu JARVIS.

## Uruchomienie na Windows 11

OpenClaw oficjalnie wspiera Windows natywnie i przez WSL2; WSL2 jest wariantem najbardziej zgodnym z Linuksem. Zobacz [instrukcję Windows](https://docs.openclaw.ai/platforms/windows) oraz [zmienne izolacji](https://docs.openclaw.ai/help/environment).

1. Zainstaluj dokładnie Node.js `24.22.1` albo `26.12.1+`. Prototyp zweryfikowano na przenośnym Node `24.22.1`.
2. Ustaw osobne katalogi, nie współdzielone z inną instalacją:

```powershell
$env:OPENCLAW_HOME = "$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\home"
$env:OPENCLAW_STATE_DIR = "$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\state"
$env:OPENCLAW_CONFIG_PATH = "$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\config\openclaw.json"
$env:OPENCLAW_WORKSPACE_DIR = "$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\workspace"
```

3. Zbuduj i zapakuj plugin:

```powershell
cd integrations\openclaw\autologika-jarvis-plugin
npm.cmd ci --ignore-scripts
npm.cmd test
npm.cmd pack --pack-destination "$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\artifacts"
```

4. Zainstaluj dokładny artefakt i sprawdź runtime:

```powershell
.\node_modules\.bin\openclaw.cmd plugins install "npm-pack:$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\artifacts\autologika-openclaw-jarvis-readonly-0.1.0-experiment.1.tgz" --force --accept-capabilities
.\node_modules\.bin\openclaw.cmd plugins enable autologika-jarvis-readonly --accept-capabilities
.\node_modules\.bin\openclaw.cmd plugins inspect autologika-jarvis-readonly --runtime --json
```

Pakiet lokalny nie pochodzi z ClawHub ani publicznego npm, dlatego OpenClaw prawidłowo zgłasza ostrzeżenie `provenance-invalid`. Przed włączeniem sprawdź zawartość paczki i wynik `plugins inspect`; `plugins.allow` w przykładowej konfiguracji jest jawną decyzją operatora, ale nie zmienia lokalnej paczki w zaufany artefakt wydawcy.

5. Skopiuj `integrations/openclaw/openclaw.example.json` do osobnego `OPENCLAW_CONFIG_PATH`. Ustaw prawdziwego, dostępnego dostawcę modelu i jego sekret jako zmienną środowiskową/SecretRef. Nie zapisuj sekretu w JSON.
6. W panelu JARVIS utwórz dwa tokeny usługowe: tylko `workshop:read` i tylko `home:read`. Przekaż je procesowi jako `JARVIS_OPENCLAW_WORKSHOP_TOKEN` i `JARVIS_OPENCLAW_HOME_TOKEN`. Ustaw także `JARVIS_OPENCLAW_BASE_URL=http://127.0.0.1:<port>` oraz `JARVIS_OPENCLAW_HA_ALLOWED_ENTITIES`.

Przykład nie zawiera sekretów i nie włącza żadnego kanału komunikacji.

## WSL2 i Docker

W WSL2 użyj tych samych czterech zmiennych z linuksowymi ścieżkami i dokładnej wersji Node. Plugin buduje się przez `npm ci`, a JARVIS musi pozostać osiągalny na jawnie wybranym loopback/forward. Nie poszerzaj allowlisty sieci do `0.0.0.0/0`.

Oficjalny obraz/Compose OpenClaw można odizolować osobnym wolumenem, siecią bez publikacji publicznej i bez montowania Docker socket. Instrukcja: [OpenClaw Docker](https://docs.openclaw.ai/install/docker). Docker i WSL2 nie były dostępne w tym środowisku, więc nie są oznaczone jako wykonane testy.

## Powtarzalny test prototypu

Po instalacji pakietu uruchom z katalogu repozytorium (ścieżki dostosuj do lokalnego Node):

```powershell
.\.venv\Scripts\python.exe scripts\check_openclaw_prototype.py `
  --node "$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\tools\node-v24.22.1-win-x64\node.exe" `
  --openclaw-entry ".\integrations\openclaw\autologika-jarvis-plugin\node_modules\openclaw\openclaw.mjs" `
  --openclaw-state "$env:LOCALAPPDATA\JARVIS-OpenClaw-Lab\state" `
  --plugin-path ".\integrations\openclaw\autologika-jarvis-plugin" `
  --evidence ".\docs\evals\openclaw-prototype-2026-10-30.json"
```

Skrypt uruchamia wyłącznie loopback: syntetyczny snapshot AutoLogiki, Home Assistant mock, JARVIS oraz kontrolowany serwer zgodny z OpenAI Chat Completions. Dwa rzeczywiste przebiegi runtime OpenClaw potwierdzają źródła. Kontrolowany model nie wykonuje inferencji, dlatego wynik nie dowodzi jakości prawdziwego modelu.

Wynik bieżący: PASS dla odczytu warsztatu, odczytu encji HA po realnym HTTP, odmowy bez zakresu, odwołania tokenu, braku niezarejestrowanej operacji, limitów argumentów/timeoutu/niedostępności, redakcji sekretów i prompt injection w tytule zlecenia. Dowód: `docs/evals/openclaw-prototype-2026-10-30.json`.

## Cofnięcie

1. Cofnij oba tokeny w JARVIS — odcięcie jest natychmiastowe.
2. `openclaw plugins uninstall autologika-jarvis-readonly` w izolowanym profilu.
3. Zatrzymaj procesy i usuń wyłącznie jawnie utworzony katalog `%LOCALAPPDATA%\JARVIS-OpenClaw-Lab`.
4. Usuń lokalny branch eksperymentalny, jeżeli wynik nie zostanie przyjęty. Nie ma migracji bazy ani zmian AutoLogiki/Supabase do cofnięcia.

## Znane braki

- brak realnej inferencji i oceny jakości odpowiedzi modelu;
- brak testu WSL2/Docker w bieżącym środowisku;
- brak rzeczywistego Home Assistant i urządzeń — tylko mock HTTP;
- brak kanałów WhatsApp/telefonii i brak publicznego Gateway;
- eksperymentalne API pluginów wymaga ponownej walidacji przy każdej zmianie wersji OpenClaw;
- lokalny pakiet nie ma zewnętrznie weryfikowalnej proweniencji ClawHub/npm; wymaga ręcznego przeglądu i jawnej allowlisty;
- adapter AutoLogiki nadal czyta offline snapshot; jedyne potwierdzone live HTTP pozostają `GET /api/orders` i `GET /api/order/{id}`.

Rekomendacja: OpenClaw jest wart dalszego pilotażu jako warstwa rozmowy/panelu, ale nie powinien przejmować reguł właściciela ani adaptera AutoLogiki. Przyjąć go warunkowo dopiero po teście wybranego realnego modelu, aktualizacji pinu i ponowieniu całego zestawu bezpieczeństwa.
