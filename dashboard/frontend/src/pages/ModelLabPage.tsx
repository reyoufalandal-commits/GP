import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiFetch, apiJson, errorMessage, JSON_HDR } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { DemoFlowGuide } from '../components/DemoFlowGuide'
import { DecisionLabelsHint, HelpCallout } from '../components/HelpCallout'
import { MarkdownReader } from '../components/MarkdownReader'
import { formatDecisionTableCell } from '../utils/labelDisplay'
import { formatScoredCell, scoredPreviewColumns } from '../utils/scoredPreviewTable'

type SupervisedFeatureSchema = {
  supervised_dir: string
  feature_columns: string[]
  n_features: number
}

function skeletonRowFromColumns(cols: string[]): Record<string, number> {
  const row: Record<string, number> = {}
  for (const c of cols) {
    row[c] = 0
  }
  return row
}

/** Non-zero sample values for teaching / demos (same keys as bundle). */
function demoRowFromColumns(cols: string[]): Record<string, number> {
  const row = skeletonRowFromColumns(cols)
  for (let i = 0; i < Math.min(6, cols.length); i++) {
    row[cols[i]] = Math.round((0.12 + i * 0.07) * 1000) / 1000
  }
  const lc = (s: string) => s.toLowerCase()
  for (const c of cols) {
    if (lc(c).includes('duration')) row[c] = 15.25
    if (lc(c).includes('byte') || lc(c).includes('bytes')) row[c] = 420 + cols.indexOf(c) * 30
  }
  return row
}

const PREFERRED_COLS = [
  'decision_label',
  'binary_prediction',
  'p_attack',
  'score',
  'anomaly_score',
  'open_set_ood_score',
  '_suppressed',
]

type ScoreTriageResponse = {
  rows?: Record<string, unknown>[]
  applied?: Record<string, unknown>
}

type LlmCapabilities = {
  llm_available: boolean
  provider: string
  base_url_display: string
  model_default: string
}

/** Matches GET /api/v1/detections/stream-hints (subset for Model lab prefill). */
type StreamHints = {
  resolved_if_empty?: string | null
  resolved_source?: string | null
  live_conn_log_abs?: string
}

function formatDurationFromSeconds(sec: number): string {
  if (!Number.isFinite(sec) || sec < 1) return '30s'
  if (sec % 3600 === 0 && sec >= 3600) return `${sec / 3600}h`
  if (sec % 60 === 0 && sec >= 60) return `${sec / 60}m`
  return `${Math.floor(sec)}s`
}

type ExplainApiResponse = { explain: Record<string, unknown>; supervised_dir: string }

type MagicBundle = {
  triage: ScoreTriageResponse
  explain: ExplainApiResponse | null
  llm: { source: string; text: string } | null
}

const MAX_JSON_ROWS_FILE_BYTES = 4 * 1024 * 1024
const MAX_CONN_LOG_FILE_BYTES = 50 * 1024 * 1024
/** Persist form fields locally so refresh/navigation feels less manual (does not auto-call APIs). */
const MODEL_LAB_STORAGE_KEY = 'hawk-eye:model-lab-v1'
const MODEL_LAB_ROWS_MAX_PERSIST_CHARS = 900_000

function readModelLabPersisted(): {
  rowsJson: string
  dur: string
  connLog: string
  alertLogPath: string
  webhookUrl: string
  rowIndex: number
  rowsTouched: boolean
} {
  const defaults = {
    rowsJson: '[]',
    dur: '30s',
    connLog: '',
    alertLogPath: '',
    webhookUrl: '',
    rowIndex: 0,
    rowsTouched: false,
  }
  if (typeof window === 'undefined') return defaults
  try {
    const raw = sessionStorage.getItem(MODEL_LAB_STORAGE_KEY)
    if (!raw) return defaults
    const o = JSON.parse(raw) as Record<string, unknown>
    let rowsJson = defaults.rowsJson
    if (typeof o.rowsJson === 'string' && o.rowsJson.length <= MODEL_LAB_ROWS_MAX_PERSIST_CHARS) {
      try {
        const v = JSON.parse(o.rowsJson) as unknown
        if (Array.isArray(v)) rowsJson = o.rowsJson
      } catch {
        /* ignore invalid */
      }
    }
    const rowsTouched = rowsJson.trim() !== '' && rowsJson.trim() !== '[]'
    return {
      rowsJson,
      dur: typeof o.dur === 'string' ? o.dur : defaults.dur,
      connLog: typeof o.connLog === 'string' ? o.connLog : defaults.connLog,
      alertLogPath: typeof o.alertLogPath === 'string' ? o.alertLogPath : defaults.alertLogPath,
      webhookUrl: typeof o.webhookUrl === 'string' ? o.webhookUrl : defaults.webhookUrl,
      rowIndex:
        typeof o.rowIndex === 'number' && Number.isFinite(o.rowIndex)
          ? Math.max(0, Math.floor(o.rowIndex))
          : defaults.rowIndex,
      rowsTouched,
    }
  } catch {
    return defaults
  }
}

function parseRowsFileText(text: string): Record<string, unknown>[] {
  const trimmed = text.trim()
  if (!trimmed) throw new Error('File is empty')
  if (trimmed.startsWith('[')) {
    const v = JSON.parse(trimmed) as unknown
    if (!Array.isArray(v)) throw new Error('JSON root must be an array of objects')
    if (!v.every((x) => x !== null && typeof x === 'object' && !Array.isArray(x))) {
      throw new Error('JSON array must contain only objects')
    }
    return v as Record<string, unknown>[]
  }
  const rows: Record<string, unknown>[] = []
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (!t) continue
    const o = JSON.parse(t) as unknown
    if (o === null || typeof o !== 'object' || Array.isArray(o)) {
      throw new Error('Each JSONL line must be one object')
    }
    rows.push(o as Record<string, unknown>)
  }
  if (!rows.length) {
    throw new Error('No JSON lines found (use one JSON object per line, or a single JSON array)')
  }
  return rows
}

function rowKeysMatchBundle(row: Record<string, unknown>, cols: string[]): boolean {
  if (cols.length !== Object.keys(row).length) return false
  const s = new Set(Object.keys(row))
  return cols.every((c) => s.has(c))
}

function tableColumns(rows: Record<string, unknown>[]): string[] {
  if (!rows.length) return []
  const keys = new Set<string>()
  for (const r of rows) {
    for (const k of Object.keys(r)) keys.add(k)
  }
  const pref = PREFERRED_COLS.filter((c) => keys.has(c))
  const rest = [...keys].filter((k) => !PREFERRED_COLS.includes(k)).sort()
  return [...pref, ...rest].slice(0, 16)
}

export function ModelLabPage() {
  const { getAuth, refresh, user } = useAuth()
  const mlInit = useMemo(() => readModelLabPersisted(), [])
  const [rowsJson, setRowsJson] = useState(mlInit.rowsJson)
  const [dur, setDur] = useState(mlInit.dur)
  const [connLog, setConnLog] = useState(mlInit.connLog)
  const [alertLogPath, setAlertLogPath] = useState(mlInit.alertLogPath)
  const [webhookUrl, setWebhookUrl] = useState(mlInit.webhookUrl)
  const [rowIndex, setRowIndex] = useState(mlInit.rowIndex)
  const [streamJobId, setStreamJobId] = useState<number | null>(null)
  const [explainResult, setExplainResult] = useState<unknown>(null)
  const [llmResult, setLlmResult] = useState<{ source: string; text: string } | null>(null)
  const [rowsFileHint, setRowsFileHint] = useState<string | null>(null)
  const [rowsFileError, setRowsFileError] = useState<string | null>(null)
  const [fileTriageData, setFileTriageData] = useState<ScoreTriageResponse | null>(null)
  const [magicBundle, setMagicBundle] = useState<MagicBundle | null>(null)
  const rowsUserTouched = useRef(mlInit.rowsTouched)

  useEffect(() => {
    if (rowsJson.length > MODEL_LAB_ROWS_MAX_PERSIST_CHARS) return
    try {
      sessionStorage.setItem(
        MODEL_LAB_STORAGE_KEY,
        JSON.stringify({
          rowsJson,
          dur,
          connLog,
          alertLogPath,
          webhookUrl,
          rowIndex,
        }),
      )
    } catch {
      /* quota or private mode */
    }
  }, [rowsJson, dur, connLog, alertLogPath, webhookUrl, rowIndex])

  const inputRows = useMemo((): Record<string, unknown>[] => {
    try {
      const v = JSON.parse(rowsJson) as unknown
      return Array.isArray(v) ? (v as Record<string, unknown>[]) : []
    } catch {
      return []
    }
  }, [rowsJson])

  const featureSchemaQ = useQuery({
    queryKey: ['supervised-feature-schema'],
    queryFn: () => apiJson<SupervisedFeatureSchema>('/api/v1/detections/supervised-feature-schema', {}, getAuth, refresh),
    enabled: !!user && user.role !== 'viewer',
    staleTime: 60_000,
  })

  const llmCapQ = useQuery({
    queryKey: ['llm-capabilities'],
    queryFn: () => apiJson<LlmCapabilities>('/api/v1/llm/capabilities', {}, getAuth, refresh),
    enabled: !!user && user.role !== 'viewer',
    staleTime: 30_000,
  })

  const detectionSettingsQ = useQuery({
    queryKey: ['detection-settings'],
    queryFn: () =>
      apiJson<{ conn_log_path?: string | null; stream_duration_default_seconds?: number }>(
        '/api/v1/settings/detection',
        {},
        getAuth,
        refresh,
      ),
    enabled: !!user && user.role !== 'viewer',
    staleTime: 30_000,
  })

  const streamHintsQ = useQuery({
    queryKey: ['stream-hints'],
    queryFn: () => apiJson<StreamHints>('/api/v1/detections/stream-hints', {}, getAuth, refresh),
    enabled: !!user && user.role !== 'viewer',
    staleTime: 15_000,
    refetchInterval: 12_000,
  })

  const connPrefilled = useRef(false)
  const durationSyncedFromSettings = useRef(false)

  useEffect(() => {
    if (connPrefilled.current) return
    const p = detectionSettingsQ.data?.conn_log_path
    if (typeof p === 'string' && p.trim()) {
      connPrefilled.current = true
      setConnLog((prev) => (prev.trim() ? prev : p.trim()))
      return
    }
    const h = streamHintsQ.data
    if (!h) return
    const resolved = (h.resolved_if_empty || '').trim()
    if (resolved) {
      connPrefilled.current = true
      setConnLog((prev) => (prev.trim() ? prev : resolved))
    }
  }, [detectionSettingsQ.data?.conn_log_path, streamHintsQ.data])

  useEffect(() => {
    if (durationSyncedFromSettings.current) return
    const sec = detectionSettingsQ.data?.stream_duration_default_seconds
    if (typeof sec !== 'number' || !Number.isFinite(sec) || sec < 1) return
    durationSyncedFromSettings.current = true
    setDur((current) => {
      if (current !== '30s') return current
      return formatDurationFromSeconds(sec)
    })
  }, [detectionSettingsQ.data?.stream_duration_default_seconds])

  const canStartStream = useMemo(() => {
    if (connLog.trim()) return true
    const p = detectionSettingsQ.data?.conn_log_path
    if (typeof p === 'string' && p.trim()) return true
    const h = streamHintsQ.data
    if (!h) return false
    return Boolean(
      (h.resolved_if_empty && String(h.resolved_if_empty).trim()) ||
        (h.live_conn_log_abs && String(h.live_conn_log_abs).trim()),
    )
  }, [connLog, streamHintsQ.data, detectionSettingsQ.data?.conn_log_path])

  useEffect(() => {
    const cols = featureSchemaQ.data?.feature_columns
    if (!cols?.length || rowsUserTouched.current) return
    const json = JSON.stringify([skeletonRowFromColumns(cols)], null, 2)
    const id = window.setTimeout(() => setRowsJson(json), 0)
    return () => window.clearTimeout(id)
  }, [featureSchemaQ.data])

  const score = useMutation({
    mutationFn: async () => {
      const rows = JSON.parse(rowsJson) as Record<string, unknown>[]
      return apiJson<ScoreTriageResponse>(
        '/api/v1/detections/score',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ rows }) },
        getAuth,
        refresh,
      )
    },
    onMutate: () => setFileTriageData(null),
    onSuccess: () => setMagicBundle(null),
  })

  const triage = useMutation({
    mutationFn: async () => {
      const rows = JSON.parse(rowsJson) as Record<string, unknown>[]
      return apiJson<ScoreTriageResponse>(
        '/api/v1/detections/triage',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ rows }) },
        getAuth,
        refresh,
      )
    },
    onMutate: () => setFileTriageData(null),
    onSuccess: () => setMagicBundle(null),
  })

  const loadLabSample = useMutation({
    mutationFn: () =>
      apiJson<{ rows: Record<string, unknown>[] }>('/api/v1/detections/lab-sample-rows', {}, getAuth, refresh),
    onMutate: () => setRowsFileError(null),
    onSuccess: (data) => {
      const cols = featureSchemaQ.data?.feature_columns
      const rows = data.rows
      if (!cols?.length || !rows?.length) {
        setRowsFileError('Could not compare sample rows to your supervised bundle.')
        return
      }
      if (!rows.every((r) => rowKeysMatchBundle(r as Record<string, unknown>, cols))) {
        setRowsFileError(
          'Repo lab sample columns do not match your supervised bundle. Run python scripts/ci_build_minimal_bundles.py for the same layout, or use "Load demo row".',
        )
        return
      }
      rowsUserTouched.current = true
      setRowsJson(JSON.stringify(rows, null, 2))
      setRowsFileHint('lab sample (data/lab)')
      setFileTriageData(null)
    },
    onError: (e) => setRowsFileError(errorMessage(e)),
  })

  const triageConnLogFile = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > MAX_CONN_LOG_FILE_BYTES) {
        throw new Error(`file too large (max ${Math.floor(MAX_CONN_LOG_FILE_BYTES / (1024 * 1024))} MB)`)
      }
      const fd = new FormData()
      fd.append('file', file)
      const res = await apiFetch('/api/v1/detections/triage-conn-log-file', { method: 'POST', body: fd }, getAuth, refresh)
      const text = await res.text()
      if (!res.ok) throw new Error(`${res.status}: ${text.slice(0, 400)}`)
      return JSON.parse(text) as ScoreTriageResponse
    },
    onSuccess: (data) => {
      setFileTriageData(data)
      setMagicBundle(null)
      score.reset()
      triage.reset()
    },
  })

  const stream = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = { duration: dur }
      if (connLog.trim()) body.conn_log_path = connLog.trim()
      if (alertLogPath.trim()) body.alert_log_path = alertLogPath.trim()
      if (webhookUrl.trim()) body.webhook_url = webhookUrl.trim()
      const res = await apiJson<{ job_id?: number; conn_log_path?: string }>(
        '/api/v1/detections/stream-session',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify(body) },
        getAuth,
        refresh,
      )
      if (typeof res.job_id === 'number') setStreamJobId(res.job_id)
      if (typeof res.conn_log_path === 'string' && res.conn_log_path.trim()) {
        connPrefilled.current = true
        setConnLog((prev) => prev.trim() || res.conn_log_path!)
      }
      return res
    },
  })

  const explain = useMutation({
    mutationFn: async () => {
      const rows = inputRows
      const idx = Math.min(Math.max(0, rowIndex), Math.max(0, rows.length - 1))
      const row = rows[idx]
      if (!row) throw new Error('no row at index')
      return apiJson<ExplainApiResponse>(
        '/api/v1/detections/explain',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ row, row_index: idx }) },
        getAuth,
        refresh,
      )
    },
    onSuccess: (data) => {
      setMagicBundle(null)
      setExplainResult(data)
      setLlmResult(null)
    },
  })

  const magicPipeline = useMutation({
    mutationFn: async () => {
      const rows = JSON.parse(rowsJson) as unknown
      if (!Array.isArray(rows) || rows.length === 0) throw new Error('Need at least one row in the JSON array.')
      const tri = await apiJson<ScoreTriageResponse>(
        '/api/v1/detections/triage',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ rows }) },
        getAuth,
        refresh,
      )
      const idx = Math.min(Math.max(0, rowIndex), rows.length - 1)
      const row = rows[idx] as Record<string, unknown>
      let explain: ExplainApiResponse | null = null
      try {
        explain = await apiJson<ExplainApiResponse>(
          '/api/v1/detections/explain',
          { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ row, row_index: idx }) },
          getAuth,
          refresh,
        )
      } catch {
        /* non-linear model or feature mismatch — triage still valid */
      }
      let llm: { source: string; text: string } | null = null
      if (explain) {
        try {
          const cap = await apiJson<LlmCapabilities>('/api/v1/llm/capabilities', {}, getAuth, refresh)
          if (cap.llm_available) {
            llm = await apiJson<{ source: string; text: string }>(
              '/api/v1/llm/format-explanation',
              { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ explain: explain.explain }) },
              getAuth,
              refresh,
            )
          }
        } catch {
          /* optional */
        }
      }
      return { tri, explain, llm }
    },
    onSuccess: (data) => {
      setMagicBundle({ triage: data.tri, explain: data.explain, llm: data.llm })
      setExplainResult(data.explain)
      setLlmResult(data.llm)
      score.reset()
      triage.reset()
      setFileTriageData(null)
    },
  })

  const llmFormat = useMutation({
    mutationFn: async (forceStub: boolean) => {
      const ex =
        explainResult && typeof explainResult === 'object' && explainResult !== null && 'explain' in explainResult
          ? (explainResult as { explain: Record<string, unknown> }).explain
          : null
      if (!ex) throw new Error('run Explain first')
      const q = forceStub ? '?use_llm=false' : ''
      return apiJson<{ source: string; text: string }>(
        `/api/v1/llm/format-explanation${q}`,
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ explain: ex }) },
        getAuth,
        refresh,
      )
    },
    onSuccess: setLlmResult,
  })

  const activeData = magicBundle?.triage ?? score.data ?? triage.data ?? fileTriageData
  const activeKind = magicBundle
    ? 'triage (full run)'
    : score.data
      ? 'score'
      : triage.data
        ? 'triage'
        : fileTriageData
          ? 'triage (conn.log upload)'
          : null
  const resultRows = activeData?.rows ?? []

  if (user?.role === 'viewer') {
    return (
      <div className="he-card">
        <p className="he-muted">Your account is read-only. Ask an admin to give you the analyst role to use Model lab.</p>
      </div>
    )
  }

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Model lab</h1>
        <p className="he-page-subtitle" style={{ marginBottom: '0.75rem' }}>
          Try data in your browser — big buttons, clear fields.
        </p>
        <div className="he-easy-welcome">
          <p>
            Load a sample or a file, then use <strong style={{ color: 'var(--he-text)' }}>Run everything</strong> for scores, explanations, and an optional plain-language summary when the server has an AI key set in{' '}
            <code>.env</code>. The table below fills itself from your project bundle so you do not have to guess column names.
          </p>
        </div>
      </header>

      <DemoFlowGuide
        intro="Same pattern on every screen: one button → visible output → optional next step. Full list: sidebar Demo flow."
        steps={[
          {
            press: 'Try sample row or Load built-in sample.',
            see: 'This page’s JSON box fills.',
            then: 'Run everything (or Quick score / Full triage).',
          },
          {
            press: 'Run everything or Quick score / Full triage.',
            see: 'Scroll down: “Your results” table and “Raw response” on this page.',
            then: 'Optional: Explain this row → then Write summary.',
          },
        ]}
      />

      <section className="he-card he-model-lab-magic" style={{ borderColor: 'rgba(56, 189, 248, 0.35)', background: 'rgba(56, 189, 248, 0.06)' }}>
        <div className="he-row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
              Fastest path: one button
            </h2>
            <p className="he-muted" style={{ margin: '0.25rem 0 0', maxWidth: 520, fontSize: 14 }}>
              Same as triage → explain → optional AI text. Adjust the JSON first if you want custom numbers.
            </p>
          </div>
          <button
            type="button"
            className="he-btn he-btn--primary he-btn-lg"
            style={{ minWidth: 200 }}
            disabled={magicPipeline.isPending || !inputRows.length}
            onClick={() => magicPipeline.mutate()}
          >
            {magicPipeline.isPending ? 'Running…' : 'Run everything'}
          </button>
        </div>
        <p className="he-muted" style={{ fontSize: 13, margin: '0.75rem 0 0' }}>
          Optional AI summary:{' '}
          {llmCapQ.isLoading ? (
            <span>checking…</span>
          ) : llmCapQ.data?.llm_available ? (
            <strong style={{ color: 'var(--he-accent)' }}>
              ready ({llmCapQ.data.provider === 'deepseek' ? 'Deepseek' : 'OpenAI-compatible'} · {llmCapQ.data.model_default})
            </strong>
          ) : (
            <span>
              offline stub — set <code>DEEPSEEK_API_KEY</code> or <code>OPENAI_API_KEY</code> in repo <code>.env</code> and restart the API
            </span>
          )}
        </p>
        {magicPipeline.isError ? <Err error={magicPipeline.error} /> : null}
      </section>

      <HelpCallout title="What you can do here">
        <p style={{ marginTop: 0 }}>
          <strong>Have a log file?</strong> Use <strong>Choose a log file</strong> below — no need to build JSON by hand.{' '}
          <strong>Prefer the table?</strong> Edit the JSON; names must match your bundle (we pre-fill when the server loads).
        </p>
        <ul className="he-help-list" style={{ marginBottom: 0 }}>
          <li>
            <strong>Run everything</strong> — Recommended: triage, explain, then optional AI text in one go.
          </li>
          <li>
            <strong>Quick score / Full triage</strong> — Run one step at a time. Explain needs the bundle columns (auto-filled).
          </li>
        </ul>
        <p style={{ marginBottom: 0, marginTop: 12 }}>
          <strong>Reading the labels</strong>
        </p>
        <DecisionLabelsHint />
      </HelpCallout>

      <section className="he-card">
        <h3>Your data</h3>
        <p className="he-muted" style={{ marginTop: '-0.25rem' }}>
          Paste a JSON array of rows, or <strong>choose a file</strong> (.json / .jsonl, max{' '}
          {Math.floor(MAX_JSON_ROWS_FILE_BYTES / (1024 * 1024))} MB). The box below is <strong>filled for you</strong> from your project bundle when the server is ready.
        </p>
        <p className="he-muted" style={{ fontSize: 13, marginTop: 6, marginBottom: 0 }}>
          Your JSON and stream fields are saved in this browser tab automatically (refresh-safe); starting jobs still needs a click.
        </p>
        <p className="he-muted" style={{ fontSize: 13, marginBottom: 0 }}>
          <strong>Built-in sample</strong> has three rows: the last is tuned for default minimal bundles so{' '}
          <strong>Full triage</strong> can show <code>Suspected_ZeroDay</code> and <code>AttackUncertain</code> (heuristic testing only, not a verified zero-day).
        </p>
        {featureSchemaQ.data ? (
          <p className="he-muted" style={{ fontSize: 13, marginBottom: 8 }}>
            Supervised bundle: <code>{featureSchemaQ.data.n_features}</code> features
            {featureSchemaQ.data.feature_columns.length <= 12
              ? ` — ${featureSchemaQ.data.feature_columns.join(', ')}`
              : ` — e.g. ${featureSchemaQ.data.feature_columns.slice(0, 8).join(', ')}, …`}
          </p>
        ) : null}
        {featureSchemaQ.isError ? (
          <p className="he-muted" style={{ fontSize: 13 }}>
            Could not load bundle feature list (Explain may still fail until the supervised bundle is available).
          </p>
        ) : null}
        <div className="he-row" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
          <label className="he-btn he-btn--ghost he-btn-lg" style={{ cursor: 'pointer' }}>
            Choose a JSON file
            <input
              type="file"
              accept=".json,.jsonl,application/json"
              data-testid="model-lab-rows-file"
              style={{ display: 'none' }}
              onChange={async (e) => {
                const f = e.target.files?.[0]
                e.target.value = ''
                if (!f) return
                setRowsFileError(null)
                if (f.size > MAX_JSON_ROWS_FILE_BYTES) {
                  setRowsFileError(`File too large (max ${Math.floor(MAX_JSON_ROWS_FILE_BYTES / (1024 * 1024))} MB)`)
                  return
                }
                try {
                  const text = await f.text()
                  const rows = parseRowsFileText(text)
                  rowsUserTouched.current = true
                  setRowsJson(JSON.stringify(rows, null, 2))
                  setRowsFileHint(f.name)
                  setFileTriageData(null)
                } catch (err) {
                  setRowsFileError(err instanceof Error ? err.message : 'invalid file')
                  setRowsFileHint(null)
                }
              }}
            />
          </label>
          <button
            type="button"
            className="he-btn"
            disabled={!featureSchemaQ.data?.feature_columns.length}
            title="Replace textarea with one row whose keys match the active supervised bundle (required for Explain)."
            onClick={() => {
              const cols = featureSchemaQ.data?.feature_columns
              if (!cols?.length) return
              rowsUserTouched.current = true
              setRowsJson(JSON.stringify([skeletonRowFromColumns(cols)], null, 2))
              setRowsFileHint(null)
              setRowsFileError(null)
              setFileTriageData(null)
            }}
          >
            Insert one row (zeros)
          </button>
          <button
            type="button"
            className="he-btn he-btn--primary he-btn-lg"
            disabled={!featureSchemaQ.data?.feature_columns.length}
            title="One row with small non-zero sample values for quick Score/Triage demos."
            onClick={() => {
              const cols = featureSchemaQ.data?.feature_columns
              if (!cols?.length) return
              rowsUserTouched.current = true
              setRowsJson(JSON.stringify([demoRowFromColumns(cols)], null, 2))
              setRowsFileHint('demo row')
              setRowsFileError(null)
              setFileTriageData(null)
            }}
          >
            Try sample row
          </button>
          <button
            type="button"
            className="he-btn he-btn-lg"
            disabled={!featureSchemaQ.data?.feature_columns.length || loadLabSample.isPending}
            title="Three rows from data/lab/model_lab_sample_rows.json — last row exercises heuristic zero-day-style triage on CI minimal bundles."
            onClick={() => loadLabSample.mutate()}
          >
            {loadLabSample.isPending ? 'Loading sample…' : 'Load built-in sample'}
          </button>
          {rowsFileHint ? <span className="he-muted">Loaded: {rowsFileHint}</span> : null}
        </div>
        {rowsFileError ? <Err message={rowsFileError} /> : null}
        <textarea
          className="he-textarea"
          style={{ minHeight: 160 }}
          value={rowsJson}
          onChange={(e) => {
            rowsUserTouched.current = true
            setRowsJson(e.target.value)
          }}
          spellCheck={false}
        />
        <div className="he-row" style={{ marginTop: 4, flexWrap: 'wrap', gap: 8 }}>
          <button type="button" className="he-btn he-btn--primary he-btn-lg" onClick={() => score.mutate()} disabled={score.isPending}>
            Quick score
          </button>
          <button type="button" className="he-btn he-btn-lg" onClick={() => triage.mutate()} disabled={triage.isPending}>
            Full triage
          </button>
        </div>
        {score.isError || triage.isError ? <Err error={score.error ?? triage.error} /> : null}
      </section>

      <section className="he-card">
        <h3>Or upload a network log</h3>
        <p className="he-muted" style={{ marginTop: '-0.25rem' }}>
          Zeek-style <code>conn.log</code> (tab-separated, with a <code>#fields</code> line). We parse it and run the same step as{' '}
          <strong>Full triage</strong>. For a timed run from a path on the server, open <strong>Live stream</strong>.
        </p>
        <div className="he-row">
          <label className="he-btn he-btn--ghost he-btn-lg" style={{ cursor: 'pointer' }}>
            Choose log file
            <input
              type="file"
              accept=".log,.txt,text/plain"
              data-testid="model-lab-conn-file"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0]
                e.target.value = ''
                if (!f) return
                triageConnLogFile.mutate(f)
              }}
            />
          </label>
          <button
            type="button"
            className="he-btn"
            disabled={triageConnLogFile.isPending}
            onClick={() => {
              setFileTriageData(null)
              triageConnLogFile.reset()
            }}
          >
            Clear upload result
          </button>
        </div>
        {triageConnLogFile.isError ? <Err error={triageConnLogFile.error} /> : null}
      </section>

      {activeKind && resultRows.length > 0 ? (
        <section className="he-card" id="model-lab-results">
          <h3>Your results ({activeKind})</h3>
          <p className="he-sheet-hint">Spreadsheet-style grid — scroll sideways if there are many columns; hover a row to highlight.</p>
          <div className="he-table-wrap he-table-wrap--sheet">
            <table className="he-table he-table--sheet">
              <thead>
                <tr>
                  {tableColumns(resultRows).map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {resultRows.map((r, i) => (
                  <tr key={i}>
                    {tableColumns(resultRows).map((c) => (
                      <td key={c}>{formatCell(c, r[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {activeData?.applied ? (
        <section className="he-card">
          <h4>Applied bundles / settings</h4>
          <JsonView data={activeData.applied} />
        </section>
      ) : null}

      {(score.data || triage.data || fileTriageData) && (
        <section className="he-card">
          <h3>Raw response</h3>
          <JsonView data={(score.data ?? triage.data ?? fileTriageData)!} />
        </section>
      )}

      <section className="he-card">
        <h3>Why this row? (explain)</h3>
        <p className="he-muted" style={{ marginTop: '-0.25rem' }}>
          Pick which row from your <em>input</em> list (0 = first). Included in <strong>Run everything</strong>, or click below after you edit JSON.
        </p>
        <div className="he-inline-fields">
          <div>
            <span className="he-label">Row index in input JSON array</span>
            <input
              className="he-input he-input--narrow"
              type="number"
              min={0}
              value={rowIndex}
              onChange={(e) => setRowIndex(parseInt(e.target.value, 10) || 0)}
            />
          </div>
          <button
            type="button"
            className="he-btn he-btn--primary he-btn-lg"
            onClick={() => explain.mutate()}
            disabled={explain.isPending || !inputRows.length}
          >
            Explain this row
          </button>
        </div>
        {explain.isError ? <Err error={explain.error} /> : null}
        {explainResult ? <JsonView data={explainResult} /> : null}
      </section>

      <section className="he-card">
        <h3>Plain-language summary</h3>
        <p className="he-muted" style={{ marginTop: '-0.25rem' }}>
          Turns explain output into short text (rendered as <strong>Markdown</strong> like a README — headings, lists, code). Needs server keys in{' '}
          <code>.env</code> (see status above) and a successful explain. Use <strong>Demo text</strong> to preview without calling an AI.
        </p>
        <div className="he-row">
          <button type="button" className="he-btn he-btn-lg" disabled={!explainResult || llmFormat.isPending} onClick={() => llmFormat.mutate(false)}>
            Write summary
          </button>
          <button type="button" className="he-btn he-btn--ghost he-btn-lg" disabled={!explainResult || llmFormat.isPending} onClick={() => llmFormat.mutate(true)}>
            Demo text (no AI)
          </button>
        </div>
        {llmFormat.isError ? <Err error={llmFormat.error} /> : null}
        {llmResult ? (
          <div style={{ marginTop: 12 }}>
            <p style={{ marginBottom: 10 }}>
              <strong>source:</strong> <code>{llmResult.source}</code>
            </p>
            <div className="he-incident-report-wrap">
              <MarkdownReader markdown={llmResult.text} className="he-markdown-readme" />
            </div>
          </div>
        ) : null}
      </section>

      <section className="he-card he-card--callout">
        <h3>Optional: live capture from the server</h3>
        <div className="he-stack" style={{ fontSize: '0.9rem', lineHeight: 1.55, color: 'var(--he-text-muted)' }}>
          <p>
            This page can start a <strong style={{ color: 'var(--he-text)' }}>timed job</strong> that reads a growing log on the machine running the API (for example Zeek&apos;s{' '}
            <code>conn.log</code>). Your browser does not sniff the network — the API reads the file you point to.
          </p>
          <p style={{ marginBottom: 0 }}>
            Paths are stored in <strong>SQLite</strong> (<code>detection_settings.conn_log_path</code> in <code>data/db/hawk_eye.db</code>). If you leave the path empty, the API
            still resolves one automatically when <code>data/live/conn.log</code>, <code>data/lab/sim_conn.log</code>, env vars, or saved settings exist — same as{' '}
            <strong>Live stream</strong>.
          </p>
          <ol style={{ margin: '0.75rem 0 0', paddingLeft: '1.25rem' }}>
            <li>Optional: put Zeek output at <code>data/live/conn.log</code> or set the path once under Detection settings.</li>
            <li>Adjust duration if needed (defaults follow SQLite when the field still shows <code>30s</code>).</li>
            <li>
              Click <strong>Start timed capture</strong>. Results appear below; Parquet may land under <code>data/stream_sessions/</code> on the server.
            </li>
          </ol>
        </div>
        <div className="he-stack" style={{ marginTop: '1rem' }}>
          <div>
            <span className="he-label">How long to run</span>
            <input className="he-input he-input--narrow" value={dur} onChange={(e) => setDur(e.target.value)} placeholder="30s, 2m" />
          </div>
          <div>
            <span className="he-label">Path to conn.log on the API server (optional — prefilled from SQLite / auto-discovery)</span>
            <input
              className="he-input"
              value={connLog}
              onChange={(e) => setConnLog(e.target.value)}
              placeholder="/path/to/conn.log"
            />
          </div>
          {!connLog.trim() && streamHintsQ.data?.resolved_if_empty ? (
            <p className="he-muted" style={{ fontSize: 13, margin: 0 }}>
              Server will use: <code>{streamHintsQ.data.resolved_if_empty}</code>
              {streamHintsQ.data.resolved_source ? (
                <>
                  {' '}
                  (<span style={{ textTransform: 'lowercase' }}>{streamHintsQ.data.resolved_source.replace(/_/g, ' ')}</span>)
                </>
              ) : null}
            </p>
          ) : null}
          <div>
            <span className="he-label">Optional: alert log path (JSONL on server)</span>
            <input
              className="he-input"
              value={alertLogPath}
              onChange={(e) => setAlertLogPath(e.target.value)}
              placeholder="/path/to/live_alerts.jsonl"
            />
          </div>
          <div>
            <span className="he-label">Optional: webhook URL (POST per alert row)</span>
            <input className="he-input" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://…" />
          </div>
          <button
            type="button"
            className="he-btn he-btn--primary he-btn-lg"
            onClick={() => stream.mutate()}
            disabled={stream.isPending || !canStartStream}
            title={!canStartStream ? 'No conn.log resolved yet — add a path in Detection settings or create data/live/conn.log / data/lab/sim_conn.log on the API host.' : undefined}
          >
            Start timed capture
          </button>
        </div>
        {stream.isError ? <Err error={stream.error} /> : null}
        {stream.data ? <JsonView data={stream.data} /> : null}
        {streamJobId != null ? <StreamJobPanel streamJobId={streamJobId} getAuth={getAuth} refresh={refresh} /> : null}
      </section>
    </div>
  )
}

function StreamJobPanel({
  streamJobId,
  getAuth,
  refresh,
}: {
  streamJobId: number
  getAuth: ReturnType<typeof useAuth>['getAuth']
  refresh: ReturnType<typeof useAuth>['refresh']
}) {
  const jobQ = useQuery({
    queryKey: ['job', streamJobId],
    queryFn: () => apiJson<{ job: Record<string, unknown> }>(`/api/v1/jobs/${streamJobId}`, {}, getAuth, refresh),
    enabled: streamJobId > 0,
    refetchInterval: (q) => {
      const st = (q.state.data?.job?.status as string) || ''
      return st === 'pending' || st === 'running' ? 2000 : false
    },
  })
  const status = jobQ.data?.job?.status as string | undefined
  const summaryQ = useQuery({
    queryKey: ['job-stream-summary', streamJobId],
    queryFn: () => apiJson<Record<string, unknown>>(`/api/v1/jobs/${streamJobId}/stream-summary`, {}, getAuth, refresh),
    enabled: streamJobId > 0 && status === 'completed',
  })
  const previewQ = useQuery({
    queryKey: ['job-scored-preview', streamJobId],
    queryFn: () =>
      apiJson<{
        job_id: number
        total_rows: number
        returned: number
        rows: Record<string, unknown>[]
        parquet_path: string
      }>(`/api/v1/jobs/${streamJobId}/scored-preview?limit=100`, {}, getAuth, refresh),
    enabled: streamJobId > 0 && status === 'completed',
  })

  return (
    <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--he-border)' }}>
      <h4>Job {streamJobId}</h4>
      {jobQ.isLoading ? <p className="he-muted">Loading…</p> : null}
      {jobQ.data ? <JsonView data={jobQ.data} /> : null}
      {jobQ.isError ? <Err error={jobQ.error} /> : null}
      {status === 'failed' && jobQ.data?.job?.error ? <Err error={jobQ.data.job.error} /> : null}
      {status === 'completed' ? (
        <>
          <h4>Stream summary</h4>
          {summaryQ.isLoading ? <p className="he-muted">Loading summary…</p> : null}
          {summaryQ.data ? <JsonView data={summaryQ.data} /> : null}
          {summaryQ.isError ? <Err error={summaryQ.error} /> : null}
          <h4>Scored rows preview (last 100)</h4>
          <p className="he-sheet-hint">Spreadsheet-style grid (same as Live stream sample table).</p>
          {previewQ.isLoading ? <p className="he-muted">Loading preview…</p> : null}
          {previewQ.isError ? <Err error={previewQ.error} /> : null}
          {previewQ.data ? (
            <>
              {(previewQ.data.total_rows != null || previewQ.data.parquet_path) && (
                <p className="he-muted" style={{ fontSize: 13, marginBottom: 8 }}>
                  {previewQ.data.total_rows != null ? <>Total rows: {previewQ.data.total_rows.toLocaleString()}. </> : null}
                  {previewQ.data.parquet_path ? (
                    <>
                      Parquet: <code>{previewQ.data.parquet_path}</code>
                    </>
                  ) : null}
                </p>
              )}
              {previewQ.data.rows?.length ? (
                <div className="he-table-wrap he-table-wrap--sheet">
                  <table className="he-table he-table--sheet">
                    <thead>
                      <tr>
                        {scoredPreviewColumns(previewQ.data.rows, 16).map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewQ.data.rows.map((r, i) => (
                        <tr key={i}>
                          {scoredPreviewColumns(previewQ.data.rows, 16).map((c) => (
                            <td key={c}>{formatScoredCell(c, r[c])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="he-muted">No rows in preview.</p>
              )}
            </>
          ) : null}
        </>
      ) : null}
    </div>
  )
}

function formatCell(column: string, v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  return formatDecisionTableCell(column, v)
}
