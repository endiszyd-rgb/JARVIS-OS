import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPanel } from './ChatPanel'

const KEY = 'synthetic-chat-owner-key-not-rendered'
const SESSION_ID = '3f8bc2aa-4d60-4cf9-a5a9-3cc94e3a8170'
const NEW_ID = '09acf626-5b0a-4b85-a798-f72f53e144f9'
const TURN_ID = '78c7cbec-3b1a-47ed-a23c-ea2c6a097a4a'
const SESSION = { id: SESSION_ID, title: 'Pierwsza rozmowa', provider: 'demo', model_name: 'demo', created: 1800000000, updated: 1800000010, active_turn: null, active_since: null, input_mode: 'text', message_count: 1 }
const MODELS = { default_provider: 'demo', default_ollama_model: 'qwen:synthetic', source: 'owner_configuration', probes_network: false,
  models: [{ provider: 'demo', name: 'demo', cloud: false }, { provider: 'ollama', name: 'qwen:synthetic', cloud: false }] }
const MESSAGE = { id: 1, role: 'assistant', content: 'Wcześniejsza odpowiedź', created: 1800000001, state: 'completed', turn_id: TURN_ID }
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined

function server(handler?: Handler, initial = SESSION) {
  const calls: Call[] = []
  const sessions = [{ ...initial }]
  const messages: Record<string, typeof MESSAGE[]> = { [initial.id]: [{ ...MESSAGE }] }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input)
    calls.push({ path, options })
    const custom = handler?.(path, options)
    if (custom !== undefined) return await custom
    const url = new URL(path, 'http://localhost')
    const method = options.method || 'GET'
    if (url.pathname === '/api/v1/models') return json(MODELS)
    if (url.pathname === '/api/v1/chat/sessions' && method === 'GET') return json(sessions)
    if (url.pathname === '/api/v1/chat/sessions' && method === 'POST') {
      const body = JSON.parse(String(options.body))
      const created = { ...SESSION, id: NEW_ID, title: body.title, provider: body.model, model_name: body.model_name, message_count: 0 }
      sessions.unshift(created)
      messages[NEW_ID] = []
      return json(created, 201)
    }
    const session = sessions.find(item => url.pathname.startsWith('/api/v1/chat/sessions/' + item.id))
    if (session && url.pathname.endsWith('/messages')) return json(messages[session.id] || [])
    if (session) return json(session)
    if (url.pathname === '/api/v1/chat' && method === 'POST') {
      const body = JSON.parse(String(options.body))
      messages[body.session_id] = [...(messages[body.session_id] || []), { ...MESSAGE, id: 2, role: 'user', content: body.message }, { ...MESSAGE, id: 3, content: 'Odpowiedź zapisana na serwerze' }]
      return json({ reply: 'Odpowiedź zapisana na serwerze', model: body.model, ai_generated: body.model !== 'demo', session_id: body.session_id, turn_id: TURN_ID, context_messages: 1, memory_capture: {} })
    }
    throw new Error('Unexpected chat request: ' + method + ' ' + path)
  }))
  return calls
}

afterEach(() => vi.unstubAllGlobals())

async function ready() {
  await screen.findByText('Wcześniejsza odpowiedź')
  return userEvent.setup()
}
const sendCalls = (calls: Call[]) => calls.filter(call => new URL(call.path, 'http://localhost').pathname === '/api/v1/chat' && call.options.method === 'POST')

describe('Owner conversation panel', () => {
  it('loads saved history, sends the explicitly selected model and re-reads the persisted answer', async () => {
    const calls = server()
    render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
    const user = await ready()
    await user.selectOptions(screen.getByLabelText('Model rozmowy'), screen.getByRole('option', { name: /Ollama.*qwen:synthetic/ }))
    await user.click(screen.getByLabelText('Nie zapisuj w pamięci'))
    await user.type(screen.getByLabelText('Wiadomość'), 'Wiadomość z panelu')
    await user.click(screen.getByRole('button', { name: 'Wyślij wiadomość' }))
    await screen.findByText('Odpowiedź zapisana na serwerze')
    const posts = sendCalls(calls)
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0].options.body))).toMatchObject({ message: 'Wiadomość z panelu', session_id: SESSION_ID, model: 'ollama', model_name: 'qwen:synthetic', input_mode: 'text', do_not_remember: true })
    expect(new Headers(posts[0].options.headers).get('X-Jarvis-Key')).toBe(KEY)
    expect(calls.filter(call => call.path.includes('/messages')).length).toBeGreaterThan(1)
    expect(document.body.innerHTML).not.toContain(KEY)
    expect(screen.getByLabelText('Wiadomość')).toHaveValue('')
  })

  it('creates a new persistent text session with the chosen title and configured model', async () => {
    const calls = server()
    render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
    const user = await ready()
    await user.type(screen.getByLabelText('Tytuł nowej rozmowy'), 'Nowy projekt')
    await user.selectOptions(screen.getByLabelText('Model rozmowy'), screen.getByRole('option', { name: /Ollama.*qwen:synthetic/ }))
    await user.click(screen.getByRole('button', { name: 'Nowa rozmowa' }))
    await waitFor(() => expect(screen.getByLabelText('Tytuł nowej rozmowy')).toHaveValue(''))
    const post = calls.find(call => call.path === '/api/v1/chat/sessions' && call.options.method === 'POST')!
    expect(JSON.parse(String(post.options.body))).toMatchObject({ title: 'Nowy projekt', model: 'ollama', model_name: 'qwen:synthetic' })
    expect(calls.some(call => call.path.includes('/' + NEW_ID + '/messages'))).toBe(true)
    expect(sendCalls(calls)).toHaveLength(0)
  })

  it('renders conversation content as plain text rather than executable HTML', async () => {
    const unsafe = '<img src=x onerror="globalThis.stolen=true">'
    server(path => path.includes('/messages') ? json([{ ...MESSAGE, content: unsafe }]) : undefined)
    render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText(unsafe)
    expect(document.querySelector('img')).toBeNull()
    expect(document.querySelector('[onerror]')).toBeNull()
  })

  it('opens voice history read-only and never converts it into a text turn', async () => {
    const calls = server(undefined, { ...SESSION, input_mode: 'voice' })
    render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await ready()
    expect(screen.getByLabelText('Wiadomość')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Wyślij wiadomość' })).toBeDisabled()
    expect(screen.getAllByText(/głosow|tylko.*odczyt/i).length).toBeGreaterThan(0)
    expect(sendCalls(calls)).toHaveLength(0)
  })

  it.each([409, 502, 504])('handles HTTP%s without leaking diagnostics or silently retrying the POST', async status => {
    const calls = server(path => path === '/api/v1/chat' ? json({ detail: 'Synthetic private provider diagnostics' }, status) : undefined)
    render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
    const user = await ready()
    await user.type(screen.getByLabelText('Wiadomość'), 'Jedna próba')
    await user.click(screen.getByRole('button', { name: 'Wyślij wiadomość' }))
    await screen.findByRole('alert')
    expect(document.body.textContent).not.toContain('Synthetic private provider diagnostics')
    expect(sendCalls(calls)).toHaveLength(1)
  })

  it('reports an expired identity to the parent rather than exposing private chat data', async () => {
    server(path => path === '/api/v1/models' ? json({ detail: 'Hidden owner model catalog' }, 401) : undefined)
    const unauthorized = vi.fn()
    render(<ChatPanel credential={KEY} onUnauthorized={unauthorized} />)
    await waitFor(() => expect(unauthorized).toHaveBeenCalled())
    expect(screen.queryByText('Wcześniejsza odpowiedź')).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Hidden owner model catalog')
  })

  it('stops waiting, then reconciles server state before enabling another turn', async () => {
    let active = false
    const calls = server((path, options) => {
      if (path === '/api/v1/chat') {
        active = true
        return new Promise<Response>((_resolve, reject) => options.signal?.addEventListener('abort', () => reject(new DOMException('Synthetic wait stopped', 'AbortError')), { once: true }))
      }
      if (new URL(path, 'http://localhost').pathname === '/api/v1/chat/sessions/' + SESSION_ID) {
        return json({ ...SESSION, active_turn: active ? TURN_ID : null, active_since: active ? 1800000020 : null })
      }
    })
    render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
    const user = await ready()
    await user.type(screen.getByLabelText('Wiadomość'), 'Dłuższa odpowiedź')
    await user.click(screen.getByRole('button', { name: 'Wyślij wiadomość' }))
    await screen.findByRole('button', { name: 'Przestań czekać' })
    await user.click(screen.getByRole('button', { name: 'Przestań czekać' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Wyślij wiadomość' })).toBeDisabled())
    const readsBeforeSelection = calls.filter(call => call.path.includes('/messages')).length
    await user.click(screen.getByRole('button', { name: SESSION.title }))
    await waitFor(() => expect(calls.filter(call => call.path.includes('/messages')).length).toBeGreaterThan(readsBeforeSelection))
    await screen.findByText(/Serwer nadal przetwarza/)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Wyślij wiadomość' })).toBeDisabled())
    active = false
    await user.click(screen.getByRole('button', { name: 'Odśwież rozmowę' }))
    await waitFor(() => expect(screen.getByLabelText('Wiadomość')).toBeEnabled())
    expect(sendCalls(calls)).toHaveLength(1)
    expect(document.body.textContent).not.toMatch(/generowanie zostało zatrzymane|zatrzymano generowanie/i)
  })

  it('aborts reads on unmount and does not display a late private response', async () => {
    let complete: ((response: Response) => void) | undefined
    let signal: AbortSignal | null | undefined
    server((path, options) => {
      if (path.includes('/messages')) {
        signal = options.signal
        return new Promise<Response>(resolve => { complete = resolve })
      }
    })
    const unauthorized = vi.fn()
    const rendered = render(<ChatPanel credential={KEY} onUnauthorized={unauthorized} />)
    await waitFor(() => expect(complete).toBeDefined())
    rendered.unmount()
    expect(signal?.aborted).toBe(true)
    await act(async () => { complete!(json([{ ...MESSAGE, content: 'Private response after logout' }])) })
    expect(document.body.textContent).not.toContain('Private response after logout')
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('clears the previous identity and draft immediately when credentials change', async () => {
    const nextCredential = 'synthetic-next-owner-key'
    let refreshing = false
    let lateRead: ((response: Response) => void) | undefined
    let oldSignal: AbortSignal | null | undefined
    server((path, options) => {
      if (new Headers(options.headers).get('X-Jarvis-Key') === nextCredential && path.includes('/chat/sessions')) {
        return new Promise<Response>(() => {})
      }
      if (refreshing && path.includes('/messages')) {
        oldSignal = options.signal
        return new Promise<Response>(resolve => { lateRead = resolve })
      }
    })
    const unauthorized = vi.fn()
    const rendered = render(<ChatPanel credential={KEY} onUnauthorized={unauthorized} />)
    const user = await ready()
    await user.type(screen.getByLabelText('Wiadomość'), 'Prywatny szkic poprzedniej sesji')
    refreshing = true
    await user.click(screen.getByRole('button', { name: 'Odśwież rozmowę' }))
    await waitFor(() => expect(lateRead).toBeDefined())
    rendered.rerender(<ChatPanel credential={nextCredential} onUnauthorized={unauthorized} />)
    expect(screen.getByLabelText('Wiadomość')).toHaveValue('')
    expect(screen.queryByText(SESSION.title)).not.toBeInTheDocument()
    expect(screen.queryByText('Wcześniejsza odpowiedź')).not.toBeInTheDocument()
    expect(oldSignal?.aborted).toBe(true)
    await act(async () => { lateRead!(json({ detail: 'Old identity expired' }, 401)) })
    expect(unauthorized).not.toHaveBeenCalled()
    expect(document.body.textContent).not.toContain('Prywatny szkic poprzedniej sesji')
  })
})

it('labels OpenAI as cloud, warns about transmitted context, and sends the selected provider', async () => {
  const cloud = { provider: 'openai', name: 'gpt-5.4-mini-2026-03-17', cloud: true }
  const calls = server(path => path === '/api/v1/models' ? json({ ...MODELS, models: [...MODELS.models, cloud] }) : undefined)
  render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
  const user = await ready()
  await user.selectOptions(screen.getByLabelText('Model rozmowy'), JSON.stringify({ provider: cloud.provider, name: cloud.name }))
  expect(screen.getByText(/Wiadomości i historia tej sesji trafią do chmury/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('Wiadomość', { exact: true }), 'Synthetic cloud input')
  await user.click(screen.getByRole('button', { name: 'Wyślij wiadomość' }))
  await waitFor(() => expect(sendCalls(calls)).toHaveLength(1))
  expect(JSON.parse(String(sendCalls(calls)[0].options.body))).toMatchObject({ model: 'openai', model_name: cloud.name })
})

it('uses the configured cloud default in a workspace without saved sessions', async () => {
  const cloud = { provider: 'openai', name: 'gpt-5.4-mini-2026-03-17', cloud: true }
  server(path => path === '/api/v1/models' ? json({ ...MODELS, default_provider: 'openai', models: [...MODELS.models, cloud] })
    : path.startsWith('/api/v1/chat/sessions?') ? json([]) : undefined)
  render(<ChatPanel credential={KEY} onUnauthorized={vi.fn()} />)
  await waitFor(() => expect(screen.getByLabelText('Model rozmowy')).toHaveValue(JSON.stringify({ provider: cloud.provider, name: cloud.name })))
})
