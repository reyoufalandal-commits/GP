import { formatDecisionTableCell } from './labelDisplay'

/** Preferred column order for scored Zeek / fusion rows (spreadsheet-style tables). */
export const SCORED_PREVIEW_COL_ORDER = [
  'decision_label',
  'supervised_prediction',
  'prediction',
  'binary_prediction',
  'p_attack',
  'score',
  'anomaly_score',
  'dst_port',
  'id.orig_h',
  'id.resp_h',
]

export function scoredPreviewColumns(rows: Record<string, unknown>[], maxCols = 12): string[] {
  if (!rows.length) return []
  const keys = new Set<string>()
  for (const r of rows) {
    for (const k of Object.keys(r)) keys.add(k)
  }
  const pref = SCORED_PREVIEW_COL_ORDER.filter((c) => keys.has(c))
  const rest = [...keys].filter((k) => !SCORED_PREVIEW_COL_ORDER.includes(k)).sort()
  return [...pref, ...rest].slice(0, maxCols)
}

export function formatScoredCell(column: string, v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  return formatDecisionTableCell(column, v)
}
