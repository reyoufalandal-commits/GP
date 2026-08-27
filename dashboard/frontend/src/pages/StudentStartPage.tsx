import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiJson } from '../api/client'
import { LoadingBlock } from '../components/Loading'

const DOC_QUICKSTART = 'docs/STUDENT_QUICKSTART.md'
const DOC_LAB = 'docs/STUDENT_LAB.md'
const DOC_QUICKSTART_LAB = 'docs/QUICKSTART_LAB.md'

type ReadyPayload = { ready?: boolean; checks?: Record<string, { path?: string; exists?: boolean }> }

export function StudentStartPage() {
  const readyQ = useQuery({
    queryKey: ['ready-start'],
    queryFn: () => apiJson<ReadyPayload>('/ready', {}, undefined, undefined),
    staleTime: 30_000,
  })

  function copyDocPath(path: string) {
    void navigator.clipboard.writeText(path)
  }

  const ready = readyQ.data?.ready
  const readyLabel =
    readyQ.isLoading || readyQ.isFetching ? (
      <LoadingBlock label="Checking API readiness…" />
    ) : readyQ.isError ? (
      <span className="he-ready-badge he-ready-badge--warn">Could not load readiness (is the API running?)</span>
    ) : ready ? (
      <span className="he-ready-badge he-ready-badge--ok">Ready to score</span>
    ) : (
      <span className="he-ready-badge he-ready-badge--warn">Not ready — fix checks on Ops / health</span>
    )

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Start here</h1>
        <p className="he-lead">
          Follow these steps in order the first time you open Hawk-Eye. For a short guided path (~15 minutes), see{' '}
          <code>{DOC_QUICKSTART_LAB}</code>. Longer write-ups: <code>{DOC_QUICKSTART}</code> and <code>{DOC_LAB}</code> (clone or
          download the project to read them).
        </p>
        <p className="he-muted" style={{ marginTop: '-0.35rem' }}>
          For reviewers: <Link to="/guide">Demo flow</Link> lists every main screen as <strong>Press</strong> → <strong>See</strong> →{' '}
          <strong>Then</strong>.
        </p>
      </header>

      <section className="he-card he-start-readiness" aria-label="Scoring readiness">
        <div className="he-row he-start-readiness-row">
          <div>
            <h2 className="he-page-section-title he-start-readiness-title">Scoring readiness</h2>
            <p className="he-muted he-start-readiness-desc">
              Same signal as <Link to="/ops">Ops / health</Link> — green means bundles and DB look good for Model lab and Live
              stream.
            </p>
          </div>
          <div className="he-start-readiness-badge-wrap">{readyLabel}</div>
        </div>
      </section>

      <div className="he-start-grid">
        <section className="he-card he-start-card">
          <h2 className="he-page-section-title">1. Check readiness</h2>
          <p className="he-muted he-start-card-lead">
            Confirm the API is up and model bundles exist on disk. Use the badge above or open Ops for full JSON checks.
          </p>
          <p className="he-muted he-start-card-lead" style={{ fontSize: 13 }}>
            <strong>Looks good when:</strong> the badge says <em>Ready to score</em>, and Ops lists binary, supervised, and anomaly
            paths as present.
          </p>
          <Link to="/ops" className="he-btn he-btn--primary">
            Open Ops / health
          </Link>
        </section>

        <section className="he-card he-start-card">
          <h2 className="he-page-section-title">2. Try Model lab</h2>
          <p className="he-muted he-start-card-lead">
            Paste JSON rows or upload a file to run Score or Triage without Zeek. This is the default home after login.
          </p>
          <p className="he-muted he-start-card-lead" style={{ fontSize: 13 }}>
            <strong>Looks good when:</strong> <strong>Load built-in sample</strong> or <strong>Try sample row</strong> fills the box, and
            Score or Full triage returns a table with decision labels (no 503 bundle errors). The built-in file includes a third row
            for testing heuristic <em>Suspected_ZeroDay</em> / <em>AttackUncertain</em> on default bundles.
          </p>
          <Link to="/" className="he-btn he-btn--primary">
            Open Model lab
          </Link>
        </section>

        <section className="he-card he-start-card">
          <h2 className="he-page-section-title">3. Run Live stream</h2>
          <p className="he-muted he-start-card-lead">
            Timed scoring of Zeek <code>conn.log</code> on the API host. Start with a 1–3 minute window.
          </p>
          <p className="he-muted he-start-card-lead" style={{ fontSize: 13 }}>
            <strong>Looks good when:</strong> the job finishes with a summary card, non-zero rows scored if traffic hit the log, and
            the status strip shows a sensible <em>conn.log</em> hint. If you see 0 rows, see{' '}
            <Link to="/stream">Live stream</Link> tips and <code>docs/TROUBLESHOOTING_STREAM.md</code>.
          </p>
          <Link to="/stream" className="he-btn he-btn--primary">
            Open Live stream
          </Link>
        </section>

        <section className="he-card he-start-card">
          <h2 className="he-page-section-title">4. Lab documentation</h2>
          <p className="he-muted he-start-card-lead">
            Instructors usually assign markdown in the repository. Open those files in your editor, or copy the path below to
            paste into a file picker.
          </p>
          <details className="he-start-doc-advanced">
            <summary>Copy repo-relative paths (advanced)</summary>
            <div className="he-row he-start-doc-buttons">
              <button type="button" className="he-btn he-btn--primary" onClick={() => copyDocPath(DOC_QUICKSTART_LAB)}>
                Copy {DOC_QUICKSTART_LAB}
              </button>
              <button type="button" className="he-btn" onClick={() => copyDocPath(DOC_QUICKSTART)}>
                Copy {DOC_QUICKSTART}
              </button>
              <button type="button" className="he-btn" onClick={() => copyDocPath(DOC_LAB)}>
                Copy {DOC_LAB}
              </button>
            </div>
          </details>
        </section>
      </div>
    </div>
  )
}
