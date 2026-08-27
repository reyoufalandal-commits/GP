import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { ApiError, apiDownloadBlob, apiJson, errorMessage, JSON_HDR } from '../api/client'
import { FusionDecisionCountLabel, SupervisedFamilyCountLabel } from '../components/FusionLabels'
import { Err } from '../components/Err'
import { LoadingBlock } from '../components/Loading'
import { DemoFlowGuide } from '../components/DemoFlowGuide'
import { HelpCallout } from '../components/HelpCallout'
import { MarkdownReader } from '../components/MarkdownReader'
import { formatScoredCell, scoredPreviewColumns } from '../utils/scoredPreviewTable'

type StreamStartResponse = {
  ok?: boolean
  job_id?: number
  duration_seconds?: number
  conn_log_path?: string
  conn_log_source?: string
  poll_seconds?: number
}

type StreamSummary = {
  mode?: string
  duration_seconds?: number
  rows_scored?: number
  alerts_emitted?: number
  output?: string
  state?: string
  decision_counts?: Record<string, number>
  /** Supervised multiclass label counts among rows with decision_label === KnownAttack */
  known_attack_types?: Record<string, number>
  /** From server: low = no attack labels; elevated = review; unknown = no rows */
  risk_level?: 'low' | 'elevated' | 'unknown'
  attack_indicators?: 'none' | 'present'
  risk_headline?: string
  risk_plain_summary?: string
}

type ScoredPreview = {
  job_id: number
  total_rows: number
  returned: number
  rows: Record<string, unknown>[]
  parquet_path?: string
}

type StreamLiveProgress = {
  job_id: number
  job_status?: string
  rows_scored?: number
  conn_log_line_offset?: number | null
  updated_at?: number | null
}

type StreamHints = {
  repo_root?: string
  live_conn_log_abs?: string
  live_conn_log_exists?: boolean
  /** Seconds since OS last saw conn.log change (mtime). */
  live_conn_log_age_sec?: number | null
  /** True when the log was touched recently (Zeek likely writing). */
  live_conn_log_active_capture?: boolean
  lab_sim_conn_log_abs?: string | null
  zeek_in_path?: boolean
  zeek_path?: string | null
  capture_script_rel?: string
  resolved_if_empty?: string | null
  resolved_source?: string | null
}

const AUTO_STREAM_INCIDENT_KEY = 'hawkEye_autoStreamIncidentReport'

/** Primary choices for short live windows. */
const QUICK_DURATION_PRESETS: { label: string; value: string }[] = [
  { label: '1 min', value: '1m' },
  { label: '2 min', value: '2m' },
  { label: '3 min', value: '3m' },
]

const MORE_DURATION_PRESETS: { label: string; value: string }[] = [
  { label: '5 min', value: '5m' },
  { label: '10 min', value: '10m' },
  { label: '30 min', value: '30m' },
]

type ReadinessStripState = {
  zeekOk: boolean
  liveOk: boolean
  listening: boolean
  ageSec: number | null
  labOk: boolean
  resolved: string | null | undefined
  rSrc: string | null | undefined
}

function StreamCaptureReadinessStrip({
  strip,
  title,
  showCopyResolved = true,
  listeningHighlight = false,
}: {
  strip: ReadinessStripState
  title: string
  showCopyResolved?: boolean
  listeningHighlight?: boolean
}) {
  return (
    <div
      className="he-smart-strip"
      style={
        listeningHighlight && strip.listening
          ? { boxShadow: '0 0 0 1px rgba(52, 211, 153, 0.35)', borderRadius: 'var(--he-radius-md)' }
          : undefined
      }
    >
      <div className="he-smart-strip-title">{title}</div>
      <span className={`he-chip ${strip.zeekOk ? 'he-chip--ok' : 'he-chip--warn'}`}>
        Zeek CLI: <strong>{strip.zeekOk ? 'on PATH' : 'not found'}</strong>
      </span>
      <span
        className={`he-chip ${
          !strip.liveOk ? 'he-chip--warn' : strip.listening ? 'he-chip--ok' : 'he-chip--warn'
        }`}
        title={
          strip.liveOk && strip.ageSec != null ? phraseSinceConnWrite(strip.ageSec) : undefined
        }
      >
        <code>data/live/conn.log</code>:{' '}
        <strong>
          {!strip.liveOk ? 'waiting for file' : strip.listening ? 'listening' : 'idle'}
        </strong>
        {strip.liveOk && strip.ageSec != null ? (
          <span style={{ fontWeight: 400, opacity: 0.9 }}> — {phraseSinceConnWrite(strip.ageSec)}</span>
        ) : null}
      </span>
      <span className={`he-chip ${strip.labOk ? 'he-chip--ok' : 'he-chip--warn'}`}>
        Lab sim file: <strong>{strip.labOk ? 'present' : 'optional'}</strong>
      </span>
      <span
        className={`he-chip ${strip.resolved ? 'he-chip--accent' : 'he-chip--warn'}`}
        title={strip.resolved ?? 'Configure Detection settings, env, or create lab/live files.'}
      >
        If path left empty:{' '}
        <strong>
          {strip.resolved ? `${humanizeConnSource(strip.rSrc ?? undefined)}` : 'no default — type a path'}
        </strong>
      </span>
      {showCopyResolved && strip.resolved ? (
        <div className="he-path-actions">
          <button
            type="button"
            className="he-btn"
            onClick={() => {
              void navigator.clipboard.writeText(strip.resolved ?? '')
            }}
          >
            Copy default path
          </button>
          <code style={{ fontSize: 12, wordBreak: 'break-all', color: 'var(--he-text-muted)' }}>
            {strip.resolved}
          </code>
        </div>
      ) : null}
    </div>
  )
}

function formatClock(totalSec: number): string {
  const s = Math.max(0, Math.floor(totalSec))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${r.toString().padStart(2, '0')}`
}

function formatDurationPhrase(seconds: number): string {
  const s = Math.round(seconds)
  if (s < 60) return `${s} sec`
  if (s % 60 === 0) {
    const m = s / 60
    return `${m} min`
  }
  return `${formatClock(s)}`
}

/** Human label for time since conn.log mtime (dashboard “listening” strip). */
function phraseSinceConnWrite(ageSec: number): string {
  if (!Number.isFinite(ageSec) || ageSec < 0) return ''
  if (ageSec < 90) return `${Math.round(ageSec)}s since last write`
  if (ageSec < 7200) return `${Math.round(ageSec / 60)}m since last write`
  return `${Math.round(ageSec / 3600)}h since last write`
}

function verdictFromSummary(summary: StreamSummary | undefined): { tone: 'ok' | 'warn' | 'neutral'; title: string; body: string } {
  if (!summary) {
    return { tone: 'neutral', title: 'Report pending', body: 'Complete a stream to see the verdict.' }
  }
  const total = summary.rows_scored ?? 0
  const counts = summary.decision_counts ?? {}
  const known = counts['KnownAttack'] ?? 0
  const uncertain = counts['AttackUncertain'] ?? 0
  const benign = counts['BenignOrLowRisk'] ?? 0
  const alerts = summary.alerts_emitted ?? 0
  const kaTypes = summary.known_attack_types ?? {}
  const kaTypePhrase =
    known > 0 && Object.keys(kaTypes).length > 0
      ? ` Supervised family mix on those KnownAttack rows: ${Object.entries(kaTypes)
          .sort((a, b) => b[1] - a[1])
          .map(([k, n]) => {
            const disp = k.trim().toLowerCase() === 'benign' ? 'normal traffic (multiclass Benign)' : k
            return `${disp} ×${n}`
          })
          .join(', ')}.`
      : ''

  if (total === 0) {
    return {
      tone: 'neutral',
      title: 'No flows scored yet',
      body:
        'Zeek may still be starting, or the log path does not match. Extend the window, confirm traffic on the interface, and verify conn_log_path on the API host.',
    }
  }

  if (known === 0 && uncertain === 0) {
    return {
      tone: 'ok',
      title: 'No attack patterns in this window',
      body: `${total.toLocaleString()} connection(s) classified as not an attack (fusion: BenignOrLowRisk — normal / low risk). Same triage stack as batch scoring, tuned to your bundles.${alerts ? ` Optional alert sinks still recorded ${alerts} row(s).` : ''}`,
    }
  }

  return {
    tone: 'warn',
    title: 'Flagged traffic in this capture',
    body: `Fusion marked ${known.toLocaleString()} as KnownAttack and ${uncertain.toLocaleString()} as AttackUncertain out of ${total.toLocaleString()} scored; ${benign.toLocaleString()} were not an attack (BenignOrLowRisk).${kaTypePhrase}${alerts ? ` ${alerts} alert line(s) / webhook posts.` : ''} Inspect the table and Parquet for specifics.`,
  }
}

function humanizeConnSource(src: string | null | undefined): string {
  if (!src) return 'server chain'
  const map: Record<string, string> = {
    request: 'this field',
    detection_settings: 'Detection settings',
    env_default: 'HAWK_EYE_DEFAULT_CONN_LOG',
    env_live: 'HAWK_EYE_LIVE_CONN_LOG',
    live_capture_file: 'data/live/conn.log (exists)',
    lab_sim_file: 'data/lab/sim_conn.log (exists)',
  }
  return map[src] ?? src
}

function riskVerdictBadge(riskLevel: string | undefined): string {
  if (riskLevel === 'low') return 'All clear'
  if (riskLevel === 'elevated') return 'Action suggested'
  if (riskLevel === 'unknown') return 'Awaiting data'
  return 'Verdict'
}

function riskMarkGlyph(riskLevel: string | undefined): string {
  if (riskLevel === 'low') return '✓'
  if (riskLevel === 'elevated') return '!'
  return '…'
}

export function StreamSessionPage() {
  const queryClient = useQueryClient()
  const { getAuth, refresh, user } = useAuth()
  const [durationStr, setDurationStr] = useState('1m')
  const [connLog, setConnLog] = useState('')
  const [alertLogPath, setAlertLogPath] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookOnlyKnownAttack, setWebhookOnlyKnownAttack] = useState(false)
  const [compareJobA, setCompareJobA] = useState('')
  const [compareJobB, setCompareJobB] = useState('')
  const [compareJson, setCompareJson] = useState<string | null>(null)
  const [jobId, setJobId] = useState<number | null>(null)
  const [windowSeconds, setWindowSeconds] = useState<number>(0)
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null)
  const [elapsedSec, setElapsedSec] = useState(0)
  const [activeConnPath, setActiveConnPath] = useState<string | null>(null)
  const [activeConnSource, setActiveConnSource] = useState<string | null>(null)
  const connPrefilled = useRef(false)
  const liveSessionRef = useRef<HTMLElement | null>(null)
  const resultsAnchorRef = useRef<HTMLDivElement | null>(null)
  const [autoIncidentReport, setAutoIncidentReport] = useState(() => {
    try {
      return sessionStorage.getItem(AUTO_STREAM_INCIDENT_KEY) === '1'
    } catch {
      return false
    }
  })
  const autoIncidentTriggeredForJob = useRef<number | null>(null)
  const [dismissStreamHintsError, setDismissStreamHintsError] = useState(false)
  /** Shown when jobId is null after reset — guides next action. */
  const [startPanelHint, setStartPanelHint] = useState<'default' | 'after_complete' | 'after_fail'>('default')

  useEffect(() => {
    try {
      sessionStorage.setItem(AUTO_STREAM_INCIDENT_KEY, autoIncidentReport ? '1' : '0')
    } catch {
      /* ignore quota / private mode */
    }
  }, [autoIncidentReport])

  const detectionSettingsQ = useQuery({
    queryKey: ['detection-settings', 'stream-page'],
    queryFn: () =>
      apiJson<{ conn_log_path?: string | null }>('/api/v1/settings/detection', {}, getAuth, refresh),
    enabled: !!user && user.role !== 'viewer',
  })

  const streamHintsQ = useQuery({
    queryKey: ['stream-hints'],
    queryFn: () => apiJson<StreamHints>('/api/v1/detections/stream-hints', {}, getAuth, refresh),
    enabled: !!user && user.role !== 'viewer',
    staleTime: 15_000,
    refetchInterval: 4000,
  })

  useEffect(() => {
    if (!streamHintsQ.isError) {
      const id = window.setTimeout(() => setDismissStreamHintsError(false), 0)
      return () => window.clearTimeout(id)
    }
  }, [streamHintsQ.isError])

  useEffect(() => {
    if (connPrefilled.current) return
    const p = detectionSettingsQ.data?.conn_log_path
    if (typeof p === 'string' && p.trim()) {
      connPrefilled.current = true
      const v = p.trim()
      const id = window.setTimeout(() => setConnLog((prev) => (prev.trim() ? prev : v)), 0)
      return () => window.clearTimeout(id)
    }
  }, [detectionSettingsQ.data?.conn_log_path])

  useEffect(() => {
    if (streamStartedAt == null) return
    const update = () => setElapsedSec(Math.floor((Date.now() - streamStartedAt) / 1000))
    const id0 = window.setTimeout(update, 0)
    const id = window.setInterval(update, 1000)
    return () => {
      window.clearTimeout(id0)
      window.clearInterval(id)
    }
  }, [streamStartedAt])

  const start = useMutation({
    mutationFn: async () => {
      const hints = streamHintsQ.data
      let path = connLog.trim()
      if (!path && hints) {
        path = (hints.resolved_if_empty || hints.live_conn_log_abs || '').trim()
      }
      const body: Record<string, unknown> = {
        duration: durationStr,
      }
      if (path) body.conn_log_path = path
      if (alertLogPath.trim()) body.alert_log_path = alertLogPath.trim()
      if (webhookUrl.trim()) body.webhook_url = webhookUrl.trim()
      if (webhookOnlyKnownAttack) body.webhook_only_known_attack = true
      return apiJson<StreamStartResponse>(
        '/api/v1/detections/stream-session',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify(body) },
        getAuth,
        refresh,
      )
    },
    onSuccess: (data) => {
      const id = data.job_id
      const sec = typeof data.duration_seconds === 'number' ? data.duration_seconds : 0
      setStartPanelHint('default')
      if (typeof data.conn_log_path === 'string') {
        connPrefilled.current = true
        setConnLog(data.conn_log_path)
        setActiveConnPath(data.conn_log_path)
        setActiveConnSource(typeof data.conn_log_source === 'string' ? data.conn_log_source : null)
      }
      if (typeof id === 'number') {
        setJobId(id)
        setWindowSeconds(sec)
        setElapsedSec(0)
        setStreamStartedAt(Date.now())
      }
      queueMicrotask(() => {
        liveSessionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    },
  })

  const jobQ = useQuery({
    queryKey: ['stream-job', jobId],
    queryFn: () => apiJson<{ job: Record<string, unknown> }>(`/api/v1/jobs/${jobId}`, {}, getAuth, refresh),
    enabled: jobId != null && jobId > 0,
    refetchInterval: (q) => {
      const st = String(q.state.data?.job?.status ?? '').toLowerCase()
      return st === 'pending' || st === 'running' ? 2000 : false
    },
  })

  const status = (jobQ.data?.job?.status != null ? String(jobQ.data.job.status) : '').toLowerCase()

  /** Treat unknown/loading status as in-flight so the live banner shows immediately after start. */
  const isStreaming = Boolean(jobId && status !== 'completed' && status !== 'failed')

  const liveProgressQ = useQuery({
    queryKey: ['stream-live-progress', jobId],
    queryFn: () =>
      apiJson<StreamLiveProgress>(`/api/v1/jobs/${jobId}/stream-live-progress`, {}, getAuth, refresh),
    enabled: jobId != null && jobId > 0 && isStreaming,
    refetchInterval: 1500,
  })

  useEffect(() => {
    if (status !== 'completed' || jobId == null) return
    const t = window.setTimeout(() => {
      resultsAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 450)
    return () => window.clearTimeout(t)
  }, [status, jobId])

  const summaryQ = useQuery({
    queryKey: ['stream-summary', jobId],
    queryFn: () => apiJson<StreamSummary>(`/api/v1/jobs/${jobId}/stream-summary`, {}, getAuth, refresh),
    enabled: jobId != null && status === 'completed',
    retry: 1,
  })

  const previewQ = useQuery({
    queryKey: ['stream-preview', jobId],
    queryFn: () =>
      apiJson<ScoredPreview>(`/api/v1/jobs/${jobId}/scored-preview?limit=50`, {}, getAuth, refresh),
    enabled: jobId != null && status === 'completed',
    retry: 1,
  })

  const incidentReport = useMutation({
    mutationFn: async () => {
      if (jobId == null) throw new Error('No job id')
      return apiJson<{ source: string; text: string }>(
        '/api/v1/llm/stream-incident-report',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ job_id: jobId }) },
        getAuth,
        refresh,
      )
    },
  })
  const { mutate: requestIncidentReport } = incidentReport

  const compareRuns = useMutation({
    mutationFn: async () => {
      const a = parseInt(compareJobA.trim(), 10)
      const b = parseInt(compareJobB.trim(), 10)
      if (!Number.isFinite(a) || !Number.isFinite(b)) throw new Error('Enter two numeric job ids')
      return apiJson<Record<string, unknown>>(
        `/api/v1/jobs/compare-streams?job_a=${a}&job_b=${b}`,
        {},
        getAuth,
        refresh,
      )
    },
    onSuccess: (data) => {
      setCompareJson(JSON.stringify(data, null, 2))
    },
  })

  useEffect(() => {
    if (status !== 'completed' || jobId == null || !autoIncidentReport) return
    if (autoIncidentTriggeredForJob.current === jobId) return
    autoIncidentTriggeredForJob.current = jobId
    requestIncidentReport()
  }, [status, jobId, autoIncidentReport, requestIncidentReport])

  const remainingSec = Math.max(0, Math.floor(windowSeconds) - elapsedSec)
  const progressPct =
    windowSeconds > 0 ? Math.min(100, (elapsedSec / windowSeconds) * 100) : status === 'completed' ? 100 : 0

  const reportVerdict = status === 'completed' && summaryQ.data ? verdictFromSummary(summaryQ.data) : null

  const serverHasDefault = Boolean(streamHintsQ.data?.resolved_if_empty)

  /** Server can resolve conn.log when the field is empty (live file, lab sim, settings, env). */
  const canStartStream = useMemo(() => {
    if (connLog.trim()) return true
    const h = streamHintsQ.data
    if (!h) return false
    return Boolean(
      (h.resolved_if_empty && String(h.resolved_if_empty).trim()) ||
        (h.live_conn_log_abs && String(h.live_conn_log_abs).trim()),
    )
  }, [connLog, streamHintsQ.data])

  const pathReadyToStart = Boolean(connLog.trim()) || canStartStream

  const smartStrip = useMemo(() => {
    const h = streamHintsQ.data
    if (!h) return null
    const zeekOk = Boolean(h.zeek_in_path)
    const liveOk = Boolean(h.live_conn_log_exists)
    const listening = h.live_conn_log_active_capture === true
    const ageSec = typeof h.live_conn_log_age_sec === 'number' ? h.live_conn_log_age_sec : null
    const labOk = Boolean(h.lab_sim_conn_log_abs)
    const resolved = h.resolved_if_empty
    const rSrc = h.resolved_source
    return { zeekOk, liveOk, listening, ageSec, labOk, resolved, rSrc }
  }, [streamHintsQ.data])

  function resetSession(hint: 'default' | 'after_complete' | 'after_fail' = 'default') {
    const id = jobId
    setStartPanelHint(hint)
    setJobId(null)
    setStreamStartedAt(null)
    setWindowSeconds(0)
    setElapsedSec(0)
    setActiveConnPath(null)
    setActiveConnSource(null)
    incidentReport.reset()
    autoIncidentTriggeredForJob.current = null
    if (id != null) {
      queryClient.removeQueries({ queryKey: ['stream-job', id] })
      queryClient.removeQueries({ queryKey: ['stream-summary', id] })
      queryClient.removeQueries({ queryKey: ['stream-preview', id] })
      queryClient.removeQueries({ queryKey: ['stream-live-progress', id] })
    }
    void queryClient.invalidateQueries({ queryKey: ['stream-hints'] })
  }

  if (user?.role === 'viewer') {
    return (
      <div className="he-card">
        <p className="he-muted">Your account is read-only. Ask an admin for the analyst role to run live streams.</p>
      </div>
    )
  }

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Live stream</h1>
        <p className="he-page-subtitle" style={{ marginBottom: '0.5rem', maxWidth: '40rem' }}>
          Pick how long to watch a log on the server, tap start, and follow the live panel — no CLI on your laptop.
        </p>
        <p className="he-lead">
          A short window (1–3 minutes) is usually enough. If you leave the path empty, the server can use its default{' '}
          <code>conn.log</code>. While the window runs you&apos;ll see <strong>Listening</strong> and rows updating; when it ends, the report and sample table appear. Lab setup:{' '}
          <code>docs/STUDENT_LAB.md</code>.
        </p>
      </header>

      <DemoFlowGuide
        intro="Reviewer path: duration → Start → wait → read summary → optional AI report. Full list: sidebar Demo flow."
        steps={[
          {
            press: 'Choose window length, then Start streaming.',
            see: 'Live card: timer and rows scored.',
            then: 'When finished: summary + table + Generate report (if you need text).',
          },
          {
            press: 'Generate report (after run) or tick “Generate AI report when stream completes”.',
            see: 'Incident section fills with formatted text.',
          },
        ]}
      />

      {streamHintsQ.isError && !dismissStreamHintsError ? (
        <section
          className="he-card"
          style={{
            borderColor: 'rgba(251, 191, 36, 0.45)',
            background: 'rgba(251, 191, 36, 0.08)',
            marginBottom: '1rem',
          }}
        >
          <div className="he-row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <p style={{ margin: 0, fontSize: 14 }}>
              <strong>Could not load stream hints.</strong>{' '}
              {streamHintsQ.error instanceof ApiError && streamHintsQ.error.status === 404
                ? 'The API returned 404 for /api/v1/detections/stream-hints. Restart the backend from the same Hawk-Eye repo and version as this UI.'
                : errorMessage(streamHintsQ.error)}
            </p>
            <button type="button" className="he-btn he-btn--ghost" onClick={() => setDismissStreamHintsError(true)}>
              Dismiss
            </button>
          </div>
        </section>
      ) : null}

      {jobId == null ? (
        <section className="he-card">
          <h3>Start a capture</h3>
          {startPanelHint === 'after_complete' ? (
            <p className="he-stream-start-hint he-stream-start-hint--neutral">
              Previous window finished. Adjust duration or <code>conn.log</code> path if needed, then start another capture.
            </p>
          ) : null}
          {startPanelHint === 'after_fail' ? (
            <p className="he-stream-start-hint he-stream-start-hint--warn">
              Last run did not complete. Check <strong>Ops / health</strong>, your Zeek or lab sim path, and the error message
              above if it is still visible — then try again.
            </p>
          ) : null}
          <details className="he-stream-before-start" style={{ marginBottom: '1rem' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600, marginBottom: 8 }}>Before you start</summary>
            <HelpCallout title="Traffic source on the API host">
              <p style={{ marginTop: 0 }}>
                The browser does not read your network. Zeek (or a lab script) must write <code>conn.log</code> on the{' '}
                <strong>same machine as the API</strong>. If you leave <code>conn_log_path</code> empty, the server picks a default
                (see the readiness strip). More detail: <code>docs/STUDENT_LAB.md</code>.
              </p>
              <ul className="he-help-list" style={{ marginBottom: 0 }}>
                <li>
                  <strong>Lab sim</strong> — generate <code>data/lab/sim_conn.log</code> with{' '}
                  <code>scripts/lab_simulate_conn_log.py</code> (no Zeek required).
                </li>
                <li>
                  <strong>Live Zeek</strong> — <code>sudo ./scripts/zeek_network_capture.sh &lt;iface&gt;</code> on the API host.
                </li>
              </ul>
            </HelpCallout>
          </details>
          {streamHintsQ.data && smartStrip ? (
            <StreamCaptureReadinessStrip strip={smartStrip} title="Pipeline readiness (auto-refresh)" />
          ) : streamHintsQ.isLoading ? (
            <p className="he-muted" style={{ marginBottom: '0.75rem' }}>
              Checking server paths…
            </p>
          ) : null}
          {streamHintsQ.data ? (
            <p className="he-muted" style={{ marginBottom: '1rem', fontSize: 14 }}>
              On the <strong>machine running the API</strong>, start capture:{' '}
              <code>sudo ./scripts/zeek_network_capture.sh &lt;iface&gt;</code> (e.g. <code>en0</code>). This dashboard polls the
              server every few seconds — when Zeek writes <code>conn.log</code>, the strip shows{' '}
              <strong style={{ color: 'var(--he-success)' }}>listening</strong>.{' '}
              {streamHintsQ.data.zeek_in_path ? (
                <> Zeek binary: <code>{streamHintsQ.data.zeek_path ?? 'zeek'}</code>.</>
              ) : (
                <> Install Zeek on the API host and refresh.</>
              )}{' '}
              <button
                type="button"
                className="he-btn"
                style={{ marginLeft: 8, verticalAlign: 'baseline' }}
                disabled={!streamHintsQ.data.live_conn_log_abs}
                onClick={() => {
                  const p = streamHintsQ.data?.live_conn_log_abs
                  if (p) {
                    connPrefilled.current = true
                    setConnLog(p)
                  }
                }}
              >
                Use live path
              </button>
            </p>
          ) : null}
          <p className="he-muted" style={{ marginBottom: '1rem' }}>
            <strong>conn_log_path</strong> is optional when the server has a default (see readiness strip). Otherwise enter an{' '}
            <strong>absolute</strong> path to <code>conn.log</code> on the API host. Duration accepts <code>30s</code>,{' '}
            <code>10m</code>, <code>1h</code>, etc.
          </p>
          <div className="he-stack">
            <div>
              <span className="he-label">Window length</span>
              <div className="he-row" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
                {QUICK_DURATION_PRESETS.map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    className={durationStr === p.value ? 'he-btn he-btn--primary' : 'he-btn'}
                    onClick={() => setDurationStr(p.value)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <p className="he-muted" style={{ fontSize: 12, margin: '0 0 8px' }}>
                Longer runs
              </p>
              <div className="he-row" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
                {MORE_DURATION_PRESETS.map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    className={durationStr === p.value ? 'he-btn he-btn--primary' : 'he-btn'}
                    onClick={() => setDurationStr(p.value)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <input
                className="he-input he-input--narrow"
                value={durationStr}
                onChange={(e) => setDurationStr(e.target.value)}
                placeholder="10m"
                style={{ maxWidth: '12rem' }}
              />
            </div>
            <div>
              <span className="he-label">conn_log_path (optional if server default exists)</span>
              <input
                className="he-input"
                value={connLog}
                onChange={(e) => {
                  connPrefilled.current = true
                  setConnLog(e.target.value)
                }}
                placeholder={
                  serverHasDefault
                    ? 'Leave empty to use server default (readiness strip)'
                    : '/absolute/path/to/conn.log'
                }
              />
              {detectionSettingsQ.isLoading ? (
                <p className="he-muted" style={{ fontSize: 13, marginTop: 6 }}>
                  Loading saved detection settings…
                </p>
              ) : detectionSettingsQ.data?.conn_log_path && !connLog.trim() ? (
                <p className="he-muted" style={{ fontSize: 13, marginTop: 6 }}>
                  Saved in settings: <code>{String(detectionSettingsQ.data.conn_log_path)}</code> — included in server default
                  resolution when the field is empty.
                </p>
              ) : !connLog.trim() && serverHasDefault ? (
                <p className="he-muted" style={{ fontSize: 13, marginTop: 6 }}>
                  Empty field → server uses the same resolution as the strip (detection settings, env, then live/lab files).
                </p>
              ) : null}
            </div>
            <div>
              <span className="he-label">alert_log_path (optional)</span>
              <input className="he-input" value={alertLogPath} onChange={(e) => setAlertLogPath(e.target.value)} />
            </div>
            <div>
              <span className="he-label">webhook_url (optional)</span>
              <input className="he-input" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} />
            </div>
            <label className="he-row" style={{ alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={webhookOnlyKnownAttack}
                onChange={(e) => setWebhookOnlyKnownAttack(e.target.checked)}
              />
              <span>Webhook / alert log: KnownAttack rows only (skip AttackUncertain)</span>
            </label>
            <label className="he-row" style={{ alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                aria-label="Generate AI report when stream completes"
                checked={autoIncidentReport}
                onChange={(e) => setAutoIncidentReport(e.target.checked)}
              />
              <span>Generate AI report when stream completes (uses this browser tab session only)</span>
            </label>
            <div className="he-row">
              <button
                type="button"
                className="he-btn he-btn--primary"
                disabled={start.isPending || streamHintsQ.isLoading || !pathReadyToStart}
                title={
                  !pathReadyToStart && streamHintsQ.isSuccess
                    ? 'Need a conn.log the API can read: type a path, or ensure data/live/conn.log / lab sim / Detection settings / env default exists on the server.'
                    : undefined
                }
                onClick={() => start.mutate()}
              >
                Start streaming
              </button>
            </div>
            {start.isError ? <Err error={start.error} /> : null}
          </div>
        </section>
      ) : null}

      {jobId != null && isStreaming ? (
        <section ref={liveSessionRef} className="he-card he-stream-hero">
          <div className="he-stream-status">
            <span className="he-pill he-pill--live">● Live</span>
            <h2 className="he-stream-heading">
              Streaming for{' '}
              <span className="he-stream-duration-label">
                {windowSeconds > 0 ? formatDurationPhrase(windowSeconds) : durationStr}
              </span>
            </h2>
            <p className="he-stream-sub">
              Elapsed <strong>{formatClock(elapsedSec)}</strong>
              {windowSeconds > 0 ? (
                <>
                  {' '}
                  · <strong>{formatClock(remainingSec)}</strong> remaining (estimate)
                </>
              ) : null}
            </p>
            {liveProgressQ.data ? (
              <div
                className="he-stream-live-metrics"
                style={{
                  marginTop: 14,
                  padding: '10px 12px',
                  borderRadius: 'var(--he-radius-sm)',
                  background: 'var(--he-bg-surface)',
                  border: '1px solid var(--he-border)',
                  textAlign: 'left',
                }}
              >
                <div className="he-label" style={{ marginBottom: 4 }}>
                  Live scoring (Zeek → model)
                </div>
                <p style={{ margin: 0, fontSize: 15 }}>
                  <strong>{(liveProgressQ.data.rows_scored ?? 0).toLocaleString()}</strong>{' '}
                  <span className="he-muted">flow rows scored so far</span>
                </p>
                {typeof liveProgressQ.data.conn_log_line_offset === 'number' ? (
                  <p className="he-muted" style={{ margin: '6px 0 0', fontSize: 13 }}>
                    Zeek <code>conn.log</code> lines read:{' '}
                    {liveProgressQ.data.conn_log_line_offset.toLocaleString()}
                  </p>
                ) : (liveProgressQ.data.rows_scored ?? 0) === 0 ? (
                  <p className="he-muted" style={{ margin: '6px 0 0', fontSize: 13 }}>
                    Waiting for new lines — keep Zeek writing to the same path as this job.
                  </p>
                ) : null}
              </div>
            ) : isStreaming ? (
              <p className="he-muted" style={{ marginTop: 12, fontSize: 13 }}>
                Loading live scoring progress…
              </p>
            ) : null}
            <p className="he-muted" style={{ marginTop: 8 }}>
              Job #{jobId} · status: <code>{status || '…'}</code>
            </p>
            <div
              className="he-stream-config-recap"
              style={{
                marginTop: 14,
                padding: '12px 14px',
                borderRadius: 'var(--he-radius-sm)',
                background: 'var(--he-bg-elevated)',
                border: '1px solid var(--he-border)',
                textAlign: 'left',
              }}
            >
              <div className="he-label" style={{ marginBottom: 6 }}>
                Config for this run
              </div>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5 }}>
                <strong>Window:</strong> {durationStr}
                {windowSeconds > 0 ? (
                  <span className="he-muted"> ({formatDurationPhrase(windowSeconds)} on server)</span>
                ) : null}
                <br />
                <strong>
                  <code>conn.log</code>:
                </strong>{' '}
                <code style={{ wordBreak: 'break-all' }}>{activeConnPath ?? '…'}</code>
                {activeConnSource ? (
                  <span className="he-muted"> ({humanizeConnSource(activeConnSource)})</span>
                ) : null}
              </p>
            </div>
            {streamHintsQ.data && smartStrip ? (
              <div style={{ marginTop: 18, textAlign: 'left' }}>
                <StreamCaptureReadinessStrip
                  strip={smartStrip}
                  title="Listening · capture status (updates while live)"
                  showCopyResolved={false}
                  listeningHighlight
                />
              </div>
            ) : null}
            <div className="he-progress-track" aria-hidden>
              <div className="he-progress-fill" style={{ width: `${progressPct}%` }} />
            </div>
          </div>
        </section>
      ) : null}

      {jobId != null && status === 'completed' ? (
        <div ref={resultsAnchorRef} className="he-stream-results-anchor">
          <p className="he-sr-only" role="status" aria-live="polite" aria-atomic="true">
            Stream job {jobId} completed. Results follow.
          </p>
          {summaryQ.isLoading ? <p className="he-muted">Loading report…</p> : null}
          {summaryQ.isError ? (
            <div className="he-card">
              <Err error={summaryQ.error} />
              <button type="button" className="he-btn" style={{ marginTop: 12 }} onClick={() => resetSession()}>
                New stream
              </button>
            </div>
          ) : null}
          {summaryQ.data && reportVerdict ? (
            <>
              {summaryQ.data.risk_level ? (
                <section
                  className={`he-card he-risk-at-a-glance he-risk-at-a-glance--${summaryQ.data.risk_level} he-risk-at-a-glance--reveal`}
                >
                  <div className="he-risk-at-a-glance-top">
                    <span
                      className={`he-risk-mark he-risk-mark--${summaryQ.data.risk_level}`}
                      aria-hidden
                    >
                      {riskMarkGlyph(summaryQ.data.risk_level)}
                    </span>
                    <div>
                      <p className="he-risk-at-a-glance-eyebrow">Your verdict · this capture window</p>
                      <p className="he-risk-at-a-glance-headline">{summaryQ.data.risk_headline ?? reportVerdict.title}</p>
                    </div>
                  </div>
                  {summaryQ.data.risk_plain_summary ? (
                    <p className="he-risk-at-a-glance-body">{summaryQ.data.risk_plain_summary}</p>
                  ) : null}
                  <div className="he-risk-at-a-glance-meta">
                    <span className="he-chip he-chip--accent">
                      {riskVerdictBadge(summaryQ.data.risk_level)} ·{' '}
                      <strong style={{ textTransform: 'capitalize' }}>{summaryQ.data.risk_level}</strong>
                    </span>
                    {summaryQ.data.attack_indicators ? (
                      <span
                        className={`he-chip ${
                          summaryQ.data.attack_indicators === 'present' ? 'he-chip--warn' : 'he-chip--ok'
                        }`}
                      >
                        Attack-style signal:{' '}
                        <strong>{summaryQ.data.attack_indicators === 'present' ? 'detected' : 'none'}</strong>
                      </span>
                    ) : null}
                  </div>
                </section>
              ) : null}
              <div className="he-row" style={{ marginBottom: 12 }}>
                <button type="button" className="he-btn he-btn--primary" onClick={() => resetSession('after_complete')}>
                  New stream
                </button>
              </div>
            <section className="he-card">
              <h3>Metrics</h3>
              <div className="he-report-stats">
                <div className="he-stat">
                  <span className="he-stat-label">Window</span>
                  <span className="he-stat-value">{formatDurationPhrase(summaryQ.data.duration_seconds ?? windowSeconds)}</span>
                </div>
                <div className="he-stat">
                  <span className="he-stat-label">Rows scored</span>
                  <span className="he-stat-value">{(summaryQ.data.rows_scored ?? 0).toLocaleString()}</span>
                </div>
                <div className="he-stat">
                  <span className="he-stat-label">Alerts emitted</span>
                  <span className="he-stat-value">{(summaryQ.data.alerts_emitted ?? 0).toLocaleString()}</span>
                </div>
              </div>
              {summaryQ.data.decision_counts && Object.keys(summaryQ.data.decision_counts).length > 0 ? (
                <>
                  <h4>Model decisions</h4>
                  <div className="he-table-wrap he-table-wrap--sheet he-table-wrap--sheet-narrow">
                    <table className="he-table he-table--sheet">
                      <thead>
                        <tr>
                          <th>Decision label</th>
                          <th>Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summaryQ.data.decision_counts)
                          .sort((a, b) => b[1] - a[1])
                          .map(([label, n]) => (
                            <tr key={label}>
                              <td>
                                <FusionDecisionCountLabel raw={label} />
                              </td>
                              <td>{n.toLocaleString()}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
              {summaryQ.data.known_attack_types && Object.keys(summaryQ.data.known_attack_types).length > 0 ? (
                <>
                  <h4>Known attack types</h4>
                  <p className="he-muted" style={{ fontSize: 13, marginTop: 0 }}>
                    Supervised multiclass names on <code>KnownAttack</code> rows only. If you see <strong>Benign</strong> here, that
                    is the dataset’s name for <em>normal traffic</em> — it is not an attack type.
                  </p>
                  <div className="he-table-wrap he-table-wrap--sheet he-table-wrap--sheet-narrow">
                    <table className="he-table he-table--sheet">
                      <thead>
                        <tr>
                          <th>Family / label</th>
                          <th>Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summaryQ.data.known_attack_types)
                          .sort((a, b) => b[1] - a[1])
                          .map(([label, n]) => (
                            <tr key={label}>
                              <td>
                                <SupervisedFamilyCountLabel raw={label} />
                              </td>
                              <td>{n.toLocaleString()}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
              {summaryQ.data.output ? (
                <p className="he-muted" style={{ marginTop: 12, fontSize: 13 }}>
                  Parquet: <code>{summaryQ.data.output}</code>
                </p>
              ) : null}
            </section>
            {((summaryQ.data.decision_counts?.KnownAttack ?? 0) > 0 ||
              (summaryQ.data.decision_counts?.AttackUncertain ?? 0) > 0) ? (
            <section className="he-card">
              <h3>Incident report (LLM)</h3>
              <p className="he-muted" style={{ marginTop: '-0.25rem' }}>
                Human-style briefing: <strong>danger vs. no clear danger</strong> in plain language, then context and next steps.
                Uses the same numbers as the verdict above — set <code>OPENAI_API_KEY</code> or <code>DEEPSEEK_API_KEY</code> on the
                API for full prose; otherwise an offline template with the same structure.
              </p>
              {summaryQ.data?.risk_plain_summary ? (
                <p className="he-incident-report-precis" style={{ marginTop: 10, marginBottom: 0 }}>
                  <strong>Quick reminder:</strong> {summaryQ.data.risk_plain_summary}
                </p>
              ) : null}
              <div className="he-row" style={{ marginBottom: 12 }}>
                <button
                  type="button"
                  className="he-btn he-btn--primary"
                  disabled={incidentReport.isPending}
                  onClick={() => incidentReport.mutate()}
                >
                  {incidentReport.isPending ? 'Generating…' : 'Generate report'}
                </button>
                {incidentReport.data ? (
                  <span className="he-muted">
                    Source: <code>{incidentReport.data.source}</code>
                  </span>
                ) : null}
              </div>
              {incidentReport.isPending ? <LoadingBlock label="Generating incident report (LLM may take up to a minute)…" /> : null}
              {incidentReport.isError ? <Err error={incidentReport.error} /> : null}
              {incidentReport.data?.text ? (
                <div className="he-incident-report-wrap">
                  <MarkdownReader markdown={incidentReport.data.text} className="he-markdown-readme he-markdown-readme--incident" />
                </div>
              ) : null}
            </section>
            ) : null}
            <section className="he-card">
              <h3>Exports and compare</h3>
              <p className="he-muted" style={{ marginTop: '-0.25rem' }}>
                Markdown embeds the incident narrative if you generated it above. Worksheet opens in a browser; use Print to PDF.
              </p>
              <div className="he-row" style={{ flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                <button
                  type="button"
                  className="he-btn"
                  disabled={jobId == null}
                  onClick={() => {
                    if (jobId == null) return
                    const body: Record<string, unknown> = {}
                    if (incidentReport.data?.text) body.incident_markdown = incidentReport.data.text
                    void apiDownloadBlob(
                      `/api/v1/jobs/${jobId}/stream-markdown`,
                      { method: 'POST', headers: JSON_HDR, body: JSON.stringify(body) },
                      `hawk-eye-stream-${jobId}.md`,
                      getAuth,
                      refresh,
                    ).catch(() => undefined)
                  }}
                >
                  Download Markdown
                </button>
                <button
                  type="button"
                  className="he-btn"
                  disabled={jobId == null}
                  onClick={() => {
                    if (jobId == null) return
                    void apiDownloadBlob(
                      `/api/v1/jobs/${jobId}/stream-worksheet`,
                      {},
                      `hawk-eye-worksheet-${jobId}.html`,
                      getAuth,
                      refresh,
                    ).catch(() => undefined)
                  }}
                >
                  Download worksheet (HTML)
                </button>
                <button
                  type="button"
                  className="he-btn"
                  disabled={jobId == null}
                  onClick={() => {
                    if (jobId == null) return
                    void apiDownloadBlob(
                      `/api/v1/jobs/${jobId}/scored-parquet-file`,
                      {},
                      `job_${jobId}_scored.parquet`,
                      getAuth,
                      refresh,
                    ).catch(() => undefined)
                  }}
                >
                  Download Parquet
                </button>
              </div>
              <div className="he-stack" style={{ maxWidth: 520 }}>
                <span className="he-label">Compare two completed stream jobs</span>
                <div className="he-row" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <input
                    className="he-input he-input--narrow"
                    placeholder="Job A id"
                    value={compareJobA}
                    onChange={(e) => setCompareJobA(e.target.value)}
                    style={{ maxWidth: '8rem' }}
                  />
                  <input
                    className="he-input he-input--narrow"
                    placeholder="Job B id"
                    value={compareJobB}
                    onChange={(e) => setCompareJobB(e.target.value)}
                    style={{ maxWidth: '8rem' }}
                  />
                  <button
                    type="button"
                    className="he-btn"
                    disabled={compareRuns.isPending}
                    onClick={() => compareRuns.mutate()}
                  >
                    Compare
                  </button>
                </div>
                {compareRuns.isError ? <Err error={compareRuns.error} /> : null}
                {compareJson ? <pre className="he-json" style={{ maxHeight: 240 }}>{compareJson}</pre> : null}
              </div>
            </section>
            </>
          ) : null}

          <section className="he-card">
            <h3>Sample scored rows (last 50)</h3>
            <p className="he-sheet-hint">Same layout as a spreadsheet: frozen header row, grid lines, monospace cells. Export Parquet or worksheet for full data.</p>
            {previewQ.isLoading ? <p className="he-muted">Loading preview…</p> : null}
            {previewQ.isError ? <Err error={previewQ.error} /> : null}
            {previewQ.data && previewQ.data.rows?.length ? (
              <div className="he-table-wrap he-table-wrap--sheet">
                <table className="he-table he-table--sheet">
                  <thead>
                    <tr>
                      {scoredPreviewColumns(previewQ.data.rows).map((c) => (
                        <th key={c}>{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewQ.data.rows.map((r, i) => (
                      <tr key={i}>
                        {scoredPreviewColumns(previewQ.data.rows).map((c) => (
                          <td key={c}>{formatScoredCell(c, r[c])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : previewQ.data ? (
              <p className="he-muted">No rows in preview (empty Parquet).</p>
            ) : null}
            {(previewQ.data?.parquet_path || previewQ.data?.total_rows != null) && (
              <p className="he-muted" style={{ fontSize: 13 }}>
                {previewQ.data.total_rows != null ? <>Total rows in file: {previewQ.data.total_rows.toLocaleString()}. </> : null}
                {previewQ.data.parquet_path ? (
                  <>
                    Path: <code>{previewQ.data.parquet_path}</code>
                  </>
                ) : null}
              </p>
            )}
          </section>

        </div>
      ) : null}

      {jobId != null && status === 'failed' ? (
        <section className="he-card">
          <Err error={jobQ.data?.job?.error ?? jobQ.error ?? new Error('Stream job failed')} />
          <button type="button" className="he-btn" style={{ marginTop: 12 }} onClick={() => resetSession('after_fail')}>
            Try again
          </button>
        </section>
      ) : null}
    </div>
  )
}
