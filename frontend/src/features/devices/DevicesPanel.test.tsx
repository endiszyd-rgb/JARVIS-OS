import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DevicesPanel } from './DevicesPanel'

const KEY = 'synthetic-device-owner-key'
const DATA = { home_readonly_enabled: true, twilio_webhook_enabled: false, physical_controls: false, whatsapp_send: false, whatsapp_calling: false }
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => vi.unstubAllGlobals())
describe('Device capabilities reflect local metadata only', () => {
  it('reads configuration explicitly and does not probe devices or expose physical controls', async () => {
    const fetch = vi.fn(async (_input: RequestInfo | URL, _options: RequestInit = {}) => json(DATA))
    vi.stubGlobal('fetch', fetch)
    render(<DevicesPanel credential={KEY} onUnauthorized={vi.fn()} />)
    expect(fetch).not.toHaveBeenCalled()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Odczytaj konfigurację' }))
    await screen.findByText('Włączony w konfiguracji')
    expect(screen.getAllByText('Niedostępne')).toHaveLength(2)
    expect(screen.getByText('Niedostępna')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/integrations')
    expect(new Headers(fetch.mock.calls[0]?.[1]?.headers).get('X-Jarvis-Key')).toBe(KEY)
    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Poprzedni panel i laboratoria' })).toHaveAttribute('href', '/')
    expect(document.body.innerHTML).not.toContain(KEY)
  })
  it('rejects malformed capability flags rather than displaying support for hardware', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ ...DATA, physical_controls: true })))
    render(<DevicesPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Odczytaj konfigurację' }))
    await screen.findByRole('alert')
    expect(screen.queryByText('Włączony w konfiguracji')).not.toBeInTheDocument()
  })
  it('clears configuration on session expiry without printing response diagnostics', async () => {
    let expired = false
    vi.stubGlobal('fetch', vi.fn(async () => expired ? json({ detail: 'Private server config' }, 401) : json(DATA)))
    const unauthorized = vi.fn(), user = userEvent.setup()
    render(<DevicesPanel credential={KEY} onUnauthorized={unauthorized} />)
    await user.click(screen.getByRole('button', { name: 'Odczytaj konfigurację' }))
    await screen.findByText('Włączony w konfiguracji')
    expired = true
    await user.click(screen.getByRole('button', { name: 'Odczytaj konfigurację' }))
    await waitFor(() => expect(unauthorized).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('Włączony w konfiguracji')).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Private server config')
  })
  it('aborts its read on unmount and ignores late configuration', async () => {
    let finish: ((result: Response) => void) | undefined, signal: AbortSignal | null | undefined
    vi.stubGlobal('fetch', vi.fn(async (_path: string, options: RequestInit = {}) => { signal = options.signal; return await new Promise<Response>(resolve => { finish = resolve }) }))
    const view = render(<DevicesPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Odczytaj konfigurację' }))
    await waitFor(() => expect(finish).toBeDefined())
    view.unmount()
    expect(signal?.aborted).toBe(true)
    await act(async () => { finish!(json(DATA)) })
    expect(document.body.textContent).not.toContain('Włączony w konfiguracji')
  })
})
