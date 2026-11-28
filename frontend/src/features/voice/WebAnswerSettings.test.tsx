import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { WebAnswerSettings } from './WebAnswerSettings'
import { SiriKeys } from '../account/SiriKeys'

const TOKEN = 'owner-token-at-least-twenty-four-chars'
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => vi.unstubAllGlobals())

describe('WebAnswerSettings', () => {
  it('saves the Claude key without showing it again and asks a test question with sources', async () => {
    const saved: Record<string, unknown>[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/config/web-answer' && options.method === 'PUT') {
        const body = JSON.parse(String(options.body)); saved.push(body.config)
        return json({ config: { ...body.config, api_key: '••••••••', api_key_set: true }, revision: 1 })
      }
      if (path === '/api/v1/config/web-answer') return json({ config: { enabled: false, api_key: '', api_key_set: false, model: 'claude-sonnet-5-5', max_searches: 3 }, revision: 0 })
      if (path === '/api/v1/voice/ask') {
        expect(JSON.parse(String(options.body))).toEqual({ text: 'moment kół Golf 7' })
        return json({ speech: 'Śruby kół Golfa 7 dokręca się momentem 120 Nm według vwgolf.pl.', kind: 'answer', sources: [{ title: 'vwgolf.pl', url: 'https://vwgolf.pl/kola' }] })
      }
      return json({ detail: 'unexpected' }, 404)
    }))
    const user = userEvent.setup()
    render(<WebAnswerSettings credential={TOKEN} onUnauthorized={vi.fn()} />)
    await user.click(await screen.findByLabelText('Odpowiadaj na pytania z internetu'))
    await user.type(screen.getByLabelText('Klucz Claude API'), 'sk-ant-api03-secret')
    await user.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(saved[0]).toEqual({ enabled: true, api_key: 'sk-ant-api03-secret', model: 'claude-sonnet-5-5', max_searches: 3 })
    const key = await screen.findByLabelText('Klucz Claude API')
    await waitFor(() => expect(key).toHaveValue(''))
    expect(key).toHaveAttribute('placeholder', expect.stringContaining('zapisany ✓'))
    expect(document.body.innerHTML).not.toContain('sk-ant-api03-secret')
    await user.type(screen.getByLabelText('Pytanie testowe'), 'moment kół Golf 7')
    await user.click(screen.getByRole('button', { name: 'Zapytaj' }))
    expect(await screen.findByText(/120 Nm według vwgolf.pl/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'vwgolf.pl' })).toHaveAttribute('href', 'https://vwgolf.pl/kola')
  })
})

describe('SiriKeys', () => {
  it('asks for 2FA first', () => {
    render(<SiriKeys credential={TOKEN} onUnauthorized={vi.fn()} mfaEnabled={false} />)
    expect(screen.getByText('Najpierw włącz 2FA powyżej.')).toBeInTheDocument()
  })

  it('adds a phone, shows its key and the shortcut steps once, and revokes it', async () => {
    let keys: { id: string; name: string; created: number; last_used: number | null }[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/auth/device-keys' && options.method === 'POST') {
        expect(JSON.parse(String(options.body))).toEqual({ name: 'iPhone Endi' })
        keys = [{ id: 'k1', name: 'iPhone Endi', created: 1_764_000_000, last_used: null }]
        return json({ id: 'k1', name: 'iPhone Endi', token: 'phone-token-shown-once-abcdefghijklmnop', scopes: ['gate:control', 'voice:ask'] })
      }
      if (path === '/api/v1/auth/device-keys') return json({ keys })
      if (path === '/api/v1/auth/device-keys/k1' && options.method === 'DELETE') { keys = []; return json({ revoked: true }) }
      return json({ detail: 'unexpected' }, 404)
    }))
    const user = userEvent.setup()
    render(<SiriKeys credential={TOKEN} onUnauthorized={vi.fn()} mfaEnabled />)
    const name = screen.getByLabelText('Nazwa telefonu')
    await user.clear(name); await user.type(name, 'iPhone Endi')
    await user.click(screen.getByRole('button', { name: 'Dodaj telefon' }))
    expect(await screen.findByText('phone-token-shown-once-abcdefghijklmnop')).toBeInTheDocument()
    expect(screen.getByText(window.location.origin + '/api/v1/voice/ask')).toBeInTheDocument()
    expect(screen.getAllByText(/Hej Siri, Jarvis/).length).toBeGreaterThan(0)
    expect(screen.getByText(/jeszcze nie użyty/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zapisałem — ukryj klucz' }))
    expect(screen.queryByText('phone-token-shown-once-abcdefghijklmnop')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Usuń telefon iPhone Endi' }))
    await waitFor(() => expect(screen.queryByText('iPhone Endi')).not.toBeInTheDocument())
  })
})
