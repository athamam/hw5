import { useState } from 'react'
import type { Approval } from '../api'
import { AGENTS, money } from '../agents'
import { Creature } from './Creature'

interface Props {
  approvals: Approval[]
  signer: string
  onSignerChange: (name: string) => void
  onApprove: (a: Approval) => Promise<void>
  onReject: (a: Approval, reason: string) => Promise<void>
}

const KIND: Record<Approval['kind'], { icon: string; title: string; verb: string }> = {
  payment: { icon: '💸', title: 'Payment', verb: 'Approve & pay' },
  purchase_order: { icon: '📦', title: 'Purchase order', verb: 'Approve PO' },
  price_override: { icon: '🏷️', title: 'Discount', verb: 'Approve price' },
}

function headline(a: Approval): string {
  const d = a.details ?? {}
  if (a.kind === 'payment') return `${money(a.amount)} to ${String(d.payee ?? '')}`
  if (a.kind === 'purchase_order') return `${String(d.qty ?? '')} × ${String(d.item ?? '')} from ${String(d.vendor ?? '')}`
  return `${String(d.qty ?? '')} × ${String(d.sku ?? '')} at ${money(Number(d.proposed_unit_price ?? 0))} each (${String(d.discount_pct ?? '')}% off)`
}

function facts(a: Approval): string[] {
  const d = a.details ?? {}
  const out: string[] = []
  if (a.kind === 'payment') {
    if (d.invoice_description) out.push(`Invoice: ${String(d.invoice_description)}`)
    if (d.due_date) out.push(`Due ${String(d.due_date)}${Number(d.days_overdue) > 0 ? ` · ${String(d.days_overdue)} days overdue` : ''}`)
    if (d.rent_due_date) out.push(`Rent due ${String(d.rent_due_date)} · in ${String(d.days_until_due)} days`)
  } else if (a.kind === 'purchase_order') {
    out.push(`Total ${money(a.amount)} · ${String(d.lead_days)}-day lead`)
    const blocked = d.blocked_by_open_invoices as number[] | undefined
    if (blocked?.length) out.push(`⚠ Vendor blocked by invoice ${blocked.join(', ')} — pay that first`)
  } else {
    out.push(`Order ${money(Number(d.order_total ?? 0))} vs ${money(Number(d.order_total_at_list ?? 0))} at list`)
    out.push(`Margin left ${money(Number(d.margin_per_unit ?? 0))}/unit (${String(d.margin_pct)}%)`)
  }
  return out
}

export function ApprovalTray({ approvals, signer, onSignerChange, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState<number | null>(null)
  const [stamped, setStamped] = useState<Set<number>>(new Set())
  const pending = approvals.filter(a => a.status === 'pending')
  const decided = approvals.filter(a => a.status !== 'pending').slice(-4).reverse()

  const act = async (a: Approval, fn: () => Promise<void>) => {
    setBusy(a.id)
    try {
      await fn()
      setStamped(s => new Set(s).add(a.id))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="panel tray" aria-label="Approvals">
      <div className="panel-head">
        <h2>Needs your signature</h2>
        <span className={`count ${pending.length ? 'count-hot' : ''}`}>{pending.length}</span>
      </div>

      <label className="signer">
        <span>Signing as</span>
        <input value={signer} onChange={e => onSignerChange(e.target.value)} placeholder="Your name" maxLength={40} />
      </label>

      {pending.length === 0 && <p className="empty">The tray is empty. Agents only <em>prepare</em> money moves, and they land here for a human.</p>}

      <div className="slips">
        {pending.map(a => {
          const k = KIND[a.kind]
          const who = AGENTS[a.requested_by]
          return (
            <article key={a.id} className={`slip slip-${a.kind}`}>
              <div className="slip-top">
                <span className="slip-kind">{k.icon} {k.title}</span>
                <span className="slip-id">#{a.id}{a.ticket_id ? ` · ticket ${a.ticket_id}` : ''}</span>
              </div>
              <h3>{headline(a)}</h3>
              <ul>{facts(a).map((f, i) => <li key={i}>{f}</li>)}</ul>
              <div className="slip-reason">
                <Creature agent={a.requested_by} size={26} /> <span><b>{who?.label}</b>: {a.reason}</span>
              </div>
              <div className="slip-sign">
                <span className="sig-line">{signer || ' '}</span>
                <div className="slip-actions">
                  <button className="btn btn-ghost" disabled={busy !== null || !signer.trim()}
                    onClick={() => {
                      const reason = window.prompt('Why reject this request?')
                      if (reason) void act(a, () => onReject(a, reason))
                    }}>
                    Reject
                  </button>
                  <button className="btn btn-approve" disabled={busy !== null || !signer.trim()} onClick={() => void act(a, () => onApprove(a))}>
                    {busy === a.id ? <span className="spinner" /> : '✍'} {k.verb}
                  </button>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      {decided.length > 0 && (
        <div className="decided">
          <h3>Recently decided</h3>
          {decided.map(a => (
            <div key={a.id} className={`decided-row ${stamped.has(a.id) ? 'just' : ''}`}>
              <span>{KIND[a.kind].icon} #{a.id} {headline(a)}</span>
              <span className={`mini-stamp ${a.status}`}>{a.status === 'approved' ? (a.kind === 'payment' ? 'PAID' : 'OK') : 'NO'}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
