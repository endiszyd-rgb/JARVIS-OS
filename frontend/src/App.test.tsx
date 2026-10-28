import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const KEY = 'synthetic-bootstrap-owner-key-for-component-tests'
const PASSWORD = 'Synthetic-account-password-for-component-tests'
const TOKEN = 'synthetic-session-token-never-render-or-persist'
const IDENTITY = { id: 'owner-key', kind: 'owner_key', role: 'owner', scopes: ['*'], username: null, expires_at: null }
const SESSION = { id: '6a96c56b-2fd6-4ef2-8945-66b392b66c36', kind: 'session', role: 'observer', scopes: ['status:read'], username: 'observer.demo', expires_at: 2000000000 }
const STATUS = {
  mode: 'demo_with_optional_readonly', settings: { name: 'Andreas', tone: 'casual', model: 'demo' },
  counts: { plugins: 6, memory: 7, audit: 25, proposals: 3, automations: 2, notifications: 4 },
  live_devices: false, models: ['demo', 'ollama'], autologika_audit: '681f7f5',
}
const READY = { status: 'ready', checks: { owner_key: true, database: true }, optional_integrations_probed: false }
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Promise<Response> | Response | undefined

function server(handler?: Handler) {
  const calls: Call[] = []
  const fetcher = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input)
    calls.push({ path, options })
    const custom = handler?.(path, options)
    if (custom !== undefined) return await custom
    if (path === '/api/v1/auth/login') return response({ token: TOKEN, user: { id: SESSION.id } })
    if (path === '/api/v1/auth/me') {
      return response(new Headers(options.headers).get('X-Jarvis-Key') === TOKEN ? SESSION : IDENTITY)
    }
    if (path === '/api/v1/auth/logout') return response({ revoked: 'synthetic-session-id' })
    if (path === '/api/v1/status') return response(STATUS)
    if (path === '/health') return response({ status: 'ok', version: '0.8.9' })
    if (path === '/ready') return response(READY)
    throw new Error('Unexpected test request: ' + path)
  })
  vi.stubGlobal('fetch', fetcher)
  return calls
}

async function keyLogin() {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Klucz właściciela' }))
  await user.type(screen.getByLabelText('Klucz dostępu', { exact: true }), KEY)
  await user.click(screen.getByRole('button', { name: 'Połącz kluczem' }))
  await screen.findByRole('heading', { name: 'Pulpit', level: 1 })
  await screen.findByRole('article', { name: 'Pamięć' })
  return user
}

async function accountLogin() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Login', { exact: true }), 'observer.demo')
  await user.type(screen.getByLabelText('Hasło', { exact: true }), PASSWORD)
  await user.click(screen.getByRole('button', { name: 'Zaloguj się' }))
  await screen.findByRole('article', { name: 'Pamięć' })
  return user
}

beforeEach(() => {
  window.history.replaceState({}, '', '/control/')
  localStorage.clear()
  sessionStorage.clear()
})
afterEach(() => vi.unstubAllGlobals())

describe('Control Center access and actual server state', () => {
  it('uses a bootstrap key only in headers, renders real counts and keeps System navigation usable', async () => {
    const calls = server()
    render(<App />)
    const user = await keyLogin()
    expect(within(screen.getByRole('article', { name: 'Pamięć' })).getByText('7')).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Propozycje' })).getByText('3')).toBeInTheDocument()
    expect(calls.find(call => call.path === '/api/v1/status')?.options.headers).toMatchObject({ 'X-Jarvis-Key': KEY })
    for (const call of calls.filter(item => ['/health', '/ready'].includes(item.path))) {
      expect(new Headers(call.options.headers).has('X-Jarvis-Key')).toBe(false)
    }
    expect(document.body.innerHTML).not.toContain(KEY)
    expect(localStorage.length + sessionStorage.length).toBe(0)
    expect(window.location.href).not.toContain(KEY)
    await user.click(screen.getByRole('link', { name: 'System' }))
    await screen.findByRole('heading', { name: 'System', level: 1 })
    expect(screen.getAllByText('Właściciel').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.8.9').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link').some(link => link.getAttribute('href') === '/')).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Wyloguj' }))
    await screen.findByRole('heading', { name: 'Połącz się z JARVIS OS' })
    expect(calls.some(call => call.path === '/api/v1/auth/logout')).toBe(false)
    expect(screen.queryByRole('article', { name: 'Pamięć' })).not.toBeInTheDocument()
  })

  it('logs an account out on the server and removes its private snapshot and credentials', async () => {
    const calls = server()
    render(<App />)
    const user = await accountLogin()
    const login = calls.find(call => call.path === '/api/v1/auth/login')!
    expect(login.options.method).toBe('POST')
    expect(JSON.parse(String(login.options.body))).toEqual({ username: 'observer.demo', password: PASSWORD })
    expect(new Headers(login.options.headers).has('X-Jarvis-Key')).toBe(false)
    expect(document.body.innerHTML).not.toContain(TOKEN)
    expect(document.body.innerHTML).not.toContain(PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Wyloguj' }))
    await screen.findByRole('heading', { name: 'Połącz się z JARVIS OS' })
    const logout = calls.find(call => call.path === '/api/v1/auth/logout')!
    expect(logout.options.method).toBe('POST')
    expect(new Headers(logout.options.headers).get('X-Jarvis-Key')).toBe(TOKEN)
    expect(localStorage.length + sessionStorage.length).toBe(0)
    expect(screen.queryByRole('article', { name: 'Pamięć' })).not.toBeInTheDocument()
  })

  it('clears rejected passwords and never echoes server bodies or accepts a service identity as UI login', async () => {
    let rejectPassword = true
    server(path => {
      if (path === '/api/v1/auth/login' && rejectPassword) return response({ detail: PASSWORD }, 401)
      if (path === '/api/v1/auth/me') return response({ ...SESSION, kind: 'service', role: 'service' })
    })
    render(<App />)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Login', { exact: true }), 'observer.demo')
    await user.type(screen.getByLabelText('Hasło', { exact: true }), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Zaloguj się' }))
    await screen.findByRole('alert')
    expect(screen.getByLabelText('Hasło', { exact: true })).toHaveValue('')
    expect(document.body.innerHTML).not.toContain(PASSWORD)
    rejectPassword = false
    await user.type(screen.getByLabelText('Hasło', { exact: true }), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Zaloguj się' }))
    await waitFor(() => expect(screen.getByLabelText('Hasło', { exact: true })).toHaveValue(''))
    expect(screen.queryByRole('heading', { name: 'Pulpit', level: 1 })).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(TOKEN)
  })

  it('keeps a dated snapshot after a failed refresh and lets the user retry', async () => {
    let requests = 0
    server(path => {
      if (path !== '/api/v1/status') return
      requests += 1
      if (requests === 2) return response({ detail: 'Internal diagnostics must not be shown' }, 500)
      return response({ ...STATUS, counts: { ...STATUS.counts, memory: requests === 1 ? 7 : 9 } })
    })
    render(<App />)
    const user = await keyLogin()
    await user.click(screen.getByRole('button', { name: 'Odśwież dane' }))
    await screen.findByRole('alert')
    expect(within(screen.getByRole('article', { name: 'Pamięć' })).getByText('7')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Internal diagnostics')
    await user.click(screen.getByRole('button', { name: 'Odśwież dane' }))
    await waitFor(() => expect(within(screen.getByRole('article', { name: 'Pamięć' })).getByText('9')).toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('clears authentication and private counters when a refresh reports an expired session', async () => {
    let expired = false
    const calls = server(path => path === '/api/v1/status' && expired ? response({}, 401) : undefined)
    render(<App />)
    const user = await accountLogin()
    expired = true
    await user.click(screen.getByRole('button', { name: 'Odśwież dane' }))
    await screen.findByRole('heading', { name: 'Połącz się z JARVIS OS' })
    expect(screen.queryByRole('article', { name: 'Pamięć' })).not.toBeInTheDocument()
    expect(calls.filter(call => call.path === '/api/v1/status')).toHaveLength(2)
    expect(document.body.innerHTML).not.toContain(TOKEN)
  })

  it('does not restore private data when an old in-flight response arrives after logout', async () => {
    let resolveStatus: ((value: Response) => void) | undefined
    let requests = 0
    server(path => {
      if (path === '/api/v1/status' && ++requests === 2) return new Promise<Response>(resolve => { resolveStatus = resolve })
    })
    render(<App />)
    const user = await accountLogin()
    await user.click(screen.getByRole('button', { name: 'Odśwież dane' }))
    await waitFor(() => expect(resolveStatus).toBeDefined())
    await user.click(screen.getByRole('button', { name: 'Wyloguj' }))
    await screen.findByRole('heading', { name: 'Połącz się z JARVIS OS' })
    await act(async () => { resolveStatus!(response({ ...STATUS, counts: { ...STATUS.counts, memory: 99999 } })) })
    expect(screen.queryByRole('article', { name: 'Pamięć' })).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('99999')
    expect(document.body.innerHTML).not.toContain(TOKEN)
  })

  it('supports keyboard navigation and closing the menu with Escape', async () => {
    server()
    render(<App />)
    const user = await keyLogin()
    const menu = screen.getByRole('button', { name: 'Otwórz menu' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    await user.click(menu)
    expect(screen.getByRole('button', { name: 'Zamknij menu' })).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: 'Otwórz menu' })).toHaveAttribute('aria-expanded', 'false')
    const link = screen.getByRole('link', { name: 'System' })
    link.focus()
    await user.keyboard('{Enter}')
    await screen.findByRole('heading', { name: 'System', level: 1 })
    expect(link).toHaveAttribute('aria-current', 'page')
  })

  it('moves focus out of the closed mobile navigation when a view is selected', async () => {
    server()
    render(<App />)
    const user = await keyLogin()
    await user.click(screen.getByRole('button', { name: 'Otwórz menu' }))
    await user.click(screen.getByRole('link', { name: 'System' }))
    await screen.findByRole('heading', { name: 'System', level: 1 })
    expect(screen.getByRole('button', { name: 'Otwórz menu' })).toHaveAttribute('aria-expanded', 'false')
    expect(document.activeElement).toBe(screen.getByRole('main'))
  })

  it('moves focus to the current System content without changing the selected view', async () => {
    server()
    render(<App />)
    const user = await keyLogin()
    await user.click(screen.getByRole('link', { name: 'System' }))
    await screen.findByRole('heading', { name: 'System', level: 1 })
    await user.click(screen.getByRole('link', { name: 'Przejdź do treści' }))
    expect(screen.getByRole('heading', { name: 'System', level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'System' })).toHaveAttribute('aria-current', 'page')
    expect(document.activeElement).toBe(screen.getByRole('main'))
  })

  it('shows a failing Core readiness check without presenting optional services as verified', async () => {
    server(path => path === '/ready' ? response({ ...READY, status: 'not_ready', checks: { owner_key: true, database: false } }, 503) : undefined)
    render(<App />)
    await keyLogin()
    expect(screen.getByRole('article', { name: 'Pamięć' })).toBeInTheDocument()
    expect(screen.queryByText('Core jest gotowy.', { exact: true })).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('link', { name: 'System' }))
    await screen.findByRole('heading', { name: 'System', level: 1 })
    expect(screen.getAllByText(/wymaga uwagi|niedostępna|niegotow|brak gotowości/i).length).toBeGreaterThan(0)
    expect(document.body.textContent).not.toMatch(/Ollama online|Modele sprawdzone|Urządzenia połączone/)
  })
})

it('does not fetch owner data when an observer opens private routes directly', async () => {
  const calls = server()
  window.history.replaceState(null, '', '#/plugins')
  render(<App />)
  await accountLogin()
  expect(window.location.hash).toBe('#/dashboard')
  for (const view of ['chat', 'settings', 'activity', 'plugins', 'workshop', 'home', 'devices', 'automations', 'memory', 'telephony', 'notifications', 'security', 'logs', 'changes']) {
    await act(async () => {
      window.location.hash = '#/' + view
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    await screen.findByRole('heading', { name: 'Dostęp właściciela' })
  }
  const allowed = new Set(['/api/v1/auth/login', '/api/v1/auth/me', '/api/v1/status', '/health', '/ready'])
  expect(calls.every(call => allowed.has(call.path))).toBe(true)
  expect(screen.queryByRole('link', { name: 'Rozmowa' })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Ustawienia' })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Historia działań' })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Pluginy' })).not.toBeInTheDocument()
})

it.each([
  { role: 'home_reader', label: 'Dom', denied: 'AutoLogika', scope: 'home:read' },
  { role: 'workshop_reader', label: 'AutoLogika', denied: 'Dom', scope: 'workshop:read' },
])('limits $role navigation to its domain without fetching owner data', async ({ role, label, denied, scope }) => {
  const calls = server(path => path === '/api/v1/auth/me' ? response({ ...SESSION, role, scopes: ['status:read', scope] }) : undefined)
  render(<App />)
  await accountLogin()
  expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: denied })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Bezpieczeństwo' })).not.toBeInTheDocument()
  await act(async () => {
    window.location.hash = '#/security'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
  await screen.findByRole('heading', { name: 'Dostęp właściciela' })
  const allowed = new Set(['/api/v1/auth/login', '/api/v1/auth/me', '/api/v1/status', '/health', '/ready'])
  expect(calls.every(call => allowed.has(call.path))).toBe(true)
})
