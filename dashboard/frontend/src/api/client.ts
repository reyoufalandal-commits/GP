export type GetAuth = () => { bearer: string | null; apiKey: string | null }

const JSON_HDR = { 'Content-Type': 'application/json' }

/** HTTP error from the API with optional FastAPI `detail` field parsed from JSON body. */
export class ApiError extends Error {
  override name = 'ApiError'
  status: number
  bodySnippet: string
  detail?: string

  constructor(message: string, status: number, bodySnippet: string, detail?: string) {
    super(message)
    this.status = status
    this.bodySnippet = bodySnippet
    this.detail = detail
  }
}

function parseFastApiDetail(text: string): string | undefined {
  try {
    const j = JSON.parse(text) as { detail?: unknown }
    if (typeof j.detail === 'string') return j.detail
    if (Array.isArray(j.detail)) return JSON.stringify(j.detail)
  } catch {
    /* not JSON */
  }
  return undefined
}

/** Human-readable message for UI (prefers API `detail` when present). */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.detail) return e.status ? `${e.status}: ${e.detail}` : e.detail
    return e.message
  }
  if (e instanceof Error) return e.message
  return String(e)
}

/**
 * Short, user-facing copy for common API failures (logs and debugging still use `errorMessage`).
 */
export function friendlyApiMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail?.trim()
    switch (e.status) {
      case 401:
        return 'Not signed in or session expired. Open Session to refresh your token or sign in again.'
      case 403:
        return d ? `Access denied: ${d}` : 'You do not have permission for this action.'
      case 404:
        if (!d || d.toLowerCase() === 'not found') {
          return (
            'API returned 404 — the browser is probably not hitting the Hawk-Eye backend. Run npm run dev or npm run preview (both proxy /api), or set VITE_API_BASE when hosting static files without a proxy. Start the API on port 8000 or set VITE_PROXY_TARGET to match your uvicorn URL.'
          )
        }
        return `Not found: ${d}`
      case 429:
        return 'Too many requests (about 120 per minute per client and path). Wait briefly, reduce polling, or batch calls — see docs/ENVIRONMENT.md.'
      case 502:
        return d
          ? `Service temporarily unavailable: ${d}`
          : 'The server could not complete this request (e.g. upstream or LLM). Try again later.'
      default:
        break
    }
  }
  return errorMessage(e)
}

function applyAuth(headers: Headers, auth: { bearer: string | null; apiKey: string | null }) {
  if (auth.apiKey) headers.set('X-API-Key', auth.apiKey)
  else if (auth.bearer) headers.set('Authorization', `Bearer ${auth.bearer}`)
}

/**
 * When `VITE_API_BASE` is set (e.g. http://127.0.0.1:8000), `/api/...` requests use that origin
 * instead of the page origin. Use when the UI is served without a dev proxy to the API
 * (e.g. `vite preview` or static files on a different port than uvicorn).
 */
export function resolveApiUrl(path: string): string {
  const raw = import.meta.env.VITE_API_BASE as string | undefined
  const base = typeof raw === 'string' ? raw.trim().replace(/\/$/, '') : ''
  if (base && path.startsWith('/api')) {
    return `${base}${path}`
  }
  return path
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
  getAuth?: GetAuth,
  refresh?: () => Promise<boolean>,
): Promise<Response> {
  const url = resolveApiUrl(path)
  const headers = new Headers(init.headers)
  if (getAuth) applyAuth(headers, getAuth())
  let res: Response
  try {
    res = await fetch(url, { ...init, headers })
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(
        'Cannot reach the Hawk-Eye API. Start it (e.g. ./scripts/run_api_8000.sh), set VITE_API_BASE to the API origin if the UI is not proxied, and ensure CORS allows this origin (docs/OPERATOR_GUIDE_LOCAL.md).',
      )
    }
    throw e
  }

  if (res.status === 401 && refresh && getAuth) {
    const a = getAuth()
    if (a.bearer && !a.apiKey) {
      const ok = await refresh()
      if (ok) {
        const h2 = new Headers(init.headers)
        applyAuth(h2, getAuth())
        res = await fetch(url, { ...init, headers: h2 })
      }
    }
  }
  return res
}

export async function apiJson<T>(
  path: string,
  init: RequestInit = {},
  getAuth?: GetAuth,
  refresh?: () => Promise<boolean>,
): Promise<T> {
  const res = await apiFetch(path, init, getAuth, refresh)
  if (!res.ok) {
    const text = await res.text()
    const detail = parseFastApiDetail(text)
    const fallback = `${res.status} ${res.statusText}: ${text.slice(0, 500)}`
    const msg = detail ?? fallback
    throw new ApiError(msg, res.status, text.slice(0, 500), detail)
  }
  return res.json() as Promise<T>
}

/** Download response body as a file in the browser (uses auth headers). */
export async function apiDownloadBlob(
  path: string,
  init: RequestInit,
  filename: string,
  getAuth?: GetAuth,
  refresh?: () => Promise<boolean>,
): Promise<void> {
  const res = await apiFetch(path, init, getAuth, refresh)
  if (!res.ok) {
    const text = await res.text()
    const detail = parseFastApiDetail(text)
    throw new ApiError(
      detail ?? `${res.status} ${res.statusText}`,
      res.status,
      text.slice(0, 500),
      detail,
    )
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export { JSON_HDR }
