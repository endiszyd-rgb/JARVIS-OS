import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Activity, ArrowRight, ArrowUpRight, ClipboardList, Fingerprint, Gauge, AudioLines, Bell, Camera, Check, ChevronRight, CircleAlert, Cpu, Database, DoorOpen, GitPullRequest, House, LayoutDashboard, LockKeyhole, LogOut, Menu, MessageSquare, Phone, Plug, RefreshCw, Settings2, ShieldCheck, UserRound, Wrench, X } from 'lucide-react'
import { ApiError, connect, endSession, readSnapshot } from './api'
import type { AuthSession, LoginInput, Role, Snapshot } from './types'
import { roleLabels } from './types'
import { passkeysSupported } from './webauthn'
import { ChatPanel } from './features/chat/ChatPanel'
import { SettingsPanel } from './features/settings/SettingsPanel'
import { ActivityPanel } from './features/activity/ActivityPanel'
import { PluginPanel } from './features/plugins/PluginPanel'
import { WorkshopPanel } from './features/workshop/WorkshopPanel'
import { HomePanel } from './features/home/HomePanel'
import { DevicesPanel } from './features/devices/DevicesPanel'
import { GatePanel } from './features/gate/GatePanel'
import { VoicePanel } from './features/voice/VoicePanel'
import { GateTile } from './features/gate/GateTile'
import { AutomationsPanel } from './features/automations/AutomationsPanel'
import { MemoryPanel } from './features/memory/MemoryPanel'
import { TelephonyPanel } from './features/telephony/TelephonyPanel'
import { NotificationsPanel } from './features/notifications/NotificationsPanel'
import { SecurityPanel } from './features/security/SecurityPanel'
import { ChangesPanel } from './features/changes/ChangesPanel'
import { CamerasPanel } from './features/cameras/CamerasPanel'
import { AccountPanel } from './features/account/AccountPanel'
import { KioskPanel } from './features/kiosk/KioskPanel'

const viewLabels = {
  dashboard: 'Pulpit', kiosk: 'Warsztat', system: 'System', chat: 'Rozmowa', voice: 'Głos', gate: 'Brama', cameras: 'Kamery', account: 'Moje konto', settings: 'Ustawienia', activity: 'Historia działań', plugins: 'Pluginy',
  workshop: 'AutoLogika', home: 'Dom', devices: 'Urządzenia', automations: 'Automatyzacje', memory: 'Pamięć',
  telephony: 'Telefonia', notifications: 'Powiadomienia', security: 'Bezpieczeństwo', logs: 'Logi', changes: 'Zmiany i zgody',
} as const
type View = keyof typeof viewLabels
const viewDescriptions: Record<View, string> = {
  dashboard: 'Podgląd Twojej instalacji. Zawsze z jasnym stanem i zakresem działania.',
  kiosk: 'Jeden ekran na warsztat i telefon: polecenia głosowe, brama, kamery i dzisiejsze zlecenia.', system: 'Gotowość instalacji i informacje o bieżącym dostępie.',
  chat: 'Twoje rozmowy, zapisane sesje i wybór skonfigurowanego modelu.', settings: 'Wszystkie ustawienia w jednym miejscu: brama, AutoLogika, kamery, głos i asystent AI. Najedź na „?”, aby zobaczyć podpowiedź.',
  voice: 'Komendy głosowe: nasłuch słowa aktywującego lub przytrzymaj i mów. Polecenia urządzeń wykonuje serwer.',
  gate: 'Sterowanie bramą warsztatu, konfiguracja sterownika i historia poleceń.',
  cameras: 'Podgląd kamer warsztatu przez lokalny serwer go2rtc. Obraz nie opuszcza JARVIS bez logowania.',
  account: 'Twoje konto: weryfikacja dwuetapowa (2FA) wymagana do dostępu spoza warsztatu.',
  activity: 'Ostatnie zdarzenia zapisane przez JARVIS OS.', plugins: 'Konfiguracja integracji, uprawnienia odczytu i jawne testy połączenia.',
  workshop: 'Kopia danych warsztatu oraz jawny odczyt skonfigurowanej AutoLogiki.', home: 'Stany dozwolonych encji Home Assistant, bez sterowania.',
  devices: 'Konfiguracja integracji i zakres dostępnych odczytów.', automations: 'Lokalne przypomnienia z osobnym zatwierdzeniem zmian.',
  memory: 'Twoje notatki, źródła, korekty i zasady zapamiętywania.', telephony: 'Dostępność właściciela i podgląd reguł obsługi kontaktu.',
  notifications: 'Ostatnie lokalne powiadomienia zapisane w JARVIS OS.', security: 'Konta, odwoływanie sesji i uprawnienia usług.',
  changes: 'Przegląd propozycji, osobne decyzje i cofanie zastosowanych zmian.',
  logs: 'Ostatnie zdarzenia audytu. Logi systemu i Dockera nie są udostępniane przez ten panel.',
}
const navGroups: { title: string; advanced?: boolean; items: { view: View; icon: ReactNode }[] }[] = [
  { title: 'Na co dzień', items: [
    { view: 'kiosk', icon: <Wrench /> }, { view: 'gate', icon: <DoorOpen /> }, { view: 'cameras', icon: <Camera /> },
    { view: 'voice', icon: <AudioLines /> }, { view: 'workshop', icon: <ClipboardList /> }, { view: 'chat', icon: <MessageSquare /> },
  ] },
  { title: 'Konto', items: [{ view: 'account', icon: <UserRound /> }] },
  { title: 'Zaawansowane', advanced: true, items: [
    { view: 'settings', icon: <Settings2 /> }, { view: 'security', icon: <ShieldCheck /> },
    { view: 'dashboard', icon: <LayoutDashboard /> }, { view: 'system', icon: <Gauge /> },
    { view: 'memory', icon: <Database /> }, { view: 'home', icon: <House /> }, { view: 'devices', icon: <Cpu /> },
    { view: 'automations', icon: <RefreshCw /> }, { view: 'notifications', icon: <Bell /> }, { view: 'telephony', icon: <Phone /> },
    { view: 'plugins', icon: <Plug /> }, { view: 'changes', icon: <GitPullRequest /> }, { view: 'activity', icon: <Activity /> },
  ] },
]
// 'logs' stays a valid address (old links) but shows the same history as 'activity', so it has no menu entry.
function canAccess(view: View, role: Role): boolean {
  if (view === 'dashboard' || view === 'system' || view === 'account' || role === 'owner') return true
  if (role === 'operator') return view === 'kiosk' || view === 'gate' || view === 'voice' || view === 'cameras'
  return view === 'home' && role === 'home_reader' || view === 'workshop' && role === 'workshop_reader'
}
const currentView = (): View => {
  const route = window.location.hash.slice(2).split('/')[0] ?? ''  // '#/settings/gate' → settings (tab handled by the view)
  return Object.hasOwn(viewLabels, route) ? route as View : 'dashboard'
}
const message = (error: unknown) => error instanceof ApiError ? error.message : 'Nie udało się wykonać żądania. Spróbuj ponownie.'
const REMEMBER_KEY = 'jarvis.owner-key'
function rememberedKey(): string | null { try { return window.localStorage.getItem(REMEMBER_KEY) } catch { return null } }
function rememberKey(value: string | null) { try { if (value) window.localStorage.setItem(REMEMBER_KEY, value); else window.localStorage.removeItem(REMEMBER_KEY) } catch { /* storage unavailable */ } }
const aborted = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

function Brand() {
  return <div className="login-brand"><span className="brand-mark" aria-hidden="true">J</span><span className="brand-copy"><strong>JARVIS OS</strong><span>Control Center</span></span></div>
}

function Login({ busy, error, onSubmit }: { busy: boolean; error: string | null; onSubmit: (input: LoginInput) => void }) {
  const [mode, setMode] = useState<'account' | 'key'>('account')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [key, setKey] = useState(() => rememberedKey() ?? '')
  const [remember, setRemember] = useState(() => rememberedKey() !== null)
  const choose = (next: 'account' | 'key') => { setMode(next); setPassword(''); setKey('') }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (busy) return
    const code = otp.replace(/\s/g, '')
    const input: LoginInput = mode === 'account' ? { mode, username: username.trim(), password, ...(code ? { otp: code } : {}) } : { mode, key }
    if (mode === 'key') rememberKey(remember ? key : null)
    setPassword(''); setKey(''); setOtp('')
    onSubmit(input)
  }
  return <main className="login-page">
    <Brand />
    <div className="login-layout">
      <section className="login-intro" aria-labelledby="welcome-title">
        <p className="eyebrow">Twoje centrum dowodzenia</p>
        <h1 id="welcome-title">Wszystko pod<br />Twoją kontrolą.</h1>
        <p>Dom, warsztat i codzienne sprawy. Jedno miejsce, w którym widzisz stan swojego asystenta i decydujesz o kolejnych krokach.</p>
        <ul className="feature-list"><li className="feature-item"><ShieldCheck aria-hidden="true" />Kontrola dostępu</li><li className="feature-item"><Activity aria-hidden="true" />Aktualny stan</li><li className="feature-item"><LockKeyhole aria-hidden="true" />Prywatna sesja</li></ul>
      </section>
      <section className="login-card" aria-labelledby="login-title">
        <h2 id="login-title">Połącz się z JARVIS OS</h2>
        <p>Zaloguj się na swoje konto lub użyj klucza właściciela tej instalacji.</p>
        <div className="auth-tabs" aria-label="Sposób logowania">
          <button type="button" className={mode === 'account' ? 'active' : ''} aria-pressed={mode === 'account'} disabled={busy} onClick={() => choose('account')}>Konto</button>
          <button type="button" className={mode === 'key' ? 'active' : ''} aria-pressed={mode === 'key'} disabled={busy} onClick={() => choose('key')}>Klucz właściciela</button>
        </div>
        {mode === 'account' && passkeysSupported() && <button className="button primary passkey-login" type="button" disabled={busy} onClick={() => { const name = username.trim(); setPassword(''); setOtp(''); onSubmit(name ? { mode: 'passkey', username: name } : { mode: 'passkey' }) }}><Fingerprint aria-hidden="true" />Zaloguj przez Face ID / klucz dostępu</button>}
        {mode === 'account' && passkeysSupported() && <p className="passkey-or">lub hasłem</p>}
        <form onSubmit={submit} aria-busy={busy}>
          {mode === 'account' ? <>
            <div className="form-field"><label htmlFor="login-name">Login</label><input id="login-name" name="username" value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} required disabled={busy} placeholder="Twoja nazwa użytkownika" /></div>
            <div className="form-field"><label htmlFor="login-password">Hasło</label><input id="login-password" name="password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required disabled={busy} placeholder="Wprowadź hasło" /></div>
            <div className="form-field"><label htmlFor="login-otp">Kod 2FA <small>(jeśli włączony)</small></label><input id="login-otp" name="otp" value={otp} onChange={event => setOtp(event.target.value)} autoComplete="one-time-code" inputMode="text" autoCapitalize="none" spellCheck={false} maxLength={16} disabled={busy} placeholder="6 cyfr z aplikacji lub kod zapasowy" /></div>
          </> : <div className="form-field"><label htmlFor="login-key">Klucz dostępu</label><input id="login-key" name="key" type="password" value={key} onChange={event => setKey(event.target.value)} autoComplete="off" autoCapitalize="none" spellCheck={false} required disabled={busy} placeholder="Klucz właściciela" /><small>Użyj klucza skonfigurowanego dla tej instalacji.</small><label className="remember-key"><input type="checkbox" checked={remember} disabled={busy} onChange={event => setRemember(event.target.checked)} />Zapamiętaj klucz na tym komputerze (tylko zaufane stanowisko, np. PC na warsztacie)</label></div>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button primary" type="submit" disabled={busy}>{busy ? <RefreshCw className="spin" aria-hidden="true" /> : <ArrowRight aria-hidden="true" />}{mode === 'account' ? 'Zaloguj się' : 'Połącz kluczem'}</button>
        </form>

        <p className="privacy-note"><LockKeyhole aria-hidden="true" />Dane dostępu pozostają tylko w pamięci tej karty. Po odświeżeniu strony połączysz się ponownie.</p>
      </section>
    </div>
  </main>
}

function Metric({ label, value, icon, caption }: { label: string; value: number; icon: ReactNode; caption: string }) {
  const id = 'metric-' + label.toLowerCase().replace(/\s/g, '-')
  return <article className="metric-card" aria-labelledby={id}><span className="metric-icon" aria-hidden="true">{icon}</span><p className="metric-value">{value.toLocaleString('pl-PL')}</p><h3 className="metric-label" id={id}>{label}</h3><p className="metric-caption">{caption}</p></article>
}

function StatusRow({ title, description, badge, tone = '' }: { title: string; description: string; badge: string; tone?: string }) {
  return <li className="status-row"><div><strong>{title}</strong><p className="row-meta">{description}</p></div><span className={'badge ' + tone}>{badge}</span></li>
}

function CoreRadar({ ready }: { ready: boolean }) {
  return <a className="core-radar" href="#/system" aria-label="Otwórz stan rdzenia JARVIS">
    <svg viewBox="0 0 300 300" aria-hidden="true">
      <circle className="radar-guide" cx="150" cy="150" r="140" />
      <circle className="radar-ticks" cx="150" cy="150" r="130" />
      <circle className="radar-orbit" cx="150" cy="150" r="114" />
      <circle className="radar-guide" cx="150" cy="150" r="94" />
      <path className="radar-cross" d="M150 0v40 M150 260v40 M0 150h40 M260 150h40" />
      <circle className="radar-inner" cx="150" cy="150" r="80" />
    </svg>
    <span className="radar-center"><Cpu aria-hidden="true" /><strong>J.A.R.V.I.S.</strong><span>{ready ? 'CORE GOTOWY' : 'WYMAGA UWAGI'}</span><small>Stan systemu ↗</small></span>
  </a>
}

function Dashboard({ snapshot, role, credential, onUnauthorized }: { snapshot: Snapshot; role: Role; credential: string; onUnauthorized: () => void }) {
  const status = snapshot.status
  const ready = snapshot.ready.status === 'ready'
  return <>
    <section className="overview-panel hud-overview" aria-labelledby="overview-title">
      <div className="overview-copy"><p className="overview-label"><Activity aria-hidden="true" />CENTRUM DOWODZENIA / 01</p><h2 id="overview-title">Witaj,<br /><span>{status.settings.name}.</span></h2><p>Twój asystent. Twoje decyzje.<br />Stan instalacji i zapisane dane w jednym miejscu.</p>
      {role === 'owner' && <a className="button primary hud-chat" href="#/chat">Rozpocznij rozmowę <ArrowUpRight aria-hidden="true" /></a>}</div>
      <CoreRadar ready={ready} />
      <div className="hud-readouts"><p className="eyebrow">TELEMETRIA CORE</p><dl>
        <div><dt>Gotowość</dt><dd>{ready ? 'GOTOWY' : 'WYMAGA UWAGI'}</dd></div>
        <div><dt>Lokalna baza</dt><dd>{snapshot.ready.checks.database ? 'DOSTĘPNA' : 'NIEDOSTĘPNA'}</dd></div>
        <div><dt>Wybrany model</dt><dd>{status.settings.model.toUpperCase()}</dd></div>
        <div><dt>Wersja Core</dt><dd>{snapshot.health.version}</dd></div>
      </dl><p className="hud-disclaimer">Modele i integracje wymagają osobnego sprawdzenia.</p></div>
    </section>
    <section className="stats-grid" aria-label="Zapisane dane">
      <Metric label="Integracje" value={status.counts.plugins} icon={<Plug />} caption="Zarejestrowane pluginy" />
      <Metric label="Pamięć" value={status.counts.memory} icon={<Database />} caption="Wszystkie zapisane wpisy" />
      <Metric label="Propozycje" value={status.counts.proposals} icon={<GitPullRequest />} caption="Wszystkie zapisane propozycje" />
      <Metric label="Powiadomienia" value={status.counts.notifications} icon={<Bell />} caption="Wszystkie zapisane powiadomienia" />
    </section>
    <div className="dashboard-grid">
      {(role === 'owner' || role === 'operator') && <GateTile credential={credential} onUnauthorized={onUnauthorized} />}
      <section className="panel" aria-labelledby="current-state-title"><h2 className="panel-heading" id="current-state-title"><Activity aria-hidden="true" />Stan systemu</h2><p className="panel-description">Gotowość Core i bieżące ustawienia. To nie jest potwierdzenie połączenia z usługami zewnętrznymi.</p><ul className="status-list">
        <StatusRow title="Core" description="Konfiguracja i lokalna baza danych" badge={ready ? 'Gotowy' : 'Wymaga uwagi'} tone={ready ? 'tone-good' : 'tone-warning'} />
        <StatusRow title="Tryb rozmów" description={status.settings.model === 'demo' ? 'Odpowiedzi demonstracyjne' : 'Wybrany dostawca '+(status.settings.model === 'openai' ? 'OpenAI (chmura)' : 'Ollama')+'; model wymaga sprawdzenia'} badge={status.settings.model === 'demo' ? 'DEMO' : status.settings.model === 'openai' ? 'OpenAI' : 'Ollama'} tone="tone-warning" />
        <StatusRow title="Sterowanie bramą" description={status.live_devices ? 'Skonfigurowany sterownik sprzętowy; polecenia trafiają do audytu' : 'Symulator lub wyłączone — skonfiguruj w widoku Brama'} badge={status.live_devices ? 'Sprzęt' : 'Symulator'} tone={status.live_devices ? 'tone-good' : ''} />
      </ul></section>
      <section className="panel legacy-card" aria-labelledby="legacy-title"><h2 className="panel-heading" id="legacy-title"><LayoutDashboard aria-hidden="true" />Więcej możliwości</h2><p className="panel-description">Laboratoria głosu, recepcji i transportu są dostępne w dotychczasowym panelu. Po przejściu połącz się ponownie.</p><ul className="legacy-feature-list"><li className="legacy-feature"><MessageSquare aria-hidden="true" />Głos</li><li className="legacy-feature"><Phone aria-hidden="true" />Recepcja</li><li className="legacy-feature"><Plug aria-hidden="true" />Transport</li><li className="legacy-feature"><ShieldCheck aria-hidden="true" />Laboratoria</li></ul><a className="link-button" href="/">Otwórz pełny panel<ArrowUpRight aria-hidden="true" /></a></section>
    </div>
  </>
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return <div className="detail-row"><dt className="detail-label">{label}</dt><dd className="detail-value">{children}</dd></div>
}

function System({ session, snapshot }: { session: AuthSession; snapshot: Snapshot }) {
  const ready = snapshot.ready
  return <div className="system-grid">
    <section className="panel" aria-labelledby="core-state-title"><h2 className="panel-heading" id="core-state-title"><Cpu aria-hidden="true" />Core i gotowość</h2><p className="panel-description">Odczyt z bieżącej instalacji JARVIS OS.</p><dl className="detail-list"><Detail label="Wersja Core">{snapshot.health.version}</Detail><Detail label="Gotowość">{ready.status === 'ready' ? 'Gotowy' : 'Brak gotowości — wymaga uwagi'}</Detail><Detail label="Baza danych">{ready.checks.database ? 'Dostępna' : 'Niedostępna'}</Detail><Detail label="Konfiguracja właściciela">{ready.checks.owner_key ? 'Poprawna' : 'Wymaga uzupełnienia'}</Detail><Detail label="Zdarzenia audytu">{snapshot.status.counts.audit.toLocaleString('pl-PL')}</Detail><Detail label="Automatyzacje">{snapshot.status.counts.automations.toLocaleString('pl-PL')}</Detail></dl><p className="info-note">Gotowość Core nie sprawdza opcjonalnego PostgreSQL, modeli, operatora ani urządzeń.</p></section>
    <section className="panel" aria-labelledby="session-state-title"><h2 className="panel-heading" id="session-state-title"><ShieldCheck aria-hidden="true" />Twoja sesja</h2><p className="panel-description">Uprawnienia są sprawdzane przez serwer przy każdym żądaniu.</p><dl className="detail-list"><Detail label="Rola">{roleLabels[session.identity.role]}</Detail><Detail label="Sposób dostępu">{session.identity.kind === 'session' ? 'Konto użytkownika' : 'Klucz właściciela'}</Detail><Detail label="Użytkownik">{session.identity.username || 'Właściciel instalacji'}</Detail><Detail label="Ważność">{session.identity.expires_at === null ? 'Do rozłączenia tej karty' : new Date(session.identity.expires_at * 1000).toLocaleString('pl-PL')}</Detail><Detail label="API">/api/v1</Detail><Detail label="Tryb integracji">DEMO + opcjonalne odczyty</Detail></dl><p className="info-note">Dane dostępu nie są zapisywane w przeglądarce. Odświeżenie strony kończy lokalne połączenie.</p></section>
  </div>
}

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [view, setView] = useState<View>(currentView)
  const [menuOpen, setMenuOpen] = useState(false)
  const [busyLogin, setBusyLogin] = useState(false)
  const [busyRefresh, setBusyRefresh] = useState(false)
  const [busyLogout, setBusyLogout] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loginError, setLoginError] = useState<string | null>(null)
  const epoch = useRef(0)
  const pending = useRef<AbortController | null>(null)
  const logoutController = useRef<AbortController | null>(null)
  const menuButton = useRef<HTMLButtonElement | null>(null)
  const sidebar = useRef<HTMLElement | null>(null)
  const firstLink = useRef<HTMLAnchorElement | null>(null)

  const begin = () => {
    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller
    const id = ++epoch.current
    return { controller, id }
  }
  const clearAuthentication = useCallback((reason: string | null = null) => {
    ++epoch.current
    pending.current?.abort(); pending.current = null
    setSession(null); setSnapshot(null); setError(null); setMenuOpen(false)
    setBusyLogin(false); setBusyRefresh(false); setLoginError(reason)
  }, [])

  const privateUnauthorized = useCallback(() => clearAuthentication('Sesja zakończyła się. Połącz się ponownie.'), [clearAuthentication])

  const autoLogin = useRef(false)
  useEffect(() => {
    const remembered = rememberedKey()
    if (remembered && !autoLogin.current) { autoLogin.current = true; void login({ mode: 'key', key: remembered }, true) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    const changed = () => setView(currentView())
    window.addEventListener('hashchange', changed)
    return () => { window.removeEventListener('hashchange', changed); ++epoch.current; pending.current?.abort(); logoutController.current?.abort() }
  }, [])
  useEffect(() => {
    if (!menuOpen) return
    let focusFrame = 0, attempts = 0
    const focusMenu = () => {
      const el = firstLink.current
      if (el && window.getComputedStyle(el).visibility === 'visible') {
        el.scrollIntoView?.({ block: 'nearest' }); el.focus()
        if (document.activeElement === el) return
      }
      if (++attempts < 60) focusFrame = window.requestAnimationFrame(focusMenu)
    }
    focusMenu()
    const keydown = (event: KeyboardEvent) => {
      window.cancelAnimationFrame(focusFrame)
      if (event.key === 'Escape') { event.preventDefault(); setMenuOpen(false); menuButton.current?.focus() }
      if (event.key === 'Tab') {
        const items = sidebar.current?.querySelectorAll<HTMLAnchorElement | HTMLButtonElement>('a[href],button:not([disabled])')
        if (!items?.length) return
        const first = items[0], last = items[items.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.scrollIntoView?.({ block: 'nearest' }); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.scrollIntoView?.({ block: 'nearest' }); first.focus() }
      }
    }
    document.addEventListener('keydown', keydown)
    return () => { window.cancelAnimationFrame(focusFrame); document.removeEventListener('keydown', keydown) }
  }, [menuOpen])

  async function login(input: LoginInput, keepView = false) {
    const { controller, id } = begin()
    setBusyLogin(true); setLoginError(null); setError(null); setSnapshot(null)
    try {
      const authenticated = await connect(input, controller.signal)
      if (epoch.current !== id || controller.signal.aborted) return
      const target = keepView ? currentView() : authenticated.identity.role === 'operator' || authenticated.identity.role === 'owner' ? 'kiosk' : 'dashboard'
      setSession(authenticated); setView(target); setMenuOpen(false)
      window.history.replaceState(null, '', '#/' + target)
      setBusyRefresh(true)
      try {
        const next = await readSnapshot(authenticated.credential, controller.signal)
        if (epoch.current === id && !controller.signal.aborted) setSnapshot(next)
      } catch (failure) {
        if (epoch.current !== id || controller.signal.aborted || aborted(failure)) return
        if (failure instanceof ApiError && failure.status === 401) clearAuthentication(failure.message)
        else setError(message(failure))
      }
    } catch (failure) {
      if (epoch.current === id && !controller.signal.aborted && !aborted(failure)) { setLoginError(message(failure)); if (failure instanceof ApiError && failure.status === 401) rememberKey(null) }
    } finally {
      if (epoch.current === id) { setBusyLogin(false); setBusyRefresh(false); pending.current = null }
    }
  }
  async function refresh() {
    if (!session || busyRefresh) return
    const { controller, id } = begin()
    setBusyRefresh(true); setError(null)
    try {
      const next = await readSnapshot(session.credential, controller.signal)
      if (epoch.current === id && !controller.signal.aborted) setSnapshot(next)
    } catch (failure) {
      if (epoch.current !== id || controller.signal.aborted || aborted(failure)) return
      if (failure instanceof ApiError && failure.status === 401) clearAuthentication(failure.message)
      else setError(message(failure))
    } finally {
      if (epoch.current === id) { setBusyRefresh(false); pending.current = null }
    }
  }
  async function logout() {
    if (!session || busyLogout) return
    const previous = session
    rememberKey(null)
    clearAuthentication()
    setBusyLogout(true)
    const controller = new AbortController()
    logoutController.current = controller
    try { await endSession(previous, controller.signal) }
    catch (failure) {
      if (!controller.signal.aborted && !(failure instanceof ApiError && failure.status === 401)) setLoginError('Połączenie w tej karcie zakończono. Nie udało się potwierdzić wylogowania na serwerze; sesję można odwołać w panelu dostępu.')
    } finally {
      if (!controller.signal.aborted) setBusyLogout(false)
      if (logoutController.current === controller) logoutController.current = null
    }
  }
  const navigate = (next: View) => {
    setView(next); setMenuOpen(false)
    if (menuOpen) document.getElementById('main-content')?.focus()
  }
  if (!session) return <Login busy={busyLogin || busyLogout} error={loginError} onSubmit={input => { void login(input) }} />
  const title = viewLabels[view]
  const isOwner = session.identity.role === 'owner'
  const ready = snapshot?.ready.status === 'ready'
  return <div className={'app-shell' + (menuOpen ? ' mobile-nav-open' : '')}>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>Przejdź do treści</a>
    {menuOpen && <button type="button" className="mobile-backdrop" tabIndex={-1} aria-label="Zamknij nawigację" onClick={() => { setMenuOpen(false); menuButton.current?.focus() }} />}
    <aside className="sidebar" id="control-navigation" ref={sidebar} aria-label="Nawigacja główna">
      <Brand />
      <nav className="sidebar-nav">{(() => {
        let first = true
        const link = (item: { view: View; icon: ReactNode }) => {
          const ref = first ? firstLink : undefined
          first = false
          return <a key={item.view} ref={ref} className="nav-link" href={'#/' + item.view} aria-current={view === item.view ? 'page' : undefined} onClick={() => navigate(item.view)}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{viewLabels[item.view]}</a>
        }
        const groups = navGroups.map(group => ({ ...group, items: group.items.filter(item => canAccess(item.view, session.identity.role)) })).filter(group => group.items.length > 0)
        const everyday = groups.some(group => !group.advanced && group.title === 'Na co dzień')
        return groups.map(group => group.advanced
          ? <details key={group.title} className="nav-group nav-advanced" open={!everyday || group.items.some(item => item.view === view) || undefined}><summary className="nav-group-title">{group.title}</summary>{group.items.map(link)}</details>
          : <div key={group.title} className="nav-group"><p className="nav-group-title">{group.title}</p>{group.items.map(link)}</div>)
      })()}</nav>
      <div className="sidebar-bottom"><a href="/">Dotychczasowy panel<ArrowUpRight aria-hidden="true" /></a><p className="sidebar-footer">JARVIS OS {snapshot?.health.version || ''}<br />Osobisty asystent · Twoje zasady</p></div>
    </aside>
    <div className="main-wrap"><header className="topbar"><div className="topbar-left"><button ref={menuButton} type="button" className="icon-button menu-button" aria-label={menuOpen ? 'Zamknij menu' : 'Otwórz menu'} aria-controls="control-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}>{menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}</button><p className="breadcrumb"><span>Control Center</span><ChevronRight aria-hidden="true" /><strong>{title}</strong></p></div><div className="topbar-right"><span className={'connection-pill ' + (snapshot && !ready ? 'tone-warning' : '')}>{snapshot ? ready ? 'Core gotowy' : 'Wymaga uwagi' : 'Odczyt danych'}</span><span className="user-avatar" aria-hidden="true">{(session.identity.username || snapshot?.status.settings.name || 'J').slice(0, 2).toUpperCase()}</span><span className="user-meta"><strong>{session.identity.username || snapshot?.status.settings.name || 'Właściciel'}</strong><span>{roleLabels[session.identity.role]}</span></span><button className="icon-button logout-button" type="button" aria-label="Wyloguj" onClick={() => { void logout() }}><LogOut aria-hidden="true" /></button></div></header>
      <main className="main-content" id="main-content" tabIndex={-1}><div className="page-heading"><div className="heading-copy"><p className="page-eyebrow">Twoje centrum dowodzenia</p><h1>{title}</h1><p>{viewDescriptions[view]}</p></div>{(view === 'dashboard' || view === 'system') && <div className="heading-actions"><button className="button secondary refresh-button" type="button" disabled={busyRefresh} onClick={() => { void refresh() }}><RefreshCw className={busyRefresh ? 'spin' : ''} aria-hidden="true" />Odśwież dane</button><p className="snapshot-time">{snapshot ? <>Odczyt: <time dateTime={new Date(snapshot.loadedAt).toISOString()}>{new Date(snapshot.loadedAt).toLocaleTimeString('pl-PL')}</time></> : 'Oczekiwanie na dane'}</p></div>}</div>
        {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}{snapshot ? ' Wyświetlany jest poprzedni odczyt.' : ''}</span></div>}
        {!canAccess(view, session.identity.role) ?
          <section className="empty-state"><ShieldCheck aria-hidden="true" /><h2>Dostęp właściciela</h2><p>To konto nie ma uprawnień do tego widoku.</p></section> :
          view === 'chat' ? <ChatPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'settings' ? <SettingsPanel credential={session.credential} onUnauthorized={privateUnauthorized} onStatusChanged={() => { void refresh() }} /> :
          view === 'activity' || view === 'logs' ? <ActivityPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'plugins' ? <PluginPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'workshop' ? <WorkshopPanel credential={session.credential} onUnauthorized={privateUnauthorized} canReadPrivate={isOwner} /> :
          view === 'home' ? <HomePanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'devices' ? <DevicesPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'gate' ? <GatePanel credential={session.credential} onUnauthorized={privateUnauthorized} owner={isOwner} /> :
          view === 'voice' ? <VoicePanel credential={session.credential} onUnauthorized={privateUnauthorized} owner={isOwner} /> :
          view === 'kiosk' ? <KioskPanel credential={session.credential} onUnauthorized={privateUnauthorized} workshopData={isOwner || session.identity.role === 'workshop_reader'} /> :
          view === 'cameras' ? <CamerasPanel credential={session.credential} onUnauthorized={privateUnauthorized} owner={isOwner} /> :
          view === 'account' ? <AccountPanel credential={session.credential} onUnauthorized={privateUnauthorized} accountSession={session.identity.kind === 'session'} /> :
          view === 'automations' ? <AutomationsPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'memory' ? <MemoryPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'telephony' ? <TelephonyPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'notifications' ? <NotificationsPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          view === 'changes' ? <ChangesPanel credential={session.credential} onUnauthorized={privateUnauthorized} onStatusChanged={() => { void refresh() }} /> :
          view === 'security' ? <SecurityPanel credential={session.credential} onUnauthorized={privateUnauthorized} /> :
          snapshot ? view === 'dashboard' ? <Dashboard snapshot={snapshot} role={session.identity.role} credential={session.credential} onUnauthorized={privateUnauthorized} /> : <System session={session} snapshot={snapshot} /> : <section className="loading-state" aria-live="polite">{busyRefresh ? <><RefreshCw className="spin" aria-hidden="true" /><p>Odczytywanie danych instalacji…</p></> : <><CircleAlert aria-hidden="true" /><p>Dane są chwilowo niedostępne. Możesz spróbować ponownie.</p></>}</section>}
        {(view === 'dashboard' || view === 'system') && <p className="footer-note"><Check aria-hidden="true" />Liczniki obejmują wszystkie zapisane rekordy. Odczyt Core nie potwierdza dostępności opcjonalnych usług ani sprzętu.</p>}
      </main>
    </div>
  </div>
}
