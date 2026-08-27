import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth/AuthContext'

const WS_PATH = '/api/v1/ws/events'

export function useLiveEvents(enabled: boolean) {
  const { accessToken, useApiKey } = useAuth()
  const [last, setLast] = useState<{ type: string; raw: string } | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!enabled || useApiKey || !accessToken) {
      const t = window.setTimeout(() => setConnected(false), 0)
      return () => window.clearTimeout(t)
    }
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${proto}//${host}${WS_PATH}?token=${encodeURIComponent(accessToken)}`
    const ws = new WebSocket(url)
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (ev) => {
      try {
        const o = JSON.parse(ev.data as string) as { type?: string }
        setLast({ type: String(o?.type ?? 'message'), raw: String(ev.data) })
      } catch {
        setLast({ type: 'raw', raw: String(ev.data) })
      }
    }
    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [enabled, accessToken, useApiKey])

  return { last, connected }
}
