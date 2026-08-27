import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

type WFLink = { to: string; title: string; desc: string }

const LINKS: WFLink[] = [
  { to: '/reports', title: 'Activity summary', desc: 'Alert counters and last stream job snapshot.' },
  { to: '/alerts', title: 'Alerts', desc: 'Alert queue and status changes.' },
  { to: '/cases', title: 'Cases', desc: 'Investigations linking alerts and notes.' },
  { to: '/rules', title: 'Rules', desc: 'Detection rules and enrichment.' },
  { to: '/suppressions', title: 'Suppressions', desc: 'Quiet noisy indicators temporarily.' },
  { to: '/exports', title: 'Exports & jobs', desc: 'CSV/JSON exports and background jobs.' },
  { to: '/governance', title: 'Governance', desc: 'Policy and schema metadata.' },
  { to: '/integrations', title: 'Integrations', desc: 'Webhook tests from the server.' },
  { to: '/api-keys', title: 'API keys', desc: 'Tokens for scripts and API clients.' },
]

export function SettingsWorkflowPage() {
  const { user } = useAuth()
  const adminLinks: WFLink[] =
    user?.role === 'admin'
      ? [{ to: '/tenants', title: 'Tenants', desc: 'Multi-tenant administration.' }]
      : []

  return (
    <div>
      <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
        Workflow &amp; tools
      </h2>
      <p className="he-muted" style={{ marginTop: '-0.5rem', marginBottom: '1rem' }}>
        Quick links to analyst workflows. These pages are unchanged; they are grouped here so the main sidebar stays focused on{' '}
        <strong>Run</strong> and <strong>System</strong>. For a single page that lists every feature as Press → See → Then, open{' '}
        <Link to="/guide">Demo flow</Link>.
      </p>
      <div className="he-stack" style={{ gap: 12 }}>
        {[...LINKS, ...adminLinks].map((l) => (
          <Link key={l.to} to={l.to} className="he-card" style={{ textDecoration: 'none', display: 'block' }}>
            <h3 style={{ margin: '0 0 0.35rem', fontSize: '1.05rem', color: 'var(--he-text)' }}>{l.title}</h3>
            <p className="he-muted" style={{ margin: 0, fontSize: 14 }}>
              {l.desc}
            </p>
          </Link>
        ))}
      </div>
    </div>
  )
}
