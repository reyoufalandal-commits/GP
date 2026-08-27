import { Link } from 'react-router-dom'
import { DemoFlowGuide } from '../components/DemoFlowGuide'

/**
 * Single page that lists every main area with the same pattern:
 * Press → See → Then. For thesis / reviewer demos where clarity matters.
 */
export function DefenseWalkthroughPage() {
  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Demo flow (all features)</h1>
        <p className="he-lead" style={{ maxWidth: '900px'}}>
          Use this page with the sidebar: every box below uses the same pattern — <strong>Press</strong> a control,{' '}
          <strong>See</strong> where the output appears, <strong>Then</strong> what to do next (if anything). No guessing.
        </p>
      </header>

      <section className="he-card" style={{ marginBottom: '1rem' }}>
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          Sidebar map
        </h2>
        <p className="he-muted" style={{ marginTop: 0 }}>
          <strong>Start here</strong> — checklist. <strong>Model lab</strong> — score/triage in the browser. <strong>Live stream</strong> — timed
          server log job. <strong>Ops / health</strong> — API alive? <strong>Settings</strong> — paths, history, links. <strong>Session</strong> — login
          tokens. Use <strong>Workflow &amp; tools</strong> under Settings for Alerts, Cases, Exports, etc.
        </p>
      </section>

      <section className="he-card" style={{ marginBottom: '1rem' }}>
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          <Link to="/">Model lab</Link> (home)
        </h2>
        <DemoFlowGuide
          intro="Fastest path for a live demo."
          steps={[
            {
              press: 'Try sample row (or Load built-in sample).',
              see: 'The JSON textarea fills with data.',
              then: 'Scroll to Run everything or Quick score / Full triage.',
            },
            {
              press: 'Run everything (big blue) or Quick score / Full triage.',
              see: 'Tables and “Raw response” appear lower on the same page.',
              then: 'Optional: Explain this row → JSON; Write summary → plain text (needs AI keys on server).',
            },
            {
              press: 'Choose a log file (conn.log) under “Or upload a network log”.',
              see: 'Triage output replaces manual JSON for that upload.',
            },
          ]}
        />
      </section>

      <section className="he-card" style={{ marginBottom: '1rem' }}>
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          <Link to="/stream">Live stream</Link>
        </h2>
        <DemoFlowGuide
          intro="Runs on the API server’s log file, not in your laptop’s network stack."
          steps={[
            {
              press: 'Pick duration (e.g. 2 min), leave path empty if the server has a default conn.log, then Start streaming.',
              see: 'A live panel shows elapsed time and row counts.',
              then: 'When the window ends, scroll to summary, preview table, and optional incident report.',
            },
            {
              press: 'Generate report (after the run) or enable “Generate AI report when stream completes”.',
              see: 'Markdown-style incident text appears in the incident section.',
              then: 'Use export buttons (worksheet, markdown, parquet) if shown for that job.',
            },
          ]}
        />
      </section>

      <section className="he-card" style={{ marginBottom: '1rem' }}>
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          <Link to="/reports">Activity summary</Link>
        </h2>
        <DemoFlowGuide
          steps={[
            {
              press: 'Open the page (no extra button).',
              see: 'JSON with alert counts and last stream job snapshot loads automatically.',
            },
          ]}
        />
      </section>

      <section className="he-card" style={{ marginBottom: '1rem' }}>
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          <Link to="/settings">Settings</Link> → Detection paths / History / Workflow
        </h2>
        <DemoFlowGuide
          steps={[
            {
              press: 'Detection paths: edit paths → Save.',
              see: 'Confirmation or updated fields (conn.log default, bundle dirs).',
            },
            {
              press: 'Detection history: open the tab.',
              see: 'Three tables: stream jobs, API runs, batch scores (from SQLite).',
            },
            {
              press: 'Workflow & tools: click a card.',
              see: 'You navigate to Alerts, Cases, Exports, etc.',
            },
          ]}
        />
      </section>

      <section className="he-card" style={{ marginBottom: '1rem' }}>
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          <Link to="/ops">Ops / health</Link>
        </h2>
        <DemoFlowGuide
          steps={[
            {
              press: 'Open the page.',
              see: '/health, /ready, and /metrics bodies load in separate cards.',
            },
          ]}
        />
      </section>

      <section className="he-card" style={{ marginBottom: '1rem' }}>
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          <Link to="/alerts">Alerts</Link> · <Link to="/cases">Cases</Link> · <Link to="/exports">Exports</Link>
        </h2>
        <DemoFlowGuide
          steps={[
            {
              press: 'Alerts: fill title/severity/label → Create (analyst+).',
              see: 'New row in the list; or change status with Patch.',
            },
            {
              press: 'Cases: create case, open detail, add comments / assign.',
              see: 'Timeline and comments update after each action.',
            },
            {
              press: 'Exports: start a job or use CSV/JSON download links.',
              see: 'File download or job status JSON.',
            },
          ]}
        />
      </section>

      <section className="he-card">
        <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
          <Link to="/session">Session</Link> · <Link to="/api-keys">API keys</Link>
        </h2>
        <DemoFlowGuide
          steps={[
            {
              press: 'Session: Logout or use refresh flow if tokens expire.',
              see: 'You return to login or stay signed in with new tokens.',
            },
            {
              press: 'API keys: Create name → copy key once.',
              see: 'Key listed; use X-API-Key in scripts.',
            },
          ]}
        />
      </section>
    </div>
  )
}
