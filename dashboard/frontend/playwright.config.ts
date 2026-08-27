import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(frontendDir, '../..')
const venvPy = path.join(repoRoot, '.venv', 'bin', 'python')
const venvPyWin = path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
const py =
  process.env.PLAYWRIGHT_PYTHON ??
  (fs.existsSync(venvPy)
    ? venvPy
    : fs.existsSync(venvPyWin)
      ? venvPyWin
      : process.platform === 'win32'
        ? 'python'
        : 'python3')

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `cd "${repoRoot}" && HAWK_EYE_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174 ${py} -m uvicorn hawk_eye.api_service:app --host 127.0.0.1 --port 8000`,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: frontendDir,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
})
