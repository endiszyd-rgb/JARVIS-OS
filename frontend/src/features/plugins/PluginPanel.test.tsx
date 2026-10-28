import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PluginPanel } from './PluginPanel'

const CREDENTIAL = 'synthetic-plugin-session-not-rendered'
const SPEC = { openapi: '3.0.3', info: { title: 'Synthetic status', version: '1' }, paths: { '/status': { get: { operationId: 'status', summary: 'Read synthetic status', responses: { '200': { description: 'Synthetic' } } } } } }
const OPENAPI = { id: 'calendar_api', name: 'Calendar API', protocol: 'openapi', description: 'Synthetic calendar', enabled: true, transport_ready: true }
const MCP = { id: 'workshop_mcp', name: 'Workshop MCP', protocol: 'mcp', description: 'Synthetic MCP', enabled: true, transport_ready: true }
const DEMO = { id: 'demo_status', name: 'Demo status', protocol: 'demo', description: 'Local demo', enabled: true, transport_ready: true }
const CONFIG = { endpoint: 'http://127.0.0.1:9102', secret_env: 'JARVIS_PLUGIN_SECRET_SYNTHETIC', reviewed_read_tools: ['status'], openapi: SPEC }
const TOOL = { id: 'calendar_api.status', plugin_id: 'calendar_api', name: 'status', protocol: 'openapi', description: 'Synthetic read', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, schema_digest: 'a'.repeat(64), read_only_reviewed: true, read_only: true, required_scope: 'plugins:invoke' }
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function server(handler?: Handler) {
  const calls: Call[] = []
  const rows = [{ ...OPENAPI }, { ...MCP }, { ...DEMO }]
  let config = structuredClone(CONFIG)
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input), method = options.method || 'GET'
    calls.push({ path, options })
    const custom = handler?.(path, options)
    if (custom !== undefined) return await custom
    if (path === '/api/v1/plugins' && method === 'GET') return response(rows)
    if (path === '/api/v1/plugins' && method === 'POST') {
      const body = JSON.parse(String(options.body))
      rows.push({ ...body, enabled: false, transport_ready: body.protocol === 'demo' })
      return response({ id: body.id, enabled: false, status: 'manifest_registered', note: 'No foreign code is installed' }, 201)
    }
    const row = rows.find(plugin => path.startsWith('/api/v1/plugins/' + plugin.id))
    if (row && path.endsWith('/config')) {
      if (method === 'PUT') { config = JSON.parse(String(options.body)); row.enabled = false; row.transport_ready = true; return response({ configured: true, enabled: false }) }
      return response(row.protocol === 'mcp' ? { ...config, endpoint: 'http://127.0.0.1:9103/mcp', openapi: null } : config)
    }
    if (row && path.endsWith('/tools')) return response([{ ...TOOL, plugin_id: row.id, id: row.id + '.status', protocol: row.protocol }])
    if (row && path.endsWith('/invoke')) return response({ mode: row.protocol === 'demo' ? 'demo' : 'live_readonly', protocol: row.protocol, data: { synthetic: true } })
    if (row && method === 'PUT') { row.enabled = JSON.parse(String(options.body)).enabled; return response({ id: row.id, enabled: row.enabled }) }
    throw new Error('Unexpected plugin request: ' + method + ' ' + path)
  }))
  return { calls, rows, config: () => config }
}
function panel(credential = CREDENTIAL) {
  const onUnauthorized = vi.fn()
  return { ...render(<PluginPanel credential={credential} onUnauthorized={onUnauthorized} />), onUnauthorized }
}
async function selectPlugin(name = OPENAPI.name) {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name }))
  if (name !== DEMO.name) await screen.findByLabelText('Adres endpointu')
  return user
}
const invokes = (calls: Call[]) => calls.filter(call => call.path.endsWith('/invoke'))
afterEach(() => vi.unstubAllGlobals())

describe('Owner Plugin Manager', () => {
  it('loads only local metadata on entry and reads configuration without discovery or invocation', async () => {
    const { calls } = server()
    panel()
    await screen.findByRole('button', { name: OPENAPI.name })
    expect(calls.map(call => call.path)).toEqual(['/api/v1/plugins'])
    await selectPlugin()
    expect(screen.getByLabelText('Adres endpointu')).toHaveValue(CONFIG.endpoint)
    expect(calls.some(call => call.path.endsWith('/tools') || call.path.endsWith('/invoke'))).toBe(false)
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
  })

  it('saves a full configuration and revokes activation without automatically invoking or re-enabling', async () => {
    const { calls, rows, config } = server()
    panel()
    const user = await selectPlugin()
    const endpoint = screen.getByLabelText('Adres endpointu')
    await user.clear(endpoint); await user.type(endpoint, 'http://127.0.0.1:9202')
    const reviewed = screen.getByLabelText('Zatwierdzone odczyty')
    await user.clear(reviewed); await user.type(reviewed, 'status\ncalendar')
    await user.click(screen.getByRole('button', { name: 'Zapisz konfigurację' }))
    await waitFor(() => expect(rows[0].enabled).toBe(false))
    const saved = calls.find(call => call.path.endsWith('/config') && call.options.method === 'PUT')!
    expect(JSON.parse(String(saved.options.body))).toEqual({ endpoint: 'http://127.0.0.1:9202', secret_env: CONFIG.secret_env, reviewed_read_tools: ['status', 'calendar'], openapi: SPEC })
    expect(config().endpoint).toBe('http://127.0.0.1:9202')
    await screen.findByRole('button', { name: 'Włącz plugin' })
    expect(calls.some(call => call.options.method === 'PUT' && !call.path.endsWith('/config'))).toBe(false)
    expect(invokes(calls)).toHaveLength(0)
  })

  it('changes enabled state only after the deliberate toggle', async () => {
    const { calls, rows } = server()
    panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Wyłącz plugin' }))
    await waitFor(() => expect(rows[0].enabled).toBe(false))
    const toggle = calls.find(call => call.path === '/api/v1/plugins/calendar_api' && call.options.method === 'PUT')!
    expect(JSON.parse(String(toggle.options.body))).toEqual({ enabled: false })
    await user.click(await screen.findByRole('button', { name: 'Włącz plugin' }))
    await waitFor(() => expect(rows[0].enabled).toBe(true))
    expect(calls.some(call => call.path.endsWith('/tools'))).toBe(false)
    expect(invokes(calls)).toHaveLength(0)
  })

  it('requires an explicit catalog action and explicit operation before a test read, escaping returned HTML', async () => {
    const unsafe = '<img src=x onerror=window.stolen=true>'
    const { calls } = server(path => path.endsWith('/invoke') ? response({ mode: 'live_readonly', protocol: 'openapi', data: { text: unsafe } }) : undefined)
    panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    const operation = await screen.findByLabelText('Operacja odczytu')
    expect(operation).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Wykonaj odczyt testowy' })).toBeDisabled()
    expect(invokes(calls)).toHaveLength(0)
    await user.selectOptions(operation, 'status')
    await user.click(screen.getByRole('button', { name: 'Wykonaj odczyt testowy' }))
    await screen.findByRole('heading', { name: 'Wynik odczytu' })
    expect(JSON.parse(String(invokes(calls)[0].options.body))).toEqual({ operation: 'status', arguments: {} })
    expect(new Headers(invokes(calls)[0].options.headers).get('X-Jarvis-Key')).toBe(CREDENTIAL)
    expect(document.body.textContent).toContain(unsafe)
    expect(document.querySelector('img')).toBeNull()
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
  })

  it('removes old tools and results when configuration is saved and requires deliberate reactivation', async () => {
    const { calls } = server()
    panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await user.selectOptions(await screen.findByLabelText('Operacja odczytu'), 'status')
    await user.click(screen.getByRole('button', { name: 'Wykonaj odczyt testowy' }))
    await screen.findByRole('heading', { name: 'Wynik odczytu' })
    await user.click(screen.getByRole('button', { name: 'Zapisz konfigurację' }))
    await screen.findByRole('button', { name: 'Włącz plugin' })
    expect(screen.queryByRole('heading', { name: 'Wynik odczytu' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Operacja odczytu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Odczytaj katalog' })).toBeDisabled()
    expect(invokes(calls)).toHaveLength(1)
  })

  it('clears previous results and blocks discovery while edited configuration remains unsaved', async () => {
    const { calls } = server()
    panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await user.selectOptions(await screen.findByLabelText('Operacja odczytu'), 'status')
    await user.click(screen.getByRole('button', { name: 'Wykonaj odczyt testowy' }))
    await screen.findByRole('heading', { name: 'Wynik odczytu' })
    const endpoint = screen.getByLabelText('Adres endpointu')
    await user.clear(endpoint); await user.type(endpoint, 'http://127.0.0.1:9202')
    expect(screen.queryByRole('heading', { name: 'Wynik odczytu' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Operacja odczytu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Odczytaj katalog' })).toBeDisabled()
    expect(screen.getByText(/niezapisane zmiany/i)).toBeInTheDocument()
    expect(calls.filter(call => call.path.endsWith('/tools'))).toHaveLength(1)
    expect(invokes(calls)).toHaveLength(1)
    expect(calls.some(call => call.options.method === 'PUT')).toBe(false)
  })

  it('labels a blocked 200 response as blocked rather than confirming connection', async () => {
    server(path => path.endsWith('/invoke') ? response({ status: 'blocked', reason: 'Physical and write side effects disabled' }) : undefined)
    panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await user.selectOptions(await screen.findByLabelText('Operacja odczytu'), 'status')
    await user.click(screen.getByRole('button', { name: 'Wykonaj odczyt testowy' }))
    await screen.findByText('Serwer zablokował wykonanie. Ten wynik nie potwierdza połączenia.')
    expect(document.body.textContent).toContain('blocked')
  })

  it('never requests network configuration for a demonstration adapter', async () => {
    const { calls } = server()
    panel()
    const user = await selectPlugin(DEMO.name)
    expect(screen.queryByLabelText('Adres endpointu')).not.toBeInTheDocument()
    expect(calls.some(call => call.path.endsWith('/config'))).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await screen.findByLabelText('Operacja odczytu')
    expect(invokes(calls)).toHaveLength(0)
  })

  it('does not discover MCP on selection and waits for a deliberate catalog request', async () => {
    const { calls } = server()
    panel()
    const user = await selectPlugin(MCP.name)
    expect(calls.some(call => call.path.endsWith('/tools'))).toBe(false)
    expect(invokes(calls)).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await screen.findByLabelText('Operacja odczytu')
    expect(calls.filter(call => call.path.endsWith('/tools'))).toHaveLength(1)
    expect(calls.find(call => call.path.endsWith('/tools'))!.path).toBe('/api/v1/plugins/workshop_mcp/tools')
    expect(invokes(calls)).toHaveLength(0)
  })

  it('rejects malformed JSON arguments locally without invoking the tool', async () => {
    const { calls } = server()
    panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await user.selectOptions(await screen.findByLabelText('Operacja odczytu'), 'status')
    const args = screen.getByLabelText('Argumenty JSON')
    await user.clear(args); await user.type(args, 'invalid JSON')
    await user.click(screen.getByRole('button', { name: 'Wykonaj odczyt testowy' }))
    await screen.findByRole('alert')
    expect(invokes(calls)).toHaveLength(0)
  })

  it.each([409, 422, 502, 504])('does not leak backend diagnostics or retry a failed catalog request (%s)', async status => {
    const detail = 'synthetic-sensitive-transport-diagnostic'
    const { calls } = server(path => path.endsWith('/tools') ? response({ detail }, status) : undefined)
    panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await screen.findByRole('alert')
    expect(document.body.textContent).not.toContain(detail)
    expect(calls.filter(call => call.path.endsWith('/tools'))).toHaveLength(1)
    expect(invokes(calls)).toHaveLength(0)
  })

  it('clears private configuration when an authenticated action returns 401', async () => {
    const { calls } = server(path => path.endsWith('/tools') ? response({}, 401) : undefined)
    const { onUnauthorized } = panel()
    const user = await selectPlugin()
    await user.click(screen.getByRole('button', { name: 'Odczytaj katalog' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
    expect(screen.queryByLabelText('Adres endpointu')).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(CONFIG.endpoint)
    expect(document.body.innerHTML).not.toContain(CONFIG.secret_env)
    expect(invokes(calls)).toHaveLength(0)
  })

  it('aborts an old identity request and ignores its late 401 after credentials change', async () => {
    let resolveOld: ((value: Response) => void) | undefined, oldSignal: AbortSignal | undefined
    server((path, options) => {
      if (path === '/api/v1/plugins' && new Headers(options.headers).get('X-Jarvis-Key') === 'old-session') {
        oldSignal = options.signal as AbortSignal
        return new Promise<Response>(resolve => { resolveOld = resolve })
      }
      return undefined
    })
    const onUnauthorized = vi.fn()
    const { rerender } = render(<PluginPanel credential="old-session" onUnauthorized={onUnauthorized} />)
    await waitFor(() => expect(resolveOld).toBeDefined())
    rerender(<PluginPanel credential="new-session" onUnauthorized={onUnauthorized} />)
    await screen.findByRole('button', { name: OPENAPI.name })
    expect(oldSignal?.aborted).toBe(true)
    await act(async () => { resolveOld!(response({}, 401)) })
    expect(onUnauthorized).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: OPENAPI.name })).toBeInTheDocument()
  })

  it('registers a manifest as disabled without installing or invoking foreign code', async () => {
    const { calls, rows } = server()
    panel()
    await screen.findByRole('button', { name: OPENAPI.name })
    const user = userEvent.setup()
    await user.click(screen.getByText('Dodaj plugin', { exact: true }))
    await user.type(screen.getByLabelText('Identyfikator pluginu'), 'new_api')
    await user.type(screen.getByLabelText('Nazwa pluginu'), 'New synthetic API')
    await user.selectOptions(screen.getByLabelText('Protokół'), 'openapi')
    await user.type(screen.getByLabelText('Opis pluginu'), 'Synthetic registration')
    await user.click(screen.getByRole('button', { name: 'Zarejestruj manifest' }))
    await waitFor(() => expect(rows.some(row => row.id === 'new_api')).toBe(true))
    expect(rows.find(row => row.id === 'new_api')?.enabled).toBe(false)
    const created = calls.find(call => call.path === '/api/v1/plugins' && call.options.method === 'POST')!
    expect(JSON.parse(String(created.options.body))).toEqual({ id: 'new_api', name: 'New synthetic API', protocol: 'openapi', description: 'Synthetic registration' })
    expect(invokes(calls)).toHaveLength(0)
  })
})
