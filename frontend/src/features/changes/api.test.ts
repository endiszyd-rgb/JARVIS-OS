import { afterEach, expect, it, vi } from 'vitest'
import { decideProposal, readProposals, rollbackProposal } from './api'
import type { Proposal } from './api'
const row: Proposal = { id: 'd525dd53-0368-43e6-b9ad-cc8c08f27438', kind: 'code', status: 'pending', payload: { description: 'Synthetic review' }, previous: null }
const signal = new AbortController().signal
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
afterEach(() => vi.unstubAllGlobals())
it('requires review_required after approving code and never calls execution', async () => {
  const fetch = vi.fn(async () => response({ id: row.id, status: 'review_required' })); vi.stubGlobal('fetch', fetch)
  expect(await decideProposal('synthetic-key', row, true, signal)).toBe('review_required')
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch).toHaveBeenCalledWith('/api/v1/proposals/' + row.id + '/decide', expect.objectContaining({ method: 'POST', body: '{"approve":true}' }))
})
it('rejects a server claim that code was applied', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ id: row.id, status: 'applied' })))
  await expect(decideProposal('synthetic-key', row, true, signal)).rejects.toThrow()
})
it('does not repeat a conflicting decision or render diagnostics', async () => {
  const fetch = vi.fn(async () => response({ detail: 'Private diagnostic' }, 409)); vi.stubGlobal('fetch', fetch)
  await expect(decideProposal('synthetic-key', row, false, signal)).rejects.toMatchObject({ status: 409 })
  expect(fetch).toHaveBeenCalledTimes(1)
})
it('refuses rollback of code or a pending proposal before network access', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  await expect(rollbackProposal('synthetic-key', row, signal)).rejects.toMatchObject({ status: 409 })
  expect(fetch).not.toHaveBeenCalled()
})
it('reads the bounded list and treats prior settings as inert JSON text', async () => {
  const previous = '{"name":"Synthetic"}'
  vi.stubGlobal('fetch', vi.fn(async () => response([{ ...row, previous }])))
  expect((await readProposals('synthetic-key', signal))[0].previous).toBe(previous)
})
