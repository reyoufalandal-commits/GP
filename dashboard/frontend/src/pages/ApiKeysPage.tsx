import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiFetch, apiJson, JSON_HDR } from '../api/client'
import { JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function ApiKeysPage() {
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [name, setName] = useState('dashboard')
  const [lastCreated, setLastCreated] = useState<unknown>(null)

  const list = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => apiJson<{ rows: unknown[] }>('/api/v1/auth/api-keys', {}, getAuth, refresh),
    enabled: user?.role !== 'viewer',
  })

  const create = useMutation({
    mutationFn: async () => {
      return apiJson<unknown>('/api/v1/auth/api-keys', { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ name }) }, getAuth, refresh)
    },
    onSuccess: (data) => {
      setLastCreated(data)
      void qc.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })

  async function revoke(id: number) {
    await apiFetch(`/api/v1/auth/api-keys/${id}`, { method: 'DELETE' }, getAuth, refresh)
    void qc.invalidateQueries({ queryKey: ['api-keys'] })
  }

  if (user?.role === 'viewer') {
    return (
      <div className="he-card">
        <p className="he-muted">API keys are managed by analysts and admins.</p>
      </div>
    )
  }

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">API keys</h1>
        <p className="he-lead">
          Long-lived tokens for scripts, SIEM connectors, or automation. Keys are as sensitive as passwords—treat leaks as
          credential compromise.
        </p>
      </header>
      <HelpCallout title="After you create a key">
        The full secret is shown <strong>once</strong>. Store it in a vault or environment variable; you cannot retrieve it
        again from this screen. To rotate, create a new key, update clients, then revoke the old id.
      </HelpCallout>
      {list.data ? (
        <section className="he-card">
          <h3 className="he-page-section-title">Existing keys</h3>
          <JsonView data={list.data} />
        </section>
      ) : null}
      <section className="he-card">
        <h3 className="he-page-section-title">Create</h3>
        <div className="he-row" style={{ alignItems: 'flex-end', gap: 12 }}>
          <div>
            <span className="he-label">Label</span>
            <input className="he-input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <button type="button" className="he-btn he-btn--primary" onClick={() => create.mutate()}>
            Create key
          </button>
        </div>
        {lastCreated ? <JsonView data={lastCreated} /> : null}
      </section>
      <section className="he-card">
        <h3 className="he-page-section-title">Revoke</h3>
        <p className="he-muted">Use the numeric id from the list above.</p>
        <RevokeForm onRevoke={revoke} />
      </section>
    </div>
  )
}

function RevokeForm({ onRevoke }: { onRevoke: (id: number) => void }) {
  const [id, setId] = useState('')
  return (
    <div className="he-row" style={{ alignItems: 'flex-end', gap: 12 }}>
      <div>
        <span className="he-label">Key id</span>
        <input className="he-input he-input--narrow" value={id} onChange={(e) => setId(e.target.value)} />
      </div>
      <button type="button" className="he-btn" onClick={() => onRevoke(parseInt(id, 10))}>
        Revoke key
      </button>
    </div>
  )
}
