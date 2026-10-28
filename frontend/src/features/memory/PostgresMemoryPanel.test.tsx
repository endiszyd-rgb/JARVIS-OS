import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { PostgresMemoryPanel } from './PostgresMemoryPanel'
const B = '/api/v1/storage/memory', ID = '11111111-1111-4111-8111-111111111111', SID = '22222222-2222-4222-8222-222222222222'
const NOTE = { id: ID, revision: 0, workshop_id: null, content: '<img src=x onerror=bad()>Private PG', category: 'note', source: 'manual', source_id: '' }
const PROFILE = { id: ID, revision: 0, workshop_id: null, name: 'Krótko', instructions: 'Odpowiadaj krótko.' }
const response = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status })
type Handler = (p: string, o: RequestInit) => Response | Promise<Response> | undefined
function server(handler?: Handler) {
  const calls: { p: string; o: RequestInit }[] = [], state = { note: { ...NOTE }, profile: { ...PROFILE }, deleted: false, revision: 0, model: 'ollama' }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, o: RequestInit = {}) => {
    const p = String(input); calls.push({ p, o }); const custom = handler?.(p, o); if (custom !== undefined) return await custom
    if (p === B + '/status') return response({ enabled: true, memory_schema_version: 4 })
    if (p.includes('/conversations')) {
      if (p.endsWith('/conversations')) { state.model = JSON.parse(String(o.body)).model; return response({ id: SID, revision: 0, provider: state.model, profile_id: ID, profile_revision: 0 }, 201) }
      if (p.endsWith('/turns')) { state.revision++; return response({ revision: state.revision }) }
      if (p.endsWith('/messages')) return response({ revision: state.revision, messages: [{ role: 'assistant', content: 'PG answer' }] })
    }
    if (p.endsWith('/history?limit=100')) return response(p.includes('/profiles') ? [state.profile] : { versions: [state.note] })
    if (o.method === 'DELETE') { state.deleted = true; return response({ deleted: ID }) }
    if (o.method === 'PATCH') { const target = p.includes('/profiles') ? state.profile : state.note; Object.assign(target, JSON.parse(String(o.body)), { revision: target.revision + 1 }); return response(target) }
    if (o.method === 'POST') return response(p.includes('/profiles') ? state.profile : state.note, 201)
    if (p.includes('?limit=20')) return response(state.deleted ? [] : [p.includes('/profiles') ? state.profile : state.note])
    throw Error('Unexpected PG request')
  }))
  return { calls, state }
}
function panel(key = 'PG-secret-A') { const unauthorized = vi.fn(); return { ...render(<PostgresMemoryPanel credential={key} onUnauthorized={unauthorized} />), unauthorized } }
afterEach(() => vi.unstubAllGlobals())
async function ready() { await screen.findByRole('button', { name: 'Notatki PostgreSQL' }); return userEvent.setup() }
it('only checks status when disabled and never fetches private records', async () => {
  const { calls } = server(p => p.endsWith('/status') ? response({ enabled: false, memory_schema_version: null }) : undefined)
  panel(); await screen.findByText(/Pamięć PostgreSQL jest wyłączona/); expect(calls).toHaveLength(1)
})
it('edits exact revision, escapes HTML, shows real history and separately confirms deletion', async () => {
  const { calls } = server(); const { container } = panel(); const u = await ready()
  await u.click(screen.getByRole('button', { name: 'Notatki PostgreSQL' })); await screen.findByText(NOTE.content)
  expect(container.querySelector('img,script')).toBeNull()
  await u.click(screen.getByRole('button', { name: 'Edytuj rekord' })); await u.clear(screen.getByLabelText('Treść notatki PostgreSQL')); await u.type(screen.getByLabelText('Treść notatki PostgreSQL'), 'Corrected')
  await u.click(screen.getByRole('button', { name: 'Zapisz korektę PostgreSQL' })); await screen.findByText('Corrected')
  expect(JSON.parse(String(calls.find(c => c.o.method === 'PATCH')!.o.body)).revision).toBe(0)
  await u.click(screen.getByRole('button', { name: 'Historia rewizji' })); await screen.findByRole('heading', { name: 'Historia zapisanych rewizji' })
  await u.click(screen.getByRole('button', { name: 'Usuń rekord' })); expect(calls.some(c => c.o.method === 'DELETE')).toBe(false)
  await u.click(screen.getByRole('button', { name: 'Potwierdź usunięcie rekordu' })); await waitFor(() => expect(calls.filter(c => c.o.method === 'DELETE')).toHaveLength(1))
  expect(calls.find(c => c.o.method === 'DELETE')!.p).toContain('?revision=1')
})
it('locks mutations after 409 until a fresh read, with no retry', async () => {
  const { calls } = server((_p, o) => o.method === 'PATCH' ? response({}, 409) : undefined); panel(); const u = await ready()
  await u.click(screen.getByRole('button', { name: 'Notatki PostgreSQL' })); await screen.findByText(NOTE.content); await u.click(screen.getByRole('button', { name: 'Edytuj rekord' })); await u.click(screen.getByRole('button', { name: 'Zapisz korektę PostgreSQL' }))
  await screen.findByRole('alert'); expect(screen.getByRole('button', { name: 'Zapisz korektę PostgreSQL' })).toBeDisabled(); expect(calls.filter(c => c.o.method === 'PATCH')).toHaveLength(1)
  await u.click(screen.getByRole('button', { name: 'Odśwież PostgreSQL' })); await waitFor(() => expect(screen.getByLabelText('Treść notatki PostgreSQL')).toBeEnabled())
})
it('pins a chosen profile and requires cloud consent on every turn', async () => {
  const { calls } = server(); panel(); const u = await ready()
  await u.click(screen.getByRole('button', { name: 'Profile odpowiedzi' })); await screen.findByText(PROFILE.instructions); await u.click(screen.getByRole('button', { name: 'Wybierz do rozmowy' }))
  await u.selectOptions(screen.getByLabelText('Dostawca nowej rozmowy'), 'openai'); await u.click(screen.getByRole('button', { name: 'Utwórz rozmowę PostgreSQL' }))
  await screen.findByLabelText('Wiadomość z kontekstem PostgreSQL')
  const created = calls.find(c => c.p.endsWith('/conversations'))!; expect(JSON.parse(String(created.o.body)).profile_ref).toEqual({ id: ID, revision: 0 })
  await u.type(screen.getByLabelText('Wiadomość z kontekstem PostgreSQL'), 'Hello'); expect(screen.getByRole('button', { name: 'Wyślij z kontekstem PostgreSQL' })).toBeDisabled()
  await u.click(screen.getByRole('checkbox')); await u.click(screen.getByRole('button', { name: 'Wyślij z kontekstem PostgreSQL' })); await screen.findByText('PG answer'); expect(screen.getByRole('checkbox')).not.toBeChecked()
  expect(JSON.parse(String(calls.find(c => c.p.endsWith('/turns'))!.o.body))).toMatchObject({ revision: 0, allow_cloud_context: true })
})
it('uses only the explicitly applied workshop and clears old records during scope reads', async () => {
  const { calls } = server(); panel(); const u = await ready(); await u.type(screen.getByLabelText('Zakres danych: UUID warsztatu'), SID)
  expect(calls).toHaveLength(1); await u.click(screen.getByRole('button', { name: 'Odczytaj zakres' })); await screen.findByText(NOTE.content)
  expect(calls.at(-1)!.p).toContain('workshop_id=' + SID)
})
it('clears private records on 401 and signals the application', async () => {
  let fail = false; server(() => fail ? response({}, 401) : undefined); const { unauthorized } = panel(); const u = await ready()
  await u.click(screen.getByRole('button', { name: 'Notatki PostgreSQL' })); await screen.findByText(NOTE.content); fail = true
  await u.click(screen.getByRole('button', { name: 'Odśwież PostgreSQL' })); await waitFor(() => expect(unauthorized).toHaveBeenCalledOnce()); expect(screen.queryByText(NOTE.content)).not.toBeInTheDocument()
})
it('ignores a late old-account response after credential change', async () => {
  let finish!: (v: Response) => void
  const { calls } = server(p => p.includes('?limit=20') ? new Promise<Response>(resolve => { finish = resolve }) : undefined)
  const view = panel(); const u = await ready(); await u.click(screen.getByRole('button', { name: 'Notatki PostgreSQL' })); const request = calls.at(-1)!
  view.rerender(<PostgresMemoryPanel credential="PG-secret-B" onUnauthorized={view.unauthorized} />)
  expect((request.o.signal as AbortSignal).aborted).toBe(true)
  await act(async () => finish(response([NOTE]))); await ready(); expect(screen.queryByText(NOTE.content)).not.toBeInTheDocument()
  expect(document.body.innerHTML).not.toContain('PG-secret-A')
})
it('rejects malformed backend records instead of displaying them', async () => {
  server(p => p.includes('?limit=20') ? response([{ ...NOTE, revision: -1 }]) : undefined); panel(); const u = await ready(); await u.click(screen.getByRole('button', { name: 'Notatki PostgreSQL' })); await screen.findByRole('alert'); expect(screen.queryByText(NOTE.content)).not.toBeInTheDocument()
})
