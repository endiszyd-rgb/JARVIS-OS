import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, CircleAlert, Copy, KeyRound, RefreshCw, ShieldCheck, UserPlus, X } from 'lucide-react'
import { ApiError } from '../../api'
import { roleLabels } from '../../types'
import type { Role } from '../../types'
import { changeUser, createUser, issueToken, readSecurity, revoke, roles, scopes } from './api'
import type { IssuedToken, Scope, Snapshot, User } from './api'
import './security.css'

export interface SecurityPanelProps { credential: string; onUnauthorized: () => void }
type Pending = { kind: 'user'; user: User; role: Role; enabled: boolean } | { kind: 'sessions' | 'tokens'; id: string; label: string }
const scopeLabels: Record<Scope, string> = { 'status:read': 'Odczyt statusu', 'scheduler:tick': 'Uruchomienie lokalnego harmonogramu', 'home:read': 'Odczyt domu', 'plugins:read': 'Katalog pluginów', 'plugins:invoke': 'Wykonanie zatwierdzonych odczytów pluginów', 'messages:read': 'Odczyt wiadomości', 'messages:draft': 'Przygotowanie szkiców wiadomości' }
const date = (value: number) => new Date(value * 1000).toLocaleString('pl-PL')
function message(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return 'Dane konta zmieniły się lub nazwa jest już zajęta. Odśwież dostęp przed kolejną próbą; zmiany nie ponowiono.'
  return error instanceof ApiError ? error.message : 'Nie udało się wykonać operacji dostępu. Sprawdź bieżący stan przed kolejną próbą.'
}
function UserEditor({ user, busy, onReview }: { user: User; busy: boolean; onReview: (role: Role, enabled: boolean) => void }) {
  const [role, setRole] = useState(user.role), [enabled, setEnabled] = useState(user.enabled)
  return <li className="security-user-card"><div><h3>{user.username}</h3><p className="security-meta">{roleLabels[user.role]} · {user.enabled ? 'Aktywne' : 'Wyłączone'} · rewizja {user.revision}</p></div><div className="security-user-fields"><div className="form-field"><label htmlFor={'role-' + user.id}>Rola konta {user.username}</label><select id={'role-' + user.id} value={role} disabled={busy} onChange={event => setRole(event.target.value as Role)}>{roles.map(item => <option key={item} value={item}>{roleLabels[item]}</option>)}</select></div><label className="security-checkbox"><input type="checkbox" checked={enabled} disabled={busy} onChange={event => setEnabled(event.target.checked)} />Konto aktywne {user.username}</label><button className="button secondary" type="button" disabled={busy || role === user.role && enabled === user.enabled} onClick={() => onReview(role, enabled)}>Przejrzyj zmianę konta {user.username}</button></div></li>
}

export function SecurityPanel(props: SecurityPanelProps) { return <SecurityWorkspace key={props.credential} {...props} /> }
function SecurityWorkspace({ credential, onUnauthorized }: SecurityPanelProps) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null), [busy, setBusy] = useState(true), [authorized, setAuthorized] = useState(true)
  const [error, setError] = useState<string | null>(null), [notice, setNotice] = useState<string | null>(null), [confirmation, setConfirmation] = useState<Pending | null>(null)
  const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [newRole, setNewRole] = useState<Role>('observer')
  const [tokenName, setTokenName] = useState(''), [tokenHours, setTokenHours] = useState(24), [tokenScopes, setTokenScopes] = useState<Scope[]>(['status:read']), [issued, setIssued] = useState<IssuedToken | null>(null)
  const controller = useRef<AbortController | null>(null), epoch = useRef(0), mounted = useRef(true), expired = useRef(false)
  const callback = useRef(onUnauthorized); callback.current = onUnauthorized
  function begin() {
    controller.current?.abort()
    const pending = new AbortController(), id = ++epoch.current
    controller.current = pending; setBusy(true); setError(null); setNotice(null); setIssued(null)
    return { pending, id }
  }
  const valid = (id: number, pending: AbortController) => mounted.current && !expired.current && id === epoch.current && !pending.signal.aborted
  function failed(failure: unknown, id: number, pending: AbortController) {
    if (!valid(id, pending) || failure instanceof DOMException && failure.name === 'AbortError') return
    if (failure instanceof ApiError && failure.status === 401) {
      expired.current = true; ++epoch.current; pending.abort(); controller.current = null
      setSnapshot(null); setPassword(''); setUsername(''); setIssued(null); setTokenName(''); setConfirmation(null); setError(null); setNotice(null); setAuthorized(false)
      callback.current()
    } else { setError(message(failure)); if (failure instanceof ApiError && failure.status === 409) setConfirmation(null) }
  }
  function finish(id: number, pending: AbortController) { if (valid(id, pending)) { setBusy(false); controller.current = null } }
  async function refresh() {
    const { pending, id } = begin(); setConfirmation(null); setPassword('')
    try { const result = await readSecurity(credential, pending.signal); if (valid(id, pending)) setSnapshot(result) }
    catch (failure) { failed(failure, id, pending) }
    finally { finish(id, pending) }
  }
  useEffect(() => {
    mounted.current = true; expired.current = false; void refresh()
    return () => { mounted.current = false; ++epoch.current; controller.current?.abort(); controller.current = null }
    // A keyed workspace is recreated for each credential.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])
  async function addUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return
    const submitted = { username: username.trim(), password, role: newRole }; setPassword('')
    const { pending, id } = begin()
    try {
      await createUser(credential, pending.signal, submitted.username, submitted.password, submitted.role)
      if (!valid(id, pending)) return
      const result = await readSecurity(credential, pending.signal)
      if (valid(id, pending)) { setSnapshot(result); setUsername(''); setNotice('Konto zostało utworzone.') }
    } catch (failure) { failed(failure, id, pending) }
    finally { finish(id, pending) }
  }
  async function applyConfirmation() {
    if (!confirmation || busy) return
    const staged = confirmation, { pending, id } = begin()
    try {
      if (staged.kind === 'user') await changeUser(credential, pending.signal, staged.user, staged.role, staged.enabled)
      else await revoke(credential, pending.signal, staged.kind, staged.id)
      if (!valid(id, pending)) return
      setConfirmation(null)
      const result = await readSecurity(credential, pending.signal)
      if (valid(id, pending)) { setSnapshot(result); setNotice(staged.kind === 'user' ? 'Konto zmienione. Wszystkie jego sesje zostały odwołane.' : staged.kind === 'sessions' ? 'Sesja została odwołana.' : 'Token usługowy został odwołany.') }
    } catch (failure) { failed(failure, id, pending) }
    finally { finish(id, pending) }
  }
  async function addToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy || tokenScopes.length === 0) return
    const submitted = { name: tokenName.trim(), scopes: [...tokenScopes], hours: tokenHours }, { pending, id } = begin()
    try {
      const secret = await issueToken(credential, pending.signal, submitted.name, submitted.scopes, submitted.hours)
      if (!valid(id, pending)) return
      setIssued(secret); setTokenName(''); setNotice('Token utworzony. Skopiuj go do bezpiecznej konfiguracji; API nie pokaże go ponownie.')
      // Preserve the one-time secret even if the metadata refresh fails. A 401 still clears it.
      const result = await readSecurity(credential, pending.signal)
      if (valid(id, pending)) setSnapshot(result)
    } catch (failure) { failed(failure, id, pending) }
    finally { finish(id, pending) }
  }
  async function copyToken() {
    if (!issued || typeof navigator.clipboard?.writeText !== 'function') return
    const generation = epoch.current
    try { await navigator.clipboard.writeText(issued.token); if (mounted.current && generation === epoch.current) setNotice('Token skopiowany do schowka.') }
    catch { if (mounted.current && generation === epoch.current) setError('Nie udało się skopiować tokenu. Możesz zaznaczyć go ręcznie.') }
  }
  function review(next: Pending) { setIssued(null); setError(null); setNotice(null); setConfirmation(next) }
  if (!authorized) return <p role="status">Sesja zakończona. Połącz się ponownie.</p>
  return <div className="security-feature" aria-busy={busy}>
    <div className="security-top"><p className="security-caption">Konta właścicielskie współdzielą prywatne dane tej instalacji. Tokeny usługowe mają wyłącznie wskazane zakresy.</p><button className="button secondary" type="button" disabled={busy} onClick={() => { void refresh() }}><RefreshCw aria-hidden="true" />Odśwież dostęp</button></div>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}{snapshot ? ' Lista może przedstawiać wcześniejszy odczyt.' : ''}</span></div>}
    {notice && <p className="security-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    {confirmation && <section className="panel security-confirmation" aria-labelledby="security-confirm-title"><h2 className="panel-heading" id="security-confirm-title">{confirmation.kind === 'user' ? 'Podgląd zmiany konta' : 'Potwierdzenie odwołania'}</h2>{confirmation.kind === 'user' ? <><p>Zmieniasz konto <strong>{confirmation.user.username}</strong>: {roleLabels[confirmation.user.role]} → {roleLabels[confirmation.role]}, {confirmation.enabled ? 'aktywne' : 'wyłączone'}.</p><p>Każdy zapis odwoła wszystkie sesje tego konta, również bieżącą, jeśli należy do niego. Zmiana wymaga zgodnej rewizji.</p></> : <p>Odwołać {confirmation.kind === 'sessions' ? 'sesję konta' : 'token usługowy'} <strong>{confirmation.label}</strong>? Używający go klient utraci dostęp; odwołanie własnej sesji zakończy połączenie w tej karcie.</p>}<div className="security-actions"><button className="button primary" type="button" disabled={busy} onClick={() => { void applyConfirmation() }}>{confirmation.kind === 'user' ? 'Zatwierdź zmianę konta' : 'Potwierdź odwołanie'}</button><button className="button secondary" type="button" disabled={busy} onClick={() => setConfirmation(null)}><X aria-hidden="true" />Anuluj</button></div></section>}
    {!snapshot && <p role="status">{busy ? 'Odczytywanie dostępu…' : 'Dane dostępu są chwilowo niedostępne.'}</p>}
    <section className="panel" aria-labelledby="security-users-title"><h2 className="panel-heading" id="security-users-title"><ShieldCheck aria-hidden="true" />Konta i role</h2><p className="panel-description">Maksymalnie 256 kont. Nie ma usuwania kont ani zmiany hasła w tym API; konto można wyłączyć.</p>{snapshot && <><ul className="security-list" aria-label="Konta instalacji">{snapshot.users.map(user => <UserEditor key={user.id + ':' + user.revision} user={user} busy={busy || confirmation !== null} onReview={(role, enabled) => review({ kind: 'user', user, role, enabled })} />)}</ul>{snapshot.users.length === 0 && <p className="security-caption">Brak kont. Możesz utworzyć pierwsze konto właściciela.</p>}</>}
      <details className="security-create"><summary><UserPlus aria-hidden="true" />Utwórz konto</summary><form className="security-form" onSubmit={event => { void addUser(event) }}><div className="form-field"><label htmlFor="security-username">Login nowego konta</label><input id="security-username" value={username} required minLength={3} maxLength={64} pattern="[a-z][a-z0-9_.\-]{2,63}" disabled={busy || confirmation !== null} onChange={event => setUsername(event.target.value)} autoComplete="off" autoCapitalize="none" /></div><div className="form-field"><label htmlFor="security-password">Hasło nowego konta</label><input id="security-password" type="password" value={password} required minLength={12} maxLength={256} disabled={busy || confirmation !== null} onChange={event => setPassword(event.target.value)} autoComplete="new-password" /><small>12–256 znaków. Pole czyścimy po próbie utworzenia.</small></div><div className="form-field"><label htmlFor="security-new-role">Rola nowego konta</label><select id="security-new-role" value={newRole} disabled={busy || confirmation !== null} onChange={event => setNewRole(event.target.value as Role)}>{roles.map(role => <option key={role} value={role}>{roleLabels[role]}</option>)}</select></div><button className="button primary" type="submit" disabled={busy || confirmation !== null || (snapshot?.users.length ?? 0) >= 256}>Utwórz konto</button></form></details>
    </section>
    <section className="panel" aria-labelledby="security-sessions-title"><h2 className="panel-heading" id="security-sessions-title">Sesje kont</h2><p className="panel-description">Metadane bieżących rekordów, bez tokenów sesji. Wygasłe i odwołane rekordy mogą zniknąć po kolejnym poprawnym logowaniu.</p>{snapshot && <><ul className="security-list" aria-label="Sesje kont">{snapshot.sessions.map(session => <li key={session.id} className="security-record"><div><h3>{session.username}</h3><p className="security-meta">{roleLabels[session.role]} · {session.revoked ? 'Odwołana' : session.expires_at <= Date.now() / 1000 ? 'Wygasła' : 'Aktywna'}</p><p className="security-meta">Ważna do: {date(session.expires_at)}</p><code className="security-id">{session.id}</code></div><button className="button secondary" type="button" disabled={busy || confirmation !== null || session.revoked} onClick={() => review({ kind: 'sessions', id: session.id, label: session.username + ' · ' + session.id })}>Odwołaj sesję {session.username} {session.id}</button></li>)}</ul>{snapshot.sessions.length === 0 && <p className="security-caption">Brak zapisanych sesji kont.</p>}</>}</section>
    <section className="panel" aria-labelledby="security-tokens-title"><h2 className="panel-heading" id="security-tokens-title"><KeyRound aria-hidden="true" />Tokeny usługowe</h2><p className="panel-description">Do workerów i integracji, bez uprawnień właściciela. Lista nie udostępnia wartości tokenów.</p>{snapshot && <><ul className="security-list" aria-label="Tokeny usługowe">{snapshot.tokens.map(token => <li key={token.id} className="security-record"><div><h3>{token.name}</h3><p className="security-meta">{token.revoked ? 'Odwołany' : token.expires <= Date.now() / 1000 ? 'Wygasły' : 'Aktywny'} · do {date(token.expires)}</p><p className="security-meta">{token.scopes.join(', ')}</p></div><button className="button secondary" type="button" disabled={busy || confirmation !== null || token.revoked} onClick={() => review({ kind: 'tokens', id: token.id, label: token.name })}>Odwołaj token {token.name}</button></li>)}</ul>{snapshot.tokens.length === 0 && <p className="security-caption">Brak tokenów usługowych.</p>}</>}
      <details className="security-create"><summary>Utwórz token usługowy</summary><form className="security-form" onSubmit={event => { void addToken(event) }}><div className="form-field"><label htmlFor="security-token-name">Nazwa tokenu</label><input id="security-token-name" value={tokenName} required maxLength={100} disabled={busy || confirmation !== null} onChange={event => setTokenName(event.target.value)} /></div><div className="form-field"><label htmlFor="security-token-hours">Ważność tokenu w godzinach</label><input id="security-token-hours" type="number" value={tokenHours} min={1} max={8760} step={1} required disabled={busy || confirmation !== null} onChange={event => setTokenHours(Number(event.target.value))} /></div><fieldset className="security-scopes" disabled={busy || confirmation !== null}><legend>Zakresy tokenu</legend>{scopes.map(scope => <label key={scope} className="security-checkbox"><input type="checkbox" checked={tokenScopes.includes(scope)} onChange={event => setTokenScopes(current => event.target.checked ? [...current, scope] : current.filter(item => item !== scope))} />{scopeLabels[scope]} <code>{scope}</code></label>)}</fieldset><button className="button primary" type="submit" disabled={busy || confirmation !== null || tokenScopes.length === 0}>Utwórz token</button></form></details>
      {issued && <section className="security-secret" aria-labelledby="security-secret-title"><h3 id="security-secret-title">Nowy token usługowy — pokazany raz</h3><p>Przenieś token do bezpiecznej konfiguracji. Opuszczenie widoku, odświeżenie lub zakończenie sesji usunie go z tej karty.</p><code className="security-token-value" aria-label="Nowy token usługowy">{issued.token}</code><div className="security-actions">{typeof navigator.clipboard?.writeText === 'function' && <button className="button secondary" type="button" onClick={() => { void copyToken() }}><Copy aria-hidden="true" />Kopiuj token</button>}<button className="button secondary" type="button" onClick={() => setIssued(null)}>Ukryj token</button></div></section>}
    </section>
  </div>
}
