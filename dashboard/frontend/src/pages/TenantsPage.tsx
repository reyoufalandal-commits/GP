import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { apiJson, JSON_HDR } from '../api/client'
import { JsonView } from '../components/Err'
import { HelpCallout } from '../components/HelpCallout'

export function TenantsPage() {
  const { getAuth, refresh, user } = useAuth()
  const qc = useQueryClient()
  const [name, setName] = useState('tenant-a')

  const list = useQuery({
    queryKey: ['tenants'],
    queryFn: () => apiJson<{ rows: unknown[] }>('/api/v1/tenants', {}, getAuth, refresh),
    enabled: !!user,
  })

  const create = useMutation({
    mutationFn: () => apiJson<unknown>('/api/v1/tenants', { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ name }) }, getAuth, refresh),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['tenants'] }),
  })

  if (user?.role !== 'admin') {
    return (
      <div className="he-card">
        <p className="he-muted">Tenant administration is restricted to global admins.</p>
      </div>
    )
  }

  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Tenants</h1>
        <p className="he-lead">
          Create logical partitions for separate teams or customers. Each tenant can hold its own users, alerts, and
          configuration boundaries depending on your deployment.
        </p>
      </header>
      <HelpCallout title="Impact">
        Creating a tenant is an administrative action. Coordinate naming with identity and billing owners; deleting or merging
        tenants may require database operations outside this UI.
      </HelpCallout>
      {list.data ? (
        <section className="he-card">
          <h3 className="he-page-section-title">All tenants</h3>
          <JsonView data={list.data} />
        </section>
      ) : null}
      <section className="he-card">
        <h3 className="he-page-section-title">Create tenant</h3>
        <div className="he-row" style={{ alignItems: 'flex-end', gap: 12 }}>
          <div>
            <span className="he-label">Name</span>
            <input className="he-input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <button type="button" className="he-btn he-btn--primary" onClick={() => create.mutate()}>
            Create tenant
          </button>
        </div>
        {create.data ? <JsonView data={create.data} /> : null}
      </section>
    </div>
  )
}
