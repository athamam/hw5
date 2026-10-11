import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, API_URL } from './api'
import type { AgentEvent, Approval, Cash, RunResult, Ticket } from './api'
import { money } from './agents'
import { buildRunView, latestRunId } from './runs'
import { TicketBoard } from './components/TicketBoard'
import { AgentFloor } from './components/AgentFloor'
import { LiveFeed } from './components/LiveFeed'
import { ShiftReport } from './components/ShiftReport'
import { CashPiggy } from './components/CashPiggy'
import { ApprovalTray } from './components/ApprovalTray'
import { Creature } from './components/Creature'

interface Toast {
  id: number
  tone: 'ok' | 'warn' | 'bad'
  text: string
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [model, setModel] = useState<string>('')
  const [online, setOnline] = useState<boolean | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [running, setRunning] = useState<number | null>(null)
  const [runStart, setRunStart] = useState<number>(-1)
  const [justFinished, setJustFinished] = useState<Set<number>>(new Set())
  const [toasts, setToasts] = useState<Toast[]>([])
  const [hearts, setHearts] = useState(0)
  const [signer, setSigner] = useState(() => localStorage.getItem('cc-signer') ?? '')
  const lastIndex = useRef(-1)

  const toast = useCallback((tone: Toast['tone'], text: string) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, tone, text }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6500)
  }, [])

  const refreshBoard = useCallback(async () => {
    const [t, a, c] = await Promise.all([api.tickets(), api.approvals(), api.cash()])
    setTickets(t.tickets)
    setApprovals(a.approvals)
    setCash(c)
    setSelected(s => s ?? t.tickets[0]?.id ?? null)
    if (t.running_ticket !== null) setRunning(r => r ?? t.running_ticket)
    return t.tickets
  }, [])

  const pollEvents = useCallback(async () => {
    const res = await api.events(lastIndex.current)
    if (res.events.length) {
      lastIndex.current = Math.max(lastIndex.current, res.events[res.events.length - 1].index)
      // Two polls can overlap (React dev mode runs effects twice), so merge by event index.
      setEvents(prev => {
        const seen = prev.length ? prev[prev.length - 1].index : -1
        const fresh = res.events.filter(e => e.index > seen)
        return fresh.length ? [...prev, ...fresh] : prev
      })
    }
    return res.last_index
  }, [])

  // First load.
  useEffect(() => {
    ;(async () => {
      try {
        const h = await api.health()
        setModel(h.model)
        setOnline(true)
        await Promise.all([refreshBoard(), pollEvents()])
      } catch {
        setOnline(false)
      }
    })()
  }, [refreshBoard, pollEvents])

  // Poll fast while the crew works, slowly otherwise.
  useEffect(() => {
    if (online === false) return
    const id = setInterval(() => {
      pollEvents().catch(() => setOnline(false))
      if (running !== null) api.cash().then(setCash).catch(() => {})
      else refreshBoard().catch(() => {}) // pick up changes made elsewhere (another tab, a reset)
    }, running !== null ? 1200 : 6000)
    return () => clearInterval(id)
  }, [running, online, pollEvents, refreshBoard])

  const startRun = async (id: number) => {
    setSelected(id)
    setRunStart(lastIndex.current)
    setRunning(id)
    setJustFinished(s => { const n = new Set(s); n.delete(id); return n })
    toast('ok', `Crew dispatched on ticket #${id}. The Boss is reading it now.`)
    try {
      const result: RunResult = await api.run(id)
      await pollEvents()
      const after = await refreshBoard()
      const status = after.find(t => t.id === id)?.status
      setJustFinished(s => new Set(s).add(id))
      if (result.error) toast('bad', `Run stopped: ${result.error}`)
      else if (status === 'resolved') {
        setHearts(h => h + 1)
        toast('ok', `Ticket #${id} resolved! 🎀`)
      } else {
        const n = result.decision?.human_approvals_needed?.length ?? 0
        toast('warn', `Ticket #${id}: crew is done. ${n ? `${n} request${n > 1 ? 's need' : ' needs'} your signature.` : ''}`)
      }
    } catch (e) {
      toast('bad', `Could not run ticket #${id}: ${(e as Error).message}`)
    } finally {
      setRunning(null)
    }
  }

  const approve = async (a: Approval) => {
    try {
      const before = cash?.balance ?? 0
      const res = await api.approve(a.id, signer.trim())
      await refreshBoard()
      if (a.kind === 'payment') toast('ok', `Paid ${money(a.amount)}. Checking went ${money(before)} → ${money(res.cash_balance)}.`)
      else toast('ok', `Approved #${a.id}. No cash moved.`)
    } catch (e) {
      toast('bad', (e as Error).message)
      throw e
    }
  }

  const reject = async (a: Approval, reason: string) => {
    try {
      await api.reject(a.id, signer.trim(), reason)
      await refreshBoard()
      toast('warn', `Rejected #${a.id}.`)
    } catch (e) {
      toast('bad', (e as Error).message)
      throw e
    }
  }

  const reset = async () => {
    if (!window.confirm('Reset the shop database to the original values? Cash goes back to $3,400 and all three tickets reopen. The audit trail is kept.')) return
    try {
      await api.reset()
      await refreshBoard()
      setJustFinished(new Set())
      toast('ok', 'Fresh start: database restored from the original.')
    } catch (e) {
      toast('bad', (e as Error).message)
    }
  }

  const setSignerSaved = (v: string) => {
    setSigner(v)
    localStorage.setItem('cc-signer', v)
  }

  // The run shown on the floor: the live one, or the latest finished run for the selected ticket.
  const view = useMemo(() => {
    if (selected === null) return null
    if (running === selected) {
      const fresh = events.filter(e => e.index > runStart && e.ticket_id === selected)
      return fresh.length ? buildRunView(fresh, fresh[0].run_id, true) : null
    }
    const runId = latestRunId(events, selected)
    return runId ? buildRunView(events, runId, false) : null
  }, [events, selected, running, runStart])

  const pendingCount = approvals.filter(a => a.status === 'pending').length
  const isLive = running !== null && running === selected

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><Creature agent="boss" size={46} /></div>
          <div>
            <h1>Campus Customs <span>Pink Desk</span></h1>
            <p>Multi-agent operations · shop date <b>{cash?.as_of ?? '…'}</b></p>
          </div>
        </div>
        <div className="topbar-right">
          <span className={`conn ${online ? 'on' : online === false ? 'off' : ''}`}>
            {online === false ? `Backend offline (${API_URL})` : online ? 'Backend live' : 'Connecting…'}
          </span>
          {model && <span className="model-chip">🧠 {model}</span>}
          {pendingCount > 0 && <span className="pending-chip">🖊 {pendingCount} awaiting you</span>}
          <span className="cash-chip">{cash ? money(cash.balance) : '…'}</span>
          <button className="btn btn-ghost" onClick={reset} disabled={running !== null}>↺ Reset shop</button>
        </div>
      </header>

      {online === false && (
        <div className="offline">
          Can’t reach the backend at <code>{API_URL}</code>. Start it from <code>backend/</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>, then refresh.
        </div>
      )}

      <main className="layout">
        <TicketBoard
          tickets={tickets}
          selected={selected}
          running={running}
          justFinished={justFinished}
          onSelect={setSelected}
          onRun={startRun}
        />

        <div className="center">
          <AgentFloor view={view} running={isLive} ticketId={selected} />
          <LiveFeed events={view?.events ?? []} running={isLive} />
          <ShiftReport view={view} ticketId={selected} />
        </div>

        <aside className="side">
          <CashPiggy cash={cash} approvals={approvals} />
          <ApprovalTray
            approvals={approvals}
            signer={signer}
            onSignerChange={setSignerSaved}
            onApprove={approve}
            onReject={reject}
          />
        </aside>
      </main>

      <div className="toasts" role="status">
        {toasts.map(t => <div key={t.id} className={`toast toast-${t.tone}`}>{t.text}</div>)}
      </div>

      {hearts > 0 && (
        <div className="hearts" key={hearts} aria-hidden>
          {Array.from({ length: 18 }, (_, i) => (
            <span key={i} style={{ left: `${(i * 37) % 100}%`, animationDelay: `${(i % 6) * 0.12}s` }}>♥</span>
          ))}
        </div>
      )}

      <footer className="foot">
        Agents prepare · humans approve · nothing is emailed or sent · every step is written to <code>output/audit_trail.json</code>
      </footer>
    </div>
  )
}
