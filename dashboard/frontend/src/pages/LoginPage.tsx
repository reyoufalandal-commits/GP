import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { login, user, loading, useApiKey, setUseApiKey, connectWithApiKey } = useAuth()
  const [userField, setUserField] = useState('admin')
  const [pass, setPass] = useState('admin123')
  const [keyField, setKeyField] = useState('')
  const [err, setErr] = useState<string | null>(null)

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErr(null)

    try {
      if (useApiKey) {
        await connectWithApiKey(keyField)
      } else {
        await login(userField, pass)
      }
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'login failed')
    }
  }

  return (
    <div className="he-login-new">
      <div className="he-login-wrapper">

        {/* LOGO */}
        <img src="/logo.png" alt="logo" className="he-login-logo-big" />

        {/* TITLE */}
        <h1 className="he-title">Hawk-Eye</h1>
         

        {/* BOX */}
        <div className="he-login-card he-login-dark">

          <p className="he-lead" style={{ textAlign: 'center' }}>
            Sign in to try sample data, upload files, and see results here — no terminal required.
          </p>

          {import.meta.env.DEV ? (
            <p className="he-muted" style={{ textAlign: 'center', fontSize: '0.85rem' }}>
              Default user: <code>admin</code> / <code>admin123</code>
            </p>
          ) : null}

          <form onSubmit={onSubmit} className="he-stack">
            <label className="he-checkbox-label">
              <input
                type="checkbox"
                checked={useApiKey}
                onChange={(e) => setUseApiKey(e.target.checked)}
              />
              Use X-API-Key
            </label>

            {useApiKey ? (
              <div>
                <span className="he-label">API key</span>
                <input
                  className="he-input"
                  value={keyField}
                  onChange={(e) => setKeyField(e.target.value)}
                  placeholder="he_…"
                />
              </div>
            ) : (
              <>
                <div>
                  <span className="he-label">Username</span>
                  <input
                    className="he-input"
                    value={userField}
                    onChange={(e) => setUserField(e.target.value)}
                    placeholder="username"
                  />
                </div>

                <div>
                  <span className="he-label">Password</span>
                  <input
                    className="he-input"
                    type="password"
                    value={pass}
                    onChange={(e) => setPass(e.target.value)}
                    placeholder="password"
                  />
                </div>
              </>
            )}

            <button className="he-btn he-btn--primary">Continue</button>

            {err ? <pre className="he-err">{err}</pre> : null}
          </form>

        </div>
      </div>
    </div>
  )
}