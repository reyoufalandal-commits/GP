import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { Err, JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function IntegrationsPage() {
  const { getAuth, refresh, user } = useAuth()
  const [url, setUrl] = useState('https://httpbin.org/post')
  const [payloadRaw, setPayloadRaw] = useState('{"msg":"hawk-eye"}')

  const test = useMutation({
    mutationFn: () => {
      let payload: unknown = {}
      try {
        payload = JSON.parse(payloadRaw)
      } catch {
        /* empty */
      }
      return apiJson<unknown>(
        '/api/v1/integrations/webhook/test',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ url, payload }) },
        getAuth,
        refresh,
      )
    },
  })

  if (user?.role === 'viewer') {
    return (
      <div className="he-card">
        <p className="he-muted">Webhook tests require analyst or admin.</p>
      </div>
    )
  }

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Integrations</h1>
        <p className="he-lead">
          Ask the <strong>Hawk-Eye server</strong> to POST a sample JSON body to your URL—handy before wiring real alert or
          stream webhooks. This is not browser traffic; the API node performs the request.
        </p>
      </header>
      <HelpCallout title="Security note">
        Only point at systems you trust. The server will send whatever JSON you specify—avoid secrets in the payload for
        tests, or use disposable endpoints.
      </HelpCallout>
      <section className="he-card">
        <h3 className="he-page-section-title">Webhook test</h3>
        <div className="he-stack">
          <div>
            <span className="he-label">URL</span>
            <input className="he-input" value={url} onChange={(e) => setUrl(e.target.value)} />
          </div>
          <div>
            <span className="he-label">JSON payload</span>
            <textarea className="he-textarea" style={{ minHeight: 80 }} value={payloadRaw} onChange={(e) => setPayloadRaw(e.target.value)} spellCheck={false} />
          </div>
          <button type="button" className="he-btn he-btn--primary" onClick={() => test.mutate()} disabled={test.isPending}>
            Send test POST
          </button>
        </div>
        {test.isError ? <Err error={test.error} /> : null}
        {test.data ? <JsonView data={test.data} /> : null}
      </section>
    </div>
  )
}
