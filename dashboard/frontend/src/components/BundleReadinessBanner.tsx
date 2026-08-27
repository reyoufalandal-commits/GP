import { useQuery } from '@tanstack/react-query'
import { apiJson } from '../api/client'

type ReadyPayload = {
  ready?: boolean
  checks?: Record<string, { path?: string; exists?: boolean }>
}

export function BundleReadinessBanner() {
  const q = useQuery({
    queryKey: ['ready-banner'],
    queryFn: () => apiJson<ReadyPayload>('/ready', {}, undefined, undefined),
    refetchInterval: 60_000,
  })

  if (q.isError || !q.data || q.data.ready !== false) {
    return null
  }

  const missing: string[] = []
  const checks = q.data.checks ?? {}
  for (const [k, v] of Object.entries(checks)) {
    if (v && v.exists === false) {
      missing.push(k)
    }
  }

  return (
    <div
      className="he-card"
      style={{
        borderColor: 'var(--he-warn-border, #b45309)',
        background: 'var(--he-warn-bg, rgba(180, 83, 9, 0.12))',
        marginBottom: '1rem',
      }}
      data-testid="bundle-readiness-banner"
    >
      <h3 className="he-page-section-title" style={{ marginTop: 0 }}>
        Model bundles not ready
      </h3>
      <p className="he-lead" style={{ marginBottom: '0.5rem' }}>
        Scoring needs supervised, binary, and anomaly bundles on disk. Missing: <strong>{missing.join(', ') || 'unknown'}</strong>.
      </p>
      <p className="he-muted" style={{ margin: 0 }}>
        See <strong>Ops / health</strong> for full paths, and <code>docs/DASHBOARD_DEPLOY.md</code> for layout. For CI, run{' '}
        <code>python scripts/ci_build_minimal_bundles.py</code> to create tiny smoke bundles under <code>artifacts/</code>.
      </p>
    </div>
  )
}
