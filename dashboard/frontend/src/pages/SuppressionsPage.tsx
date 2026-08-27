import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function SuppressionsPage() {
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [targetType, setTargetType] = useState('ip')
  const [targetValue, setTargetValue] = useState('10.0.0.1')
  const [reason, setReason] = useState('test')

  const list = useQuery({
    queryKey: ['suppressions'],
    queryFn: () => apiJson<{ rows: unknown[] }>('/api/v1/suppressions', {}, getAuth, refresh),
  })
  const create = useMutation({
    mutationFn: () =>
      apiJson<unknown>(
        '/api/v1/suppressions',
        {
          method: 'POST',
          headers: JSON_HDR,
          body: JSON.stringify({ target_type: targetType, target_value: targetValue, reason }),
        },
        getAuth,
        refresh,
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['suppressions'] }),
  })

  const intro = (
    <>
      <header className="he-page-header">
        <h1 className="he-page-title">Suppressions</h1>
        <p className="he-lead">
          Temporarily mute noisy but trusted targets (for example a scanner IP or management host) so they do not flood
          alerts. Always record <strong>why</strong> you suppressed, and review periodically.
        </p>
      </header>
      <HelpCallout title="Safety">
        Suppressions reduce visibility—use the smallest scope (single IP or label) that fixes the problem, and remove them
        when the underlying traffic changes.
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
          <h3 className="he-page-section-title">Active suppressions</h3>
          <JsonView data={list.data} />
        </section>
      ) : null}
      <section className="he-card">
        <h3 className="he-page-section-title">Add suppression</h3>
        <div className="he-stack">
          <div>
            <span className="he-label">Target type</span>
            <input className="he-input he-input--narrow" value={targetType} onChange={(e) => setTargetType(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Target value</span>
            <input className="he-input" value={targetValue} onChange={(e) => setTargetValue(e.target.value)} />
          </div>
          <div>
            <span className="he-label">Reason (auditable)</span>
            <input className="he-input" value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <button type="button" className="he-btn he-btn--primary" onClick={() => create.mutate()}>
            Create
          </button>
        </div>
      </section>
    </div>
  )
}
