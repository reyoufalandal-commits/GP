import { useQuery } from '@tanstack/react-query'
import { apiJson } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type StatusPayload = {
  version?: string
  service?: string
  ready?: boolean
  llm?: { llm_available?: boolean; provider?: string; model_default?: string }
}

type StreamHintsStrip = {
  live_conn_log_exists?: boolean
  live_conn_log_active_capture?: boolean
  resolved_if_empty?: string | null
}

function connLogStripLabel(h: StreamHintsStrip | undefined): string | null {
  if (!h) return null
  if (h.live_conn_log_exists) {
    return h.live_conn_log_active_capture ? 'conn.log: active' : 'conn.log: idle/stale'
  }
  return 'conn.log: not found'
}

/** Compact API + readiness + LLM (+ optional Zeek path hint when signed in). */
export function SystemStatusStrip() {
  const { user, getAuth, refresh } = useAuth()
  const q = useQuery({
    queryKey: ['api-v1-status'],
    queryFn: () => apiJson<StatusPayload>('/api/v1/status', {}, undefined, undefined),
    staleTime: 60_000,
    refetchInterval: 120_000,
  })

  const hintsQ = useQuery({
    queryKey: ['stream-hints-strip'],
    queryFn: () => apiJson<StreamHintsStrip>('/api/v1/detections/stream-hints', {}, getAuth, refresh),
    enabled: !!user,
    staleTime: 60_000,
    refetchInterval: 120_000,
  })

  if (q.isError || !q.data) {
    return null
  }

  const d = q.data
  const ver = d.version ?? '—'
  const ready = d.ready === true
  const llmOn = d.llm?.llm_available === true
  const llmLabel = llmOn ? `${d.llm?.provider ?? 'llm'} · ${d.llm?.model_default ?? ''}` : 'LLM off'
  const zeek = hintsQ.data ? connLogStripLabel(hintsQ.data) : null

  return (
    <div className="he-system-strip" role="status" aria-label="System status">
      <span className="he-system-strip-item">
        API <strong>{d.service ?? 'hawk-eye'}</strong> v{ver}
      </span>
      <span className={`he-system-strip-item ${ready ? 'he-system-strip-ok' : 'he-system-strip-warn'}`}>
        {ready ? 'Ready to score' : 'Not ready'}
      </span>
      <span className="he-system-strip-item">{llmLabel}</span>
      {zeek ? (
        <span className="he-system-strip-item" title={hintsQ.data?.resolved_if_empty || undefined}>
          {zeek}
        </span>
      ) : null}
    </div>
  )
}
