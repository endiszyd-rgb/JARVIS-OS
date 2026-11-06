import { useState } from 'react'
import { apiRequest, ApiError } from '../../api'
import { useRead } from '../home/useRead'
import type { ReadProps } from '../home/useRead'

type Entry = { text: string; amount_grosz?: number; currency?: string }
type Order = { id: string; revision: number; status: string; notes: Entry[]; tasks: Entry[]; quotes: Entry[] }
type Result = { mode: 'synthetic_write_lab'; order?: Order; id?: string; digest?: string; status?: string; before?: Order; after?: Order }
const labels = { note: 'Notatka', task: 'Zadanie', quote: 'Wycena', status: 'Status' }
type Operation = keyof typeof labels
async function request(credential: string, signal: AbortSignal, path = '', body?: unknown): Promise<Result> {
  const value = await apiRequest('/api/v1/autologika/write-lab' + path, signal, credential, { body })
  if (!value || typeof value !== 'object' || !('mode' in value) || value.mode !== 'synthetic_write_lab') throw new ApiError(null, 'response')
  return value as Result
}

function OrderPreview({ order, title }: { order: Order; title: string }) {
  return <section><h4>{title}</h4><p className="workshop-caption">{order.id} · wersja {order.revision} · status {order.status}</p>
    {(['notes', 'tasks', 'quotes'] as const).map((key, index) => <div key={key}><strong>{['Notatki', 'Zadania', 'Wyceny'][index]}</strong>
      {order[key].length ? <ul>{order[key].map((entry, position) => <li key={position}>{entry.text}{entry.amount_grosz !== undefined && <> — {(entry.amount_grosz / 100).toLocaleString('pl-PL', { style: 'currency', currency: 'PLN' })}</>}</li>)}</ul> : <p className="workshop-caption">Brak wpisów</p>}</div>)}
  </section>
}

export function WriteLab(props: ReadProps) {
  const read = useRead<Result>(props)
  const [operation, setOperation] = useState<Operation>('note')
  const [text, setText] = useState('')
  const [amount, setAmount] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const result = read.value
  const pending = result?.status === 'pending'
  const order = result?.order
  const validAmount = /^\d{1,7}(\.\d{1,2})?$/.test(amount) && Number(amount) <= 1000000
  const ready = order && text.trim() && (operation !== 'quote' || validAmount)
  const refresh = () => { setConfirmed(false); void read.run((key, signal) => request(key, signal)) }
  function decide(approve: boolean) {
    if (!result?.id || !result.digest || (approve && !confirmed)) return
    const { id, digest } = result
    setConfirmed(false)
    void read.run((key, signal) => request(key, signal, `/proposals/${id}/decide`, { approve, digest }))
  }
  return <section className="panel" aria-labelledby="write-lab-title" aria-busy={read.busy}>
    <h2 id="write-lab-title" className="panel-heading">Laboratorium zapisów · DEMO</h2>
    <p className="workshop-notice">Wyłącznie syntetyczne zlecenie DEMO-1. Żaden zapis nie trafia do AutoLogiki. Dane znikają po restarcie lub 30 minutach bezczynności; propozycja wygasa po 15 minutach.</p>
    <button className="button secondary" disabled={read.busy} onClick={refresh}>Odczytaj stan laboratorium</button>
    {order && <form className="chat-new" onSubmit={event => {
      event.preventDefault()
      if (!ready || read.busy) return
      setConfirmed(false)
      void read.run((key, signal) => request(key, signal, '/proposals', {
        request_id: crypto.randomUUID(), revision: order.revision, operation, text,
        ...(operation === 'quote' ? { amount_grosz: Math.round(Number(amount) * 100) } : {}),
      }))
    }}>
      <p className="workshop-caption">DEMO-1 · wersja {order.revision} · status {order.status}</p>
      <label>Operacja DEMO<select aria-label="Operacja DEMO" value={operation} disabled={read.busy} onChange={event => { setOperation(event.target.value as Operation); setText('') }}>{Object.entries(labels).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
      {operation === 'status' ? <label>Nowy status DEMO<select aria-label="Nowy status DEMO" value={text} onChange={event => setText(event.target.value)} required><option value="">Wybierz status</option>{['PRZYJETE', 'DIAGNOZA', 'WYCENA', 'NAPRAWA', 'GOTOWE'].map(status => <option key={status}>{status}</option>)}</select></label>
        : <label>Treść DEMO<input value={text} maxLength={2000} disabled={read.busy} required onChange={event => setText(event.target.value)} /></label>}
      {operation === 'quote' && <label>Kwota DEMO (PLN)<input type="number" min="0" max="1000000" step="0.01" value={amount} disabled={read.busy} onChange={event => setAmount(event.target.value)} required /></label>}
      <button className="button secondary" disabled={read.busy || !ready}>Przygotuj podgląd DEMO</button>
    </form>}
    {result?.before && result.after && <>
      <h3>Podgląd zmiany DEMO</h3>
      <div className="workshop-details"><OrderPreview order={result.before} title="Przed" /><OrderPreview order={result.after} title="Po" /></div>
      <p role="status">{pending ? 'Oczekuje na osobną decyzję' : result.status === 'applied_demo' ? 'Zapisano wyłącznie w laboratorium DEMO' : 'Odrzucono propozycję DEMO'}</p>
      {pending && <><label className="chat-checkbox"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />Sprawdziłem podgląd; potwierdzam zmianę w DEMO</label>
        <div className="chat-compose-actions"><button className="button secondary" disabled={read.busy} onClick={() => decide(false)}>Odrzuć zmianę DEMO</button><button className="button primary" disabled={read.busy || !confirmed} onClick={() => decide(true)}>Zatwierdź zmianę DEMO</button></div></>}
    </>}
    {read.error && <p role="alert">Nie wykonano potwierdzonego odczytu wyniku. Odczytaj stan laboratorium przed kolejną próbą. {read.error.status === 409 ? 'Wersja danych lub decyzja uległa zmianie.' : read.error.message}</p>}
  </section>
}
