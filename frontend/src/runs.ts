import type { AgentEvent, AgentName, AgentOutput } from './api'
import { AGENT_ORDER, TOOL_VERBS } from './agents'
import type { CreatureMood } from './components/Creature'

export interface Handoff {
  index: number
  from: AgentName
  to: AgentName
  task: string
}

export interface AgentView {
  mood: CreatureMood
  line: string | null
  tools: Record<string, number>
  output: AgentOutput | null
  turns: number
  delegatedBy: AgentName | null
}

export interface RunView {
  runId: string
  events: AgentEvent[]
  agents: Record<AgentName, AgentView>
  handoffs: Handoff[]
  active: AgentName | null
  finished: boolean
  tokens: number
  requests: number
}

/** The run_id of the most recent agent run on a ticket. */
export function latestRunId(events: AgentEvent[], ticketId: number): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].ticket_id === ticketId) return events[i].run_id
  }
  return null
}

/** Replay one run's events to work out what each agent is doing and has done. */
export function buildRunView(events: AgentEvent[], runId: string, running: boolean): RunView {
  const runEvents = events.filter(e => e.run_id === runId)
  const agents = Object.fromEntries(
    AGENT_ORDER.map(a => [a, { mood: 'idle', line: null, tools: {}, output: null, turns: 0, delegatedBy: null }]),
  ) as Record<AgentName, AgentView>
  const handoffs: Handoff[] = []
  let active: AgentName | null = null
  let tokens = 0
  let requests = 0

  for (const e of runEvents) {
    const view = agents[e.agent]
    tokens = Math.max(tokens, e.usage?.total_tokens ?? 0)
    requests = Math.max(requests, e.usage?.requests ?? 0)
    if (e.delegated_by) view.delegatedBy = e.delegated_by
    if (e.kind === 'agent_turn') {
      view.mood = 'working'
      view.turns += 1
      active = e.agent
      const calls = e.tools.filter(t => t.tool !== 'final_result')
      for (const t of calls) view.tools[t.tool] = (view.tools[t.tool] ?? 0) + 1
      const handoff = calls.find(t => t.tool === 'delegate')
      if (handoff?.args) {
        const to = handoff.args.to_agent as AgentName
        handoffs.push({ index: e.index, from: e.agent, to, task: String(handoff.args.task ?? '') })
        agents[to].mood = 'working'
        active = to
      }
      view.line = e.said ?? (calls.length ? TOOL_VERBS[calls[0].tool] ?? calls[0].tool : view.line)
    } else if (e.kind === 'end') {
      view.mood = 'done'
      view.output = e.output
      view.line = e.said ?? view.line
      active = e.delegated_by ?? null
    } else if (e.kind === 'error') {
      view.mood = 'done'
      view.line = e.said
    }
  }

  const finished = !running && runEvents.some(e => e.agent === 'boss' && (e.kind === 'end' || e.kind === 'error'))
  if (finished || !running) {
    for (const a of AGENT_ORDER) if (agents[a].mood === 'idle') agents[a].mood = 'benched'
    active = null
  }
  return { runId, events: runEvents, agents, handoffs, active, finished, tokens, requests }
}

export function toolsText(tools: Record<string, number>): string[] {
  return Object.entries(tools)
    .filter(([t]) => t !== 'delegate')
    .map(([t, n]) => (n > 1 ? `${t} ×${n}` : t))
}
