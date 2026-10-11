import { useEffect, useRef } from 'react'
import type { AgentEvent } from '../api'
import { AGENTS, TOOL_VERBS } from '../agents'
import { Creature } from './Creature'

interface Props {
  events: AgentEvent[]
  running: boolean
}

function argText(args: Record<string, unknown> | undefined): string {
  if (!args) return ''
  return Object.entries(args)
    .filter(([k, v]) => v !== null && v !== undefined && k !== 'task' && k !== 'body' && k !== 'note' && k !== 'reason' && k !== 'resolution')
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
}

export function LiveFeed({ events, running }: Props) {
  const endRef = useRef<HTMLDivElement>(null)
  const shown = events.filter(e => e.kind !== 'tool_results')

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [shown.length])

  return (
    <section className="panel feed" aria-label="Live feed">
      <div className="panel-head">
        <h2>Live chatter {running && <span className="live-dot">LIVE</span>}</h2>
        <span className="muted">{shown.length} moments</span>
      </div>
      <div className="feed-scroll" role="log" aria-live="polite">
        {shown.length === 0 && <p className="empty">Nothing yet. When the crew starts, every thought and tool call shows up here.</p>}
        {shown.map(e => {
          const meta = AGENTS[e.agent]
          const calls = e.tools.filter(t => t.tool !== 'final_result')
          const handoff = calls.find(t => t.tool === 'delegate')
          return (
            <div key={e.index} data-i={e.index} className={`line line-${e.kind}`} style={{ ['--c' as string]: meta.color, marginLeft: `${Math.min(e.depth, 3) * 18}px` }}>
              <div className="line-avatar"><Creature agent={e.agent} size={34} /></div>
              <div className="line-main">
                <div className="line-who">
                  <strong>{meta.label}</strong>
                  {e.delegated_by && <span className="muted"> for {AGENTS[e.delegated_by].label}</span>}
                  <time>{new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
                </div>
                {e.kind === 'end' && <div className="line-said said-final">🏁 {e.said ?? 'Finished.'}</div>}
                {e.kind === 'error' && <div className="line-said said-error">⚠ {e.said}</div>}
                {e.kind === 'agent_turn' && e.said && <div className="line-said">{e.said}</div>}
                {handoff && (
                  <div className="line-handoff">
                    ✈ Hands off to <b style={{ color: AGENTS[handoff.args?.to_agent as keyof typeof AGENTS]?.color }}>
                      {AGENTS[handoff.args?.to_agent as keyof typeof AGENTS]?.label}
                    </b>
                    : <em>{String(handoff.args?.task ?? '')}</em>
                  </div>
                )}
                {calls.filter(t => t.tool !== 'delegate').length > 0 && (
                  <div className="chips">
                    {calls.filter(t => t.tool !== 'delegate').map((t, i) => (
                      <span key={i} className="tool-chip" title={JSON.stringify(t.args ?? {})}>
                        <span className="tool-verb">{TOOL_VERBS[t.tool] ?? 'Using a tool'}</span>
                        <code>{t.tool}({argText(t.args)})</code>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )
        })}
        {running && (
          <div className="line line-thinking">
            <span className="typing"><i /><i /><i /></span> the crew is thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>
    </section>
  )
}
