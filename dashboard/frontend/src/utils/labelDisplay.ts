/** Shared display helpers so “Benign” / BenignOrLowRisk read as non-attack, not as attack types. */

function norm(s: string): string {
  return s.trim().toLowerCase()
}

export type FusionParts = { friendly: string; raw: string }

/** Fusion `decision_label` values — plain language + technical token. */
export function fusionParts(raw: string): FusionParts {
  switch (raw.trim()) {
    case 'BenignOrLowRisk':
      return { friendly: 'Not an attack — normal / low risk', raw: 'BenignOrLowRisk' }
    case 'KnownAttack':
      return { friendly: 'Known attack pattern', raw: 'KnownAttack' }
    case 'AttackUncertain':
      return { friendly: 'Uncertain — review', raw: 'AttackUncertain' }
    default:
      return { friendly: raw, raw: raw }
  }
}

/** Multiclass family name (e.g. UNSW “Benign” class) — not an attack category. */
export function supervisedFamilyParts(raw: string): FusionParts {
  if (norm(raw) === 'benign') {
    return { friendly: 'Normal traffic (not an attack)', raw: raw.trim() }
  }
  return { friendly: raw, raw: raw }
}

/** Binary bundle output: Benign vs Attack. */
export function binaryPredictionParts(raw: string): FusionParts {
  const n = norm(raw)
  if (n === 'benign') return { friendly: 'Not an attack', raw: 'Benign' }
  if (n === 'attack') return { friendly: 'Attack', raw: 'Attack' }
  return { friendly: raw, raw: raw }
}

/** Single cell string for results tables (Model lab, Live stream preview). */
export function formatDecisionTableCell(column: string, value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  const s = String(value)
  if (column === 'decision_label') {
    const p = fusionParts(s)
    return p.friendly === p.raw ? s : `${p.friendly} (${p.raw})`
  }
  if (column === 'supervised_prediction' || column === 'prediction') {
    const p = supervisedFamilyParts(s)
    return p.friendly === p.raw ? s : `${p.friendly} — ${p.raw}`
  }
  if (column === 'binary_prediction') {
    const p = binaryPredictionParts(s)
    return p.friendly === p.raw ? s : `${p.friendly} (${p.raw})`
  }
  return s
}
