import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ChangesPanel } from './ChangesPanel'
import type { Proposal } from './api'
const row: Proposal = { id:'d525dd53-0368-43e6-b9ad-cc8c08f27438',kind:'code',status:'pending',payload:{description:'<img src=x> Synthetic code'},previous:null }
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status})
function server() {
  let current={...row}, expired=false, conflict=false
  const calls:{path:string;method:string}[]=[]
  vi.stubGlobal('fetch',vi.fn(async (path:string,options:RequestInit={})=>{
    calls.push({path,method:options.method??'GET'})
    if(expired)return json({detail:'Private diagnostic'},401)
    if(path==='/api/v1/proposals')return json([current])
    if(conflict)return json({},409)
    current={...current,status:JSON.parse(String(options.body)).approve?'review_required':'rejected'}
    return json({id:row.id,status:current.status})
  }))
  return {calls,expire:()=>{expired=true},change:()=>{current={...current,status:'rejected'}},conflict:()=>{conflict=true}}
}
afterEach(()=>vi.unstubAllGlobals())
it('requires separate confirmation, moves focus, and sends code only to review',async()=>{
  const s=server(),user=userEvent.setup();render(<ChangesPanel credential="synthetic-key" onUnauthorized={vi.fn()}/> )
  await user.click(await screen.findByRole('button',{name:'Przejrzyj zatwierdzenie'}))
  const heading=screen.getByRole('heading',{name:'Potwierdzenie decyzji'});expect(heading).toHaveFocus()
  expect(s.calls.every(c=>c.method==='GET')).toBe(true)
  await user.click(screen.getByRole('button',{name:'Potwierdź decyzję'}))
  await screen.findByText('Opis skierowano do przeglądu. Nie wykonano kodu.')
  expect(s.calls.filter(c=>c.method==='POST')).toHaveLength(1)
  expect(document.querySelector('img')).toBeNull()
})
it('cancel sends no mutation',async()=>{
  const s=server(),user=userEvent.setup();render(<ChangesPanel credential="synthetic" onUnauthorized={vi.fn()}/> )
  await user.click(await screen.findByRole('button',{name:'Przejrzyj odrzucenie'}));await user.click(screen.getByRole('button',{name:'Anuluj decyzję'}))
  expect(s.calls.every(c=>c.method==='GET')).toBe(true)
  expect(screen.getByRole('button',{name:'Przejrzyj odrzucenie'})).toHaveFocus()
})
it('checks current state before confirming and refuses a stale proposal',async()=>{
  const s=server(),user=userEvent.setup();render(<ChangesPanel credential="synthetic" onUnauthorized={vi.fn()}/> )
  await user.click(await screen.findByRole('button',{name:'Przejrzyj zatwierdzenie'}));s.change()
  await user.click(screen.getByRole('button',{name:'Potwierdź decyzję'}));await screen.findByRole('alert')
  expect(s.calls.every(c=>c.method==='GET')).toBe(true)
})
it('requires refresh after a conflict instead of retrying the mutation',async()=>{
  const s=server(),user=userEvent.setup();render(<ChangesPanel credential="synthetic" onUnauthorized={vi.fn()}/> )
  await user.click(await screen.findByRole('button',{name:'Przejrzyj zatwierdzenie'}));s.conflict()
  await user.click(screen.getByRole('button',{name:'Potwierdź decyzję'}));await screen.findByRole('alert')
  expect(s.calls.filter(c=>c.method==='POST')).toHaveLength(1)
  expect(screen.getByRole('button',{name:'Przejrzyj zatwierdzenie'})).toBeDisabled()
  await user.click(screen.getByRole('button',{name:'Odśwież propozycje'}))
  await waitFor(()=>expect(screen.getByRole('button',{name:'Przejrzyj zatwierdzenie'})).toBeEnabled())
})
it('clears private data on 401',async()=>{
  const s=server(),user=userEvent.setup(),unauthorized=vi.fn();render(<ChangesPanel credential="synthetic" onUnauthorized={unauthorized}/> )
  await screen.findByText('Opis do przeglądu, bez wykonania kodu.');s.expire();await user.click(screen.getByRole('button',{name:'Odśwież propozycje'}))
  await waitFor(()=>expect(unauthorized).toHaveBeenCalledTimes(1));expect(document.body.textContent).not.toContain('Synthetic code');expect(document.body.textContent).not.toContain('Private diagnostic')
})
it('aborts on unmount and ignores late data',async()=>{
  let resolve:((r:Response)=>void)|undefined;let signal:AbortSignal|null|undefined
  vi.stubGlobal('fetch',vi.fn((_path:string,o:RequestInit)=>{signal=o.signal;return new Promise<Response>(r=>{resolve=r})}))
  const v=render(<ChangesPanel credential="synthetic" onUnauthorized={vi.fn()}/> );v.unmount();expect(signal?.aborted).toBe(true)
  await act(async()=>{resolve!(json([row]))});expect(document.body.textContent).not.toContain('Synthetic code')
})
