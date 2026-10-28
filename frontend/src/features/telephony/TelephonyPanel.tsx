import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, CircleAlert, Eye, Phone, RefreshCw, Save } from 'lucide-react'
import { ApiError } from '../../api'
import { aware, days, fromDraft, InputError, previewPolicy, readPolicy, savePolicy, toDraft } from './api'
import type { Decision, Draft, SavedPolicy, Situation } from './api'
import './telephony.css'

export interface TelephonyPanelProps { credential: string; onUnauthorized: () => void }
const reasons: Record<string, string> = { disabled: 'Przekazywanie wyłączone', do_not_disturb: 'Nie przeszkadzać', date_exception: 'Urlop lub wyjątek w kalendarzu', outside_hours: 'Poza godzinami dostępności', escalation_not_justified: 'Asystent powinien najpierw obsłużyć sprawę', escalation_within_hours: 'Uzasadniona eskalacja w godzinach dostępności' }
const failureMessage = (failure: unknown) => failure instanceof InputError ? failure.message : failure instanceof ApiError ? failure.status === 409 ? 'Zasady zmieniły się. Wczytaj je ponownie przed następnym zapisem; nie nadpisano nowszej wersji.' : failure.status === 422 ? 'Zasady lub termin wymagają poprawienia. Sprawdź numery, godziny, wyjątki i strefę czasową.' : failure.message : 'Nie udało się wykonać operacji. Sprawdź zapisany stan przed kolejną próbą.'
export function TelephonyPanel(props: TelephonyPanelProps) { return <TelephonyWorkspace key={props.credential} {...props} /> }
function TelephonyWorkspace({ credential, onUnauthorized }: TelephonyPanelProps) {
  const [saved, setSaved] = useState<SavedPolicy | null>(null), [draft, setDraft] = useState<Draft | null>(null)
  const [at, setAt] = useState(''), [situation, setSituation] = useState<Situation>('routine'), [decision, setDecision] = useState<Decision | null>(null)
  const [busy, setBusy] = useState(false), [conflict, setConflict] = useState(false), [authorized, setAuthorized] = useState(true)
  const [error, setError] = useState<string | null>(null), [notice, setNotice] = useState<string | null>(null)
  const pending = useRef<AbortController | null>(null), epoch = useRef(0), mounted = useRef(true), expired = useRef(false)
  const callback = useRef(onUnauthorized); callback.current = onUnauthorized
  const begin = () => { pending.current?.abort(); const controller = new AbortController(), id = ++epoch.current; pending.current = controller; setBusy(true); setError(null); setNotice(null); return { controller, id } }
  const valid = (id: number, controller: AbortController) => mounted.current && !expired.current && epoch.current === id && !controller.signal.aborted
  const failed = (failure: unknown, id: number, controller: AbortController) => {
    if (!valid(id, controller) || failure instanceof DOMException && failure.name === 'AbortError') return
    if (failure instanceof ApiError && failure.status === 401) {
      expired.current = true; ++epoch.current; pending.current?.abort(); pending.current = null
      setSaved(null); setDraft(null); setDecision(null); setAt(''); setError(null); setNotice(null); setAuthorized(false); callback.current()
    } else { if (failure instanceof ApiError && failure.status === 409) setConflict(true); setError(failureMessage(failure)) }
  }
  const finish = (id: number, controller: AbortController) => { if (valid(id, controller)) { setBusy(false); pending.current = null } }
  async function load() {
    const { controller, id } = begin(); setDecision(null)
    try { const result = await readPolicy(credential, controller.signal); if (valid(id, controller)) { setSaved(result); setDraft(toDraft(result.policy)); setConflict(false) } }
    catch (failure) { failed(failure, id, controller) } finally { finish(id, controller) }
  }
  useEffect(() => {
    mounted.current = true; expired.current = false; void load()
    return () => { mounted.current = false; ++epoch.current; pending.current?.abort(); pending.current = null }
  }, [credential])
  const edit = (patch: Partial<Draft>) => { setDraft(current => current ? { ...current, ...patch } : null); setDecision(null); setNotice(null) }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!saved || !draft || busy || conflict) return
    let policy
    try { policy = fromDraft(draft) } catch (failure) { setError(failureMessage(failure)); return }
    const current = saved, { controller, id } = begin(); setDecision(null)
    try { const result = await savePolicy(credential, current, policy, controller.signal); if (valid(id, controller)) { setSaved(result); setDraft(toDraft(result.policy)); setNotice('Zapisano zasady. Nie wykonano połączenia.') } }
    catch (failure) { failed(failure, id, controller) } finally { finish(id, controller) }
  }
  async function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!saved || busy) return
    if (at.trim() && !aware(at.trim())) { setError('Termin podglądu wymaga poprawnej daty i przesunięcia strefy, np. +01:00.'); return }
    const { controller, id } = begin(); setDecision(null)
    try { const result = await previewPolicy(credential, at, situation, controller.signal); if (valid(id, controller)) setDecision(result) }
    catch (failure) { failed(failure, id, controller) } finally { finish(id, controller) }
  }
  if (!authorized) return <p role="status">Sesja zakończona. Połącz się ponownie.</p>
  return <div className="telephony-feature" aria-busy={busy}>
    <section className="panel telephony-intro"><h2 className="panel-heading"><Phone aria-hidden="true" />Zasady dostępności</h2><p className="panel-description">JARVIS ma obsługiwać klientów jako pierwszy. Kontakt do właściciela wymaga uzasadnionej eskalacji, dostępności i osobnej akceptacji. Ten panel zapisuje lokalne zasady i sprawdza decyzję.</p><span className="badge tone-warning">Operator niepodłączony</span><p className="telephony-caption">Nie aktywuje przekierowania Play, połączeń, wiadomości ani wysyłki powiadomień.</p></section>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="telephony-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <section className="panel" aria-labelledby="telephony-policy-title"><div className="telephony-heading"><div><h2 className="panel-heading" id="telephony-policy-title">Przekazywanie do właściciela</h2><p className="panel-description">Czas polski: Europe/Warsaw, z automatyczną zmianą czasu. {saved && <>Zapisana wersja: {saved.revision}.</>}</p></div><button className="button secondary" type="button" disabled={busy} onClick={() => { void load() }}><RefreshCw aria-hidden="true" />Wczytaj zasady ponownie</button></div>
      <p className="telephony-caption">Ponowne wczytanie zastępuje niezapisane zmiany formularza.</p>
      {!draft ? <p className="telephony-caption" role="status">{busy ? 'Odczytywanie zasad…' : 'Zasady są chwilowo niedostępne.'}</p> : <form className="telephony-form" onSubmit={event => { void save(event) }}>
        <label className="telephony-checkbox telephony-wide"><input type="checkbox" checked={draft.enabled} disabled={busy} onChange={event => edit({ enabled: event.target.checked })} />Zezwalaj na przekazywanie</label>
        <div className="form-field"><label htmlFor="phone-owner">Numer właściciela</label><input id="phone-owner" type="tel" value={draft.owner} maxLength={16} disabled={busy} onChange={event => edit({ owner: event.target.value })} autoComplete="off" placeholder="+48…" /><small>Drugi numer, pod którym właściciel może przyjąć kontakt.</small></div>
        <div className="form-field"><label htmlFor="phone-workshop">Numer warsztatu</label><input id="phone-workshop" type="tel" value={draft.workshop} maxLength={16} disabled={busy} onChange={event => edit({ workshop: event.target.value })} autoComplete="off" placeholder="+48…" /></div>
        <fieldset className="telephony-week telephony-wide"><legend>Godziny dostępności</legend><p className="telephony-caption">Format: 08:00-12:00, 13:00-18:00. Puste pole oznacza brak dostępności. Do 8 przedziałów dziennie; przez północ rozdziel je na dwa dni, koniec dnia to 24:00.</p><div className="telephony-days">{days.map((day, weekday) => <div className="form-field" key={day}><label htmlFor={'phone-day-' + weekday}>{day}</label><input id={'phone-day-' + weekday} value={draft.hours[weekday]} maxLength={120} disabled={busy} onChange={event => edit({ hours: draft.hours.map((hours, index) => index === weekday ? event.target.value : hours) })} placeholder="08:00-18:00" autoComplete="off" /></div>)}</div></fieldset>
        <div className="form-field telephony-wide"><label htmlFor="phone-exceptions">Urlopy i wyjątki</label><textarea id="phone-exceptions" value={draft.exceptions} maxLength={13000} disabled={busy} onChange={event => edit({ exceptions: event.target.value })} placeholder="2026-12-24..2026-12-26 | Urlop" /><small>Jeden dzień lub zakres dat w wierszu, opcjonalnie | opis. Wyjątki obejmują całe dni. Święta nie są dodawane automatycznie.</small></div>
        <label className="telephony-checkbox telephony-wide"><input type="checkbox" checked={draft.dnd} disabled={busy} onChange={event => edit({ dnd: event.target.checked })} />Nie przeszkadzać</label>
        <div className="form-field telephony-wide"><label htmlFor="phone-dnd-until">Nie przeszkadzać do</label><input id="phone-dnd-until" value={draft.until} maxLength={60} disabled={busy} onChange={event => edit({ until: event.target.value })} placeholder="2026-10-28T18:00:00+01:00" autoComplete="off" /><small>Opcjonalny termin ze strefą, np. +01:00 zimą, +02:00 latem. Ręczne Nie przeszkadzać działa do wyłączenia niezależnie od tego terminu.</small></div>
        <p className="telephony-caption telephony-wide">Kryzys nie omija godzin, urlopu ani Nie przeszkadzać. Poza dostępnością: zapis sprawy i przygotowanie powiadomienia. Brak odpowiedzi właściciela: prośba o oddzwonienie, bez obietnicy godziny.</p>
        <button className="button primary telephony-save" type="submit" disabled={busy || conflict}><Save aria-hidden="true" />Zapisz zasady</button>
      </form>}
    </section>
    <section className="panel" aria-labelledby="telephony-preview-title"><h2 className="panel-heading" id="telephony-preview-title"><Eye aria-hidden="true" />Sprawdź decyzję JARVIS-a</h2><p className="panel-description">Podgląd korzysta z aktualnie zapisanych zasad po stronie serwera. Pomija niezapisane zmiany formularza i nie analizuje nagrania.</p><form className="telephony-form" onSubmit={event => { void preview(event) }}>
      <div className="form-field telephony-wide"><label htmlFor="phone-preview-at">Termin podglądu ze strefą</label><input id="phone-preview-at" value={at} maxLength={60} disabled={busy} onChange={event => { setAt(event.target.value); setDecision(null) }} placeholder="Puste = teraz; np. 2026-10-28T10:00:00+01:00" autoComplete="off" /></div>
      <div className="form-field telephony-wide"><label htmlFor="phone-preview-situation">Przykładowa sytuacja</label><select id="phone-preview-situation" value={situation} disabled={busy} onChange={event => { setSituation(event.target.value as Situation); setDecision(null) }}><option value="routine">Zwykła sprawa</option><option value="contact_requested">Pierwsza prośba o właściciela</option><option value="insistent">Klient ponawia żądanie i odrzuca pomoc</option><option value="crisis">Sprawa kryzysowa</option></select></div>
      <button className="button secondary" type="submit" disabled={!saved || busy}><Eye aria-hidden="true" />Sprawdź decyzję</button>
    </form>
      {decision && <div className="telephony-decision" role="status"><h3>{decision.action === 'request_owner_acceptance' ? 'Można poprosić właściciela o przyjęcie kontaktu' : decision.action === 'continue_reception' ? 'JARVIS kontynuuje obsługę' : 'Zapis sprawy i przygotowanie powiadomienia'}</h3><ul>{decision.reasons.map((reason, index) => <li key={index}>{reasons[reason] ?? reason}</li>)}</ul><p>Czas w Polsce: {decision.local_time}. Wersja zasad: {decision.revision}.</p><p>Właściciel zawsze musi osobno zaakceptować kontakt.</p><strong>Podgląd — nie wykonano połączenia ani wysyłki.</strong>{decision.emergency_services_notice && <p>Przy bezpośrednim zagrożeniu życia kontakt z właścicielem nie zastępuje służb ratunkowych.</p>}</div>}
    </section>
    <section className="panel"><h2 className="panel-heading">Recepcja i transport</h2><p className="panel-description">Dotychczasowy panel zachowuje osobne laboratoria recepcji i transportu. Symulacje tekstowe nie są połączeniami z operatorem ani rozmową audio.</p><a className="link-button" href="/">Otwórz dotychczasowy panel</a></section>
  </div>
}
