import { useEffect, useState } from 'react'
import { Copy, Mic, Plus, Trash2 } from 'lucide-react'
import { ApiError, apiRequest } from '../../api'

interface DeviceKey { id: string; name: string; created: number; last_used: number | null }
interface Created { id: string; name: string; token: string; scopes: string[] }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const LOCAL = new Set(['localhost', '127.0.0.1', '[::1]'])

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false)
  return <button type="button" className="button subtle" aria-label={label} onClick={() => {
    void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 2000) }).catch(() => undefined)
  }}><Copy aria-hidden="true" />{done ? 'Skopiowano' : 'Kopiuj'}</button>
}

/** Phone keys for the hands-free Siri shortcut: narrow scope (questions + gate), shown once, revocable. */
export function SiriKeys({ credential, onUnauthorized, mfaEnabled }: { credential: string; onUnauthorized: () => void; mfaEnabled: boolean }) {
  const [keys, setKeys] = useState<DeviceKey[] | null>(null)
  const [name, setName] = useState('iPhone')
  const [created, setCreated] = useState<Created | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fail = (failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 401) { onUnauthorized(); return }
    const detail = failure instanceof ApiError ? failure.detail ?? '' : ''
    setError(/two-factor/.test(detail) ? 'Zaloguj się ponownie z kodem 2FA, aby dodać telefon.' : /Too many/.test(detail) ? 'Masz już 8 telefonów — usuń nieużywany.'
      : /Device name/.test(detail) ? 'Nazwa: litery, cyfry, spacje, kropki lub myślniki (do 40 znaków).' : failure instanceof ApiError ? failure.message : 'Nie udało się. Spróbuj ponownie.')
  }
  async function reload(signal = new AbortController().signal) {
    const value = await apiRequest('/api/v1/auth/device-keys', signal, credential)
    if (!object(value) || !Array.isArray(value.keys)) throw new ApiError(null, 'response')
    setKeys(value.keys as DeviceKey[])
  }
  useEffect(() => {
    if (!mfaEnabled) return
    const controller = new AbortController()
    reload(controller.signal).catch(failure => { if (!controller.signal.aborted) fail(failure) })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential, mfaEnabled])
  async function add() {
    setBusy(true); setError(null)
    try {
      const value = await apiRequest('/api/v1/auth/device-keys', new AbortController().signal, credential, { body: { name: name.trim() } })
      if (!object(value) || typeof value.token !== 'string') throw new ApiError(null, 'response')
      setCreated(value as unknown as Created); await reload()
    } catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  async function remove(item: DeviceKey) {
    setBusy(true); setError(null)
    try { await apiRequest('/api/v1/auth/device-keys/' + encodeURIComponent(item.id), new AbortController().signal, credential, { method: 'DELETE' }); await reload() }
    catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  const url = window.location.origin + '/api/v1/voice/ask'
  const local = LOCAL.has(window.location.hostname)
  return <section className="panel" aria-labelledby="account-siri-title">
    <h2 className="panel-heading" id="account-siri-title"><Mic aria-hidden="true" />Telefon i Siri — pytania bez rąk</h2>
    <p className="panel-description">„Hej Siri, Jarvis” → pytasz o moment dokręcania albo mówisz „brama”, odpowiedź słyszysz w słuchawce. Klucz telefonu pozwala tylko na pytania i bramę.</p>
    {!mfaEnabled ? <p className="account-state">Najpierw włącz 2FA powyżej.</p> : <>
      {keys && keys.length > 0 && <ul className="account-passkeys">{keys.map(item => <li key={item.id}><div><strong>{item.name}</strong>
        <span>dodano {new Date(item.created * 1000).toLocaleDateString('pl-PL')}{item.last_used ? ' · ostatnio ' + new Date(item.last_used * 1000).toLocaleString('pl-PL') : ' · jeszcze nie użyty'}</span></div>
        <button type="button" className="icon-button" aria-label={'Usuń telefon ' + item.name} disabled={busy} onClick={() => { void remove(item) }}><Trash2 aria-hidden="true" /></button></li>)}</ul>}
      <div className="account-form">
        <div className="form-field"><label htmlFor="siri-name">Nazwa telefonu</label><input id="siri-name" value={name} maxLength={40} onChange={event => setName(event.target.value)} disabled={busy} /></div>
        <button type="button" className="button primary" disabled={busy || !name.trim()} onClick={() => { void add() }}><Plus aria-hidden="true" />Dodaj telefon</button>
      </div>
      {created && <div className="account-backup siri-setup" aria-labelledby="siri-setup-title">
        <h3 id="siri-setup-title">Klucz dla „{created.name}” — pokazany tylko raz</h3>
        {local && <p className="form-warning">Ten panel jest otwarty na komputerze ({window.location.host}). Telefon potrzebuje adresu z tunelu — otwórz „Moje konto” na telefonie przez adres Tailscale i dodaj telefon stamtąd, albo w kroku 3 wpisz adres Tailscale zamiast poniższego.</p>}
        <div className="siri-values">
          <div><span>Adres</span><code>{url}</code><CopyButton text={url} label="Kopiuj adres" /></div>
          <div><span>Klucz</span><code>{created.token}</code><CopyButton text={created.token} label="Kopiuj klucz" /></div>
        </div>
        <ol className="siri-steps">
          <li>Na iPhonie otwórz aplikację <strong>Skróty</strong> → <strong>+</strong> → nazwij skrót <strong>Jarvis</strong>.</li>
          <li>Dodaj akcję <strong>Dyktuj tekst</strong> (język: polski, „Przestań słuchać”: po przerwie).</li>
          <li>Dodaj <strong>Pobierz zawartość URL</strong>: adres jak wyżej, Metoda <strong>POST</strong>, Nagłówki: <code>X-Jarvis-Key</code> = klucz, Treść żądania <strong>JSON</strong>: pole <code>text</code> (Tekst) = <em>Dyktowany tekst</em>.</li>
          <li>Dodaj <strong>Pobierz wartość ze słownika</strong>: klucz <code>speech</code>, słownik = <em>Zawartość URL</em>.</li>
          <li>Dodaj <strong>Mów tekst</strong> → <em>Wartość słownika</em>.</li>
          <li>Powiedz <strong>„Hej Siri, Jarvis”</strong>, potem pytanie, np. „moment dokręcania kół Golf 7” albo „brama”. Tailscale w telefonie musi być włączony.</li>
        </ol>
        <button type="button" className="button secondary" onClick={() => setCreated(null)}>Zapisałem — ukryj klucz</button>
      </div>}
    </>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>
}
