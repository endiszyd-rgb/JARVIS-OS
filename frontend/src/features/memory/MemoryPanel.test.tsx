import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryPanel } from './MemoryPanel'
import type { MemoryNote, PolicySnapshot } from './api'

const KEY = 'synthetic-memory-owner-session'
const ID = '30000000-0000-4000-8000-000000000001'
const NEW_ID = '30000000-0000-4000-8000-000000000002'
const NOTE: MemoryNote = { id: ID, text: 'Private local note', source: 'owner_manual', category: 'manual', revision: 3, created: 1800000000, updated: 1800000000 }
const POLICY: PolicySnapshot = { revision: 4, policy: { enabled: true, mode: 'manual', categories: ['preferences', 'equipment'], retention_days: null }, automatic_extraction_active: false, automatic_extractor: 'pl-declarations-v1' }
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
function server(handler?: Handler) {
  const calls: Call[] = []
  const state = { notes: [{ ...NOTE }], policy: structuredClone(POLICY) }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input)
    calls.push({ path, options })
    const custom = handler?.(path, options)
    if (custom !== undefined) return await custom
    if (path === '/api/v1/memory' && options.method === 'GET') return response(state.notes)
    if (path === '/api/v1/memory/policy' && options.method === 'GET') return response(state.policy)
    if (path === '/api/v1/memory' && options.method === 'POST') {
      const body = JSON.parse(String(options.body))
      state.notes.unshift({ ...NOTE, ...body, id: NEW_ID, revision: 0 })
      return response({ id: NEW_ID }, 201)
    }
    if (path.startsWith('/api/v1/memory/') && options.method === 'PUT' && path !== '/api/v1/memory/policy') {
      const body = JSON.parse(String(options.body)), id = path.split('/').at(-1)
      const note = state.notes.find(row => row.id === id)!
      if (body.revision !== note.revision) return response({}, 409)
      Object.assign(note, body, { revision: note.revision + 1, source: 'owner_correction' })
      return response({ id, revision: note.revision })
    }
    if (path.startsWith('/api/v1/memory/') && options.method === 'DELETE') {
      const id = path.split('/').at(-1)
      state.notes = state.notes.filter(row => row.id !== id)
      return response({ deleted: id })
    }
    if (path === '/api/v1/memory/policy' && options.method === 'PUT') {
      const body = JSON.parse(String(options.body))
      if (body.revision !== state.policy.revision) return response({}, 409)
      state.policy = { ...state.policy, revision: state.policy.revision + 1, policy: body.policy }
      return response(state.policy)
    }
    if (path === '/api/v1/memory/retention') {
      const dryRun = JSON.parse(String(options.body)).dry_run
      return response({ dry_run: dryRun, count: dryRun ? 2 : 1, retention_days: state.policy.policy.retention_days })
    }
    if (path.endsWith('/history')) return response([{ revision: 0, text: '<img src=x onerror=bad()>Old note', source: 'owner_manual', category: 'manual', created: 1800000000 }])
    if (path.endsWith('/origins')) return response([{ revision: 1, quote: '<script>bad()</script>', session_id: ID, turn_id: NEW_ID, extractor: 'pl-declarations-v1', created: 1800000000, session_available: 0 }])
    throw new Error('Unexpected memory request: ' + path)
  }))
  return { state, calls }
}
function panel() {
  const onUnauthorized = vi.fn()
  return { ...render(<MemoryPanel credential={KEY} onUnauthorized={onUnauthorized} />), onUnauthorized }
}
afterEach(() => vi.unstubAllGlobals())

describe('owner personal memory', () => {
  it('loads only local notes and policy, then filters the latest 100 without network searches', async () => {
    const { calls } = server()
    panel()
    await screen.findByText(NOTE.text)
    expect(calls.map(call => call.path)).toEqual(['/api/v1/memory', '/api/v1/memory/policy'])
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Filtruj notatki'), 'PRIVATE')
    expect(screen.getByText(NOTE.text)).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Filtruj notatki'))
    await user.type(screen.getByLabelText('Filtruj notatki'), 'not-found')
    expect(screen.queryByText(NOTE.text)).not.toBeInTheDocument()
    expect(calls).toHaveLength(2)
    expect(document.body.innerHTML).not.toContain(KEY)
  })

  it('adds escaped text, edits using its exact revision, and deletes only after separate confirmation', async () => {
    const { state, calls } = server()
    const { container } = panel()
    await screen.findByText(NOTE.text)
    const user = userEvent.setup()
    const html = '<img src=x onerror=bad()>Keep as text'
    await user.type(screen.getByLabelText('Nowa notatka'), html)
    await user.click(screen.getByRole('button', { name: 'Dodaj notatkę' }))
    await screen.findByText(html)
    expect(container.querySelector('img,script')).toBeNull()
    const list = screen.getByRole('list', { name: 'Pobrane notatki' })
    const first = within(list).getAllByRole('listitem')[0]
    await user.click(within(first).getByRole('button', { name: 'Edytuj notatkę' }))
    await user.clear(screen.getByLabelText('Treść korekty'))
    await user.type(screen.getByLabelText('Treść korekty'), 'Corrected note')
    await user.click(screen.getByRole('button', { name: 'Zapisz korektę' }))
    await screen.findByText('Corrected note')
    const update = calls.find(call => call.path === '/api/v1/memory/' + NEW_ID && call.options.method === 'PUT')!
    expect(JSON.parse(String(update.options.body))).toEqual({ text: 'Corrected note', category: 'manual', revision: 0 })
    expect(state.notes[0].revision).toBe(1)
    const changed = within(list).getAllByRole('listitem')[0]
    await user.click(within(changed).getByRole('button', { name: 'Usuń notatkę' }))
    expect(calls.some(call => call.options.method === 'DELETE')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Potwierdź usunięcie' }))
    await waitFor(() => expect(screen.queryByText('Corrected note')).not.toBeInTheDocument())
    expect(calls.filter(call => call.options.method === 'DELETE')).toHaveLength(1)
  })

  it('refuses stale edits on 409 and requires a fresh read instead of retrying a mutation', async () => {
    const { state, calls } = server()
    panel()
    await screen.findByText(NOTE.text)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Edytuj notatkę' }))
    state.notes[0] = { ...NOTE, text: 'Newer owner correction', revision: 4 }
    await user.type(screen.getByLabelText('Treść korekty'), ' old draft')
    await user.click(screen.getByRole('button', { name: 'Zapisz korektę' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Odśwież pamięć')
    expect(screen.getByRole('button', { name: 'Zapisz korektę' })).toBeDisabled()
    expect(calls.filter(call => call.options.method === 'PUT')).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Odśwież pamięć' }))
    await screen.findByText('Newer owner correction')
    expect(screen.queryByLabelText('Treść korekty')).not.toBeInTheDocument()
  })

  it('loads history and origins only on action and renders their private quotes as plain text', async () => {
    const { calls } = server()
    const { container } = panel()
    await screen.findByText(NOTE.text)
    expect(calls.some(call => call.path.endsWith('/history') || call.path.endsWith('/origins'))).toBe(false)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Historia korekt' }))
    await screen.findByText('<img src=x onerror=bad()>Old note')
    await user.click(screen.getByRole('button', { name: 'Źródła notatki' }))
    await screen.findByText('<script>bad()</script>')
    expect(container.querySelector('img,script')).toBeNull()
  })

  it('saves the full policy with its revision and previews retention before separate execution', async () => {
    const { calls, state } = server()
    panel()
    await screen.findByText(NOTE.text)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Retencja w dniach'), '30')
    expect(screen.getByRole('button', { name: 'Podgląd retencji' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Zapisz zasady pamięci' }))
    await screen.findByText('Zasady pamięci zostały zapisane z nową rewizją.')
    const saved = calls.find(call => call.path === '/api/v1/memory/policy' && call.options.method === 'PUT')!
    expect(JSON.parse(String(saved.options.body))).toEqual({ revision: 4, policy: { ...POLICY.policy, retention_days: 30 } })
    expect(state.policy.revision).toBe(5)
    await user.click(screen.getByRole('button', { name: 'Podgląd retencji' }))
    const execute = await screen.findByRole('button', { name: 'Wykonaj retencję' })
    expect(calls.filter(call => call.path.endsWith('/retention')).map(call => JSON.parse(String(call.options.body)))).toEqual([{ dry_run: true }])
    await user.click(execute)
    await screen.findByText(/Usunięto 1 notatek/)
    expect(calls.filter(call => call.path.endsWith('/retention')).map(call => JSON.parse(String(call.options.body)))).toEqual([{ dry_run: true }, { dry_run: false }])
  })

  it('does not execute retention after detecting a newer policy revision', async () => {
    const { calls, state } = server()
    state.policy.policy.retention_days = 30
    panel()
    await screen.findByText(NOTE.text)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Podgląd retencji' }))
    const execute = await screen.findByRole('button', { name: 'Wykonaj retencję' })
    state.policy.revision += 1
    state.policy.policy.retention_days = 1
    await user.click(execute)
    await screen.findByRole('alert')
    expect(calls.filter(call => call.path.endsWith('/retention'))).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Wykonaj retencję' })).toBeDisabled()
  })

  it('requires a refresh after a stale policy save and does not retry it', async () => {
    const { calls, state } = server()
    panel()
    await screen.findByText(NOTE.text)
    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Tryb pamięci'), 'auto')
    state.policy = { ...state.policy, revision: 5, policy: { ...state.policy.policy, retention_days: 7 } }
    await user.click(screen.getByRole('button', { name: 'Zapisz zasady pamięci' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('button', { name: 'Zapisz zasady pamięci' })).toBeDisabled()
    expect(calls.filter(call => call.path.endsWith('/policy') && call.options.method === 'PUT')).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Odśwież pamięć' }))
    await waitFor(() => expect(screen.getByLabelText('Retencja w dniach')).toHaveValue(7))
    expect(screen.getByLabelText('Tryb pamięci')).toHaveValue('manual')
  })

  it('does not retry a failed mutation or reveal backend diagnostics', async () => {
    const diagnostics = 'Synthetic internal diagnostics must not be visible'
    const { calls } = server((path, options) => path === '/api/v1/memory' && options.method === 'POST' ? response({ detail: diagnostics }, 500) : undefined)
    panel()
    await screen.findByText(NOTE.text)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Nowa notatka'), 'Unconfirmed note')
    await user.click(screen.getByRole('button', { name: 'Dodaj notatkę' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Odśwież pamięć przed ponowieniem')
    expect(calls.filter(call => call.path === '/api/v1/memory' && call.options.method === 'POST')).toHaveLength(1)
    expect(document.body.textContent).not.toContain(diagnostics)
    expect(screen.getByLabelText('Nowa notatka')).toHaveValue('Unconfirmed note')
  })

  it('clears private notes, drafts and details after a 401 refresh', async () => {
    let expired = false
    server(path => expired && path === '/api/v1/memory' ? response({}, 401) : undefined)
    const { onUnauthorized } = panel()
    await screen.findByText(NOTE.text)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Nowa notatka'), 'Private unsaved draft')
    expired = true
    await user.click(screen.getByRole('button', { name: 'Odśwież pamięć' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
    expect(document.body.innerHTML).not.toContain(NOTE.text)
    expect(document.body.innerHTML).not.toContain('Private unsaved draft')
    expect(document.body.innerHTML).not.toContain(KEY)
  })

  it('aborts reads and ignores an old identity response after credentials change', async () => {
    let resolveOld: ((value: Response) => void) | undefined
    let oldSignal: AbortSignal | undefined
    server((path, options) => {
      if (path === '/api/v1/memory' && new Headers(options.headers).get('X-Jarvis-Key') === 'old-owner') {
        oldSignal = options.signal as AbortSignal
        return new Promise<Response>(resolve => { resolveOld = resolve })
      }
    })
    const onUnauthorized = vi.fn()
    const { rerender } = render(<MemoryPanel credential="old-owner" onUnauthorized={onUnauthorized} />)
    await waitFor(() => expect(resolveOld).toBeDefined())
    rerender(<MemoryPanel credential="new-owner" onUnauthorized={onUnauthorized} />)
    await screen.findByText(NOTE.text)
    expect(oldSignal?.aborted).toBe(true)
    await act(async () => { resolveOld!(response({}, 401)) })
    expect(onUnauthorized).not.toHaveBeenCalled()
    expect(screen.getByText(NOTE.text)).toBeInTheDocument()
  })

  it('rejects oversized or malformed note responses without displaying their data', async () => {
    server(path => path === '/api/v1/memory' ? response(Array.from({ length: 101 }, () => NOTE)) : undefined)
    panel()
    await screen.findByRole('alert')
    expect(screen.queryByText(NOTE.text)).not.toBeInTheDocument()
  })
})
