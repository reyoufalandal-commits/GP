import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  /** Backend for dev + preview proxies (browser still calls same-origin `/api/...`). */
  const apiTarget = (env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000').replace(/\/$/, '')

  const proxy: Record<string, { target: string; changeOrigin: boolean; ws?: boolean }> = {
    '/api': { target: apiTarget, changeOrigin: true, ws: true },
    '/health': { target: apiTarget, changeOrigin: true },
    '/ready': { target: apiTarget, changeOrigin: true },
    '/metrics': { target: apiTarget, changeOrigin: true },
    '/docs': { target: apiTarget, changeOrigin: true },
    '/openapi.json': { target: apiTarget, changeOrigin: true },
  }

  return {
    plugins: [react()],
    server: {
      proxy,
    },
    /** Without this, `vite preview` serves the SPA but does not forward `/api` → 404 on all API calls. */
    preview: {
      proxy,
    },
    build: {
      outDir: 'dist',
    },
  }
})
