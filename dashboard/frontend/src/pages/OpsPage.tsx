import { useQuery } from '@tanstack/react-query'
import { apiJson } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { LoadingBlock } from '../components/Loading'
import { HelpCallout } from '../components/HelpCallout'

async function text(path: string) {
  const r = await fetch(path)
  return { ok: r.ok, status: r.status, body: await r.text() }
}

export function OpsPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => apiJson<unknown>('/health', {}, undefined, undefined) })
  const ready = useQuery({ queryKey: ['ready'], queryFn: () => apiJson<unknown>('/ready', {}, undefined, undefined) })
  const metrics = useQuery({
    queryKey: ['metrics'],
    queryFn: async () => {
      const t = await text('/metrics')
      return t
    },
  })

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Ops / health</h1>
        <p className="he-lead">
          Confirm the API process is running and whether it is <strong>ready to score traffic</strong> (bundles, database,
          paths). Use this when something fails in Model lab or Live stream.
        </p>
      </header>
      <HelpCallout title="What each check means">
        <ul className="he-help-list" style={{ marginTop: 0 }}>
          <li>
            <strong>Health</strong> — The web service responds; a minimal “is the process up?” signal.
          </li>
          <li>
            <strong>Ready</strong> — Deeper checks: can the service actually load models and dependencies for scoring.
          </li>
          <li>
            <strong>Metrics</strong> — Prometheus-style text for monitoring tools; optional for day-to-day dashboard use.
          </li>
        </ul>
      </HelpCallout>

      <section className="he-card">
        <h3 className="he-page-section-title">/health</h3>
        <p className="he-muted">Process liveness.</p>
        {health.isError ? (
          <Err error={health.error} />
        ) : health.data ? (
          <JsonView data={health.data} />
        ) : (
          <LoadingBlock label="Loading health…" />
        )}
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">/ready</h3>
        <p className="he-muted">Scoring readiness (bundles, DB, etc.).</p>
        {ready.isError ? (
          <Err error={ready.error} />
        ) : ready.data ? (
          <JsonView data={ready.data} />
        ) : (
          <LoadingBlock label="Loading readiness…" />
        )}
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">/metrics (Prometheus)</h3>
        <p className="he-muted">For observability stacks; large text blob.</p>
        {metrics.data ? (
          <pre className="he-json" style={{ maxHeight: 280 }}>
            {metrics.data.body}
          </pre>
        ) : (
          <LoadingBlock label="Loading metrics…" />
        )}
      </section>
    </div>
  )
}
