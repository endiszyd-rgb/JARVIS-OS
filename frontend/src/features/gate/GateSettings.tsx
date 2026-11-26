import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Check, CircleAlert, DoorOpen, Radar, Save } from 'lucide-react'
import { ApiError } from '../../api'
import { FieldLabel } from '../../components/HelpTip'
import { DRIVERS, driverLabels, emptyHomeAssistant, emptyHttp, emptyTuya, readGate, saveGateConfig, testGate } from './api'
import type { GateConfig, GateDriver, GateOverview } from './api'
import './gate.css'

interface Props { credential: string; onUnauthorized: () => void }

const shortDriver: Record<GateDriver, string> = {
  tuya_cloud: 'Setti / Tuya (aplikacja Setti+, Smart Life)', http: 'Przekaźnik w sieci (Shelly, Tasmota, ESP)',
  home_assistant: 'Home Assistant', simulator: 'Symulator — bez sprzętu (do prób)', disabled: 'Wyłączone',
}
const ORDER: GateDriver[] = ['tuya_cloud', 'http', 'home_assistant', 'simulator', 'disabled']

function Text({ id, label, help, value, onChange, secret, saved, placeholder, disabled, max = 300 }: {
  id: string; label: string; help?: ReactNode; value: string; onChange: (value: string) => void; secret?: boolean; saved?: boolean; placeholder?: string; disabled: boolean; max?: number
}) {
  return <div className="form-field"><FieldLabel htmlFor={id} help={help}>{label}</FieldLabel>
    <input id={id} type={secret ? 'password' : 'text'} value={value} maxLength={max} disabled={disabled} autoComplete={secret ? 'new-password' : 'off'}
      placeholder={secret && saved ? 'zapisane — zostaw puste, aby nie zmieniać' : placeholder} onChange={event => onChange(event.target.value)} /></div>
}

/** Gate driver settings (owner). Everyday control stays in the Gate view. */
export function GateSettings({ credential, onUnauthorized }: Props) {
  const [overview, setOverview] = useState<GateOverview | null>(null)
  const [draft, setDraft] = useState<GateConfig | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized
  const fail = (failure: unknown) => { if (failure instanceof ApiError && failure.status === 401) unauthorized.current(); else setError(failure instanceof ApiError ? failure.message : 'Nie udało się wykonać żądania.') }

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
  async function test() {
    setBusy(true); setError(null); setNotice(null)
    try { const gate = await testGate(credential, new AbortController().signal); setNotice(`Sterownik odpowiada. Stan bramy: ${gate.state_label}.`) }
    catch (failure) { fail(failure) } finally { setBusy(false) }
  }

  if (!draft) return error ? <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div> : <p role="status">Odczytywanie ustawień bramy…</p>
  const set = (patch: Partial<GateConfig>) => setDraft({ ...draft, ...patch })
  const tuya = draft.tuya, http = draft.http, ha = draft.home_assistant
  return <form className="gate-form settings-block" onSubmit={event => { void save(event) }} aria-busy={busy}>
    <h2 className="panel-heading"><DoorOpen aria-hidden="true" />Brama</h2>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="gate-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <div className="gate-grid">
      <div className="form-field"><FieldLabel htmlFor="gate-driver" help="Czym JARVIS steruje bramą. Sterownik Setti Wi‑Fi działa w chmurze Tuya — wybierz pierwszą opcję. Symulator pozwala wypróbować przyciski bez ruchu bramy.">Sterownik</FieldLabel>
        <select id="gate-driver" value={draft.driver} disabled={busy} onChange={event => {
          const driver = event.target.value as GateDriver
          set({ driver, http: driver === 'http' ? http ?? { ...emptyHttp } : http, tuya: driver === 'tuya_cloud' ? tuya ?? { ...emptyTuya } : tuya, home_assistant: driver === 'home_assistant' ? ha ?? { ...emptyHomeAssistant } : ha })
        }}>{(ORDER.filter(item => DRIVERS.includes(item))).map(item => <option key={item} value={item} title={driverLabels[item]}>{shortDriver[item]}</option>)}</select></div>
      <Text id="gate-name" label="Nazwa" help="Tak JARVIS nazywa bramę w odpowiedziach, np. „Otwieram: Brama warsztatu”." value={draft.name} max={80} disabled={busy} onChange={name => set({ name })} />
    </div>
    <label className="gate-check"><input type="checkbox" checked={draft.require_confirmation} disabled={busy} onChange={event => set({ require_confirmation: event.target.checked })} />Pytaj „czy na pewno?” przed ruchem bramy</label>

    {draft.driver === 'tuya_cloud' && tuya && <fieldset className="gate-fieldset"><legend>Setti / Tuya</legend>
      <div className="gate-grid">
        <div className="form-field"><FieldLabel htmlFor="tuya-endpoint" help="Region konta Tuya. W Polsce prawie zawsze „Europa Centralna”.">Region</FieldLabel>
          <select id="tuya-endpoint" value={tuya.endpoint} disabled={busy} onChange={event => set({ tuya: { ...tuya, endpoint: event.target.value } })}>
            <option value="https://openapi.tuyaeu.com">Europa Centralna</option><option value="https://openapi-weaz.tuyaeu.com">Europa Zachodnia</option><option value="https://openapi.tuyaus.com">USA</option><option value="https://openapi-ueaz.tuyaus.com">USA Wschód</option><option value="https://openapi.tuyacn.com">Chiny</option><option value="https://openapi.tuyain.com">Indie</option></select></div>
        <Text id="tuya-id" label="Access ID" help={<>Na <code>iot.tuya.com</code>: Cloud → Development → Twój projekt → Overview → <b>Access ID/Client ID</b>.</>} value={tuya.access_id} max={64} disabled={busy} onChange={access_id => set({ tuya: { ...tuya, access_id } })} />
        <Text id="tuya-secret" label="Access Secret" secret saved={tuya.access_secret_set} help="Tam samo, pole Access Secret/Client Secret (kliknij oko, aby je pokazać). Po zapisaniu nie jest już wyświetlane." value={tuya.access_secret} max={128} disabled={busy} onChange={access_secret => set({ tuya: { ...tuya, access_secret } })} />
        <Text id="tuya-device" label="ID urządzenia" help="Projekt → Devices → sterownik bramy → kolumna Device ID. Wcześniej połącz w projekcie konto aplikacji (Devices → Link App Account)." value={tuya.device_id} max={64} disabled={busy} onChange={device_id => set({ tuya: { ...tuya, device_id } })} />
      </div>
      <details className="settings-more"><summary>Więcej opcji</summary><div className="gate-grid">
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
      <label className="gate-check"><input type="checkbox" checked={draft.pulse} disabled={busy} onChange={event => set({ pulse: event.target.checked })} />Brama impulsowa (jeden przycisk otwiera i zamyka)</label>
      <div className="gate-grid">
        <div className="form-field"><FieldLabel htmlFor="gate-cooldown" help="Minimalna przerwa między poleceniami — chroni przed przypadkowym podwójnym kliknięciem.">Przerwa między poleceniami (s)</FieldLabel><input id="gate-cooldown" type="number" min={0} max={120} value={draft.cooldown_seconds} disabled={busy} onChange={event => set({ cooldown_seconds: Number(event.target.value) })} /></div>
        <div className="form-field"><FieldLabel htmlFor="gate-travel" help="Ile sekund brama jedzie od zamkniętej do otwartej. JARVIS pokazuje „otwiera się” przez ten czas.">Czas ruchu bramy (s)</FieldLabel><input id="gate-travel" type="number" min={1} max={300} value={draft.travel_seconds} disabled={busy} onChange={event => set({ travel_seconds: Number(event.target.value) })} /></div>
      </div>
    </details>}

    <div className="gate-actions"><button type="submit" className="button primary" disabled={busy}><Save aria-hidden="true" />Zapisz</button>
      <button type="button" className="button secondary" disabled={busy || overview?.config.driver === 'disabled'} onClick={() => { void test() }}><Radar aria-hidden="true" />Sprawdź połączenie (brama się nie ruszy)</button></div>
  </form>
}
