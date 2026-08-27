import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { apiJson } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function GovernancePage() {
  const { getAuth, refresh, user } = useAuth()
  const policy = useQuery({
    queryKey: ['gov-policy'],
    queryFn: () => apiJson<unknown>('/api/v1/governance/policy', {}, getAuth, refresh),
    enabled: user?.role !== 'viewer',
  })
  const schema = useQuery({
    queryKey: ['gov-schema'],
    queryFn: () => apiJson<unknown>('/api/v1/governance/schema-info', {}, getAuth, refresh),
    enabled: user?.role !== 'viewer',
  })
  const fusionPolicy = useQuery({
    queryKey: ['gov-fusion-policy'],
    queryFn: () => apiJson<unknown>('/api/v1/governance/fusion-policy', {}, getAuth, refresh),
  })

  if (user?.role === 'viewer') {
    return (
      <div>
        <header className="he-page-header">
          <h1 className="he-page-title">Governance</h1>
          <p className="he-lead">Read-only fusion metadata. Full policy JSON requires analyst or admin.</p>
        </header>
        <section className="he-card">
          <h3 className="he-page-section-title">Fusion policy (versioned)</h3>
          {fusionPolicy.isError ? (
            <Err error={fusionPolicy.error} />
          ) : fusionPolicy.data ? (
            <JsonView data={fusionPolicy.data} />
          ) : (
            <p className="he-muted">…</p>
          )}
        </section>
      </div>
    )
  }

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Governance</h1>
        <p className="he-lead">
          Policy documents and schema metadata the platform exposes for compliance and automation. Typical operators interact
          with <strong>Model lab</strong> and <strong>Alerts</strong> first; this area is for deeper audits.
        </p>
      </header>
      <HelpCallout title="What you are looking at">
        <strong>Policy</strong> is the active ruleset JSON the API evaluates. <strong>Schema info</strong> describes internal
        shapes auditors or integrators may need—both are read-only here.
      </HelpCallout>
      <section className="he-card">
        <h3 className="he-page-section-title">Policy</h3>
        {policy.isError ? <Err error={policy.error} /> : policy.data ? <JsonView data={policy.data} /> : <p className="he-muted">…</p>}
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">Schema info</h3>
        {schema.data ? <JsonView data={schema.data} /> : <p className="he-muted">…</p>}
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">Fusion policy (versioned)</h3>
        <p className="he-muted">Resolved thresholds plus SHA-256 of on-disk JSON sources for reproducibility.</p>
        {fusionPolicy.isError ? (
          <Err error={fusionPolicy.error} />
        ) : fusionPolicy.data ? (
          <JsonView data={fusionPolicy.data} />
        ) : (
          <p className="he-muted">…</p>
        )}
      </section>
    </div>
  )
}
