import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { apiFetch, apiJson, JSON_HDR, type GetAuth } from '../api/client'

const STORAGE_AT = 'hawk-eye-access'
const STORAGE_RT = 'hawk-eye-refresh'
const STORAGE_API = 'hawk-eye-api-key'

export type Role = 'admin' | 'analyst' | 'viewer'

export type AuthUser = {
  id: number
  username: string
  role: Role
  tenant_id: number | null
}

type Ctx = {
  user: AuthUser | null
  accessToken: string | null
  apiKey: string | null
  loading: boolean
  useApiKey: boolean
  setUseApiKey: (v: boolean) => void
  setApiKey: (k: string | null) => void
  getAuth: GetAuth
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<boolean>
  revokeAll: () => Promise<void>
  connectWithApiKey: (raw: string) => Promise<void>
}

const AuthContext = createContext<Ctx | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(() => sessionStorage.getItem(STORAGE_AT))
  const [refreshToken, setRefreshToken] = useState<string | null>(() => sessionStorage.getItem(STORAGE_RT))
  const [apiKey, setApiKeyState] = useState<string | null>(() => sessionStorage.getItem(STORAGE_API))
  const [useApiKey, setUseApiKey] = useState(() => !!sessionStorage.getItem(STORAGE_API))
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const getAuth = useCallback<GetAuth>(
    () => ({
      bearer: useApiKey ? null : accessToken,
      apiKey: useApiKey ? apiKey : null,
    }),
    [useApiKey, accessToken, apiKey],
  )

  const refresh = useCallback(async (): Promise<boolean> => {
    const rt = refreshToken
    if (!rt) return false
    try {
      const data = await apiJson<{ access_token: string; refresh_token: string }>('/api/v1/auth/refresh', {
        method: 'POST',
        headers: JSON_HDR,
        body: JSON.stringify({ refresh_token: rt }),
      })
      setAccessToken(data.access_token)
      setRefreshToken(data.refresh_token)
      sessionStorage.setItem(STORAGE_AT, data.access_token)
      sessionStorage.setItem(STORAGE_RT, data.refresh_token)
      return true
    } catch {
      setAccessToken(null)
      setRefreshToken(null)
      sessionStorage.removeItem(STORAGE_AT)
      sessionStorage.removeItem(STORAGE_RT)
      setUser(null)
      return false
    }
  }, [refreshToken])

  useEffect(() => {
    async function loadMe() {
      const auth = getAuth()
      if (!auth.apiKey && !auth.bearer) {
        setUser(null)
        setLoading(false)
        return
      }
      try {
        const r = await apiJson<{ user: AuthUser }>('/api/v1/auth/me', {}, getAuth, refresh)
        setUser(r.user)
      } catch {
        setUser(null)
      }
      setLoading(false)
    }
    void loadMe()
  }, [accessToken, apiKey, useApiKey, getAuth, refresh])

  const connectWithApiKey = useCallback(async (raw: string) => {
    const k = raw.trim()
    setApiKeyState(k)
    sessionStorage.setItem(STORAGE_API, k)
    setUseApiKey(true)
    setAccessToken(null)
    setRefreshToken(null)
    sessionStorage.removeItem(STORAGE_AT)
    sessionStorage.removeItem(STORAGE_RT)
    const r = await apiJson<{ user: AuthUser }>(
      '/api/v1/auth/me',
      {},
      () => ({ bearer: null, apiKey: k }),
      undefined,
    )
    setUser(r.user)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiJson<{
      access_token: string
      refresh_token: string
      user: AuthUser
    }>('/api/v1/auth/login', {
      method: 'POST',
      headers: JSON_HDR,
      body: JSON.stringify({ username, password }),
    })
    setUseApiKey(false)
    setApiKeyState(null)
    sessionStorage.removeItem(STORAGE_API)
    setAccessToken(data.access_token)
    setRefreshToken(data.refresh_token)
    setUser(data.user)
    sessionStorage.setItem(STORAGE_AT, data.access_token)
    sessionStorage.setItem(STORAGE_RT, data.refresh_token)
  }, [])

  const logout = useCallback(async () => {
    const t = accessToken
    if (t) {
      try {
        await apiFetch(
          '/api/v1/auth/logout',
          { method: 'POST', headers: JSON_HDR, body: JSON.stringify({ token: t }) },
          () => ({ bearer: t, apiKey: null }),
        )
      } catch {
        /* ignore */
      }
    }
    setAccessToken(null)
    setRefreshToken(null)
    setUser(null)
    sessionStorage.removeItem(STORAGE_AT)
    sessionStorage.removeItem(STORAGE_RT)
  }, [accessToken])

  const revokeAll = useCallback(async () => {
    await apiJson('/api/v1/auth/revoke-all', { method: 'POST' }, getAuth, refresh)
    await logout()
  }, [getAuth, refresh, logout])

  const setApiKey = useCallback((k: string | null) => {
    setApiKeyState(k)
    if (k) sessionStorage.setItem(STORAGE_API, k)
    else sessionStorage.removeItem(STORAGE_API)
  }, [])

  const value = useMemo(
    () => ({
      user,
      accessToken,
      apiKey,
      loading,
      useApiKey,
      setUseApiKey,
      setApiKey,
      getAuth,
      login,
      logout,
      refresh,
      revokeAll,
      connectWithApiKey,
    }),
    [user, accessToken, apiKey, loading, useApiKey, setApiKey, getAuth, login, logout, refresh, revokeAll, connectWithApiKey],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/** Hook is intentionally colocated with provider (Fast Refresh expects one component export per file for HMR). */
// eslint-disable-next-line react-refresh/only-export-components -- useAuth must live next to AuthProvider
export function useAuth() {
  const c = useContext(AuthContext)
  if (!c) throw new Error('useAuth outside provider')
  return c
}
