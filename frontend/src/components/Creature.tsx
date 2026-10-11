import type { AgentName } from '../api'
import { AGENTS } from '../agents'

export type CreatureMood = 'idle' | 'working' | 'done' | 'benched'

interface Props {
  agent: AgentName
  size?: number
  mood?: CreatureMood
}

/** A small Labubu-style creature built only from HTML and CSS: tall ears, toothy grin, one accessory per role. */
export function Creature({ agent, size = 80, mood = 'idle' }: Props) {
  const meta = AGENTS[agent]
  return (
    <div
      className={`creature creature--${meta.accessory} mood-${mood}`}
      style={{ fontSize: `${size / 10}px`, ['--c' as string]: meta.color }}
      role="img"
      aria-label={`${meta.label} creature`}
    >
      <div className="cr-ear cr-ear--l" />
      <div className="cr-ear cr-ear--r" />
      <div className="cr-body">
        <div className="cr-face">
          <span className="cr-eye cr-eye--l" />
          <span className="cr-eye cr-eye--r" />
          <span className="cr-blush cr-blush--l" />
          <span className="cr-blush cr-blush--r" />
          <span className="cr-mouth" />
        </div>
        <div className="cr-belly" />
      </div>
      <div className="cr-foot cr-foot--l" />
      <div className="cr-foot cr-foot--r" />
      <div className={`cr-acc cr-acc--${meta.accessory}`}>
        {meta.accessory === 'glasses' && (
          <>
            <span />
            <span />
          </>
        )}
        {meta.accessory === 'headset' && <span className="mic" />}
      </div>
      {mood === 'done' && <div className="cr-check">✓</div>}
    </div>
  )
}
