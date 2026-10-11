import type { Ticket } from '../api'
import { TICKET_ICONS } from '../agents'

interface Props {
  tickets: Ticket[]
  selected: number | null
  running: number | null
  canRun: boolean
  readyToClose: Set<number>
  justFinished: Set<number>
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_on_human: 'Waiting on you',
  resolved: 'Resolved',
}

function ticketLine(t: Ticket): string {
  if (t.sku) return `${t.sku}${t.size ? ` · size ${t.size}` : ''}${t.qty ? ` · qty ${t.qty}` : ''}`
  if (t.lease_id) return `Lease #${t.lease_id}`
  return t.type
}

export function TicketBoard({ tickets, selected, running, canRun, readyToClose, justFinished, onSelect, onRun }: Props) {
  return (
    <section className="panel tickets" aria-label="Tickets">
      <div className="panel-head">
        <h2>Ticket rail</h2>
        <span className="muted">{tickets.filter(t => !t.is_resolved).length} open</span>
      </div>
      <ol className="ticket-list">
        {tickets.map(t => {
          const isSel = t.id === selected
          const isRun = t.id === running
          const closeOut = readyToClose.has(t.id)
          return (
            <li key={t.id}>
              <article
                className={`ticket status-${t.status} ${isSel ? 'is-selected' : ''} ${isRun ? 'is-running' : ''}`}
                onClick={() => onSelect(t.id)}
                onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onSelect(t.id)}
                tabIndex={0}
                aria-pressed={isSel}
              >
                <div className="ticket-stub">
                  <span className="ticket-no">#{t.id}</span>
                  <span className="ticket-icon" aria-hidden>{TICKET_ICONS[t.type] ?? '📋'}</span>
                </div>
                <div className="ticket-body">
                  <div className="ticket-top">
                    <h3>{t.subject}</h3>
                    <span className={`pill pill-${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
                  </div>
                  <p className="ticket-from">from <strong>{t.requester}</strong></p>
                  <p className="ticket-line">{ticketLine(t)}</p>
                  {t.notes && <p className="ticket-note">“{t.notes}”</p>}
                  {closeOut && !isRun && <p className="closeout-hint">✍ All requests signed. Let the Boss close it out.</p>}
                  <div className="ticket-foot">
                    <button
                      className={`btn btn-run ${closeOut ? 'btn-closeout' : ''}`}
                      disabled={running !== null || !canRun}
                      title={!canRun ? 'Add PORTKEY_API_KEY to .env to run the agents' : closeOut ? 'All approvals are decided: the Boss checks them and resolves the ticket' : undefined}
                      onClick={e => {
                        e.stopPropagation()
                        onRun(t.id)
                      }}
                    >
                      {isRun ? <><span className="spinner" /> Crew at work…</> : t.status === 'open' ? '▶ Start the crew' : closeOut ? '✔ Close out' : '↻ Run again'}
                    </button>
                    {(t.status === 'resolved' || t.status === 'waiting_on_human') && (
                      <div className={`stamp ${t.status === 'resolved' ? 'stamp-resolved' : 'stamp-waiting'} ${justFinished.has(t.id) ? 'stamp-new' : ''}`}>
                        {t.status === 'resolved' ? 'Resolved ✓' : <>Crew done<br />needs your OK</>}
                      </div>
                    )}
                  </div>
                </div>
              </article>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
