import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AccountPanel } from './AccountPanel'

const TOKEN = 'synthetic-account-session-token-0123456789'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => vi.unstubAllGlobals())

describe('Account panel (2FA)', () => {
  it('enrolls with a QR code, confirms the code and shows backup codes once', async () => {
    let enabled = false
    const fetch = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/auth/mfa') return json(enabled ? { enabled: true, pending: false, backup_codes_left: 8 } : { enabled: false, pending: false, backup_codes_left: 0 })
      if (path === '/api/v1/auth/mfa/setup') return json({ secret: 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP', uri: 'otpauth://totp/JARVIS%20OS%3Aendi?secret=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP&issuer=JARVIS%20OS', period: 30, digits: 6 })
      if (path === '/api/v1/auth/mfa/enable') {
        expect(JSON.parse(String(options.body))).toEqual({ code: '123456' })
        enabled = true
        return json({ enabled: true, backup_codes: ['abcde-fghjk', 'mnpqr-stuvw'] })
      }
      return json({ detail: 'unexpected' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    render(<AccountPanel credential={TOKEN} onUnauthorized={vi.fn()} accountSession />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Włącz 2FA' }))
    expect(await screen.findByRole('img', { name: 'Kod QR do aplikacji uwierzytelniającej' })).toBeInTheDocument()
    expect(screen.getByText('JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Kod z aplikacji'), '123 456')
    await user.click(screen.getByRole('button', { name: 'Potwierdź i włącz 2FA' }))
    expect(await screen.findByText('abcde-fghjk')).toBeInTheDocument()
    expect(screen.getByText(/2FA włączone · pozostałe kody zapasowe: 8/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zapisałem kody — ukryj' }))
    expect(screen.queryByText('abcde-fghjk')).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(TOKEN)
  })

  it('explains that the owner key has no second factor', async () => {
    vi.stubGlobal('fetch', vi.fn())
    render(<AccountPanel credential={TOKEN} onUnauthorized={vi.fn()} accountSession={false} />)
    expect(screen.getByRole('heading', { name: 'Połączono kluczem właściciela' })).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('shows a wrong code without ending the session', async () => {
    const unauthorized = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === '/api/v1/auth/mfa') return json({ enabled: false, pending: false, backup_codes_left: 0 })
      if (path === '/api/v1/auth/mfa/setup') return json({ secret: 'JBSWY3DPEHPK3PXP', uri: 'otpauth://totp/x?secret=JBSWY3DPEHPK3PXP' })
      return json({ detail: 'Invalid authenticator code' }, 422)
    }))
    render(<AccountPanel credential={TOKEN} onUnauthorized={unauthorized} accountSession />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Włącz 2FA' }))
    await user.type(await screen.findByLabelText('Kod z aplikacji'), '000000')
    await user.click(screen.getByRole('button', { name: 'Potwierdź i włącz 2FA' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Nieprawidłowy kod')
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('adds this device as a passkey and lists it', async () => {
    const raw = new Uint8Array([9, 9]).buffer
    const created = { id: 'CQk', rawId: raw, type: 'public-key', authenticatorAttachment: 'platform', getClientExtensionResults: () => ({}),
      response: { clientDataJSON: new Uint8Array([123, 125]).buffer, attestationObject: raw, getTransports: () => ['internal'] } }
    const create = vi.fn(async () => created)
    vi.stubGlobal('PublicKeyCredential', function PublicKeyCredential() { /* marker */ })
    vi.stubGlobal('isSecureContext', true)
    Object.defineProperty(navigator, 'credentials', { configurable: true, value: { create } })
    let items: unknown[] = []
    let verified: unknown = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/auth/mfa') return json({ enabled: true, pending: false, backup_codes_left: 8 })
      if (path === '/api/v1/auth/passkeys') return json(items)
      if (path === '/api/v1/auth/passkeys/register/options') return json({ ticket: 'ticket-0123456789abcdef', options: { challenge: 'AAEC', rp: { id: 'localhost', name: 'JARVIS OS' }, user: { id: 'dXNlcg', name: 'endi', displayName: 'endi' }, pubKeyCredParams: [], excludeCredentials: [] } })
      if (path === '/api/v1/auth/passkeys/register/verify') {
        verified = JSON.parse(String(options.body))
        items = [{ id: 'p1', name: 'Komputer', created: 1764100000, last_used: null, rp_id: 'localhost' }]
        return json(items[0], 201)
      }
      return json({}, 404)
    }))
    render(<AccountPanel credential={TOKEN} onUnauthorized={vi.fn()} accountSession />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Dodaj to urządzenie' }))
    expect(await screen.findByText(/Dodano\./)).toBeInTheDocument()
    expect(screen.getByText('Komputer')).toBeInTheDocument()
    const user = (create.mock.calls[0] as unknown as [CredentialCreationOptions])[0].publicKey!.user
    expect(new TextDecoder().decode(user.id as ArrayBuffer)).toBe('user')
    expect(verified).toMatchObject({ ticket: 'ticket-0123456789abcdef', name: 'Komputer', credential: { id: 'CQk', rawId: 'CQk', response: { attestationObject: 'CQk', transports: ['internal'] } } })
    Object.defineProperty(navigator, 'credentials', { configurable: true, value: undefined })
  })
})
