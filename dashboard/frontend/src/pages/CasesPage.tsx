import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function CasesPage() {
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [title, setTitle] = useState('case')
  const [priority, setPriority] = useState('medium')
  const [alertId, setAlertId] = useState('')

  const list = useQuery({
    queryKey: ['cases'],
    queryFn: () => apiJson<{ rows: { id: number; title: string; status: string }[] }>('/api/v1/cases', {}, getAuth, refresh),
  })

  const create = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = { title, priority }
      if (alertId.trim()) body.alert_id = parseInt(alertId, 10)
      return apiJson<unknown>('/api/v1/cases', { method: 'POST', headers: JSON_HDR, body: JSON.stringify(body) }, getAuth, refresh)
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['cases'] }),
  })

  const intro = (
    <>
      <header className="he-page-header">
        <h1 className="he-page-title">Cases</h1>
        <p className="he-lead">
          Investigation folders: attach alerts, add comments, assign owners, and track status until closure. Think “ticket”
          or “incident” tied to Hawk-Eye evidence.
        </p>
      </header>
      <HelpCallout title="Workflow">
        Open a case from a noisy alert cluster, then use comments and assignments so the team shares the same timeline.
      </HelpCallout>
    </>
  )

  if (user?.role === 'viewer') {
    return (
      <div>
        {intro}
        {list.data ? (
          <section className="he-card">
            <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
              {list.data.rows?.map((r) => (
                <li key={r.id}>
                  <Link to={`/cases/${r.id}`}>
                    #{r.id} {r.title} ({r.status})
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    )
  }

  return (
    <div>
      {intro}
      {list.data?.rows?.length ? (
        <section className="he-card">
          <h3 className="he-page-section-title">Open cases</h3>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {list.data.rows.map((r) => (
              <li key={r.id}>
                <Link to={`/cases/${r.id}`}>
                  #{r.id} {r.title} ({r.status})
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="he-muted">No cases yet—create one below.</p>
      )}

      <section className="he-card">
        <h3 className="he-page-section-title">New case</h3>
        <div className="he-stack">
          <div>
            <span className="he-label">Title</span>
            <input className="he-input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Priority</span>
            <input className="he-input he-input--narrow" value={priority} onChange={(e) => setPriority(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Link alert id (optional)</span>
            <input
              className="he-input he-input--narrow"
              value={alertId}
              onChange={(e) => setAlertId(e.target.value)}
              placeholder="Link alert id (optional)"
              aria-label="Link alert id (optional)"
            />
          </div>
          <button type="button" className="he-btn he-btn--primary" onClick={() => create.mutate()}>
            Create case
          </button>
        </div>
        {create.data ? <JsonView data={create.data} /> : null}
      </section>
    </div>
  )
}

export function CaseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const caseId = parseInt(id ?? '0', 10)
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [comment, setComment] = useState('')
  const [assignee, setAssignee] = useState('analyst')
  const [status, setStatus] = useState('in_progress')
  const [owner, setOwner] = useState<string | null>(null)

  const timeline = useQuery({
    queryKey: ['case-timeline', caseId],
    queryFn: () => apiJson<unknown>(`/api/v1/cases/${caseId}/timeline`, {}, getAuth, refresh),
    enabled: caseId > 0,
  })
  const comments = useQuery({
    queryKey: ['case-comments', caseId],
    queryFn: () => apiJson<unknown>(`/api/v1/cases/${caseId}/comments`, {}, getAuth, refresh),
    enabled: caseId > 0,
  })
  const assignments = useQuery({
    queryKey: ['case-assign', caseId],
    queryFn: () => apiJson<unknown>(`/api/v1/cases/${caseId}/assignments`, {}, getAuth, refresh),
    enabled: caseId > 0,
  })

  const addComment = useMutation({
    mutationFn: () =>
      apiJson<unknown>(
        `/api/v1/cases/${caseId}/comments`,
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ comment }) },
        getAuth,
        refresh,
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['case-comments', caseId] }),
  })
  const assign = useMutation({
    mutationFn: () =>
      apiJson<unknown>(
        `/api/v1/cases/${caseId}/assign`,
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ assignee }) },
        getAuth,
        refresh,
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['case-assign', caseId] }),
  })
  const patch = useMutation({
    mutationFn: () =>
      apiJson<unknown>(
        `/api/v1/cases/${caseId}`,
        { method: 'PATCH', headers: JSON_HDR, body: JSON.stringify({ status, owner }) },
        getAuth,
        refresh,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['cases'] })
      void qc.invalidateQueries({ queryKey: ['case-timeline', caseId] })
    },
  })

  if (!caseId) return <Err message="invalid id" />

  const detailIntro = (
    <>
      <header className="he-page-header">
        <h1 className="he-page-title">Case #{caseId}</h1>
        <p className="he-lead">Timeline, discussion, ownership, and status for this investigation.</p>
      </header>
      <Link to="/cases" className="he-btn he-btn--ghost" style={{ display: 'inline-block', marginBottom: 16 }}>
        ← All cases
      </Link>
    </>
  )

  if (user?.role === 'viewer') {
    return (
      <div>
        {detailIntro}
        <section className="he-card">
          <h3 className="he-page-section-title">Timeline</h3>
          {timeline.data ? <JsonView data={timeline.data} /> : null}
        </section>
        <section className="he-card">
          <h3 className="he-page-section-title">Comments</h3>
          {comments.data ? <JsonView data={comments.data} /> : null}
        </section>
      </div>
    )
  }

  return (
    <div>
      {detailIntro}
      <section className="he-card">
        <h3 className="he-page-section-title">Timeline</h3>
        {timeline.data ? <JsonView data={timeline.data} /> : null}
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">Comments</h3>
        {comments.data ? <JsonView data={comments.data} /> : null}
        <div className="he-row" style={{ marginTop: 12, alignItems: 'flex-end' }}>
          <input className="he-input" style={{ flex: 1, minWidth: 200 }} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a note" />
          <button type="button" className="he-btn he-btn--primary" onClick={() => addComment.mutate()}>
            Add comment
          </button>
        </div>
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">Assignments</h3>
        {assignments.data ? <JsonView data={assignments.data} /> : null}
        <div className="he-row" style={{ marginTop: 12, alignItems: 'flex-end' }}>
          <input className="he-input he-input--narrow" value={assignee} onChange={(e) => setAssignee(e.target.value)} />
          <button type="button" className="he-btn" onClick={() => assign.mutate()}>
            Assign
          </button>
        </div>
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">Update case</h3>
        <p className="he-muted">Change lifecycle fields stored on the case record.</p>
        <div className="he-stack">
          <div>
            <span className="he-label">Status</span>
            <input className="he-input he-input--narrow" value={status} onChange={(e) => setStatus(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Owner</span>
            <input className="he-input he-input--narrow" value={owner ?? ''} onChange={(e) => setOwner(e.target.value || null)} />
          </div>
          <button type="button" className="he-btn" onClick={() => patch.mutate()}>
            Save
          </button>
        </div>
      </section>
    </div>
  )
}
