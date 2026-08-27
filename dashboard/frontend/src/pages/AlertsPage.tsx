import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function AlertsPage() {
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [title, setTitle] = useState('test alert')
  const [severity, setSeverity] = useState('medium')
  const [label, setLabel] = useState('AttackUncertain')
  const [payloadRaw, setPayloadRaw] = useState('{}')
  const [statusAlertId, setStatusAlertId] = useState('')
  const [newStatus, setNewStatus] = useState('acknowledged')

  const list = useQuery({
    queryKey: ['alerts'],
    queryFn: () => apiJson<{ rows: unknown[] }>('/api/v1/alerts', {}, getAuth, refresh),
  })

  const create = useMutation({
    mutationFn: async () => {
      const payload = JSON.parse(payloadRaw || '{}') as Record<string, unknown>
      return apiJson<unknown>(
        '/api/v1/alerts',
        {
          method: 'POST',
          headers: JSON_HDR,
          body: JSON.stringify({ title, severity, decision_label: label, payload }),
        },
        getAuth,
        refresh,
      )
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  const patchStatus = useMutation({
    mutationFn: async () => {
      const id = parseInt(statusAlertId, 10)
      return apiJson<unknown>(
        `/api/v1/alerts/${id}/status`,
        { method: 'PATCH', headers: JSON_HDR, body: JSON.stringify({ status: newStatus }) },
        getAuth,
        refresh,
      )
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  const header = (
    <>
      <header className="he-page-header">
        <h1 className="he-page-title">Alerts</h1>
        <p className="he-lead">
          Workqueue of notable events (from the model, integrations, or manual entry). Analysts can acknowledge or triage;
          viewers can read the list.
        </p>
      </header>
      <HelpCallout title="Labels">
        <code>decision_label</code> usually matches model output (for example <code>AttackUncertain</code>). Severity is a
        separate human-oriented field for dashboards.
      </HelpCallout>
    </>
  )

  if (user?.role === 'viewer') {
    return (
      <div>
        {header}
        {list.data ? (
          <section className="he-card">
            <JsonView data={list.data} />
          </section>
        ) : (
          <p className="he-muted">Loading…</p>
        )}
      </div>
    )
  }

  return (
    <div>
      {header}
      {list.isError ? <Err error={list.error} /> : null}
      {list.data ? (
        <section className="he-card">
          <h3 className="he-page-section-title">All alerts</h3>
          <JsonView data={list.data} />
        </section>
      ) : list.isLoading ? (
        <p className="he-muted">Loading…</p>
      ) : null}

      <section className="he-card">
        <h3 className="he-page-section-title">Create alert</h3>
        <p className="he-muted">Manually file an alert (useful for drills or external systems).</p>
        <div className="he-stack" style={{ marginTop: 12 }}>
          <div>
            <span className="he-label">Title</span>
            <input className="he-input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Severity</span>
            <input className="he-input he-input--narrow" value={severity} onChange={(e) => setSeverity(e.target.value)} />
          </div>
          <div>
            <span className="he-label">decision_label</span>
            <input className="he-input he-input--narrow" value={label} onChange={(e) => setLabel(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Payload (JSON)</span>
            <textarea className="he-textarea" style={{ minHeight: 72 }} value={payloadRaw} onChange={(e) => setPayloadRaw(e.target.value)} spellCheck={false} />
          </div>
          <button type="button" className="he-btn he-btn--primary" onClick={() => create.mutate()} disabled={create.isPending}>
            Create
          </button>
        </div>
        {create.data ? <JsonView data={create.data} /> : null}
      </section>

      <section className="he-card">
        <h3 className="he-page-section-title">Update status</h3>
        <p className="he-muted">Move an alert through your workflow (ids appear in the list JSON).</p>
        <div className="he-inline-fields">
          <div>
            <span className="he-label">Alert id</span>
            <input
              className="he-input he-input--narrow"
              value={statusAlertId}
              onChange={(e) => setStatusAlertId(e.target.value)}
              placeholder="Alert id"
              aria-label="Alert id"
            />
          </div>
          <div>
            <span className="he-label">New status</span>
            <input className="he-input he-input--narrow" value={newStatus} onChange={(e) => setNewStatus(e.target.value)} />
          </div>
          <button type="button" className="he-btn" onClick={() => patchStatus.mutate()} disabled={patchStatus.isPending}>
            Apply
          </button>
        </div>
        {patchStatus.data ? <JsonView data={patchStatus.data} /> : null}
      </section>
    </div>
  )
}
