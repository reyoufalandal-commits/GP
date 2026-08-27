import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function RulesPage() {
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [name, setName] = useState('rule1')
  const [expression, setExpression] = useState('true')
  const [severity, setSeverity] = useState('medium')

  const list = useQuery({
    queryKey: ['rules'],
    queryFn: () => apiJson<{ rows: unknown[] }>('/api/v1/rules', {}, getAuth, refresh),
  })
  const create = useMutation({
    mutationFn: () =>
      apiJson<unknown>(
        '/api/v1/rules',
        { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ name, expression, severity, enabled: true }) },
        getAuth,
        refresh,
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['rules'] }),
  })

  const intro = (
    <>
      <header className="he-page-header">
        <h1 className="he-page-title">Rules</h1>
        <p className="he-lead">
          Named expressions the engine can evaluate against events or context—useful for routing, enrichment, or guardrails.
          Treat <code>expression</code> like code: test carefully before enabling in production.
        </p>
      </header>
      <HelpCallout title="Tip">
        Start with simple predicates you can reason about. pair rules with <strong>Suppressions</strong> when noise is from
        known-good assets.
      </HelpCallout>
    </>
  )

  if (user?.role === 'viewer') {
    return (
      <div>
        {intro}
        {list.data ? (
          <section className="he-card">
            <JsonView data={list.data} />
          </section>
        ) : null}
      </div>
    )
  }

  return (
    <div>
      {intro}
      {list.data ? (
        <section className="he-card">
          <h3 className="he-page-section-title">All rules</h3>
          <JsonView data={list.data} />
        </section>
      ) : null}
      <section className="he-card">
        <h3 className="he-page-section-title">Create rule</h3>
        <div className="he-stack">
          <div>
            <span className="he-label">Name</span>
            <input className="he-input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Expression</span>
            <input className="he-input" value={expression} onChange={(e) => setExpression(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Severity</span>
            <input className="he-input he-input--narrow" value={severity} onChange={(e) => setSeverity(e.target.value)} />
          </div>
          <button type="button" className="he-btn he-btn--primary" onClick={() => create.mutate()}>
            Create
          </button>
        </div>
        {create.data ? <JsonView data={create.data} /> : null}
      </section>
    </div>
  )
}
