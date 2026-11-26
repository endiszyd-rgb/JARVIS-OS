import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { AudioLines, Bot, Camera, Check, CircleAlert, ClipboardList, DoorOpen, Eye, RefreshCw, Settings2, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '../../api'
import { FieldLabel } from '../../components/HelpTip'
import { GateSettings } from '../gate/GateSettings'
import { VoiceSettings } from '../voice/VoiceSettings'
import { CameraSettings } from '../cameras/CamerasPanel'
import { ConnectionSettings } from '../workshop/TodayCard'
import { decideSettings, proposeSettings, readCatalog, readSettings, sameSettings } from './api'
import type { ModelCatalog, Settings, SettingsProposal } from './api'
import './settings.css'

interface Props { credential: string; onUnauthorized: () => void; onStatusChanged: () => void }
interface Preview { proposal: SettingsProposal; before: Settings; conflict: boolean }
const toneLabel = (tone: Settings['tone']) => tone === 'formal' ? 'Formalny' : 'Swobodny'
const providerLabel = (model: Settings['model']) => model === 'ollama' ? 'Ollama' : model === 'openai' ? 'OpenAI' : 'DEMO'
const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : 'Nie udało się wykonać żądania. Spróbuj ponownie.'

function SettingsEditor({ credential, onUnauthorized, onStatusChanged }: Props) {
  const [current, setCurrent] = useState<Settings | null>(null)
  const [draft, setDraft] = useState<Settings | null>(null)
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const callbacks = useRef({ onUnauthorized, onStatusChanged })
  callbacks.current = { onUnauthorized, onStatusChanged }
  const epoch = useRef(0)
  const pending = useRef<AbortController | null>(null)
  const begin = () => {
    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller
    const id = ++epoch.current
    setBusy(true); setError(null); setNotice(null)
    return { controller, id }
  }
  const valid = (id: number, controller: AbortController) => epoch.current === id && !controller.signal.aborted
  const failed = (failure: unknown, id: number, controller: AbortController) => {
    if (!valid(id, controller)) return
    if (failure instanceof ApiError && failure.status === 401) {
      setCurrent(null); setDraft(null); setCatalog(null); setPreview(null)
      callbacks.current.onUnauthorized()
    } else setError(errorMessage(failure))
  }
  const finish = (id: number, controller: AbortController) => {
    if (valid(id, controller)) { setBusy(false); pending.current = null }
  }

  useEffect(() => {
    const controller = new AbortController()
    pending.current = controller
    const id = ++epoch.current
    setCurrent(null); setDraft(null); setCatalog(null); setPreview(null); setError(null); setNotice(null); setBusy(true)
    void Promise.all([readSettings(credential, controller.signal), readCatalog(credential, controller.signal)])
      .then(([settings, models]) => {
        if (valid(id, controller)) { setCurrent(settings); setDraft(settings); setCatalog(models) }
      }).catch(failure => failed(failure, id, controller)).finally(() => finish(id, controller))
    return () => { ++epoch.current; controller.abort(); pending.current?.abort(); pending.current = null }
  }, [credential])

  async function refresh() {
    if (busy || preview) return
    const { controller, id } = begin()
    try {
      const [settings, models] = await Promise.all([readSettings(credential, controller.signal), readCatalog(credential, controller.signal)])
      if (valid(id, controller)) { setCurrent(settings); setDraft(settings); setCatalog(models) }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }

  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!current || !draft || busy || preview) return
    const submitted = { ...draft }
    const previous = { ...current }
    const { controller, id } = begin()
    try {
      const latest = await readSettings(credential, controller.signal)
      if (!valid(id, controller)) return
      if (!sameSettings(latest, previous)) {
        setCurrent(latest); setDraft(latest)
        setError('Ustawienia zmieniły się. Wczytano bieżące wartości; wprowadź zmianę ponownie.')
        return
      }
      const proposal = await proposeSettings(credential, controller.signal, submitted)
      if (valid(id, controller)) setPreview({ proposal, before: latest, conflict: false })
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }

  async function decide(approve: boolean) {
    if (!preview || busy) return
    const staged = preview
    const { controller, id } = begin()
    try {
      if (approve) {
        const latest = await readSettings(credential, controller.signal)
        if (!valid(id, controller)) return
        if (!sameSettings(latest, staged.before)) {
          setCurrent(latest); setPreview({ ...staged, conflict: true })
          setError('Ustawienia zmieniły się od podglądu. Nie zatwierdzono tej propozycji. Odrzuć ją i przygotuj nową zmianę.')
          return
        }
      }
      await decideSettings(credential, controller.signal, staged.proposal.id, approve)
      if (!valid(id, controller)) return
      setPreview(null)
      if (approve) { setCurrent(staged.proposal.payload); setDraft(staged.proposal.payload) }
      else setDraft(current)
      setNotice(approve ? 'Ustawienia zostały zapisane.' : 'Propozycja została odrzucona. Ustawienia pozostały bez zmian.')
      callbacks.current.onStatusChanged()
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }

  return <div className="settings-feature">
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="settings-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <section className="panel" aria-labelledby="settings-form-title">
      <div className="settings-section-heading"><div><h2 className="panel-heading" id="settings-form-title"><Settings2 aria-hidden="true" />Ustawienia asystenta</h2><p className="panel-description">Zmianę najpierw zobaczysz w podglądzie, zapis po osobnym zatwierdzeniu.</p></div><button type="button" className="button subtle" onClick={() => { void refresh() }} disabled={busy || preview !== null}><RefreshCw aria-hidden="true" />Odśwież ustawienia</button></div>
      {!draft ? <p className="settings-loading" role="status">{busy ? 'Odczytywanie ustawień…' : 'Ustawienia są chwilowo niedostępne.'}</p> : <form className="settings-form" onSubmit={event => { void prepare(event) }} aria-busy={busy}>
        <div className="form-field"><FieldLabel htmlFor="assistant-name" help="Jak JARVIS ma się do Ciebie zwracać w rozmowie.">Imię</FieldLabel><input id="assistant-name" value={draft.name} minLength={1} maxLength={80} required disabled={busy || preview !== null} onChange={event => setDraft({ ...draft, name: event.target.value })} autoComplete="off" /></div>
        <div className="form-field"><FieldLabel htmlFor="assistant-tone" help="Swobodny — krótko, po koleżeńsku. Formalny — grzecznościowo, jak do klienta.">Styl odpowiedzi</FieldLabel><select id="assistant-tone" value={draft.tone} disabled={busy || preview !== null} onChange={event => setDraft({ ...draft, tone: event.target.value as Settings['tone'] })}><option value="casual">Swobodny</option><option value="formal">Formalny</option></select></div>
        <div className="form-field"><FieldLabel htmlFor="assistant-provider" help="Model AI do rozmów. DEMO — bez AI, tylko polecenia. Ollama — model na własnym komputerze. OpenAI — model w chmurze (wymaga klucza w pliku .env). Polecenia bramy i części działają zawsze, bez AI.">Model AI</FieldLabel><select id="assistant-provider" value={draft.model} disabled={busy || preview !== null} onChange={event => setDraft({ ...draft, model: event.target.value as Settings['model'] })}><option value="demo">DEMO</option><option value="ollama">Ollama</option><option value="openai">OpenAI · chmura</option></select></div>
        <div className="settings-actions"><button type="submit" className="button primary" disabled={busy || preview !== null || current !== null && sameSettings(current, draft)}><Eye aria-hidden="true" />Podgląd zmiany</button></div>
      </form>}
    </section>
    {preview && <section className="panel settings-preview" aria-label="Podgląd zmiany" aria-labelledby="settings-preview-title">
      <h2 className="panel-heading" id="settings-preview-title"><Eye aria-hidden="true" />Podgląd zmiany</h2><p className="panel-description">Propozycja jest zapisana, ale jeszcze nie zmienia ustawień.</p>
      <dl className="settings-change-list"><div><dt>Imię</dt><dd><span>{preview.before.name}</span><span aria-hidden="true">→</span><strong>{preview.proposal.payload.name}</strong></dd></div><div><dt>Styl odpowiedzi</dt><dd><span>{toneLabel(preview.before.tone)}</span><span aria-hidden="true">→</span><strong>{toneLabel(preview.proposal.payload.tone)}</strong></dd></div><div><dt>Domyślny dostawca</dt><dd><span>{providerLabel(preview.before.model)}</span><span aria-hidden="true">→</span><strong>{providerLabel(preview.proposal.payload.model)}</strong></dd></div></dl>
      <p className="settings-confirmation-note">Przed zatwierdzeniem ponownie odczytamy ustawienia. Równoległe zmiany innego właściciela mogą nadal wymagać ponownego sprawdzenia.</p>
      <div className="settings-actions"><button type="button" className="button primary" disabled={busy || preview.conflict} onClick={() => { void decide(true) }}><Check aria-hidden="true" />Zatwierdź zmianę</button><button type="button" className="button secondary" disabled={busy} onClick={() => { void decide(false) }}><X aria-hidden="true" />Odrzuć propozycję</button></div>
    </section>}
    {catalog && <section className="panel" aria-labelledby="configured-models-title"><h2 className="panel-heading" id="configured-models-title">Modele w konfiguracji</h2><p className="panel-description">Lista właściciela, bez testowania usług. Model rozmowy wybierzesz w panelu rozmów.</p><ul className="settings-model-list">{catalog.models.map(model => <li key={model.provider + ':' + model.name}><strong>{model.name}</strong><span className="badge">{providerLabel(model.provider)}{model.cloud ? ' · chmurowy' : ''}</span></li>)}</ul><p className="settings-model-note">Domyślny model Ollama: <strong>{catalog.defaultOllamaModel}</strong>. Zmiana nazw modeli i konfiguracji dostawcy wymaga ustawień instalacji.</p></section>}
  </div>
}

export function AssistantSettings(props: Props) {
  // A new authenticated identity receives a new editor before its first paint.
  return <SettingsEditor key={props.credential} {...props} />
}

const TABS = [
  { id: 'gate', label: 'Brama', icon: <DoorOpen /> },
  { id: 'autologika', label: 'AutoLogika', icon: <ClipboardList /> },
  { id: 'cameras', label: 'Kamery', icon: <Camera /> },
  { id: 'voice', label: 'Głos', icon: <AudioLines /> },
  { id: 'assistant', label: 'Asystent AI', icon: <Bot /> },
] as const satisfies readonly { id: string; label: string; icon: ReactNode }[]
type Tab = typeof TABS[number]['id']
const tabFromHash = (): Tab => {
  const wanted = window.location.hash.split('/')[2] ?? ''
  return (TABS.find(item => item.id === wanted)?.id) ?? 'gate'
}

/** All configuration in one place, one topic per tab; addresses like #/settings/gate open a tab directly. */
export function SettingsPanel(props: Props) {
  const [tab, setTab] = useState<Tab>(tabFromHash)
  useEffect(() => {
    const changed = () => setTab(tabFromHash())
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const choose = (next: Tab) => { setTab(next); try { window.history.replaceState(null, '', '#/settings/' + next) } catch { /* history unavailable */ } }
  return <div className="settings-hub">
    <div className="settings-tabs" role="tablist" aria-label="Kategorie ustawień">{TABS.map(item =>
      <button key={item.id} type="button" role="tab" id={'settings-tab-' + item.id} aria-selected={tab === item.id} aria-controls="settings-tabpanel"
        className={'settings-tab' + (tab === item.id ? ' is-active' : '')} onClick={() => choose(item.id)}><span aria-hidden="true">{item.icon}</span>{item.label}</button>)}</div>
    <section className="panel settings-tabpanel" id="settings-tabpanel" role="tabpanel" aria-labelledby={'settings-tab-' + tab}>
      {tab === 'gate' ? <GateSettings key={props.credential} credential={props.credential} onUnauthorized={props.onUnauthorized} />
        : tab === 'autologika' ? <ConnectionSettings key={props.credential} credential={props.credential} onUnauthorized={props.onUnauthorized} onSaved={() => undefined} />
          : tab === 'cameras' ? <CameraSettings key={props.credential} credential={props.credential} onUnauthorized={props.onUnauthorized} />
            : tab === 'voice' ? <VoiceSettings key={props.credential} credential={props.credential} onUnauthorized={props.onUnauthorized} />
              : <AssistantSettings {...props} />}
    </section>
    <p className="settings-footnote">Konta użytkowników, tokeny i sesje: <a href="#/security">Bezpieczeństwo</a>. Twoje 2FA i Face ID: <a href="#/account">Moje konto</a>.</p>
  </div>
}
