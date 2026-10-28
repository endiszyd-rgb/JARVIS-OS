import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, CircleAlert, Code, Play, Plug, Plus, Power, RefreshCw, Save, ShieldCheck } from 'lucide-react'
import { ApiError } from '../../api'
import { formConfig, InputError, invokeRead, parseObject, readConfig, readPlugins, readTools, registerPlugin, saveConfig, togglePlugin } from './api'
import type { Manifest, Plugin, Protocol, Tool } from './api'
import './plugins.css'

export interface PluginPanelProps { credential: string; onUnauthorized: () => void }
const emptyManifest = (): Manifest => ({ id: '', name: '', protocol: 'openapi', description: '' })
const protocolLabel = (kind: Protocol) => kind === 'demo' ? 'DEMO' : kind === 'mcp' ? 'MCP' : 'OpenAPI'
function failureMessage(failure: unknown): string {
  if (failure instanceof InputError) return failure.message
  if (failure instanceof ApiError) {
    if (failure.status === 409) return 'Plugin jest wyłączony, nieskonfigurowany lub identyfikator jest już zajęty. Sprawdź listę i konfigurację.'
    if (failure.status === 422) return 'Konfiguracja, katalog lub argumenty wymagają poprawienia i ponownego lokalnego przeglądu.'
    if (failure.status === 501) return 'Plugin wymaga konfiguracji endpointu przed wykonaniem odczytu.'
    if (failure.status === 502) return 'Nie udało się odczytać poprawnej odpowiedzi pluginu. Połączenie nie zostało potwierdzone.'
    if (failure.status === 504) return 'Upłynął limit czasu pluginu. Nie ponowiono odczytu automatycznie.'
    return failure.message
  }
  return 'Nie udało się wykonać operacji pluginu. Sprawdź bieżący stan przed kolejną próbą.'
}

export function PluginPanel(props: PluginPanelProps) { return <PluginWorkspace key={props.credential} {...props} /> }
function PluginWorkspace({ credential, onUnauthorized }: PluginPanelProps) {
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [endpoint, setEndpoint] = useState(''), [secret, setSecret] = useState(''), [reviewed, setReviewed] = useState(''), [spec, setSpec] = useState('{}')
  const [configLoaded, setConfigLoaded] = useState(false), [configDirty, setConfigDirty] = useState(false)
  const [tools, setTools] = useState<Tool[] | null>(null)
  const [operation, setOperation] = useState(''), [args, setArgs] = useState('{}')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [manifest, setManifest] = useState<Manifest>(emptyManifest)
  const [busy, setBusy] = useState(false), [loaded, setLoaded] = useState(false), [authorized, setAuthorized] = useState(true)
  const [error, setError] = useState<string | null>(null), [notice, setNotice] = useState<string | null>(null)
  const pending = useRef<AbortController | null>(null), epoch = useRef(0), mounted = useRef(true), expired = useRef(false)
  const callback = useRef(onUnauthorized); callback.current = onUnauthorized
  const selected = plugins.find(item => item.id === selectedId)
  const chosenTool = tools?.find(item => item.name === operation)
  function begin() {
    pending.current?.abort()
    const controller = new AbortController(), id = ++epoch.current
    pending.current = controller; setBusy(true); setError(null); setNotice(null)
    return { controller, id }
  }
  function valid(id: number, controller: AbortController) { return mounted.current && !expired.current && epoch.current === id && !controller.signal.aborted }
  function failed(failure: unknown, id: number, controller: AbortController) {
    if (!valid(id, controller) || failure instanceof DOMException && failure.name === 'AbortError') return
    if (failure instanceof ApiError && failure.status === 401) {
      expired.current = true; ++epoch.current; controller.abort(); pending.current = null
      setPlugins([]); setSelectedId(null); setEndpoint(''); setSecret(''); setReviewed(''); setSpec('{}'); setTools(null); setResult(null); setArgs('{}'); setManifest(emptyManifest()); setError(null); setNotice(null); setAuthorized(false)
      callback.current()
    } else setError(failureMessage(failure))
  }
  function finish(id: number, controller: AbortController) { if (valid(id, controller)) { setBusy(false); pending.current = null } }
  function editedConfig(change: () => void) { change(); setConfigDirty(true); clearTools() }
  function clearTools() { setTools(null); setOperation(''); setResult(null); setArgs('{}') }
  function clearConfig() { setEndpoint(''); setSecret(''); setReviewed(''); setSpec('{}'); setConfigLoaded(false); setConfigDirty(false) }
  async function refresh() {
    const { controller, id } = begin()
    setSelectedId(null); clearConfig(); clearTools()
    try { const rows = await readPlugins(credential, controller.signal); if (valid(id, controller)) { setPlugins(rows); setLoaded(true) } }
    catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  useEffect(() => {
    mounted.current = true; expired.current = false
    void refresh()
    return () => { mounted.current = false; ++epoch.current; pending.current?.abort(); pending.current = null }
    // The keyed workspace is recreated for each credential.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])
  async function choose(plugin: Plugin) {
    if (busy) return
    setSelectedId(plugin.id); clearConfig(); clearTools()
    if (plugin.protocol === 'demo') { setError(null); setNotice(null); return }
    const { controller, id } = begin()
    try {
      const config = await readConfig(credential, plugin.id, controller.signal)
      if (!valid(id, controller)) return
      if (config) { setEndpoint(config.endpoint); setSecret(config.secret_env ?? ''); setReviewed(config.reviewed_read_tools.join('\n')); setSpec(JSON.stringify(config.openapi ?? {}, null, 2)) }
      setConfigLoaded(true)
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || busy || !configLoaded) return
    let config
    try { config = formConfig(endpoint, secret, reviewed, spec, selected.protocol) } catch (failure) { setError(failureMessage(failure)); return }
    const plugin = selected, { controller, id } = begin(); clearTools()
    try {
      await saveConfig(credential, plugin.id, config, controller.signal)
      if (valid(id, controller)) { setConfigDirty(false); setPlugins(rows => rows.map(item => item.id === plugin.id ? { ...item, enabled: false, transport_ready: true } : item)); setNotice('Konfiguracja zapisana. Plugin został wyłączony; włącz go osobno po sprawdzeniu odczytów.') }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  async function toggle() {
    if (!selected || busy) return
    const plugin = selected, enabled = !plugin.enabled, { controller, id } = begin(); clearTools()
    try {
      await togglePlugin(credential, plugin.id, enabled, controller.signal)
      if (valid(id, controller)) { setPlugins(rows => rows.map(item => item.id === plugin.id ? { ...item, enabled } : item)); setNotice(enabled ? 'Plugin włączony. Nie wykonano testu połączenia.' : 'Plugin wyłączony.') }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  async function discover() {
    if (!selected?.enabled || busy || configDirty) return
    const plugin = selected, { controller, id } = begin(); clearTools()
    try {
      const rows = await readTools(credential, plugin.id, controller.signal)
      if (valid(id, controller)) { setTools(rows); setNotice(plugin.protocol === 'mcp' ? 'Odczytano katalog przez sesję MCP. Katalog nie potwierdza działania każdej operacji.' : plugin.protocol === 'openapi' ? 'Odczytano lokalny katalog OpenAPI z konfiguracji. Nie wykonano testu połączenia.' : 'Odczytano katalog DEMO, bez połączenia z usługą.') }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  async function invoke(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected?.enabled || !chosenTool || busy || configDirty) return
    let parsed
    try { parsed = parseObject(args, 'Argumenty') } catch (failure) { setError(failureMessage(failure)); return }
    const plugin = selected, name = chosenTool.name, { controller, id } = begin(); setResult(null)
    try {
      const response = await invokeRead(credential, plugin.id, name, parsed, controller.signal)
      if (valid(id, controller)) {
        setResult(response)
        setNotice(response.status === 'blocked' ? 'Serwer zablokował wykonanie. Ten wynik nie potwierdza połączenia.' : plugin.protocol === 'demo' ? 'Wykonano odczyt DEMO. Nie nawiązano połączenia z rzeczywistą usługą.' : 'Otrzymano odpowiedź odczytu pluginu. Wynik dotyczy wybranej operacji i tej próby.')
      }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const submitted = { ...manifest, id: manifest.id.trim(), name: manifest.name.trim() }, { controller, id } = begin()
    try {
      await registerPlugin(credential, submitted, controller.signal)
      if (!valid(id, controller)) return
      const rows = await readPlugins(credential, controller.signal)
      if (valid(id, controller)) { setPlugins(rows); setManifest(emptyManifest()); setSelectedId(null); clearConfig(); clearTools(); setNotice('Manifest zarejestrowany. Plugin jest wyłączony; nie zainstalowano obcego kodu.') }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  if (!authorized) return <p role="status">Sesja zakończona. Połącz się ponownie.</p>
  return <div className="plugins-feature" aria-busy={busy}>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="plugins-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <div className="plugins-layout">
      <section className="panel plugins-list-panel" aria-labelledby="plugins-list-title"><div className="plugins-heading"><h2 className="panel-heading" id="plugins-list-title"><Plug aria-hidden="true" />Twoje pluginy</h2><button className="button subtle" type="button" onClick={() => { void refresh() }} disabled={busy}><RefreshCw aria-hidden="true" />Odśwież pluginy</button></div>
        <p className="panel-description">Aktywacja i konfiguracja są oddzielne od potwierdzenia połączenia.</p>
        {!loaded && <p className="plugins-caption" role="status">{busy ? 'Odczytywanie pluginów…' : 'Lista jest chwilowo niedostępna.'}</p>}
        {loaded && plugins.length === 0 && <p className="plugins-caption">Brak zarejestrowanych pluginów.</p>}
        <ul className="plugins-list">{plugins.map(plugin => <li key={plugin.id}><button className="plugins-list-button" type="button" aria-label={plugin.name} aria-current={selectedId === plugin.id ? 'true' : undefined} disabled={busy} onClick={() => { void choose(plugin) }}><strong>{plugin.name}</strong><span>{protocolLabel(plugin.protocol)} · {plugin.enabled ? 'Włączony' : 'Wyłączony'}</span><small>{plugin.protocol === 'demo' ? 'Dane demonstracyjne' : plugin.transport_ready ? 'Konfiguracja zapisana' : 'Wymaga konfiguracji'}</small></button></li>)}</ul>
        <details className="plugins-register"><summary><Plus aria-hidden="true" />Dodaj plugin</summary><p className="plugins-caption">Rejestracja manifestu, bez instalowania kodu. Plugin zaczyna jako wyłączony.</p><form className="plugins-form" onSubmit={event => { void register(event) }}>
          <div className="form-field"><label htmlFor="plugin-register-id">Identyfikator pluginu</label><input id="plugin-register-id" value={manifest.id} pattern="[a-z][a-z0-9_]{1,40}" minLength={2} maxLength={41} required disabled={busy} onChange={event => setManifest({ ...manifest, id: event.target.value })} autoComplete="off" /></div>
          <div className="form-field"><label htmlFor="plugin-register-name">Nazwa pluginu</label><input id="plugin-register-name" value={manifest.name} maxLength={100} required disabled={busy} onChange={event => setManifest({ ...manifest, name: event.target.value })} /></div>
          <div className="form-field"><label htmlFor="plugin-register-protocol">Protokół</label><select id="plugin-register-protocol" value={manifest.protocol} disabled={busy} onChange={event => setManifest({ ...manifest, protocol: event.target.value as Protocol })}><option value="openapi">OpenAPI</option><option value="mcp">MCP</option><option value="demo">DEMO</option></select></div>
          <div className="form-field"><label htmlFor="plugin-register-description">Opis pluginu</label><input id="plugin-register-description" value={manifest.description} maxLength={1000} disabled={busy} onChange={event => setManifest({ ...manifest, description: event.target.value })} /></div>
          <button className="button secondary" type="submit" disabled={busy}>Zarejestruj manifest</button>
        </form></details>
      </section>
      {!selected ? <section className="panel plugins-empty"><Plug aria-hidden="true" /><h2>Wybierz plugin</h2><p>Otwórz jego konfigurację, sprawdź uprawnienia i zdecyduj o aktywacji.</p></section> : <div className="plugins-detail">
        <section className="panel" aria-labelledby="plugin-selected-title"><div className="plugins-heading"><div><p className="plugins-eyebrow">{protocolLabel(selected.protocol)} · {selected.id}</p><h2 className="panel-heading" id="plugin-selected-title">{selected.name}</h2></div><span className={'badge ' + (selected.enabled ? 'tone-good' : '')}>{selected.enabled ? 'Włączony' : 'Wyłączony'}</span></div><p className="panel-description">{selected.description || 'Brak opisu manifestu.'}</p><button className="button secondary" type="button" onClick={() => { void toggle() }} disabled={busy}><Power aria-hidden="true" />{selected.enabled ? 'Wyłącz plugin' : 'Włącz plugin'}</button><p className="plugins-caption">{selected.protocol === 'demo' ? 'Adapter DEMO używa danych syntetycznych.' : selected.transport_ready ? 'Konfiguracja jest zapisana. Połączenie wymaga jawnego sprawdzenia.' : 'Brak zapisanej konfiguracji. Samo włączenie nie zapewnia dostępności.'}</p></section>
        {selected.protocol !== 'demo' && <section className="panel" aria-labelledby="plugin-config-title"><h2 className="panel-heading" id="plugin-config-title"><Code aria-hidden="true" />Konfiguracja połączenia</h2><p className="panel-description">Zapis zastępuje całą konfigurację i wyłącza plugin. Równoległa edycja nie jest chroniona rewizją.</p>
          {!configLoaded ? <p className="plugins-caption">{busy ? 'Odczytywanie konfiguracji…' : 'Konfiguracja jest chwilowo niedostępna. Wybierz plugin ponownie, aby odczytać.'}</p> : <form className="plugins-form" onSubmit={event => { void save(event) }}>
            <div className="form-field"><label htmlFor="plugin-endpoint">Adres endpointu</label><input id="plugin-endpoint" type="url" value={endpoint} maxLength={500} required disabled={busy} onChange={event => editedConfig(() => setEndpoint(event.target.value))} autoComplete="off" spellCheck={false} /><small>HTTP/HTTPS, bez danych logowania, query i fragmentu. Backend wymaga dozwolonego adresu sieciowego.</small></div>
            <div className="form-field"><label htmlFor="plugin-secret">Nazwa zmiennej sekretu</label><input id="plugin-secret" value={secret} maxLength={81} disabled={busy} onChange={event => editedConfig(() => setSecret(event.target.value))} autoComplete="off" spellCheck={false} placeholder="JARVIS_PLUGIN_SECRET_…" /><small>Wyłącznie nazwa zmiennej w środowisku Core. Panel nie przyjmuje wartości ani nie potwierdza istnienia sekretu.</small></div>
            <div className="form-field"><label htmlFor="plugin-reviewed">Zatwierdzone odczyty</label><textarea id="plugin-reviewed" value={reviewed} maxLength={8100} disabled={busy} onChange={event => editedConfig(() => setReviewed(event.target.value))} spellCheck={false} /><small>Do100 nazw oddzielonych nową linią lub przecinkiem. Wpisz tylko samodzielnie sprawdzone operacje odczytu. Opis serwera i readOnlyHint nie nadają uprawnień.</small></div>
            {selected.protocol === 'openapi' && <div className="form-field"><label htmlFor="plugin-openapi">Specyfikacja OpenAPI JSON</label><textarea id="plugin-openapi" className="plugins-code-editor" value={spec} maxLength={65536} disabled={busy} onChange={event => editedConfig(() => setSpec(event.target.value))} spellCheck={false} /><small>OpenAPI3.x, obsługiwany podzbiór GET ze skalarnymi parametrami path/query, bez $ref i regexów.</small></div>}
            <button className="button primary" type="submit" disabled={busy}><Save aria-hidden="true" />Zapisz konfigurację</button>
          </form>}
        </section>}
        <section className="panel" aria-labelledby="plugin-tools-title"><h2 className="panel-heading" id="plugin-tools-title"><ShieldCheck aria-hidden="true" />Uprawnienia i test odczytu</h2><p className="panel-description">{selected.protocol === 'mcp' ? 'Odczyt katalogu nawiąże sesję z endpointem MCP.' : selected.protocol === 'openapi' ? 'Katalog OpenAPI jest odczytywany lokalnie z konfiguracji. Test połączenia wymaga osobnego wykonania wybranego odczytu.' : 'Katalog i odczyty DEMO nie testują rzeczywistego połączenia.'}</p><button className="button secondary" type="button" onClick={() => { void discover() }} disabled={busy || !selected.enabled || configDirty}><RefreshCw aria-hidden="true" />Odczytaj katalog</button>
          {configDirty && <p className="plugins-caption" role="status">Masz niezapisane zmiany konfiguracji. Zapisz je i osobno włącz plugin przed testowaniem.</p>}<p className="plugins-caption">Każda operacja wymaga po stronie Core zakresu plugins:invoke i lokalnego zatwierdzenia odczytu. Sterowanie, zapisy oraz instalacja kodu pozostają poza tym panelem.</p>
          {tools && <><p className="plugins-caption">{tools.length ? `Dostępne zatwierdzone odczyty: ${tools.length}.` : 'Brak zatwierdzonych odczytów w katalogu.'}</p><form className="plugins-form" onSubmit={event => { void invoke(event) }}>
            <div className="form-field"><label htmlFor="plugin-operation">Operacja odczytu</label><select id="plugin-operation" value={operation} disabled={busy || !selected.enabled || configDirty} onChange={event => { setOperation(event.target.value); setResult(null); setArgs('{}') }}><option value="">Wybierz operację</option>{tools.map(tool => <option key={tool.id} value={tool.name}>{tool.name}</option>)}</select></div>
            {chosenTool && <details className="plugins-schema"><summary>Schemat i opis operacji</summary><p className="plugins-caption">{chosenTool.description}</p><pre>{JSON.stringify(chosenTool.inputSchema, null, 2)}</pre></details>}
            <div className="form-field"><label htmlFor="plugin-arguments">Argumenty JSON</label><textarea id="plugin-arguments" className="plugins-code-editor" value={args} maxLength={65536} disabled={busy || !chosenTool} onChange={event => { setArgs(event.target.value); setResult(null) }} spellCheck={false} /></div>
            <button className="button primary" type="submit" disabled={busy || !selected.enabled || !chosenTool || configDirty}><Play aria-hidden="true" />Wykonaj odczyt testowy</button><p className="plugins-caption">Jawna próba odczytu, bez automatycznego ponawiania. Przerwanie karty nie gwarantuje zatrzymania pracy backendu.</p>
          </form></>}
          {result && <div className="plugins-result"><h3>Wynik odczytu</h3><pre>{JSON.stringify(result, null, 2)}</pre></div>}
        </section>
      </div>}
    </div>
  </div>
}
