import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { NotificationsPanel } from './NotificationsPanel'

const ID = '40000000-0000-4000-8000-000000000001', CREDENTIAL = 'synthetic-private-notifications-session'
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => vi.unstubAllGlobals())

it('loads latest local notifications as plain text and filters only that list without requests', async () => {
  const unsafe = '<img src=x onerror=window.secret=true>'
  const fetcher = vi.fn(async () => response([{ id: ID, message: unsafe, created: 1800000000 }, { id: '40000000-0000-4000-8000-000000000002', message: 'Części gotowe', created: 1799999900 }]))
  vi.stubGlobal('fetch', fetcher)
  render(<NotificationsPanel credential={CREDENTIAL} onUnauthorized={vi.fn()} />)
  await screen.findByText(unsafe)
  expect(document.querySelector('img')).toBeNull()
  expect(document.body.innerHTML).not.toContain(CREDENTIAL)
  await userEvent.setup().type(screen.getByLabelText('Filtruj powiadomienia'), 'części')
  expect(screen.queryByText(unsafe)).not.toBeInTheDocument()
  expect(screen.getByText('Części gotowe')).toBeInTheDocument()
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('refreshes deliberately and preserves a labelled previous result on errors without diagnostics or retry', async () => {
  const diagnostic = 'secret-server-diagnostic'
  const fetcher = vi.fn().mockResolvedValueOnce(response([{ id: ID, message: 'Zapisane lokalnie', created: 1800000000 }])).mockResolvedValueOnce(response({ detail: diagnostic }, 502))
  vi.stubGlobal('fetch', fetcher)
  render(<NotificationsPanel credential={CREDENTIAL} onUnauthorized={vi.fn()} />)
  await screen.findByText('Zapisane lokalnie')
  await userEvent.setup().click(screen.getByRole('button', { name: 'Odśwież powiadomienia' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('poprzedni odczyt')
  expect(screen.getByText('Zapisane lokalnie')).toBeInTheDocument()
  expect(document.body.textContent).not.toContain(diagnostic)
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it('clears private rows and filter on 401', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response([{ id: ID, message: 'Prywatna wiadomość', created: 1800000000 }])).mockResolvedValueOnce(response({}, 401)))
  const onUnauthorized = vi.fn()
  render(<NotificationsPanel credential={CREDENTIAL} onUnauthorized={onUnauthorized} />)
  await screen.findByText('Prywatna wiadomość')
  await userEvent.setup().click(screen.getByRole('button', { name: 'Odśwież powiadomienia' }))
  await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
  expect(screen.queryByText('Prywatna wiadomość')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Filtruj powiadomienia')).not.toBeInTheDocument()
})

it('rejects more than 100 rows without pretending the endpoint supports a complete archive', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response(Array.from({ length: 101 }, () => ({ id: ID, message: 'Excess', created: 1800000000 })))))
  render(<NotificationsPanel credential={CREDENTIAL} onUnauthorized={vi.fn()} />)
  await screen.findByRole('alert')
  expect(screen.queryByText('Excess')).not.toBeInTheDocument()
})

it('aborts an old identity request and ignores late private rows after a credential change', async () => {
  let release: ((value: Response) => void) | undefined, oldSignal: AbortSignal | undefined
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, options: RequestInit = {}) => {
    if (new Headers(options.headers).get('X-Jarvis-Key') === 'old-session') {
      oldSignal = options.signal as AbortSignal
      return await new Promise<Response>(resolve => { release = resolve })
    }
    return response([])
  }))
  const onUnauthorized = vi.fn()
  const { rerender } = render(<NotificationsPanel credential="old-session" onUnauthorized={onUnauthorized} />)
  await waitFor(() => expect(release).toBeDefined())
  rerender(<NotificationsPanel credential="new-session" onUnauthorized={onUnauthorized} />)
  await screen.findByText('Brak zapisanych powiadomień.')
  expect(oldSignal?.aborted).toBe(true)
  await act(async () => { release!(response([{ id: ID, message: 'Old private reply', created: 1800000000 }])) })
  expect(screen.queryByText('Old private reply')).not.toBeInTheDocument()
  expect(onUnauthorized).not.toHaveBeenCalled()
})
