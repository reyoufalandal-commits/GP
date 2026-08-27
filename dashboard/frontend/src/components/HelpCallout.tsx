import type { ReactNode } from 'react'

type HelpCalloutProps = {
  title?: string
  children: ReactNode
}

/** Short, user-facing context box (not error/warning). */
export function HelpCallout({ title = 'What this means', children }: HelpCalloutProps) {
  return (
    <aside className="he-help-callout" aria-label={title}>
      <div className="he-help-callout-title">{title}</div>
      <div className="he-help-callout-body">{children}</div>
    </aside>
  )
}

/** Fusion labels shown in tables and stream reports. */
export function DecisionLabelsHint() {
  return (
    <ul className="he-help-list">
      <li>
        <strong>BenignOrLowRisk</strong> — Not an attack: normal or low-priority traffic (fusion treats this as non-malicious).
      </li>
      <li>
        <strong>AttackUncertain</strong> — Suspicious; review recommended.
      </li>
      <li>
        <strong>KnownAttack</strong> — High-confidence alignment with a known attack pattern.
      </li>
    </ul>
  )
}
