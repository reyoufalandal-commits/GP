import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function SettingsDetectionPage() {
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [raw, setRaw] = useState('')
  const q = useQuery({
    queryKey: ['detection-settings'],
    queryFn: () => apiJson<Record<string, unknown>>('/api/v1/settings/detection', {}, getAuth, refresh),
  })
  const mut = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      return apiJson<Record<string, unknown>>(
        '/api/v1/settings/detection',
        { method: 'PATCH', headers: JSON_HDR, body: JSON.stringify(body) },
        getAuth,
        refresh,
      )
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['detection-settings'] }),
  })

  if (user?.role === 'viewer') {
    return (
      <div className="he-card">
        <p className="he-muted">Viewers cannot change detection settings. Ask an analyst or admin to update paths or bundles.</p>
      </div>
    )
  }

  function apply() {
    try {
      const patch = JSON.parse(raw || '{}') as Record<string, unknown>
      if (!Object.keys(patch).length) {
        return
      }
      mut.mutate(patch)
    } catch {
      mut.reset()
    }
  }

  return (
    <div>
      <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
        Detection paths
      </h2>
      <p className="he-muted" style={{ marginTop: '-0.5rem', marginBottom: '1rem' }}>
        Server-side defaults: <strong>Zeek conn.log</strong>, poll interval, artifact directories. <strong>Live stream</strong> uses{' '}
        <code>conn_log_path</code> here unless overridden per job.
      </p>
      <HelpCallout title="Editing safely">
        Below is the current JSON the API stores. In the text area, paste only the <strong>fields you want to change</strong>{' '}
        and click Apply—this sends a PATCH, not a full replace. Common keys include <code>conn_log_path</code>,{' '}
        <code>stream_poll_seconds</code>, and bundle paths. Invalid JSON will be rejected.
      </HelpCallout>

      <section className="he-card">
        <h3 className="he-page-section-title">Current settings</h3>
        {q.data ? <JsonView data={q.data} /> : q.isLoading ? <p className="he-muted">Loading…</p> : <Err error={q.error} />}
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">PATCH body (JSON)</h3>
        <p className="he-muted">Example: {'{'} &quot;conn_log_path&quot;: &quot;/var/log/zeek/conn.log&quot; {'}'}</p>
        <textarea className="he-textarea" style={{ minHeight: 120 }} value={raw} onChange={(e) => setRaw(e.target.value)} spellCheck={false} />
        <div className="he-row" style={{ marginTop: 10 }}>
          <button type="button" className="he-btn he-btn--primary" onClick={apply} disabled={mut.isPending}>
            Apply changes
          </button>
        </div>
        {mut.isError ? <Err error={mut.error} /> : null}
        {mut.data ? <JsonView data={mut.data} /> : null}
      </section>
    </div>
  )
}
