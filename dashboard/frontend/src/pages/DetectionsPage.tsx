import { useMutation } from '@tanstack/react-query'
import { useState as useReactState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { Err, JsonView } from '../components/Err'

const sampleRows = '[\n  {"Flow Duration": 100, "Total Fwd Packets": 2}\n]'

export function DetectionsPage() {
  const { getAuth, refresh, user } = useAuth()
  const [rowsJson, setRowsJson] = useReactState(sampleRows)
  const [dur, setDur] = useReactState('30s')
  const [connLog, setConnLog] = useReactState('')

  const score = useMutation({
    mutationFn: async () => {
      const rows = JSON.parse(rowsJson) as Record<string, unknown>[]
      return apiJson<unknown>(
        '/api/v1/detections/score',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ rows }) },
        getAuth,
        refresh,
      )
    },
  })
  const triage = useMutation({
    mutationFn: async () => {
      const rows = JSON.parse(rowsJson) as Record<string, unknown>[]
      return apiJson<unknown>(
        '/api/v1/detections/triage',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ rows }) },
        getAuth,
        refresh,
      )
    },
  })
  const stream = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = { duration: dur }
      if (connLog.trim()) body.conn_log_path = connLog.trim()
      return apiJson<unknown>(
        '/api/v1/detections/stream-session',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify(body) },
        getAuth,
        refresh,
      )
    },
  })

  if (user?.role === 'viewer') return <p>Analyst or admin required.</p>

  return (
    <div>
      <h2>Detections</h2>
      <p>Rows JSON array (feature columns must match bundles):</p>
      <textarea style={{ width: '100%', minHeight: 140, fontFamily: 'monospace' }} value={rowsJson} onChange={(e) => setRowsJson(e.target.value)} />
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button type="button" onClick={() => score.mutate()} disabled={score.isPending}>
          POST /score
        </button>
        <button type="button" onClick={() => triage.mutate()} disabled={triage.isPending}>
          POST /triage
        </button>
      </div>
      {score.isError ? <Err error={score.error} /> : null}
      {score.data ? <JsonView data={score.data} /> : null}
      {triage.isError ? <Err error={triage.error} /> : null}
      {triage.data ? <JsonView data={triage.data} /> : null}

      <h3>Stream session</h3>
      <label>
        duration{' '}
        <input value={dur} onChange={(e) => setDur(e.target.value)} />
      </label>
      <label style={{ display: 'block', marginTop: 8 }}>
        conn_log_path override (optional if set in settings)
        <input value={connLog} onChange={(e) => setConnLog(e.target.value)} style={{ width: '100%' }} />
      </label>
      <button type="button" style={{ marginTop: 8 }} onClick={() => stream.mutate()} disabled={stream.isPending}>
        POST /stream-session
      </button>
      {stream.isError ? <Err error={stream.error} /> : null}
      {stream.data ? <JsonView data={stream.data} /> : null}
    </div>
  )
}
