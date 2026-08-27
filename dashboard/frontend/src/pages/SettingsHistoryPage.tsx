import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiJson, ApiError, type GetAuth } from '../api/client'
import { Err } from '../components/Err'
import { LoadingBlock } from '../components/Loading'

type HistoryResponse = {
  stream_jobs: Record<string, unknown>[]
  detection_runs: Record<string, unknown>[]
  scored_events_recent: Record<string, unknown>[]
}

/** Rows per page in each table (UI). */
const PAGE_SIZE = 100
/** Max rows to request from the API per list (backend caps: jobs 200, runs 500, scored 200). */
const FETCH_LIMIT_JOBS = 200
const FETCH_LIMIT_RUNS = 200
const FETCH_LIMIT_SCORED = 200

/** Try all known aliases (proxies may only expose top-level /api/v1/* or certain prefixes). */
const DETECTION_HISTORY_PATHS = [
  '/api/v1/detection-history',
  '/api/v1/detections/history',
  '/api/v1/reports/detection-history',
  '/api/v1/settings/detection-history',
] as const

function historyQueryString(): string {
  const p = new URLSearchParams()
  p.set('limit_jobs', String(FETCH_LIMIT_JOBS))
  p.set('limit_runs', String(FETCH_LIMIT_RUNS))
  p.set('limit_scored', String(FETCH_LIMIT_SCORED))
  return `?${p.toString()}`
}

function normalizeHistory(raw: HistoryResponse | null | undefined): HistoryResponse {
  return {
    stream_jobs: Array.isArray(raw?.stream_jobs) ? raw.stream_jobs : [],
    detection_runs: Array.isArray(raw?.detection_runs) ? raw.detection_runs : [],
    scored_events_recent: Array.isArray(raw?.scored_events_recent) ? raw.scored_events_recent : [],
  }
}

async function fetchDetectionHistory(
  getAuth: GetAuth,
  refresh: () => Promise<boolean>,
): Promise<HistoryResponse> {
  const qs = historyQueryString()
  let last: unknown
  for (const path of DETECTION_HISTORY_PATHS) {
    try {
      const data = await apiJson<HistoryResponse>(`${path}${qs}`, {}, getAuth, refresh)
      return normalizeHistory(data)
    } catch (e) {
      last = e
      if (e instanceof ApiError && e.status === 404) continue
      throw e
    }
  }
  throw last
}

function usePagedSlice<T>(items: T[], pageSize: number) {
  const [page, setPage] = useState(0)
  const total = items.length
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const safePage = Math.min(page, totalPages - 1)
  useEffect(() => {
    setPage((p) => Math.min(p, Math.max(0, totalPages - 1)))
  }, [totalPages])
  const slice = items.slice(safePage * pageSize, safePage * pageSize + pageSize)
  return { page: safePage, setPage, slice, totalPages, total }
}

function TablePager({
  page,
  totalPages,
  total,
  showing,
  pageSize,
  onPrev,
  onNext,
}: {
  page: number
  totalPages: number
  total: number
  showing: number
  pageSize: number
  onPrev: () => void
  onNext: () => void
}) {
  if (total === 0) return null
  return (
    <div className="he-row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
      <span className="he-muted" style={{ fontSize: 13 }}>
        Showing {showing} of {total} ({pageSize} per page)
      </span>
      {totalPages > 1 ? (
        <div className="he-row" style={{ gap: 8, alignItems: 'center' }}>
          <button type="button" className="he-btn he-btn--ghost" disabled={page <= 0} onClick={onPrev}>
            Previous
          </button>
          <span className="he-muted" style={{ fontSize: 13 }}>
            Page {page + 1} / {totalPages}
          </span>
          <button type="button" className="he-btn he-btn--ghost" disabled={page >= totalPages - 1} onClick={onNext}>
            Next
          </button>
        </div>
      ) : null}
    </div>
  )
}

function fmtTs(v: unknown): string {
  if (v == null) return '—'
  const n = typeof v === 'number' ? v : parseInt(String(v), 10)
  if (!Number.isFinite(n)) return '—'
  return new Date(n * 1000).toLocaleString()
}

export function SettingsHistoryPage() {
  const { getAuth, refresh, user } = useAuth()
  const q = useQuery({
    queryKey: ['detections-history', FETCH_LIMIT_JOBS, FETCH_LIMIT_RUNS, FETCH_LIMIT_SCORED],
    queryFn: async () => fetchDetectionHistory(getAuth, refresh),
    enabled: !!user,
    retry: 1,
    staleTime: 30_000,
  })

  const streamJobs = q.data?.stream_jobs ?? []
  const detectionRuns = q.data?.detection_runs ?? []
  const scoredEvents = q.data?.scored_events_recent ?? []

  const pj = usePagedSlice(streamJobs, PAGE_SIZE)
  const pr = usePagedSlice(detectionRuns, PAGE_SIZE)
  const ps = usePagedSlice(scoredEvents, PAGE_SIZE)

  return (
    <div>
      <h2 className="he-page-section-title" style={{ marginTop: 0 }}>
        Detection history
      </h2>
      <p className="he-muted" style={{ marginTop: '-0.5rem', marginBottom: '1rem' }}>
        Data is read from SQLite: <strong>Live stream</strong> jobs, <strong>API</strong> score/triage runs from Model lab, and rows written by{' '}
        <code>store_results_sqlite.py</code>. Open a stream job on <Link to="/stream">Live stream</Link> for full detail. Lists load up to {FETCH_LIMIT_JOBS} / {FETCH_LIMIT_RUNS} /{' '}
        {FETCH_LIMIT_SCORED} rows each, shown <strong>{PAGE_SIZE}</strong> per page.
      </p>
      {q.isError ? <Err error={q.error} /> : null}
      {q.isPending ? <LoadingBlock label="Loading history…" /> : null}
      {q.isSuccess ? (
        <>
          <section className="he-card">
            <h3 className="he-page-section-title">Live stream jobs</h3>
            {streamJobs.length === 0 ? (
              <p className="he-muted">No stream jobs yet.</p>
            ) : (
              <>
                <p className="he-sheet-hint">Spreadsheet-style grid — scroll for long paths.</p>
                <div className="he-table-wrap he-table-wrap--sheet">
                  <table className="he-table he-table--sheet">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Summary / Parquet</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pj.slice.map((j) => (
                        <tr key={String(j.id)}>
                          <td>
                            <Link to="/stream">{String(j.id)}</Link>
                          </td>
                          <td>{String(j.status ?? '')}</td>
                          <td>{fmtTs(j.created_at)}</td>
                          <td className="he-muted" style={{ fontSize: 13, maxWidth: 360 }}>
                            {j.summary_json_path ? String(j.summary_json_path) : String(j.result_path ?? '—')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <TablePager
                  page={pj.page}
                  totalPages={pj.totalPages}
                  total={pj.total}
                  showing={pj.slice.length}
                  pageSize={PAGE_SIZE}
                  onPrev={() => pj.setPage((p) => Math.max(0, p - 1))}
                  onNext={() => pj.setPage((p) => Math.min(pj.totalPages - 1, p + 1))}
                />
              </>
            )}
          </section>
          <section className="he-card">
            <h3 className="he-page-section-title">API detection runs (score / triage)</h3>
            {detectionRuns.length === 0 ? (
              <p className="he-muted">No recorded runs yet — use Model lab to score or triage.</p>
            ) : (
              <>
                <p className="he-sheet-hint">Spreadsheet-style grid.</p>
                <div className="he-table-wrap he-table-wrap--sheet">
                  <table className="he-table he-table--sheet">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Kind</th>
                        <th>Rows</th>
                        <th>Actor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pr.slice.map((r) => (
                        <tr key={String(r.id)}>
                          <td>{fmtTs(r.created_at)}</td>
                          <td>
                            <code>{String(r.kind ?? '')}</code>
                          </td>
                          <td>{String(r.row_count ?? '')}</td>
                          <td>{String(r.actor_username ?? '')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <TablePager
                  page={pr.page}
                  totalPages={pr.totalPages}
                  total={pr.total}
                  showing={pr.slice.length}
                  pageSize={PAGE_SIZE}
                  onPrev={() => pr.setPage((p) => Math.max(0, p - 1))}
                  onNext={() => pr.setPage((p) => Math.min(pr.totalPages - 1, p + 1))}
                />
              </>
            )}
          </section>
          <section className="he-card">
            <h3 className="he-page-section-title">Recent batch scores (scored_events)</h3>
            {scoredEvents.length === 0 ? (
              <p className="he-muted">None — use scripts/store_results_sqlite.py or API-persisted rows.</p>
            ) : (
              <>
                <p className="he-sheet-hint">Spreadsheet-style grid — preview column may truncate; full value is in SQLite.</p>
                <div className="he-table-wrap he-table-wrap--sheet">
                  <table className="he-table he-table--sheet">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Score</th>
                        <th>Label</th>
                        <th>Preview</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ps.slice.map((s) => (
                        <tr key={String(s.id)}>
                          <td>{fmtTs(s.created_at)}</td>
                          <td>{String(s.score ?? '')}</td>
                          <td>{String(s.label ?? '—')}</td>
                          <td className="he-muted" style={{ fontSize: 12, maxWidth: 400 }}>
                            {(() => {
                              const t = String(s.raw_json_preview ?? '')
                              return t.length > 220 ? `${t.slice(0, 220)}…` : t
                            })()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <TablePager
                  page={ps.page}
                  totalPages={ps.totalPages}
                  total={ps.total}
                  showing={ps.slice.length}
                  pageSize={PAGE_SIZE}
                  onPrev={() => ps.setPage((p) => Math.max(0, p - 1))}
                  onNext={() => ps.setPage((p) => Math.min(ps.totalPages - 1, p + 1))}
                />
              </>
            )}
          </section>
        </>
      ) : null}
    </div>
  )
}
