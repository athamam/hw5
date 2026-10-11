import { AGENTS, AGENT_ORDER } from '../agents'
import type { RunView } from '../runs'
import { Creature } from './Creature'

interface Props {
  view: RunView | null
  running: boolean
  ticketId: number | null
}

const MOOD_LABEL = { idle: 'Ready', working: 'On it', done: 'Done', benched: 'Not needed' } as const
const TOKEN_LIMIT = 200_000
const REQUEST_LIMIT = 40

const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)

export function AgentFloor({ view, running, ticketId }: Props) {
  const tokens = view?.tokens ?? 0
  const pct = Math.min(100, (tokens / TOKEN_LIMIT) * 100)
  return (
    <section className="panel floor" aria-label="Agent floor">
      <div className="panel-head">
        <h2>The crew {ticketId !== null && <span className="muted">· ticket #{ticketId}</span>}</h2>
        <div className="fuel" title={`Token guard: ${tokens.toLocaleString()} of ${TOKEN_LIMIT.toLocaleString()} tokens`}>
          <span className="fuel-label">Token guard</span>
          <span className="fuel-bar"><span style={{ width: `${pct}%` }} /></span>
          <span className="fuel-num">
            {(tokens / 1000).toFixed(1)}k / {TOKEN_LIMIT / 1000}k · {view?.requests ?? 0}/{REQUEST_LIMIT} calls
          </span>
        </div>
      </div>

      <div className="handoff-trail" aria-label="Hand-offs">
        {view && view.handoffs.length > 0 ? (
          view.handoffs.map(h => (
            <span key={h.index} className="handoff" title={h.task}>
              <b style={{ color: AGENTS[h.from].color }}>{AGENTS[h.from].label}</b>
              <span className="plane" aria-hidden>✈</span>
              <b style={{ color: AGENTS[h.to].color }}>{AGENTS[h.to].label}</b>
            </span>
          ))
        ) : (
          <span className="muted">{running ? 'Boss is reading the ticket…' : 'Pick a ticket and start the crew. Hand-offs appear here.'}</span>
        )}
      </div>

      <div className="desks">
        {AGENT_ORDER.map(name => {
          const meta = AGENTS[name]
          const a = view?.agents[name]
          const mood = a?.mood ?? 'idle'
          const isActive = running && view?.active === name
          return (
            <div key={name} className={`desk mood-${mood} ${isActive ? 'is-active' : ''}`} style={{ ['--c' as string]: meta.color }}>
              <div className={`bubble ${a?.line ? '' : 'bubble-empty'}`} aria-live={isActive ? 'polite' : 'off'}>
                {isActive && <span className="typing"><i /><i /><i /></span>}
                {a?.line ? clip(a.line, 150) : mood === 'benched' ? 'Sat this one out.' : meta.role}
              </div>
              <Creature agent={name} size={86} mood={isActive ? 'working' : mood === 'working' ? 'idle' : mood} />
              <div className="desk-top" />
              <div className="nameplate">
                <strong>{meta.label}</strong>
                <span>“{meta.nickname}”</span>
              </div>
              {(() => {
                const waiting = running && !isActive && mood === 'working'
                const chip = isActive ? 'working' : waiting ? 'waiting' : mood
                const label = isActive ? 'Working…' : waiting ? 'Waiting on a teammate' : MOOD_LABEL[mood]
                return <span className={`mood-chip mood-chip-${chip}`}>{label}</span>
              })()}
            </div>
          )
        })}
      </div>
    </section>
  )
}
