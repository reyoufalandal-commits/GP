import { useAuth } from '../auth/AuthContext'
import { JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function SessionPage() {
  const { logout, revokeAll, user, refresh } = useAuth()
  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Session</h1>
        <p className="he-lead">
          Manage how you are signed in: refresh short-lived access tokens, log out this browser, or revoke every issued token
          for your account (forces re-login everywhere).
        </p>
      </header>
      <HelpCallout title="When to use these buttons">
        <p style={{ margin: 0 }}>
          Use <strong>Refresh access token</strong> if API calls suddenly return 401 but your password or API key is still
          valid. Use <strong>Logout</strong> on shared machines. <strong>Revoke all tokens</strong> is the strongest reset if
          you suspect key theft.
        </p>
      </HelpCallout>
      <section className="he-card">
        <h3 className="he-page-section-title">Current user</h3>
        <JsonView data={user ?? {}} />
      </section>
      <div className="he-row" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
        <button type="button" className="he-btn" onClick={() => void refresh()}>
          Refresh access token
        </button>
        <button type="button" className="he-btn" onClick={() => void logout()}>
          Logout (this browser)
        </button>
        <button type="button" className="he-btn he-btn--ghost" onClick={() => void revokeAll()}>
          Revoke all tokens
        </button>
      </div>
    </div>
  )
}
