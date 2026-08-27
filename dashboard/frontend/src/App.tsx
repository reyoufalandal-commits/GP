import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Shell } from './layout/Shell'
import { LoginPage } from './pages/LoginPage'
import { HomePage } from './pages/HomePage'
import { ModelLabPage } from './pages/ModelLabPage'
import { OpsPage } from './pages/OpsPage'
import { SettingsLayout } from './pages/SettingsLayout'
import { SettingsDetectionPage } from './pages/SettingsDetectionPage'
import { SettingsHistoryPage } from './pages/SettingsHistoryPage'
import { SettingsWorkflowPage } from './pages/SettingsWorkflowPage'
import { AlertsPage } from './pages/AlertsPage'
import { CasesPage, CaseDetailPage } from './pages/CasesPage'
import { RulesPage } from './pages/RulesPage'
import { SuppressionsPage } from './pages/SuppressionsPage'
import { ExportsPage } from './pages/ExportsPage'
import { GovernancePage } from './pages/GovernancePage'
import { IntegrationsPage } from './pages/IntegrationsPage'
import { ApiKeysPage } from './pages/ApiKeysPage'
import { TenantsPage } from './pages/TenantsPage'
import { SessionPage } from './pages/SessionPage'
import { StreamSessionPage } from './pages/StreamSessionPage'
import { StudentStartPage } from './pages/StudentStartPage'
import { DefenseWalkthroughPage } from './pages/DefenseWalkthroughPage'
import { LoadingBlock } from './components/Loading'

const qc = new QueryClient()

function Private({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingBlock label="Loading session…" />
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Private>
            <Shell />
          </Private>
        }
      >
        <Route index element={<ModelLabPage />} />
        <Route path="start" element={<StudentStartPage />} />
        <Route path="guide" element={<DefenseWalkthroughPage />} />
        <Route path="stream" element={<StreamSessionPage />} />
        <Route path="reports" element={<HomePage />} />
        {/* Alias: home route is Model lab; /lab redirects for bookmarks */}
        <Route path="lab" element={<Navigate to="/" replace />} />
        <Route path="ops" element={<OpsPage />} />
        <Route path="settings" element={<SettingsLayout />}>
          <Route index element={<SettingsDetectionPage />} />
          <Route path="history" element={<SettingsHistoryPage />} />
          <Route path="workflow" element={<SettingsWorkflowPage />} />
        </Route>
        {/* Legacy path; detections UI lives under Model lab + Live stream */}
        <Route path="detections" element={<Navigate to="/" replace />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="cases" element={<CasesPage />} />
        <Route path="cases/:id" element={<CaseDetailPage />} />
        <Route path="rules" element={<RulesPage />} />
        <Route path="suppressions" element={<SuppressionsPage />} />
        <Route path="exports" element={<ExportsPage />} />
        <Route path="governance" element={<GovernancePage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="api-keys" element={<ApiKeysPage />} />
        <Route path="tenants" element={<TenantsPage />} />
        <Route path="session" element={<SessionPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
