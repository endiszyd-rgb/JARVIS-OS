import { useState } from 'react'
import { Home, RefreshCw } from 'lucide-react'
import { ENTITY, readHome } from './api'
import type { HomeRead } from './api'
import { useRead } from './useRead'
import type { ReadProps } from './useRead'
import './home.css'

export function HomePanel(props: ReadProps) { return <HomeWorkspace key={props.credential} {...props} /> }
function HomeWorkspace(props: ReadProps) {
  const read = useRead<HomeRead>(props)
  const [entity, setEntity] = useState('')
  const trimmed = entity.trim(), valid = !trimmed || ENTITY.test(trimmed)
  return <section className="panel home-panel" aria-labelledby="home-title" aria-busy={read.busy}>
    <h2 className="panel-heading" id="home-title"><Home aria-hidden="true" />Dom i czujniki</h2>
    <p className="panel-description">Odczyt stanów Home Assistant z listy dozwolonych encji. Połączenie z usługą następuje dopiero po naciśnięciu przycisku. Sterowanie światłem, scenami i bramą jest niedostępne.</p>
    <form className="home-read-form" onSubmit={event => { event.preventDefault(); if (valid && !read.busy) void read.run((credential, signal) => readHome(credential, signal, trimmed)) }}>
      <div className="form-field"><label htmlFor="home-entity">Encja Home Assistant (opcjonalnie)</label><input id="home-entity" value={entity} maxLength={200} onChange={event => { setEntity(event.target.value); read.clear() }} placeholder="sensor.temperatura" aria-invalid={!valid} />
        <small>Puste pole odczytuje wszystkie dozwolone encje. Format: sensor.temperatura; dostęp kontroluje backend.</small></div>
      <button className="button secondary" type="submit" disabled={read.busy || !valid}><RefreshCw aria-hidden="true" />Odczytaj stany</button>
    </form>
    {read.busy && <p className="home-caption" role="status">Odczytywanie Home Assistant…</p>}
    {read.error && <div className="app-error" role="alert">{read.error.status === 503 ? 'Odczyt Home Assistant jest wyłączony lub wymaga konfiguracji.' : read.error.status === 403 ? 'Ta encja lub funkcja jest poza dozwolonym zakresem.' : read.error.status === 502 ? 'Nie udało się odczytać Home Assistant. Sprawdź usługę i konfigurację.' : read.error.message}</div>}
    {read.value ? <>
      <p className="home-caption">Źródło: Home Assistant · <span className="badge">live_readonly</span> · Odczyt: {new Date(read.loadedAt!).toLocaleString('pl-PL')}. Wynik nie potwierdza sterowania urządzeniami.</p>
      {!read.value.states.length && <p className="home-empty">Brak dozwolonych encji w odpowiedzi usługi.</p>}
      <ul className="home-states" aria-label="Odczytane stany">{read.value.states.map((row, index) => <li className="home-state" key={row.entity_id + index}>
        <div><h3>{row.attributes.friendly_name || row.entity_id}</h3><p className="home-caption">{row.entity_id}</p></div>
        <p className="home-state-value">{row.state}<span>{row.attributes.unit_of_measurement || ''}</span></p>
      </li>)}</ul>
    </> : !read.busy && !read.error && <p className="home-empty">Nie wykonano jeszcze odczytu. Dane demonstracyjne nie zastępują odpowiedzi usługi.</p>}
    <a className="link-button" href="/">Otwórz poprzedni panel i laboratoria</a>
  </section>
}
