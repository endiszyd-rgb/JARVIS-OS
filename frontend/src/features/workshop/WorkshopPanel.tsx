import { useState } from 'react'
import { Car, Database, Download } from 'lucide-react'
import { DOMAINS, PAGE, page, readOrders, readSnapshotDomain, readSnapshotInfo } from './api'
import type { Domain, SnapshotDomain, WorkshopRead } from './api'
import { useRead } from '../home/useRead'
import type { ReadProps } from '../home/useRead'
import './workshop.css'

interface Props extends ReadProps { canReadPrivate: boolean }
const LABELS: Record<Domain, string> = { calendar: 'Terminarz', orders: 'Zlecenia', vehicles: 'Pojazdy', parts: 'Części', customers: 'Klienci', diagnostics: 'Diagnostyka', finances: 'Finanse', reports: 'Raporty', notifications: 'Powiadomienia' }
const FIELD: Record<string, string> = { symptom_confirmed: 'Potwierdzony objaw', dtcs: 'Kody DTC', measurements: 'Pomiary', hypothesis: 'Hipoteza', conclusion: 'Wniosek', recommendation: 'Zalecenie', time_hours: 'Czas (h)', updated_at: 'Zaktualizowano', id: 'ID', title: 'Tytuł', name: 'Nazwa', status: 'Status', vehicle_id: 'Pojazd ID', order_id: 'Zlecenie ID', customer_id: 'Klient ID', plate: 'Rejestracja', make: 'Marka', model: 'Model', year: 'Rok', mileage: 'Przebieg', phone: 'Telefon', email: 'Email', company: 'Firma', start_at: 'Początek', end_at: 'Koniec', opened_at: 'Otwarto', due_at: 'Termin', created_at: 'Utworzono', bay: 'Stanowisko', total: 'Wartość PLN', variable_cost: 'Koszt zmienny PLN', wait_state: 'Oczekiwanie', qty: 'Ilość', part_no: 'Numer części', unit_cost: 'Koszt jednostkowy', unit_price: 'Cena jednostkowa', count: 'Liczba', text: 'Treść', kind: 'Rodzaj', stock: 'Stan', min_stock: 'Minimum', sell_price: 'Cena sprzedaży', expected_at: 'Przewidywany termin' }
function text(value: unknown): string { return value === null || value === undefined ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value) }
function Rows({ rows, label }: { rows: Record<string, unknown>[]; label: string }) {
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))].slice(0, 24)
  if (!rows.length) return <p className="workshop-caption">Brak rekordów w tym odczycie.</p>
  return <div className="workshop-table-wrap" tabIndex={0} role="region" aria-label={label}><table className="workshop-table"><caption>{label} · {rows.length} rekordów w odczycie</caption>
    <thead><tr>{columns.map(key => <th scope="col" key={key}>{FIELD[key] || key}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index}>{columns.map(key => <td key={key}>{text(row[key]).slice(0, 2000)}</td>)}</tr>)}</tbody>
  </table></div>
}
function SnapshotData({ value }: { value: SnapshotDomain }) {
  if (value.domain === 'parts') return <>{(['job_part_orders', 'inventory_parts', 'repair_parts'] as const).map((key, index) => {
    const collection = value.data[key]
    return page(collection) && <section className="workshop-collection" key={key}><h3>{['Zamówienia części', 'Magazyn części', 'Części napraw'][index]}</h3><Rows rows={collection.items} label={['Zamówienia części', 'Magazyn części', 'Części napraw'][index]} /><p className="workshop-caption">{collection.has_more ? 'Są kolejne rekordy tej kolekcji.' : 'Koniec tej kolekcji w tym odczycie.'}</p></section>
  })}<p className="workshop-caption">Wszystkie trzy kolekcje korzystają z tego samego przesunięcia strony; ich długości mogą się różnić.</p></>
  if (value.domain === 'finances') return <>
    <p className="workshop-notice">Miesiąc: {text(value.data.month)}. Wartość zleceń i wkład nie są zyskiem księgowym.</p>
    <dl className="workshop-finances">{Object.entries({ orders_count: 'Liczba zleceń', orders_value: 'Wartość zleceń PLN', contribution: 'Wkład PLN', receivables: 'Należności PLN', paid_in_month: 'Płatności w miesiącu PLN' }).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{text(value.data[key])}</dd></div>)}</dl>
  </>
  if (value.domain === 'reports') return <><Rows rows={value.data.status_counts as Record<string, unknown>[]} label="Zlecenia według statusu" /><p className="workshop-caption">Wszystkie nieusunięte zlecenia, również wydane. To ograniczony raport kopii, bez pełnej analityki AutoLogiki.</p></>
  return page(value.data) && <Rows rows={value.data.items} label={LABELS[value.domain]} />
}

export function WorkshopPanel(props: Props) { return <WorkshopWorkspace key={props.credential + ':' + props.canReadPrivate} {...props} /> }
function WorkshopWorkspace(props: Props) {
  const read = useRead<WorkshopRead>(props)
  const [domain, setDomain] = useState<Domain>('orders'), [offset, setOffset] = useState(0)
  const [requestSource, setRequestSource] = useState<'snapshot' | 'live'>('snapshot')
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7)), [orderId, setOrderId] = useState('')
  const allowed = props.canReadPrivate ? DOMAINS : DOMAINS.filter(key => !['finances', 'reports', 'notifications'].includes(key))
  const validMonth = /^\d{4}-(0[1-9]|1[0-2])$/.test(month)
  const validOrder = !orderId.trim() || (/^[1-9][0-9]*$/.test(orderId.trim()) && Number.isSafeInteger(Number(orderId.trim())))
  function readDomain(nextOffset = offset) {
    if (!allowed.includes(domain) || !validMonth || read.busy) return
    setRequestSource('snapshot')
    setOffset(nextOffset)
    void read.run((credential, signal) => readSnapshotDomain(credential, signal, domain, nextOffset, month))
  }
  const snapshot = read.value?.kind === 'snapshot' ? read.value.value : null
  const hasMore = snapshot && (snapshot.domain === 'parts' ? Object.values(snapshot.data).some(value => page(value) && value.has_more) : page(snapshot.data) && snapshot.data.has_more)
  const pageable = snapshot && !['finances', 'reports'].includes(snapshot.domain)

  return <div className="workshop-workspace">
    <section className="panel" aria-labelledby="workshop-title" aria-busy={read.busy}>
      <h2 className="panel-heading" id="workshop-title"><Car aria-hidden="true" />AutoLogika · kopia i odczyt</h2>
      <p className="panel-description">Dane z przygotowanej kopii albo jawny odczyt skonfigurowanej usługi. Ten panel nie zapisuje do AutoLogiki i nie synchronizuje kopii. Na otwarciu nie wykonuje żadnego odczytu.</p>
      <div className="workshop-source-heading"><h3><Database aria-hidden="true" />Kopia offline</h3><button className="button secondary" type="button" disabled={read.busy} onClick={() => { setRequestSource('snapshot'); void read.run(readSnapshotInfo) }}>Sprawdź kopię</button></div>
      {!props.canReadPrivate && <p className="workshop-caption">Dostęp warsztatowy obejmuje sześć domen. Finanse, raporty i powiadomienia są dostępne właścicielowi.</p>}
      <form className="workshop-form" onSubmit={event => { event.preventDefault(); readDomain(0) }}>
        <div className="form-field"><label htmlFor="workshop-domain">Domena kopii</label><select id="workshop-domain" value={domain} disabled={read.busy} onChange={event => { setDomain(event.target.value as Domain); setOffset(0); read.clear() }}>{allowed.map(key => <option key={key} value={key}>{LABELS[key]}</option>)}</select></div>
        <div className="form-field"><label htmlFor="workshop-month">Miesiąc finansów</label><input id="workshop-month" type="month" value={month} disabled={read.busy || domain !== 'finances'} onChange={event => { setMonth(event.target.value); setOffset(0); read.clear() }} /></div>
        <button className="button secondary" type="submit" disabled={read.busy || !validMonth}>Odczytaj domenę</button>
      </form>
      <div className="workshop-live"><h3><Download aria-hidden="true" />Odczyt z usługi AutoLogika</h3>
        <p className="workshop-caption">Przycisk łączy się ze skonfigurowaną usługą. Lista obejmuje maksymalnie 100 niewydanych zleceń; opcjonalny numer pobiera szczegóły jednego zlecenia.</p>
        <form className="workshop-live-form" onSubmit={event => { event.preventDefault(); if (validOrder && !read.busy) { setRequestSource('live'); void read.run((credential, signal) => readOrders(credential, signal, orderId.trim())) } }}>
          <div className="form-field"><label htmlFor="workshop-order">Numer zlecenia (opcjonalnie)</label><input id="workshop-order" inputMode="numeric" value={orderId} maxLength={16} disabled={read.busy} aria-invalid={!validOrder} onChange={event => { setOrderId(event.target.value); read.clear() }} placeholder="Dodatni numer ID" /></div>
          <button className="button secondary" type="submit" disabled={read.busy || !validOrder}>Odczytaj zlecenia</button>
        </form>
      </div>
      {read.busy && <p className="workshop-caption" role="status">Odczytywanie danych AutoLogiki…</p>}
      {read.error && <div className="app-error" role="alert">{read.error.status === 503 ? requestSource === 'snapshot' ? 'Kopia AutoLogiki jest niedostępna. Przygotuj zgodny snapshot i konfigurację.' : 'Odczyt usługi AutoLogika jest wyłączony lub wymaga konfiguracji adaptera.' : read.error.status === 502 ? 'Nie udało się odczytać usługi AutoLogika. Sprawdź dostępność i konfigurację.' : read.error.message}</div>}
      {!read.value && !read.busy && !read.error && <p className="workshop-caption">Wybierz źródło i wykonaj odczyt. Brak kopii lub połączenia nie jest zastępowany danymi DEMO.</p>}
      <a className="link-button" href="/">Poprzedni panel i laboratoria AutoLogiki</a>
    </section>
    {read.value && <section className="panel workshop-result" aria-labelledby="workshop-result-title">
      <h2 className="panel-heading" id="workshop-result-title">{read.value.kind === 'metadata' ? 'Informacje o kopii' : read.value.kind === 'snapshot' ? LABELS[read.value.value.domain] : 'Zlecenia z usługi'}</h2>
      <p className="workshop-caption">Źródło: {read.value.kind === 'live' ? 'usługa AutoLogika' : 'kopia offline'} · <span className="badge">{read.value.value.mode}</span> · Odczyt: {new Date(read.loadedAt!).toLocaleString('pl-PL')}.</p>
      <p className="workshop-caption">Audytowany commit: {read.value.value.audited_commit}</p>
      {read.value.kind !== 'live' && <><p className="workshop-caption">Utworzono kopię: {new Date(read.value.kind === 'metadata' ? read.value.value.created_at : read.value.value.snapshot_created_at).toLocaleString('pl-PL')}.</p><details className="workshop-details"><summary>Suma kontrolna kopii</summary><p>{read.value.value.sha256}</p></details><p className="workshop-notice">To stan w chwili utworzenia kopii. Nie potwierdza aktualnych terminów ani danych w działającej AutoLogice.</p></>}
      {read.value.kind === 'metadata' && <p className="workshop-caption">Kopia jest dostępna do odczytu. Wybierz domenę w formularzu powyżej.</p>}
      {snapshot && <><SnapshotData value={snapshot} />{pageable && <div className="workshop-pagination"><button className="button subtle" type="button" disabled={read.busy || snapshot.offset === 0} onClick={() => readDomain(Math.max(0, snapshot.offset - PAGE))}>Poprzednia strona danych</button><p className="workshop-caption">Strona {snapshot.offset / PAGE + 1} · do {PAGE} rekordów na kolekcję</p><button className="button subtle" type="button" disabled={read.busy || !hasMore || snapshot.offset + PAGE > 100000} onClick={() => readDomain(snapshot.offset + PAGE)}>Następna strona danych</button></div>}</>}
      {read.value.kind === 'live' && (read.value.value.detail ? <details className="workshop-details" open><summary>Szczegóły zlecenia</summary><pre>{JSON.stringify(read.value.value.data, null, 2).slice(0, 32000)}</pre><p className="workshop-caption">Podgląd szczegółów ograniczony do 32 000 znaków.</p></details> : <Rows rows={read.value.value.data as Record<string, unknown>[]} label="Niewydane zlecenia · maksymalnie 100" />)}
    </section>}
  </div>
}
