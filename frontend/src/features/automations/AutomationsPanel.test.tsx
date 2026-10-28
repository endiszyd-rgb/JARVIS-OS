import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AutomationsPanel } from './AutomationsPanel'

const ID = '30000000-0000-4000-8000-000000000001'
const CREDENTIAL = 'synthetic-private-automation-session'
const PAYLOAD = { title: 'Sprawdź części', interval_minutes: 30, message: 'Przejrzyj lokalną listę części' }
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
function server(handler?: Handler) {
  const calls: Call[] = [], rows: { id: string; payload: typeof PAYLOAD; next_run: number }[] = []
  let pending: typeof PAYLOAD | null = null
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input); calls.push({ path, options })
    const custom = handler?.(path, options); if (custom !== undefined) return await custom
    if (path === '/api/v1/automations') return response(rows)
    if (path === '/api/v1/proposals') { pending = JSON.parse(String(options.body)).payload; return response({ id: ID, kind: 'automation', payload: pending, status: 'pending' }, 201) }
    if (path === '/api/v1/proposals/' + ID + '/decide') {
      const approve = JSON.parse(String(options.body)).approve
      if (approve && pending) rows.push({ id: ID, payload: pending, next_run: 1800000000 })
      return response({ id: ID, status: approve ? 'applied' : 'rejected' })
    }
    if (path === '/api/v1/automations/tick') return response({ fired: [ID], external_request_sent: false })
    throw new Error('Unexpected automation request')
  }))
  return { calls, rows }
}
async function fillForm() {
  const user = userEvent.setup()
  await screen.findByText('Brak zapisanych przypomnień.')
  await user.type(screen.getByLabelText('Tytuł przypomnienia'), PAYLOAD.title)
  await user.clear(screen.getByLabelText('Co ile minut')); await user.type(screen.getByLabelText('Co ile minut'), '30')
  await user.type(screen.getByLabelText('Treść przypomnienia'), PAYLOAD.message)
  return user
}
afterEach(() => vi.unstubAllGlobals())

describe('Local automation proposals', () => {
  it('creates a full preview without applying it, then uses a separate approval request', async () => {
    const { calls, rows } = server()
    render(<AutomationsPanel credential={CREDENTIAL} onUnauthorized={vi.fn()} />)
    const user = await fillForm()
    await user.click(screen.getByRole('button', { name: 'Podgląd przypomnienia' }))
    await screen.findByRole('button', { name: 'Zatwierdź przypomnienie' })
    expect(rows).toHaveLength(0)
    expect(calls.some(call => call.path.endsWith('/decide'))).toBe(false)
    const proposed = calls.find(call => call.path === '/api/v1/proposals')!
    expect(JSON.parse(String(proposed.options.body))).toEqual({ kind: 'automation', payload: PAYLOAD })
    expect(new Headers(proposed.options.headers).get('X-Jarvis-Key')).toBe(CREDENTIAL)
    await user.click(screen.getByRole('button', { name: 'Zatwierdź przypomnienie' }))
    await screen.findByText('Przypomnienie zatwierdzone i zapisane.')
    await waitFor(() => expect(rows).toHaveLength(1))
    expect(JSON.parse(String(calls.find(call => call.path.endsWith('/decide'))!.options.body))).toEqual({ approve: true })
    expect(await screen.findByRole('heading', { name: PAYLOAD.title })).toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
  })

  it('rejects a preview without adding a schedule', async () => {
    const { calls, rows } = server()
    render(<AutomationsPanel credential={CREDENTIAL} onUnauthorized={vi.fn()} />)
    const user = await fillForm()
    await user.click(screen.getByRole('button', { name: 'Podgląd przypomnienia' }))
    await user.click(await screen.findByRole('button', { name: 'Odrzuć przypomnienie' }))
    await screen.findByText('Propozycja przypomnienia odrzucona. Nie utworzono automatyzacji.')
    expect(rows).toHaveLength(0)
    expect(JSON.parse(String(calls.find(call => call.path.endsWith('/decide'))!.options.body))).toEqual({ approve: false })
  })

  it('ticks only after a deliberate click and reports local notifications without external requests', async () => {
    const { calls } = server()
    render(<AutomationsPanel credential={CREDENTIAL} onUnauthorized={vi.fn()} />)
    await screen.findByText('Brak zapisanych przypomnień.')
    expect(calls.map(call => call.path)).toEqual(['/api/v1/automations'])
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Sprawdź terminy teraz' }))
    await screen.findByText('Lokalne powiadomienia utworzone: 1. Nie wysłano żądań zewnętrznych.')
    const tick = calls.find(call => call.path.endsWith('/tick'))!
    expect(tick.options.method).toBe('POST')
    expect(JSON.parse(String(tick.options.body))).toEqual({})
    expect(calls.filter(call => call.path.endsWith('/tick'))).toHaveLength(1)
    expect(calls.map(call => call.path)).not.toContain('/api/v1/notifications')
  })

  it('does not claim a local-only tick if the server contract says an external request was sent', async () => {
    const { calls } = server(path => path.endsWith('/tick') ? response({ fired: [], external_request_sent: true }) : undefined)
    render(<AutomationsPanel credential={CREDENTIAL} onUnauthorized={vi.fn()} />)
    await screen.findByText('Brak zapisanych przypomnień.')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Sprawdź terminy teraz' }))
    await screen.findByRole('alert')
    expect(screen.queryByText(/Lokalne powiadomienia utworzone:/)).not.toBeInTheDocument()
    expect(calls.filter(call => call.path.endsWith('/tick'))).toHaveLength(1)
  })

  it('clears the form and preview on a 401 decision without retrying', async () => {
    const { calls } = server(path => path.endsWith('/decide') ? response({ detail: 'hidden' }, 401) : undefined)
    const onUnauthorized = vi.fn()
    render(<AutomationsPanel credential={CREDENTIAL} onUnauthorized={onUnauthorized} />)
    const user = await fillForm()
    await user.click(screen.getByRole('button', { name: 'Podgląd przypomnienia' }))
    await user.click(await screen.findByRole('button', { name: 'Zatwierdź przypomnienie' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
    expect(screen.queryByLabelText('Tytuł przypomnienia')).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain(PAYLOAD.message)
    expect(calls.filter(call => call.path.endsWith('/decide'))).toHaveLength(1)
  })

  it('ignores an old identity reply after the credential changes', async () => {
    let release: ((value: Response) => void) | undefined, oldSignal: AbortSignal | undefined
    server((path, options) => {
      if (path === '/api/v1/automations' && new Headers(options.headers).get('X-Jarvis-Key') === 'old-session') {
        oldSignal = options.signal as AbortSignal
        return new Promise<Response>(resolve => { release = resolve })
      }
      return undefined
    })
    const onUnauthorized = vi.fn()
    const { rerender } = render(<AutomationsPanel credential="old-session" onUnauthorized={onUnauthorized} />)
    await waitFor(() => expect(release).toBeDefined())
    rerender(<AutomationsPanel credential="new-session" onUnauthorized={onUnauthorized} />)
    await screen.findByText('Brak zapisanych przypomnień.')
    expect(oldSignal?.aborted).toBe(true)
    await act(async () => { release!(response({ detail: 'private-late-data' }, 401)) })
    expect(onUnauthorized).not.toHaveBeenCalled()
    expect(document.body.textContent).not.toContain('private-late-data')
  })
})
