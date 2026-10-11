import { AGENTS, AGENT_ORDER } from '../agents'
import type { RunView } from '../runs'
import { toolsText } from '../runs'
import { Creature } from './Creature'

interface Props {
  view: RunView | null
  ticketId: number | null
}

export function ShiftReport({ view, ticketId }: Props) {
  if (!view || !view.finished) {
    return (
      <section className="panel report" aria-label="Shift report">
        <div className="panel-head"><h2>Shift report</h2></div>
        <p className="empty">
          {ticketId === null ? 'Pick a ticket.' : `After the crew finishes ticket #${ticketId}, each agent hands in a one-card summary here.`}
        </p>
      </section>
    )
  }
  const boss = view.agents.boss.output
  const worked = AGENT_ORDER.filter(a => view.agents[a].mood === 'done')
  const benched = AGENT_ORDER.filter(a => view.agents[a].mood === 'benched')

  return (
    <section className="panel report" aria-label="Shift report">
      <div className="panel-head">
        <h2>Shift report · ticket #{ticketId}</h2>
        <span className="muted">run {view.runId.slice(0, 6)} · {(view.tokens / 1000).toFixed(1)}k tokens</span>
      </div>

      {boss?.decision && (
        <div className="verdict">
          <span className="verdict-label">Boss’s call</span>
          <p>{boss.decision}</p>
        </div>
      )}

      <div className="report-grid">
        {worked.map(name => {
          const meta = AGENTS[name]
          const a = view.agents[name]
          const out = a.output
          const approvals = out?.approval_ids ?? out?.human_approvals_needed ?? []
          const drafts = out?.draft_ids ?? []
          return (
            <article key={name} className="report-card" style={{ ['--c' as string]: meta.color }}>
              <header>
                <Creature agent={name} size={44} mood="done" />
                <div>
                  <strong>{meta.label}</strong>
                  {a.delegatedBy && <span className="muted"> · asked by {AGENTS[a.delegatedBy].label}</span>}
                </div>
              </header>
              <p className="report-summary">{name === 'boss' ? (out?.next_steps?.length ? out.next_steps.join(' ') : 'Routed the ticket, checked the numbers and set the status.') : out?.summary ?? a.line}</p>
              {out?.actions_taken && out.actions_taken.length > 0 && (
                <ul className="report-actions">
                  {out.actions_taken.slice(0, 4).map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              )}
              <div className="report-meta">
                {approvals.length > 0 && <span className="tag tag-appr">🖊 {approvals.length} for approval</span>}
                {drafts.length > 0 && <span className="tag tag-draft">✉ {drafts.length} draft</span>}
                {out?.ticket_status && <span className="tag">status → {out.ticket_status.replace(/_/g, ' ')}</span>}
              </div>
              <div className="report-tools">
                {toolsText(a.tools).map(t => <code key={t}>{t}</code>)}
              </div>
            </article>
          )
        })}
      </div>
      {benched.length > 0 && (
        <p className="benched">
          Sat this one out: {benched.map(b => AGENTS[b].label).join(', ')}. The Boss didn’t need them.
        </p>
      )}
    </section>
  )
}
