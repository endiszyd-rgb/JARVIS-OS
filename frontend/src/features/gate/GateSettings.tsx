import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Check, CircleAlert, DoorOpen, KeyRound, Radar, Save, Search } from 'lucide-react'
import { ApiError } from '../../api'
import { FieldLabel, HelpTip } from '../../components/HelpTip'
import { DRIVERS, driverLabels, emptyHomeAssistant, emptyHttp, emptyTuya, emptyTuyaLocal, fetchTuyaLocalKey, readGate, saveGateConfig, scanTuyaLocal, testGate } from './api'
import type { FoundDevice, GateConfig, GateDriver, GateOverview } from './api'
import './gate.css'

interface Props { credential: string; onUnauthorized: () => void }

const SECRET_MASK = '••••••••'
const shortDriver: Record<GateDriver, string> = {
  tuya_local: 'Setti / Tuya lokalnie, bez chmury (zalecane)',
  tuya_cloud: 'Setti / Tuya przez chmurę Tuya', http: 'Przekaźnik w sieci (Shelly, Tasmota, ESP)',
  home_assistant: 'Home Assistant', simulator: 'Symulator — bez sprzętu (do prób)', disabled: 'Wyłączone',
}
const ORDER: GateDriver[] = ['tuya_local', 'tuya_cloud', 'http', 'home_assistant', 'simulator', 'disabled']

function Text({ id, label, help, value, onChange, secret, saved, placeholder, disabled, max = 300 }: {
  id: string; label: string; help?: ReactNode; value: string; onChange: (value: string) => void; secret?: boolean; saved?: boolean; placeholder?: string; disabled: boolean; max?: number
}) {
  // A stored secret comes back as a mask: show an empty field with "zapisany ✓" instead of dots that look like a cut-off key.
  const storedMask = secret && value === SECRET_MASK
  return <div className="form-field"><FieldLabel htmlFor={id} help={help}>{label}</FieldLabel>
    <input id={id} type={secret ? 'password' : 'text'} value={storedMask ? '' : value} maxLength={max} disabled={disabled} autoComplete={secret ? 'new-password' : 'off'}
      placeholder={secret && (saved || storedMask) ? 'zapisany ✓ — wpisz nowy tylko, aby zmienić' : placeholder} onChange={event => onChange(event.target.value.trim() === '' && storedMask ? SECRET_MASK : event.target.value.trim())} /></div>
}

type Signal = boolean | number | string
const BRAMA_SIGNAL_HELP = 'Sygnał, który rusza bramą. Jeśli wcześniej działał tylko przycisk Zamknij, wybierz „Wyłącz”. Sprawdź jednym naciśnięciem „Brama” w widoku Brama.'
const signalKey = (value: Signal) => value === true ? 'on' : value === false ? 'off' : 'other'

/** One-button Setti controllers: "Otwórz" sends exactly what "Zamknij" sends (the same function and value). */
function SameSignal({ id, same, disabled, onChange }: { id: string; same: boolean; disabled: boolean; onChange: (same: boolean) => void }) {
  return <label className="gate-check" htmlFor={id}><input id={id} type="checkbox" checked={same} disabled={disabled} onChange={event => onChange(event.target.checked)} />
    Jeden przycisk w sterowniku: „Otwórz” wysyła ten sam sygnał co „Zamknij”
    <HelpTip topic="Jeden przycisk" text="Zaznacz, gdy sterownik ma jeden sygnał, który raz otwiera, a raz zamyka bramę (np. Setti), i działa tylko jeden z przycisków. Oba przyciski i komenda głosowa „otwórz bramę” wyślą wtedy ten sam, działający sygnał." /></label>
}

/** Which value a button sends: on/off for switch_1 style relays, other values kept as they are. */
function SignalSelect({ id, label, help, value, disabled, onChange }: { id: string; label: string; help: string; value: Signal; disabled: boolean; onChange: (value: Signal) => void }) {
  const key = signalKey(value)
  return <div className="form-field"><FieldLabel htmlFor={id} help={help}>{label}</FieldLabel>
    <select id={id} value={key} disabled={disabled} onChange={event => onChange(event.target.value === 'on' ? true : event.target.value === 'off' ? false : value)}>
      <option value="on">Włącz</option><option value="off">Wyłącz</option>{key === 'other' && <option value="other">Inna wartość: {String(value)}</option>}</select></div>
}

/** Turn the server's driver error into a concrete next step (the generic text hid Tuya's reason). */
export function explain(failure: ApiError): string {
  const detail = failure.detail ?? ''
  const code = /Tuya error (\d+)/.exec(detail)?.[1]
  if (code) {
    const hints: Record<string, string> = {
      '28841107': 'centrum danych projektu jest wstrzymane — na iot.tuya.com: Overview → Edit → usuń wszystkie centra danych → Save → dodaj Central Europe → Save.',
      '28841101': 'wygasł okres próbny IoT Core — Cloud → Cloud Services → IoT Core → Extend Trial Period.',
      '28841105': 'projekt nie ma uprawnień do API — Service API → dodaj IoT Core i Authorization Token Management.',
      '1004': 'zły Access Secret — skopiuj go ponownie z Overview na iot.tuya.com.',
      '1010': 'token wygasł — kliknij jeszcze raz.',
      '1106': 'brak uprawnień do urządzenia — sprawdź, czy sterownik jest w Devices → All Devices i ma prawo zapisu.',
      '2009': 'urządzenie nie obsługuje tego kodu — sprawdź kod w Device Debugging.',
      '2008': 'urządzenie nie obsługuje tego kodu — sprawdź kod w Device Debugging.',
    }
    return 'Tuya (' + code + '): ' + (hints[code] ?? detail.replace(/^Tuya error \d+:\s*/, ''))
  }
  if (detail.startsWith('Tuya local error')) return 'Sterownik w sieci: ' + detail.replace(/^Tuya local error \S*:\s*/, '')
  if (detail === 'Tuya local key is not configured') return 'Brakuje klucza lokalnego — kliknij „Pobierz klucz z chmury Tuya”.'
  if (detail === 'Save the Tuya cloud access (Access ID/Secret) first') return 'Najpierw zapisz dane chmury: wybierz „Setti / Tuya przez chmurę Tuya”, wpisz Access ID i Secret, Zapisz, potem wróć tutaj.'
  if (detail === 'Gate controller is unreachable') return 'Sterownik nie odpowiada — sprawdź adres IP i czy jest w tej samej sieci Wi‑Fi.'
  if (detail === 'Local network scan failed') return 'Nie udało się przeszukać sieci (zapora Windows może blokować porty UDP 6666–6667).'
  return detail && failure.status && failure.status >= 400 && failure.status < 600 && failure.status !== 401 ? detail : failure.message
}

/** Gate driver settings (owner). Everyday control stays in the Gate view. */
export function GateSettings({ credential, onUnauthorized }: Props) {
  const [overview, setOverview] = useState<GateOverview | null>(null)
  const [draft, setDraft] = useState<GateConfig | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [found, setFound] = useState<FoundDevice[] | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized
  const fail = (failure: unknown) => { if (failure instanceof ApiError && failure.status === 401) unauthorized.current(); else setError(failure instanceof ApiError ? explain(failure) : 'Nie udało się wykonać żądania.') }

  const load = useCallback(async (signal: AbortSignal) => {
    const next = await readGate(credential, signal)
    if (!signal.aborted) { setOverview(next); setDraft(structuredClone(next.config)) }
  }, [credential])
  useEffect(() => { const controller = new AbortController(); load(controller.signal).catch(failure => { if (!controller.signal.aborted) fail(failure) }); return () => controller.abort() }, [load])

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft || !overview || busy) return
    setBusy(true); setError(null); setNotice(null)
    try {
      await saveGateConfig(credential, new AbortController().signal, overview.revision, draft)
      await load(new AbortController().signal)
      setNotice('Ustawienia bramy zapisane.')
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) { setError('Ustawienia zmieniły się w międzyczasie — wczytano aktualne.'); void load(new AbortController().signal) }
      else if (failure instanceof ApiError && failure.status === 422) setError('Sprawdź pola wybranego sterownika — serwer odrzucił adres lub identyfikator.')
      else fail(failure)
    } finally { setBusy(false) }
  }
  async function scan() {
    setBusy(true); setError(null); setNotice('Szukam urządzeń Tuya w sieci (ok. 8 sekund)…'); setFound(null)
    try { const devices = await scanTuyaLocal(credential, new AbortController().signal); setFound(devices); setNotice(devices.length ? `Znaleziono: ${devices.length}. Wybierz sterownik bramy z listy.` : 'Nie znaleziono urządzeń. Sprawdź, czy komputer i sterownik są w tej samej sieci Wi‑Fi.') }
    catch (failure) { setNotice(null); fail(failure) } finally { setBusy(false) }
  }
  async function fetchKey() {
    const local = draft?.tuya_local
    if (!draft || !local) return
    if (!local.device_id.trim()) { setError('Najpierw wpisz ID urządzenia (albo wybierz je z wyszukiwania).'); return }
    setBusy(true); setError(null); setNotice(null)
    try { const info = await fetchTuyaLocalKey(credential, new AbortController().signal, local.device_id.trim()); setDraft({ ...draft, tuya_local: { ...local, local_key: info.local_key } }); setNotice('Klucz pobrany' + (info.name ? ` (${info.name})` : '') + '. Kliknij Zapisz.') }
    catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  async function test() {
    setBusy(true); setError(null); setNotice(null)
    try { const gate = await testGate(credential, new AbortController().signal); setNotice(`Sterownik odpowiada. Stan bramy: ${gate.state_label}.`) }
    catch (failure) { fail(failure) } finally { setBusy(false) }
  }

  if (!draft) return error ? <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div> : <p role="status">Odczytywanie ustawień bramy…</p>
  const set = (patch: Partial<GateConfig>) => setDraft({ ...draft, ...patch })
  const tuya = draft.tuya, http = draft.http, ha = draft.home_assistant, local = draft.tuya_local ?? null
  return <form className="gate-form settings-block" onSubmit={event => { void save(event) }} aria-busy={busy}>
    <h2 className="panel-heading"><DoorOpen aria-hidden="true" />Brama</h2>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="gate-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <div className="gate-grid">
      <div className="form-field"><FieldLabel htmlFor="gate-driver" help="Czym JARVIS steruje bramą. Sterownik Setti Wi‑Fi działa w chmurze Tuya — wybierz pierwszą opcję. Symulator pozwala wypróbować przyciski bez ruchu bramy.">Sterownik</FieldLabel>
        <select id="gate-driver" value={draft.driver} disabled={busy} onChange={event => {
          const driver = event.target.value as GateDriver
          set({ driver, http: driver === 'http' ? http ?? { ...emptyHttp } : http, tuya: driver === 'tuya_cloud' ? tuya ?? { ...emptyTuya } : tuya,
            tuya_local: driver === 'tuya_local' ? local ?? { ...emptyTuyaLocal, device_id: tuya?.device_id ?? '' } : local, home_assistant: driver === 'home_assistant' ? ha ?? { ...emptyHomeAssistant } : ha })
        }}>{(ORDER.filter(item => DRIVERS.includes(item))).map(item => <option key={item} value={item} title={driverLabels[item]}>{shortDriver[item]}</option>)}</select></div>
      <Text id="gate-name" label="Nazwa" help="Tak JARVIS nazywa bramę w odpowiedziach, np. „Otwieram: Brama warsztatu”." value={draft.name} max={80} disabled={busy} onChange={name => set({ name })} />
    </div>
    <label className="gate-check"><input type="checkbox" checked={draft.require_confirmation} disabled={busy} onChange={event => set({ require_confirmation: event.target.checked })} />Pytaj „czy na pewno?” przed ruchem bramy</label>
    {draft.driver !== 'disabled' && <label className="gate-check" htmlFor="gate-pulse"><input id="gate-pulse" type="checkbox" checked={draft.pulse} disabled={busy} onChange={event => set({ pulse: event.target.checked })} />
      Jeden przycisk „Brama” (jak pilot)
      <HelpTip topic="Jeden przycisk Brama" text="Dla sterowników, w których jeden sygnał po kolei otwiera, zatrzymuje i zamyka bramę (np. Setti). Zamiast Otwórz/Zamknij/Stop będzie jeden przycisk „Brama”, a komenda głosowa to „Jarvis, brama”." /></label>}

    {draft.driver === 'tuya_local' && local && <fieldset className="gate-fieldset"><legend>Setti / Tuya w sieci warsztatu</legend>
      <p className="workshop-caption">JARVIS łączy się ze sterownikiem bezpośrednio przez Wi‑Fi — działa bez internetu i bez abonamentu Tuya. Chmura jest potrzebna tylko raz, do pobrania klucza.</p>
      <div className="gate-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => { void scan() }}><Search aria-hidden="true" />Znajdź w sieci</button></div>
      {found && found.length > 0 && <ul className="gate-found">{found.map(item => <li key={item.address + item.device_id}><button type="button" className="button subtle" disabled={busy}
        onClick={() => { set({ tuya_local: { ...local, address: item.address, device_id: item.device_id, version: (['3.1', '3.3', '3.4', '3.5'].includes(item.version) ? item.version : 'auto') as typeof local.version } }); setFound(null); setNotice('Wybrano ' + item.address + '. Teraz pobierz klucz.') }}>
        {item.address} · {item.device_id}{item.device_id === tuya?.device_id ? ' · to Twoja brama' : ''}{item.version ? ' · v' + item.version : ''}</button></li>)}</ul>}
      <div className="gate-grid">
        <Text id="local-address" label="Adres IP sterownika" placeholder="192.168.1.50" help="Adres sterownika w sieci warsztatu. Najprościej: „Znajdź w sieci”. Albo w routerze (lista urządzeń) lub w aplikacji Tuya Smart: urządzenie → ✎ → Informacje o urządzeniu → IP. Warto przypisać mu stały adres w routerze." value={local.address} max={45} disabled={busy} onChange={address => set({ tuya_local: { ...local, address } })} />
        <Text id="local-device" label="ID urządzenia" help="Device ID z iot.tuya.com (Devices → All Devices) albo z aplikacji: urządzenie → ✎ → Informacje o urządzeniu → Wirtualny ID. „Znajdź w sieci” wpisze je samo." value={local.device_id} max={64} disabled={busy} onChange={device_id => set({ tuya_local: { ...local, device_id } })} />
        <Text id="local-key" label="Klucz lokalny" secret saved={local.local_key_set} help="16-znakowy klucz szyfrowania urządzenia. Kliknij „Pobierz klucz z chmury Tuya” — działa, gdy dane chmury (Access ID/Secret) są zapisane i okres IoT Core jest aktywny. Klucz zmienia się, gdy urządzenie dodasz w aplikacji od nowa." value={local.local_key} max={64} disabled={busy} onChange={local_key => set({ tuya_local: { ...local, local_key } })} />
      </div>
      <div className="gate-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => { void fetchKey() }}><KeyRound aria-hidden="true" />Pobierz klucz z chmury Tuya</button></div>
      {draft.pulse ? <div className="gate-grid"><SignalSelect id="local-pulse-value" label="Sygnał przycisku Brama" help={BRAMA_SIGNAL_HELP} value={local.open_value} disabled={busy}
          onChange={value => set({ tuya_local: { ...local, open_value: value, close_dp: local.open_dp, close_value: value } })} /></div>
        : <SameSignal id="local-same" disabled={busy} same={local.open_dp === local.close_dp && local.open_value === local.close_value}
        onChange={same => set({ tuya_local: same ? { ...local, open_dp: local.close_dp, open_value: local.close_value } : { ...local, open_value: true, close_value: false } })} />}
      <details className="settings-more"><summary>Więcej opcji</summary><div className="gate-grid">
        {!draft.pulse && <><SignalSelect id="local-open-value" label="Sygnał przycisku Otwórz" help="Co wysyła przycisk Otwórz: Włącz albo Wyłącz przekaźnika. Domyślnie Włącz." value={local.open_value} disabled={busy} onChange={open_value => set({ tuya_local: { ...local, open_value } })} />
        <SignalSelect id="local-close-value" label="Sygnał przycisku Zamknij" help="Co wysyła przycisk Zamknij. Domyślnie Wyłącz." value={local.close_value} disabled={busy} onChange={close_value => set({ tuya_local: { ...local, close_value } })} /></>}
        <div className="form-field"><FieldLabel htmlFor="local-version" help="Wersja protokołu Tuya. „Automatycznie” sprawdzi 3.3, 3.4, 3.5 i 3.1 i zapamięta działającą. „Znajdź w sieci” podaje ją sama.">Wersja protokołu</FieldLabel>
          <select id="local-version" value={local.version} disabled={busy} onChange={event => set({ tuya_local: { ...local, version: event.target.value as typeof local.version } })}><option value="auto">Automatycznie</option><option value="3.3">3.3</option><option value="3.4">3.4</option><option value="3.5">3.5</option><option value="3.1">3.1</option></select></div>
        <div className="form-field"><FieldLabel htmlFor="local-open" help="Numer funkcji (DP) przekaźnika. Dla switch_1 to 1. Inne numery widać w Device Debugging na iot.tuya.com.">Numer funkcji otwarcia</FieldLabel><input id="local-open" type="number" min={1} max={255} value={local.open_dp} disabled={busy} onChange={event => set({ tuya_local: { ...local, open_dp: Number(event.target.value) } })} /></div>
        <div className="form-field"><FieldLabel htmlFor="local-close" help="Zwykle ten sam numer co otwarcie (1), z wartością „wyłącz”.">Numer funkcji zamknięcia</FieldLabel><input id="local-close" type="number" min={1} max={255} value={local.close_dp} disabled={busy} onChange={event => set({ tuya_local: { ...local, close_dp: Number(event.target.value) } })} /></div>
        <div className="form-field"><FieldLabel htmlFor="local-status" help="Numer funkcji czujnika krańcowego, jeśli jest. 0 = brak czujnika.">Numer funkcji stanu</FieldLabel><input id="local-status" type="number" min={0} max={255} value={local.status_dp} disabled={busy} onChange={event => set({ tuya_local: { ...local, status_dp: Number(event.target.value) } })} /></div>
      </div></details>
    </fieldset>}

    {draft.driver === 'tuya_cloud' && tuya && <fieldset className="gate-fieldset"><legend>Setti / Tuya przez chmurę</legend>
      <div className="gate-grid">
        <div className="form-field"><FieldLabel htmlFor="tuya-endpoint" help="Region konta Tuya. W Polsce prawie zawsze „Europa Centralna”.">Region</FieldLabel>
          <select id="tuya-endpoint" value={tuya.endpoint} disabled={busy} onChange={event => set({ tuya: { ...tuya, endpoint: event.target.value } })}>
            <option value="https://openapi.tuyaeu.com">Europa Centralna</option><option value="https://openapi-weaz.tuyaeu.com">Europa Zachodnia</option><option value="https://openapi.tuyaus.com">USA</option><option value="https://openapi-ueaz.tuyaus.com">USA Wschód</option><option value="https://openapi.tuyacn.com">Chiny</option><option value="https://openapi.tuyain.com">Indie</option></select></div>
        <Text id="tuya-id" label="Access ID" help={<>Na <code>iot.tuya.com</code>: Cloud → Development → Twój projekt → Overview → <b>Access ID/Client ID</b>.</>} value={tuya.access_id} max={64} disabled={busy} onChange={access_id => set({ tuya: { ...tuya, access_id } })} />
        <Text id="tuya-secret" label="Access Secret" secret saved={tuya.access_secret_set} help="Tam samo, pole Access Secret/Client Secret (kliknij oko, aby je pokazać). Po zapisaniu nie jest już wyświetlane." value={tuya.access_secret} max={128} disabled={busy} onChange={access_secret => set({ tuya: { ...tuya, access_secret } })} />
        <Text id="tuya-device" label="ID urządzenia" help="Projekt → Devices → sterownik bramy → kolumna Device ID. Wcześniej połącz w projekcie konto aplikacji (Devices → Link App Account)." value={tuya.device_id} max={64} disabled={busy} onChange={device_id => set({ tuya: { ...tuya, device_id } })} />
      </div>
      {draft.pulse ? <div className="gate-grid"><SignalSelect id="tuya-pulse-value" label="Sygnał przycisku Brama" help={BRAMA_SIGNAL_HELP} value={tuya.open_value} disabled={busy}
          onChange={value => set({ tuya: { ...tuya, open_value: value, close_code: tuya.open_code, close_value: value } })} /></div>
        : <SameSignal id="tuya-same" disabled={busy} same={tuya.open_code === tuya.close_code && tuya.open_value === tuya.close_value}
        onChange={same => set({ tuya: same ? { ...tuya, open_code: tuya.close_code, open_value: tuya.close_value } : { ...tuya, open_value: true, close_value: false } })} />}
      <details className="settings-more"><summary>Więcej opcji</summary><div className="gate-grid">
        {!draft.pulse && <><SignalSelect id="tuya-open-value" label="Sygnał przycisku Otwórz" help="Co wysyła przycisk Otwórz: Włącz (true) albo Wyłącz (false). Domyślnie Włącz." value={tuya.open_value} disabled={busy} onChange={open_value => set({ tuya: { ...tuya, open_value } })} />
        <SignalSelect id="tuya-close-value" label="Sygnał przycisku Zamknij" help="Co wysyła przycisk Zamknij. Domyślnie Wyłącz (false)." value={tuya.close_value} disabled={busy} onChange={close_value => set({ tuya: { ...tuya, close_value } })} /></>}
        <Text id="tuya-open" label="Kod otwarcia" help={<>Nazwa funkcji sterownika z zakładki Device Debugging. Zwykle <code>switch_1</code> — zostaw, jeśli nie wiesz.</>} value={tuya.open_code} max={64} disabled={busy} onChange={open_code => set({ tuya: { ...tuya, open_code } })} />
        <Text id="tuya-close" label="Kod zamknięcia" help="Zwykle ten sam co otwarcia (switch_1) z wartością „wyłącz”." value={tuya.close_code} max={64} disabled={busy} onChange={close_code => set({ tuya: { ...tuya, close_code } })} />
        <Text id="tuya-stop" label="Kod zatrzymania" help="Opcjonalnie. Puste — przycisk Stop będzie niedostępny." value={tuya.stop_code} max={64} disabled={busy} onChange={stop_code => set({ tuya: { ...tuya, stop_code } })} />
        <Text id="tuya-status" label="Kod stanu" help={<>Opcjonalnie, jeśli sterownik ma czujnik krańcowy, np. <code>doorcontact_state</code>. Wtedy JARVIS pokazuje prawdziwy stan bramy.</>} value={tuya.status_code} max={64} disabled={busy} onChange={status_code => set({ tuya: { ...tuya, status_code } })} />
      </div></details>
    </fieldset>}

    {draft.driver === 'http' && http && <fieldset className="gate-fieldset"><legend>Przekaźnik w sieci</legend>
      <div className="gate-grid">
        <Text id="http-open_url" label="Adres otwarcia" placeholder="http://192.168.1.50/relay/0?turn=on" help={<>Adres, który włącza przekaźnik. Shelly: <code>http://IP/relay/0?turn=on</code>, Tasmota: <code>http://IP/cm?cmnd=Power%20On</code>. Sieć musi być w <code>JARVIS_NETWORK_ALLOWLIST</code>.</>} value={http.open_url} max={500} disabled={busy} onChange={open_url => set({ http: { ...http, open_url } })} />
        <Text id="http-close_url" label="Adres zamknięcia" placeholder="http://192.168.1.50/relay/0?turn=off" help="Adres zamykający. Przy bramie impulsowej może być taki sam jak otwarcia." value={http.close_url} max={500} disabled={busy} onChange={close_url => set({ http: { ...http, close_url } })} />
      </div>
      <details className="settings-more"><summary>Więcej opcji</summary><div className="gate-grid">
        <Text id="http-stop_url" label="Adres zatrzymania" help="Opcjonalnie." value={http.stop_url} max={500} disabled={busy} onChange={stop_url => set({ http: { ...http, stop_url } })} />
        <Text id="http-status_url" label="Adres stanu" help="Opcjonalnie: adres zwracający stan przekaźnika, np. Shelly http://IP/relay/0." value={http.status_url} max={500} disabled={busy} onChange={status_url => set({ http: { ...http, status_url } })} />
        <Text id="http-match" label="Tekst „otwarta”" placeholder={'"ison":true'} help="Fragment odpowiedzi adresu stanu oznaczający otwartą bramę." value={http.status_open_match} max={120} disabled={busy} onChange={status_open_match => set({ http: { ...http, status_open_match } })} />
        <div className="form-field"><FieldLabel htmlFor="http-method" help="Większość przekaźników przyjmuje GET.">Metoda</FieldLabel><select id="http-method" value={http.method} disabled={busy} onChange={event => set({ http: { ...http, method: event.target.value as 'GET' | 'POST' } })}><option>GET</option><option>POST</option></select></div>
        <Text id="http-user" label="Użytkownik" help="Jeśli przekaźnik ma włączone logowanie." value={http.username} max={120} disabled={busy} onChange={username => set({ http: { ...http, username } })} />
        <Text id="http-pass" label="Hasło" secret saved={http.password_set} help="Hasło przekaźnika. Po zapisaniu nie jest wyświetlane." value={http.password} max={200} disabled={busy} onChange={password => set({ http: { ...http, password } })} />
      </div></details>
    </fieldset>}

    {draft.driver === 'home_assistant' && ha && <fieldset className="gate-fieldset"><legend>Home Assistant</legend>
      <div className="gate-grid">
        <Text id="ha-url" label="Adres Home Assistant" placeholder="http://192.168.1.10:8123" help="Puste — użyj HA_URL z pliku .env." value={ha.url} disabled={busy} onChange={url => set({ home_assistant: { ...ha, url } })} />
        <Text id="ha-token" label="Token" secret saved={ha.token_set} help="Profil w Home Assistant → Tokeny dostępu długoterminowego → Utwórz." value={ha.token} max={500} disabled={busy} onChange={token => set({ home_assistant: { ...ha, token } })} />
        <Text id="ha-entity" label="Encja bramy" placeholder="cover.brama" help="Identyfikator bramy w Home Assistant (Ustawienia → Encje), np. cover.brama." value={ha.entity_id} max={120} disabled={busy} onChange={entity_id => set({ home_assistant: { ...ha, entity_id } })} />
      </div>
      <details className="settings-more"><summary>Więcej opcji</summary><div className="gate-grid">
        <Text id="ha-open" label="Usługa otwarcia" help="Domyślnie cover.open_cover." value={ha.open_service} disabled={busy} onChange={open_service => set({ home_assistant: { ...ha, open_service } })} />
        <Text id="ha-close" label="Usługa zamknięcia" help="Domyślnie cover.close_cover." value={ha.close_service} disabled={busy} onChange={close_service => set({ home_assistant: { ...ha, close_service } })} />
        <Text id="ha-stop" label="Usługa zatrzymania" help="Domyślnie cover.stop_cover." value={ha.stop_service} disabled={busy} onChange={stop_service => set({ home_assistant: { ...ha, stop_service } })} />
      </div></details>
    </fieldset>}

    {draft.driver !== 'disabled' && <details className="settings-more"><summary>Zachowanie bramy</summary>
      <div className="gate-grid">
        <div className="form-field"><FieldLabel htmlFor="gate-cooldown" help="Minimalna przerwa między poleceniami — chroni przed przypadkowym podwójnym kliknięciem.">Przerwa między poleceniami (s)</FieldLabel><input id="gate-cooldown" type="number" min={0} max={120} value={draft.cooldown_seconds} disabled={busy} onChange={event => set({ cooldown_seconds: Number(event.target.value) })} /></div>
        <div className="form-field"><FieldLabel htmlFor="gate-travel" help="Ile sekund brama jedzie od zamkniętej do otwartej. JARVIS pokazuje „otwiera się” przez ten czas.">Czas ruchu bramy (s)</FieldLabel><input id="gate-travel" type="number" min={1} max={300} value={draft.travel_seconds} disabled={busy} onChange={event => set({ travel_seconds: Number(event.target.value) })} /></div>
      </div>
    </details>}

    <div className="gate-actions"><button type="submit" className="button primary" disabled={busy}><Save aria-hidden="true" />Zapisz</button>
      <button type="button" className="button secondary" disabled={busy || overview?.config.driver === 'disabled'} onClick={() => { void test() }}><Radar aria-hidden="true" />Sprawdź połączenie (brama się nie ruszy)</button></div>
  </form>
}
