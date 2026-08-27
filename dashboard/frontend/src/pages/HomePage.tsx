import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { apiJson } from '../api/client'
import { DemoFlowGuide } from '../components/DemoFlowGuide'
import { Err, JsonView } from '../components/Err'
import { LoadingBlock } from '../components/Loading'

export function HomePage() {
  const { getAuth, refresh } = useAuth()
  const q = useQuery({
    queryKey: ['report-summary'],
    queryFn: () => apiJson<Record<string, unknown>>('/api/v1/reports/summary', {}, getAuth, refresh),
  })
  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Activity summary</h1>
        <p className="he-lead">
          Quick <strong>API snapshot</strong> of alert counters and recent jobs — not PDF or worksheet exports. For scoring
          and narratives, use <strong>Model lab</strong> (default home) or <strong>Live stream</strong>.
        </p>
      </header>
      <DemoFlowGuide
        steps={[
          {
            press: 'Open this page (no button).',
            see: 'JSON loads below automatically — alert counts and last stream job.',
            then: 'Go to Model lab or Live stream to create new activity.',
          },
        ]}
      />
      {q.isError ? <Err error={q.error} /> : null}
      {q.data ? (
        <section className="he-card">
          <h3 className="he-page-section-title">Summary</h3>
          {q.data.last_stream_job != null && typeof q.data.last_stream_job === 'object' ? (
            <div style={{ marginBottom: '1rem' }}>
              <p className="he-muted" style={{ marginBottom: 6, fontSize: 14 }}>
                Last <strong>Live stream</strong> job (tenant-scoped)
              </p>
              <p style={{ fontSize: 14 }}>
                Job <code>#{(q.data.last_stream_job as { job_id?: number }).job_id}</code> — status{' '}
                <code>{String((q.data.last_stream_job as { status?: string }).status)}</code>
                {(q.data.last_stream_job as { risk_level?: string }).risk_level ? (
                  <>
                    {' '}
                    · risk <strong>{(q.data.last_stream_job as { risk_level: string }).risk_level}</strong>
                  </>
                ) : null}
              </p>
            </div>
          ) : (
            <p className="he-muted" style={{ marginBottom: '1rem', fontSize: 14 }}>
              No stream_collect jobs yet — start one under <strong>Live stream</strong>.
            </p>
          )}
          <JsonView data={q.data} />
        </section>
      ) : q.isLoading ? (
        <LoadingBlock label="Loading activity summary…" />
      ) : null}
    </div>
  )
}
