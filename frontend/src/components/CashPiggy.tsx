import { useEffect, useRef, useState } from 'react'
import type { Approval, Cash } from '../api'
import { money } from '../agents'

interface Props {
  cash: Cash | null
  approvals: Approval[]
}

const OPENING = 3400

/** Smoothly count from the old balance to the new one. */
function useTween(target: number, ms = 1200) {
  const [value, setValue] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = performance.now()
    const begin = from.current
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(begin + (target - begin) * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    // Browsers pause animation frames in hidden tabs; make sure the real number always lands.
    const settle = setTimeout(() => {
      setValue(target)
      from.current = target
    }, ms + 150)
    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(settle)
    }
  }, [target, ms])
  return value
}

export function CashPiggy({ cash, approvals }: Props) {
  const balance = cash?.balance ?? 0
  const shown = useTween(balance)
  const prev = useRef<number | null>(null)
  const [dropKey, setDropKey] = useState(0)

  useEffect(() => {
    if (cash && prev.current !== null && cash.balance < prev.current) setDropKey(k => k + 1)
    if (cash) prev.current = cash.balance
  }, [cash])

  const paid = approvals.filter(a => a.kind === 'payment' && a.status === 'approved')
  const pending = cash?.pending_payment_requests ?? []
  const pct = Math.max(0, Math.min(100, (balance / OPENING) * 100))
  const projectedPct = Math.max(0, Math.min(100, ((cash?.projected_balance ?? balance) / OPENING) * 100))

  return (
    <section className="panel cash" aria-label="Cash">
      <div className="panel-head">
        <h2>Checking</h2>
        <span className="muted">as of {cash?.as_of ?? '…'}</span>
      </div>

      <div className="piggy-row">
        <div className="piggy" aria-hidden>
          <div className="pig-ear pig-ear-l" />
          <div className="pig-ear pig-ear-r" />
          <div className="pig-body">
            <span className="pig-slot" />
            <span className="pig-eye pig-eye-l" />
            <span className="pig-eye pig-eye-r" />
            <span className="pig-snout"><i /><i /></span>
            <span className="pig-blush pig-blush-l" />
            <span className="pig-blush pig-blush-r" />
          </div>
          <div className="pig-leg pig-leg-1" />
          <div className="pig-leg pig-leg-2" />
          <div className="pig-tail" />
          {dropKey > 0 && (
            <div key={dropKey} className="coins">
              <span>$</span><span>$</span><span>$</span>
            </div>
          )}
        </div>
        <div className="balance-block">
          <div className={`balance ${dropKey ? 'balance-drop' : ''}`} key={`b${dropKey}`} aria-live="polite">
            {money(shown)}
          </div>
          <div className="runway" title="Balance vs the opening $3,400">
            <span className="runway-projected" style={{ width: `${projectedPct}%` }} />
            <span className="runway-now" style={{ width: `${pct}%` }} />
          </div>
          <p className="muted small">
            {pending.length > 0
              ? <>If every pending pay is approved: <b>{money(cash!.projected_balance)}</b></>
              : 'Cash only goes out here. No sales come in.'}
          </p>
        </div>
      </div>

      <div className="ledger">
        <h3>Receipt tape</h3>
        {paid.length === 0 ? (
          <p className="empty small">No money has left yet. Every dollar needs a human signature.</p>
        ) : (
          <ul>
            {paid.map(p => (
              <li key={p.id}>
                <span>{String(p.details?.payee ?? p.ref_type)}<small>signed by {p.decided_by}</small></span>
                <b>−{money(p.amount)}</b>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
