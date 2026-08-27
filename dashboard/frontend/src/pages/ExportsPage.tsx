import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function ExportsPage() {
  const { getAuth, refresh } = useAuth()
  const qc = useQueryClient()
  const [jobId, setJobId] = useState('')

  const job = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => apiJson<unknown>(`/api/v1/jobs/${jobId}`, {}, getAuth, refresh),
    enabled: !!jobId && /^\d+$/.test(jobId),
  })

  const mkJob = useMutation({
    mutationFn: (jobType: string) =>
      apiJson<unknown>('/api/v1/jobs', { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ job_type: jobType }) }, getAuth, refresh),
    onSuccess: (data) => {
      const d = data as { job?: { id?: number } }
      if (d?.job?.id) setJobId(String(d.job.id))
      void qc.invalidateQueries({ queryKey: ['job'] })
    },
  })

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Exports & jobs</h1>
        <p className="he-lead">
          Pull bulk data out of Hawk-Eye or track <strong>background jobs</strong>. Direct browser links usually cannot send
          your auth cookie to downloads—use these buttons or <code>curl</code> with a token.
        </p>
      </header>
      <HelpCallout title="Downloads vs jobs">
        Links open in a new tab but may fail without headers. Prefer creating an export job and polling its id until the file
        is ready, or call the API from a script.
      </HelpCallout>

      <section className="he-card">
        <h3 className="he-page-section-title">Direct links (may require auth in another tool)</h3>
        <p>
          <a href="/api/v1/export/alerts.csv" target="_blank" rel="noreferrer">
            alerts.csv
          </a>
        </p>
        <p>
          <a href="/api/v1/export/audit.json" target="_blank" rel="noreferrer">
            audit.json
          </a>
        </p>
      </section>

      <section className="he-card">
        <h3 className="he-page-section-title">Create background job</h3>
        <p className="he-muted">Queues server-side export work; capture the returned job id.</p>
        <div className="he-row">
          <button type="button" className="he-btn" onClick={() => mkJob.mutate('export_alerts_csv')}>
            export_alerts_csv
          </button>
          <button type="button" className="he-btn" onClick={() => mkJob.mutate('export_audit_json')}>
            export_audit_json
          </button>
        </div>
        {mkJob.data ? <JsonView data={mkJob.data} /> : null}
      </section>

      <section className="he-card">
        <h3 className="he-page-section-title">Poll job by id</h3>
        <input className="he-input he-input--narrow" style={{ maxWidth: 160 }} value={jobId} onChange={(e) => setJobId(e.target.value)} placeholder="job id" />
        {job.data ? <JsonView data={job.data} /> : job.isError ? <Err error={job.error} /> : null}
      </section>
    </div>
  )
}
