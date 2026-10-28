import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SecurityPanel } from './SecurityPanel'

const CREDENTIAL = 'synthetic-owner-auth-never-rendered'
const PASSWORD = 'Synthetic-new-account-password-123'
const SECRET = 'jv_' + 'synthetic_service_secret_'.repeat(3)
const USER = { id: '00000000-0000-4000-8000-000000000001', username: 'operator.demo', role: 'observer', enabled: true, revision: 3, created: 1800000000, updated: 1800000000 }
const SESSION = { id: '00000000-0000-4000-8000-000000000002', user_id: USER.id, username: USER.username, role: USER.role, expires_at: 2100000000, revoked: false, created: 1800000000 }
const TOKEN = { id: '00000000-0000-4000-8000-000000000003', name: 'Synthetic worker', scopes: ['status:read'], expires: 2100000000, revoked: 0 }
const CREATED = '00000000-0000-4000-8000-000000000004'
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
function server(handler?: Handler) {
  const calls: Call[] = [], users = [{ ...USER }], sessions = [{ ...SESSION }], tokens = [{ ...TOKEN }]
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input), method = options.method || 'GET'
    calls.push({ path, options })
    const custom = handler?.(path, options)
    if (custom !== undefined) return await custom
    if (path === '/api/v1/security/users' && method === 'GET') return response(users)
    if (path === '/api/v1/security/sessions' && method === 'GET') return response(sessions)
    if (path === '/api/v1/security/tokens' && method === 'GET') return response(tokens)
    if (path === '/api/v1/security/users' && method === 'POST') {
      const body = JSON.parse(String(options.body)); const row = { ...USER, id: CREATED, username: body.username, role: body.role, revision: 0 }
      users.push(row); return response(row, 201)
    }
    if (path === '/api/v1/security/users/' + USER.id && method === 'PATCH') {
      const body = JSON.parse(String(options.body)); Object.assign(users[0], { role: body.role, enabled: body.enabled, revision: USER.revision + 1 }); sessions[0].revoked = true
      return response(users[0])
    }
    if (path === '/api/v1/security/sessions/' + SESSION.id && method === 'DELETE') { sessions[0].revoked = true; return response({ revoked: SESSION.id }) }
    if (path === '/api/v1/security/tokens/' + TOKEN.id && method === 'DELETE') { tokens[0].revoked = 1; return response({ revoked: TOKEN.id }) }
    if (path === '/api/v1/security/tokens' && method === 'POST') {
      const body = JSON.parse(String(options.body)); tokens.push({ ...TOKEN, id: CREATED, name: body.name, scopes: body.scopes })
      return response({ id: CREATED, token: SECRET, note: 'Shown once' }, 201)
    }
    throw new Error('Unexpected security request: ' + method + ' ' + path)
  }))
  return { calls, users, sessions, tokens }
}
function panel(credential = CREDENTIAL) {
  const onUnauthorized = vi.fn()
  return { ...render(<SecurityPanel credential={credential} onUnauthorized={onUnauthorized} />), onUnauthorized }
}
async function ready() { await within(await screen.findByRole('list', { name: 'Konta instalacji' })).findByRole('heading', { name: USER.username, level: 3 }); await waitFor(() => expect(screen.getByRole('button', { name: 'Odśwież dostęp' })).toBeEnabled()) }
async function tokenForm() {
  const user = userEvent.setup()
  await user.click(screen.getByText('Utwórz token usługowy', { selector: 'summary' }))
  await user.type(screen.getByLabelText('Nazwa tokenu', { exact: true }), 'New worker')
  return user
}
afterEach(() => vi.unstubAllGlobals())

describe('owner Security Panel', () => {
  it('reads account/session/token metadata with header credentials and safe text', async () => {
    const { calls } = server()
    panel(); await ready()
    expect(calls.map(call => call.path).sort()).toEqual(['/api/v1/security/sessions', '/api/v1/security/tokens', '/api/v1/security/users'])
    for (const call of calls) expect(new Headers(call.options.headers).get('X-Jarvis-Key')).toBe(CREDENTIAL)
    expect(screen.getByRole('list', { name: 'Sesje kont' })).toHaveTextContent(SESSION.id)
    expect(screen.getByRole('list', { name: 'Tokeny usługowe' })).toHaveTextContent(TOKEN.name)
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
    expect(screen.queryByLabelText('Nowy token usługowy')).not.toBeInTheDocument()
  })

  it('clears the account password before the create request resolves and never echoes diagnostics', async () => {
    let complete: ((value: Response) => void) | undefined
    const { calls } = server((path, options) => path.endsWith('/users') && options.method === 'POST' ? new Promise<Response>(resolve => { complete = resolve }) : undefined)
    panel(); await ready()
    const user = userEvent.setup()
    await user.click(screen.getByText('Utwórz konto', { selector: 'summary' }))
    await user.type(screen.getByLabelText('Login nowego konta'), 'new.observer')
    await user.type(screen.getByLabelText('Hasło nowego konta'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Utwórz konto' }))
    await waitFor(() => expect(complete).toBeDefined())
    expect(screen.getByLabelText('Hasło nowego konta')).toHaveValue('')
    expect(JSON.parse(String(calls.find(call => call.options.method === 'POST')?.options.body))).toEqual({ username: 'new.observer', password: PASSWORD, role: 'observer' })
    await act(async () => { complete!(response({ detail: PASSWORD }, 422)) })
    expect(await screen.findByRole('alert')).not.toHaveTextContent(PASSWORD)
    expect(document.body.innerHTML).not.toContain(PASSWORD)
  })

  it('creates an account with a chosen role and refreshes the actual server list', async () => {
    const { users, calls } = server(); panel(); await ready()
    const user = userEvent.setup()
    await user.click(screen.getByText('Utwórz konto', { selector: 'summary' }))
    await user.type(screen.getByLabelText('Login nowego konta'), 'workshop.viewer')
    await user.type(screen.getByLabelText('Hasło nowego konta'), PASSWORD)
    await user.selectOptions(screen.getByLabelText('Rola nowego konta'), 'workshop_reader')
    await user.click(screen.getByRole('button', { name: 'Utwórz konto' }))
    await screen.findByText('Konto zostało utworzone.')
    expect(users[1]).toMatchObject({ username: 'workshop.viewer', role: 'workshop_reader' })
    expect(calls.filter(call => call.options.method === 'POST')).toHaveLength(1)
    expect(screen.getByLabelText('Hasło nowego konta')).toHaveValue('')
  })

  it('previews role/activity changes and sends the observed revision only after separate approval', async () => {
    const { calls, sessions } = server(); panel(); await ready()
    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Rola konta ' + USER.username), 'home_reader')
    await user.click(screen.getByLabelText('Konto aktywne ' + USER.username))
    await user.click(screen.getByRole('button', { name: 'Przejrzyj zmianę konta ' + USER.username }))
    expect(calls.some(call => call.options.method === 'PATCH')).toBe(false)
    expect(screen.getByText(/Każdy zapis odwoła wszystkie sesje tego konta/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zatwierdź zmianę konta' }))
    await screen.findByText('Konto zmienione. Wszystkie jego sesje zostały odwołane.')
    const patch = calls.find(call => call.options.method === 'PATCH')!
    expect(patch.path).toBe('/api/v1/security/users/' + USER.id)
    expect(JSON.parse(String(patch.options.body))).toEqual({ revision: 3, role: 'home_reader', enabled: false })
    expect(sessions[0].revoked).toBe(true)
  })

  it('reports a revision conflict without retrying or keeping the stale approval', async () => {
    const { calls } = server((_path, options) => options.method === 'PATCH' ? response({ detail: 'Internal account revision diagnostics' }, 409) : undefined)
    panel(); await ready(); const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Rola konta ' + USER.username), 'home_reader')
    await user.click(screen.getByRole('button', { name: 'Przejrzyj zmianę konta ' + USER.username }))
    await user.click(screen.getByRole('button', { name: 'Zatwierdź zmianę konta' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Odśwież dostęp')
    expect(calls.filter(call => call.options.method === 'PATCH')).toHaveLength(1)
    expect(screen.queryByRole('button', { name: 'Zatwierdź zmianę konta' })).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Internal account revision diagnostics')
  })

  it.each(['sessions', 'tokens'] as const)('requires confirmation before revoking %s and calls its own endpoint', async kind => {
    const { calls } = server(); panel(); await ready(); const user = userEvent.setup()
    const button = kind === 'sessions' ? 'Odwołaj sesję ' + USER.username + ' ' + SESSION.id : 'Odwołaj token ' + TOKEN.name
    const ident = kind === 'sessions' ? SESSION.id : TOKEN.id
    await user.click(screen.getByRole('button', { name: button }))
    expect(calls.some(call => call.options.method === 'DELETE')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Potwierdź odwołanie' }))
    await waitFor(() => expect(calls.some(call => call.path === '/api/v1/security/' + kind + '/' + ident && call.options.method === 'DELETE')).toBe(true))
    expect(calls.filter(call => call.options.method === 'DELETE')).toHaveLength(1)
    await waitFor(() => expect(screen.getByRole('button', { name: button })).toBeDisabled())
  })

  it('issues only selected token scopes and hours, exposes it once and clears it on refresh', async () => {
    const { calls } = server(); panel(); await ready(); const user = await tokenForm()
    const hours = screen.getByLabelText('Ważność tokenu w godzinach'); await user.clear(hours); await user.type(hours, '2')
    await user.click(screen.getByLabelText(/Odczyt domu/))
    await user.click(screen.getByRole('button', { name: 'Utwórz token' }))
    expect(await screen.findByLabelText('Nowy token usługowy')).toHaveTextContent(SECRET)
    const request = calls.find(call => call.path.endsWith('/tokens') && call.options.method === 'POST')!
    expect(JSON.parse(String(request.options.body))).toEqual({ name: 'New worker', scopes: ['status:read', 'home:read'], hours: 2 })
    expect(localStorage.length + sessionStorage.length).toBe(0)
    expect(window.location.href).not.toContain(SECRET)
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Odśwież dostęp' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Odśwież dostęp' }))
    await waitFor(() => expect(screen.queryByLabelText('Nowy token usługowy')).not.toBeInTheDocument())
    expect(document.body.innerHTML).not.toContain(SECRET)
    expect(calls.filter(call => call.options.method === 'POST')).toHaveLength(1)
  })

  it('hides the issued secret explicitly and does not restore it from metadata', async () => {
    server(); panel(); await ready(); const user = await tokenForm()
    await user.click(screen.getByRole('button', { name: 'Utwórz token' }))
    await screen.findByLabelText('Nowy token usługowy')
    await user.click(screen.getByRole('button', { name: 'Ukryj token' }))
    expect(document.body.innerHTML).not.toContain(SECRET)
    expect(screen.queryByLabelText('Nowy token usługowy')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Odśwież dostęp' }))
    await ready(); expect(document.body.innerHTML).not.toContain(SECRET)
  })

  it('clears users, forms and the one-time secret on 401', async () => {
    let expired = false
    server(() => expired ? response({ detail: SECRET }, 401) : undefined)
    const { onUnauthorized } = panel(); await ready(); const user = await tokenForm()
    await user.click(screen.getByRole('button', { name: 'Utwórz token' }))
    await screen.findByLabelText('Nowy token usługowy')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Odśwież dostęp' })).toBeEnabled()); expired = true
    await user.click(screen.getByRole('button', { name: 'Odśwież dostęp' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
    expect(document.body.innerHTML).not.toContain(SECRET)
    expect(screen.queryByRole('list', { name: 'Konta instalacji' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Login nowego konta')).not.toBeInTheDocument()
  })

  it('aborts an old pending token creation and ignores its secret after identity changes', async () => {
    let complete: ((value: Response) => void) | undefined, signal: AbortSignal | undefined
    server((path, options) => path.endsWith('/tokens') && options.method === 'POST' ? new Promise<Response>(resolve => { complete = resolve; signal = options.signal as AbortSignal }) : undefined)
    const { rerender, onUnauthorized } = panel(); await ready(); const user = await tokenForm()
    await user.click(screen.getByRole('button', { name: 'Utwórz token' }))
    await waitFor(() => expect(complete).toBeDefined())
    rerender(<SecurityPanel credential="new-synthetic-identity" onUnauthorized={onUnauthorized} />)
    await ready(); expect(signal?.aborted).toBe(true)
    await act(async () => { complete!(response({ id: CREATED, token: SECRET }, 201)) })
    expect(document.body.innerHTML).not.toContain(SECRET)
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('renders account and token names as plain text', async () => {
    const injection = '<img src=x onerror="window.compromised=true">'
    server((path, options) => options.method === 'GET' && path.endsWith('/tokens') ? response([{ ...TOKEN, name: injection }]) : undefined)
    const { container } = panel(); await ready()
    expect(within(screen.getByRole('list', { name: 'Tokeny usługowe' })).getByRole('heading', { name: injection })).toBeInTheDocument()
    expect(container.querySelector('img,script')).toBeNull()
  })
})
