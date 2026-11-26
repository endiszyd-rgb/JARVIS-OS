import { useId, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import './help-tip.css'

const WIDTH = 300
const MARGIN = 12

/** A "?" next to a field: the hint appears on mouse hover, keyboard focus or a tap (phones), kept inside the screen. */
export function HelpTip({ text, topic }: { text: ReactNode; topic: string }) {
  const id = useId()
  const button = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [place, setPlace] = useState<CSSProperties>({})
  const show = () => {
    const rect = button.current?.getBoundingClientRect()
    if (rect && typeof window !== 'undefined') {
      const width = Math.min(WIDTH, window.innerWidth - 2 * MARGIN)
      const left = Math.max(MARGIN, Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width - MARGIN))
      const above = rect.top > 140
      setPlace(above ? { left, width, bottom: window.innerHeight - rect.top + 8 } : { left, width, top: rect.bottom + 8 })
    }
    setOpen(true)
  }
  return <span className={'help-tip' + (open ? ' is-open' : '')} onMouseEnter={show} onMouseLeave={() => setOpen(false)}>
    <button ref={button} type="button" className="help-tip-button" aria-label={'Podpowiedź: ' + topic} aria-describedby={id} aria-expanded={open}
      onClick={show} onFocus={show} onBlur={() => setOpen(false)} onKeyDown={event => { if (event.key === 'Escape') setOpen(false) }}>?</button>
    <span role="tooltip" id={id} className="help-tip-bubble" style={place}>{text}</span>
  </span>
}

/** Label with an optional "?" hint, used by every settings form. */
export function FieldLabel({ htmlFor, help, children }: { htmlFor: string; help?: ReactNode; children: string }) {
  return <span className="field-label"><label htmlFor={htmlFor}>{children}</label>{help && <HelpTip text={help} topic={children} />}</span>
}
