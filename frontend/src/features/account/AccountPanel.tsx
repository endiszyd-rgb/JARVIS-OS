import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, CircleAlert, Fingerprint, Globe, KeyRound, ShieldCheck, ShieldOff, Trash2 } from 'lucide-react'
import qrcode from 'qrcode-generator'
import { ApiError, apiRequest } from '../../api'
import { creationOptions, credentialJSON, passkeysSupported } from '../../webauthn'
import './account.css'

interface Props { credential: string; onUnauthorized: () => void; accountSession: boolean }
interface MfaStatus { enabled: boolean; pending: boolean; backup_codes_left: number }
interface Setup { secret: string; uri: string }
interface Passkey { id: string; name: string; created: number; last_used: number | null; rp_id: string }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const invalid = (): never => { throw new ApiError(null, 'response') }
const message = (error: unknown) => error instanceof ApiError
  ? error.status === 422 ? 'Nieprawidłowy kod. Sprawdź godzinę w telefonie i wpisz aktualny kod.' : error.status === 401 ? 'Nieprawidłowe hasło lub kod.' : error.message
  : 'Nie udało się wykonać operacji. Spróbuj ponownie.'

export async function readMfa(credential: string, signal: AbortSignal): Promise<MfaStatus> {
  const value = await apiRequest('/api/v1/auth/mfa', signal, credential)
  if (!object(value) || typeof value.enabled !== 'boolean' || typeof value.pending !== 'boolean' || !Number.isSafeInteger(value.backup_codes_left)) return invalid()
  return value as unknown as MfaStatus
}

/** Authenticator QR rendered as SVG rectangles (no external service, no innerHTML). */
export function QrCode({ text, label }: { text: string; label: string }) {
  const qr = qrcode(0, 'M')
  qr.addData(text)
  qr.make()
  const size = qr.getModuleCount()
  const cells: string[] = []
  for (let row = 0; row < size; row++) for (let col = 0; col < size; col++) if (qr.isDark(row, col)) cells.push(`M${col + 4} ${row + 4}h1v1h-1z`)
  return <svg className="account-qr" viewBox={`0 0 ${size + 8} ${size + 8}`} role="img" aria-label={label} shapeRendering="crispEdges">
    <rect width={size + 8} height={size + 8} fill="#fff" /><path d={cells.join('')} fill="#000" />
  </svg>
}

function Passkeys({ credential, onUnauthorized }: { credential: string; onUnauthorized: () => void }) {
  const [items, setItems] = useState<Passkey[] | null>(null)
  const [name, setName] = useState(() => /iPhone|iPad/.test(navigator.userAgent) ? 'iPhone' : /Android/.test(navigator.userAgent) ? 'Telefon Android' : 'Komputer')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const supported = passkeysSupported()
  const load = (signal: AbortSignal) => apiRequest('/api/v1/auth/passkeys', signal, credential).then(value => {
    if (!Array.isArray(value)) return invalid()
    setItems(value as Passkey[])
  })
  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal).catch(failure => { if (!controller.signal.aborted) { if (failure instanceof ApiError && failure.status === 401) onUnauthorized(); else setNote(message(failure)) } })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])
  async function add() {
    if (busy) return
    setBusy(true); setNote(null)
    try {
      const start = await apiRequest('/api/v1/auth/passkeys/register/options', new AbortController().signal, credential, { body: {} })
      if (!object(start) || typeof start.ticket !== 'string' || !object(start.options)) return invalid()
      const created = await navigator.credentials.create({ publicKey: creationOptions(start.options) })
      if (!created) throw new DOMException('cancelled', 'NotAllowedError')
      await apiRequest('/api/v1/auth/passkeys/register/verify', new AbortController().signal, credential, { body: { ticket: start.ticket, name: name.trim() || 'Urządzenie', credential: credentialJSON(created as PublicKeyCredential) } })
      await load(new AbortController().signal)
      setNote('Dodano. Następnym razem wybierz „Zaloguj przez Face ID / klucz dostępu”.')
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401 && failure.detail === 'Unauthorized') onUnauthorized()
      else if (failure instanceof ApiError && failure.status === 403) setNote('Najpierw zaloguj się z kodem 2FA, potem dodaj Face ID.')
      else if (failure instanceof DOMException) setNote(failure.name === 'InvalidStateError' ? 'To urządzenie ma już klucz dostępu dla JARVIS.' : 'Dodawanie przerwane.')
      else setNote(message(failure))
    } finally { setBusy(false) }
  }
  async function remove(item: Passkey) {
    if (busy) return
    setBusy(true); setNote(null)
    try { await apiRequest('/api/v1/auth/passkeys/' + encodeURIComponent(item.id), new AbortController().signal, credential, { method: 'DELETE' }); await load(new AbortController().signal) }
    catch (failure) { setNote(message(failure)) } finally { setBusy(false) }
  }
  return <section className="panel" aria-labelledby="account-passkeys-title">
    <h2 className="panel-heading" id="account-passkeys-title"><Fingerprint aria-hidden="true" />Face ID / Touch ID / Windows Hello</h2>
    <p className="panel-description">Klucz dostępu (passkey) zastępuje hasło i kod 2FA — logowanie jednym spojrzeniem lub odciskiem palca. Działa też spoza warsztatu. Klucz jest przypisany do adresu, pod którym go dodasz (np. domena tunelu).</p>
    {items && items.length > 0 && <ul className="account-passkeys">{items.map(item => <li key={item.id}><div><strong>{item.name}</strong><span>{item.rp_id} · dodano {new Date(item.created * 1000).toLocaleDateString('pl-PL')}{item.last_used ? ' · ostatnio ' + new Date(item.last_used * 1000).toLocaleString('pl-PL') : ''}</span></div><button type="button" className="icon-button" aria-label={'Usuń klucz ' + item.name} disabled={busy} onClick={() => { void remove(item) }}><Trash2 aria-hidden="true" /></button></li>)}</ul>}
    {supported ? <div className="account-form">
      <div className="form-field"><label htmlFor="passkey-name">Nazwa urządzenia</label><input id="passkey-name" value={name} maxLength={60} onChange={event => setName(event.target.value)} /></div>
      <button className="button primary" type="button" disabled={busy} onClick={() => { void add() }}><Fingerprint aria-hidden="true" />Dodaj to urządzenie</button>
    </div> : <p className="workshop-caption">Ta przeglądarka lub adres nie obsługuje kluczy dostępu. Otwórz panel przez https (tunel) albo http://localhost:17321 — nie przez adres IP.</p>}
    {note && <p className="workshop-caption" role="status">{note}</p>}
  </section>
}

export function AccountPanel(props: Props) { return <AccountWorkspace key={props.credential} {...props} /> }

function AccountWorkspace({ credential, onUnauthorized, accountSession }: Props) {
  const [status, setStatus] = useState<MfaStatus | null>(null)
  const [setup, setSetup] = useState<Setup | null>(null)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [backup, setBackup] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  const fail = (failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 401 && failure.detail === 'Unauthorized') { unauthorized.current(); return }
    setError(message(failure))
  }
  useEffect(() => {
    if (!accountSession) return
    const controller = new AbortController()
    readMfa(credential, controller.signal).then(setStatus).catch(failure => { if (!controller.signal.aborted) fail(failure) })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential, accountSession])

  async function begin() {
    setBusy(true); setError(null); setNotice(null); setBackup(null)
    try {
      const value = await apiRequest('/api/v1/auth/mfa/setup', new AbortController().signal, credential, { body: {} })
      if (!object(value) || typeof value.secret !== 'string' || typeof value.uri !== 'string' || !value.uri.startsWith('otpauth://totp/')) return invalid()
      setSetup({ secret: value.secret, uri: value.uri })
    } catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  async function enable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return
    setBusy(true); setError(null)
    try {
      const value = await apiRequest('/api/v1/auth/mfa/enable', new AbortController().signal, credential, { body: { code: code.replace(/\s/g, '') } })
      if (!object(value) || !Array.isArray(value.backup_codes) || !value.backup_codes.every(item => typeof item === 'string')) return invalid()
      setBackup(value.backup_codes as string[]); setSetup(null); setCode('')
      setStatus(await readMfa(credential, new AbortController().signal))
      setNotice('2FA włączone. Zaloguj się ponownie z kodem, aby ta sesja działała także spoza warsztatu.')
    } catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  async function disable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return
    setBusy(true); setError(null)
    const submitted = { password, code: code.replace(/\s/g, '') }
    setPassword(''); setCode('')
    try {
      await apiRequest('/api/v1/auth/mfa/disable', new AbortController().signal, credential, { body: submitted })
      unauthorized.current()  // the server revoked all sessions of this account
    } catch (failure) { fail(failure) } finally { setBusy(false) }
  }

  const remote = <section className="panel" aria-labelledby="account-remote-title">
    <h2 className="panel-heading" id="account-remote-title"><Globe aria-hidden="true" />Dostęp spoza warsztatu</h2>
    <p className="panel-description">Przez tunel (Cloudflare Tunnel lub Tailscale) JARVIS przyjmuje tylko sesje kont z włączonym 2FA. Klucz właściciela i tokeny usługowe działają wyłącznie lokalnie na komputerze warsztatowym. Instrukcja: <code>docs/DOSTEP-ZDALNY.md</code>.</p>
  </section>

  if (!accountSession) return <div className="account-feature">
    <section className="panel" aria-labelledby="account-key-title"><h2 className="panel-heading" id="account-key-title"><KeyRound aria-hidden="true" />Połączono kluczem właściciela</h2>
      <p className="panel-description">Weryfikacja dwuetapowa należy do konta. Utwórz konto z rolą „Właściciel” (lub „Operator” dla pracownika) w widoku <a href="#/security">Bezpieczeństwo</a>, zaloguj się nim i włącz 2FA tutaj.</p></section>
    {remote}
  </div>

  return <div className="account-feature">
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="account-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <section className="panel" aria-labelledby="account-mfa-title">
      <h2 className="panel-heading" id="account-mfa-title"><ShieldCheck aria-hidden="true" />Weryfikacja dwuetapowa (2FA)</h2>
      <p className="panel-description">Kod z aplikacji (Google Authenticator, Microsoft Authenticator, Aegis, Hasła w iPhonie) przy każdym logowaniu. Wymagana do dostępu z internetu.</p>
      {!status ? <p role="status">Odczytywanie stanu…</p> : status.enabled ? <>
        <p className="account-state is-on"><ShieldCheck aria-hidden="true" />2FA włączone · pozostałe kody zapasowe: {status.backup_codes_left}</p>
        <details className="account-disable"><summary><ShieldOff aria-hidden="true" />Wyłącz 2FA</summary>
          <form className="account-form" onSubmit={event => { void disable(event) }}>
            <div className="form-field"><label htmlFor="mfa-disable-password">Hasło</label><input id="mfa-disable-password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required disabled={busy} /></div>
            <div className="form-field"><label htmlFor="mfa-disable-code">Kod z aplikacji lub zapasowy</label><input id="mfa-disable-code" value={code} onChange={event => setCode(event.target.value)} autoComplete="one-time-code" required maxLength={16} disabled={busy} /></div>
            <button className="button secondary" type="submit" disabled={busy}>Wyłącz 2FA i wyloguj wszystkie sesje</button>
          </form></details>
      </> : setup ? <div className="account-setup">
        <QrCode text={setup.uri} label="Kod QR do aplikacji uwierzytelniającej" />
        <div className="account-steps">
          <ol><li>Zeskanuj kod QR aplikacją uwierzytelniającą albo <a href={setup.uri}>otwórz link w telefonie</a>.</li><li>Lub wpisz klucz ręcznie: <code className="account-secret">{setup.secret.replace(/(.{4})/g, '$1 ').trim()}</code></li><li>Wpisz 6-cyfrowy kod, który pokazuje aplikacja.</li></ol>
          <form className="account-form" onSubmit={event => { void enable(event) }}>
            <div className="form-field"><label htmlFor="mfa-code">Kod z aplikacji</label><input id="mfa-code" value={code} onChange={event => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9 ]{6,7}" required disabled={busy} placeholder="123 456" /></div>
            <button className="button primary" type="submit" disabled={busy}>Potwierdź i włącz 2FA</button>
          </form>
        </div>
      </div> : <button className="button primary" type="button" disabled={busy} onClick={() => { void begin() }}><ShieldCheck aria-hidden="true" />Włącz 2FA</button>}
      {backup && <div className="account-backup" aria-labelledby="account-backup-title"><h3 id="account-backup-title">Kody zapasowe — pokazane tylko raz</h3><p>Każdy działa jednorazowo zamiast kodu z aplikacji (np. po utracie telefonu). Zapisz je w bezpiecznym miejscu.</p><ul>{backup.map(item => <li key={item}><code>{item}</code></li>)}</ul><button className="button secondary" type="button" onClick={() => setBackup(null)}>Zapisałem kody — ukryj</button></div>}
    </section>
    <Passkeys credential={credential} onUnauthorized={unauthorized.current} />
    {remote}
  </div>
}
