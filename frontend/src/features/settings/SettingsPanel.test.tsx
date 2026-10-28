import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SettingsPanel } from './SettingsPanel'

const CREDENTIAL = 'synthetic-settings-session-token'
const PROPOSAL = '20000000-0000-4000-8000-000000000001'
const MODEL_CATALOG = {
  default_provider: 'demo', models: [{ provider: 'demo', name: 'demo', cloud: false }, { provider: 'ollama', name: 'qwen:local', cloud: false }],
  default_ollama_model: 'qwen:local', source: 'owner_configuration', probes_network: false,
}
type Settings = { name: string; tone: 'casual' | 'formal'; model: 'demo' | 'ollama' }
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function server(handler?: Handler) {
  const calls: Call[] = []
  const state: { current: Settings; pending: Settings | null } = { current: { name: 'Andreas', tone: 'casual', model: 'demo' }, pending: null }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input)
    calls.push({ path, options })
    const custom = handler?.(path, options)
    if (custom !== undefined) return await custom
    if (path === '/api/v1/status') return response({ mode: 'demo_with_optional_readonly', settings: { ...state.current }, counts: { plugins: 6, memory: 0, audit: 0, proposals: 0, automations: 0, notifications: 0 }, live_devices: false, models: ['demo', 'ollama'], autologika_audit: 'synthetic' })
    if (path === '/api/v1/models') return response(MODEL_CATALOG)
    if (path === '/api/v1/proposals' && options.method === 'POST') {
      const body = JSON.parse(String(options.body))
      state.pending = { ...body.payload }
      return response({ id: PROPOSAL, kind: 'settings', payload: state.pending, status: 'pending' }, 201)
    }
    if (path === '/api/v1/proposals/' + PROPOSAL + '/decide' && options.method === 'POST') {
      const approve = JSON.parse(String(options.body)).approve
      if (approve && state.pending) state.current = { ...state.pending }
      return response({ id: PROPOSAL, status: approve ? 'applied' : 'rejected' })
    }
    throw new Error('Unexpected settings request: ' + path)
  }))
  return { calls, state }
}
function renderPanel() {
  const onUnauthorized = vi.fn(), onStatusChanged = vi.fn()
  const rendered = render(<SettingsPanel credential={CREDENTIAL} onUnauthorized={onUnauthorized} onStatusChanged={onStatusChanged} />)
  return { ...rendered, onUnauthorized, onStatusChanged }
}
async function editName(name: string) {
  const user = userEvent.setup()
  const field = await screen.findByLabelText('Imię')
  await user.clear(field)
  await user.type(field, name)
  return user
}
afterEach(() => vi.unstubAllGlobals())

describe('Settings proposals require a separate decision', () => {
  it('previews a full settings payload without applying it and approves only on the next deliberate action', async () => {
    const { calls, state } = server()
    const { onStatusChanged } = renderPanel()
    const user = await editName('Marta')
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    await screen.findByRole('button', { name: 'Zatwierdź zmianę' })
    const created = calls.find(call => call.path === '/api/v1/proposals')!
    expect(JSON.parse(String(created.options.body))).toEqual({ kind: 'settings', payload: { name: 'Marta', tone: 'casual', model: 'demo' } })
    expect(new Headers(created.options.headers).get('X-Jarvis-Key')).toBe(CREDENTIAL)
    expect(state.current.name).toBe('Andreas')
    expect(calls.some(call => call.path.endsWith('/decide'))).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Zatwierdź zmianę' }))
    await waitFor(() => expect(state.current.name).toBe('Marta'))
    expect(JSON.parse(String(calls.find(call => call.path.endsWith('/decide'))!.options.body))).toEqual({ approve: true })
    await waitFor(() => expect(onStatusChanged).toHaveBeenCalled())
    expect(screen.getByLabelText('Imię')).toHaveValue('Marta')
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
  })

  it('rejects the pending proposal without changing current settings', async () => {
    const { calls, state } = server()
    renderPanel()
    const user = await editName('Not applied')
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    await user.click(await screen.findByRole('button', { name: 'Odrzuć propozycję' }))
    await waitFor(() => expect(calls.some(call => call.path.endsWith('/decide'))).toBe(true))
    expect(JSON.parse(String(calls.find(call => call.path.endsWith('/decide'))!.options.body))).toEqual({ approve: false })
    expect(state.current).toEqual({ name: 'Andreas', tone: 'casual', model: 'demo' })
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Zatwierdź zmianę' })).not.toBeInTheDocument())
  })

  it('reloads an externally changed baseline before preview instead of submitting stale unchanged fields', async () => {
    const { calls, state } = server()
    renderPanel()
    const user = await editName('Marta')
    state.current = { name: 'Andreas', tone: 'formal', model: 'demo' }
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    await waitFor(() => expect(screen.getByLabelText('Styl odpowiedzi')).toHaveValue('formal'))
    expect(calls.some(call => call.path === '/api/v1/proposals')).toBe(false)
    const name = screen.getByLabelText('Imię')
    await user.clear(name); await user.type(name, 'Marta')
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    await screen.findByRole('button', { name: 'Zatwierdź zmianę' })
    const created = calls.find(call => call.path === '/api/v1/proposals')!
    expect(JSON.parse(String(created.options.body)).payload).toEqual({ name: 'Marta', tone: 'formal', model: 'demo' })
  })

  it('does not approve a preview after a detected external settings change', async () => {
    const { calls, state } = server()
    renderPanel()
    const user = await editName('Marta')
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    const approve = await screen.findByRole('button', { name: 'Zatwierdź zmianę' })
    state.current = { name: 'Newer owner setting', tone: 'formal', model: 'ollama' }
    await user.click(approve)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(calls.some(call => call.path.endsWith('/decide'))).toBe(false)
    expect(state.current.name).toBe('Newer owner setting')
  })

  it('keeps transport diagnostics out of the UI when creating a proposal fails', async () => {
    const secret = 'Synthetic backend diagnostics that must not be rendered'
    server((path, options) => path === '/api/v1/proposals' && options.method === 'POST' ? response({ detail: secret }, 500) : undefined)
    renderPanel()
    const user = await editName('Marta')
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    await screen.findByRole('alert')
    expect(document.body.textContent).not.toContain(secret)
    expect(screen.queryByRole('button', { name: 'Zatwierdź zmianę' })).not.toBeInTheDocument()
  })

  it('clears private form data and notifies authentication when a preview refresh returns 401', async () => {
    let expired = false
    server(path => expired && path === '/api/v1/status' ? response({}, 401) : undefined)
    const { onUnauthorized } = renderPanel()
    const user = await editName('Private pending name')
    expired = true
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
    expect(document.body.innerHTML).not.toContain('Private pending name')
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
  })

  it('clears a private preview if the session expires while approving it', async () => {
    const { calls, state } = server((path, options) => path.endsWith('/decide') && options.method === 'POST' ? response({}, 401) : undefined)
    const { onUnauthorized, onStatusChanged } = renderPanel()
    const user = await editName('Private proposal name')
    await user.click(screen.getByRole('button', { name: 'Podgląd zmiany' }))
    await user.click(await screen.findByRole('button', { name: 'Zatwierdź zmianę' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
    expect(calls.filter(call => call.path.endsWith('/decide'))).toHaveLength(1)
    expect(state.current.name).toBe('Andreas')
    expect(onStatusChanged).not.toHaveBeenCalled()
    expect(document.body.innerHTML).not.toContain('Private proposal name')
    expect(screen.queryByRole('button', { name: 'Zatwierdź zmianę' })).not.toBeInTheDocument()
  })

  it('ignores an old identity response after the credential changes', async () => {
    let resolveOld: ((value: Response) => void) | undefined
    let oldSignal: AbortSignal | undefined
    server((path, options) => {
      const credential = new Headers(options.headers).get('X-Jarvis-Key')
      if (path === '/api/v1/status' && credential === 'old-session') {
        oldSignal = options.signal as AbortSignal
        return new Promise<Response>(resolve => { resolveOld = resolve })
      }
      if (path === '/api/v1/status' && credential === 'new-session') return response({ settings: { name: 'New owner', tone: 'casual', model: 'demo' } })
    })
    const onUnauthorized = vi.fn(), onStatusChanged = vi.fn()
    const { rerender } = render(<SettingsPanel credential="old-session" onUnauthorized={onUnauthorized} onStatusChanged={onStatusChanged} />)
    await waitFor(() => expect(resolveOld).toBeDefined())
    rerender(<SettingsPanel credential="new-session" onUnauthorized={onUnauthorized} onStatusChanged={onStatusChanged} />)
    await waitFor(() => expect(screen.getByLabelText('Imię')).toHaveValue('New owner'))
    expect(oldSignal?.aborted).toBe(true)
    await act(async () => { resolveOld!(response({ settings: { name: 'Old private owner', tone: 'formal', model: 'ollama' } })) })
    expect(screen.getByLabelText('Imię')).toHaveValue('New owner')
    expect(document.body.innerHTML).not.toContain('Old private owner')
    expect(onUnauthorized).not.toHaveBeenCalled()
  })
})
