import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './features/auth/AuthContext'
import { RequireRole } from './features/auth/RequireRole'
import { SuperAdminShell } from './components/layout/SuperAdminShell'
import { SuperAdminLoginPage } from './pages/super-admin/SuperAdminLoginPage'

const SuperAdminOrgsPage = lazy(() =>
  import('./pages/super-admin/SuperAdminOrgsPage').then((m) => ({
    default: m.SuperAdminOrgsPage,
  })),
)
const SuperAdminOrgCreatePage = lazy(() =>
  import('./pages/super-admin/SuperAdminOrgCreatePage').then((m) => ({
    default: m.SuperAdminOrgCreatePage,
  })),
)
const SuperAdminOrgDetailPage = lazy(() =>
  import('./pages/super-admin/SuperAdminOrgDetailPage').then((m) => ({
    default: m.SuperAdminOrgDetailPage,
  })),
)
const SuperAdminProvisionPage = lazy(() =>
  import('./pages/super-admin/SuperAdminProvisionPage').then((m) => ({
    default: m.SuperAdminProvisionPage,
  })),
)
const SuperAdminHealthPage = lazy(() =>
  import('./pages/super-admin/SuperAdminHealthPage').then((m) => ({
    default: m.SuperAdminHealthPage,
  })),
)
const SuperAdminSettingsPage = lazy(() =>
  import('./pages/super-admin/SuperAdminSettingsPage').then((m) => ({
    default: m.SuperAdminSettingsPage,
  })),
)

function PageFallback() {
  return (
    <div className="text-body-sm text-on-surface-variant py-lg">Loading…</div>
  )
}

function Lazy({ children }) {
  return <Suspense fallback={<PageFallback />}>{children}</Suspense>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/super-admin/login" replace />} />
          <Route path="/super-admin/login" element={<SuperAdminLoginPage />} />
          <Route path="/login" element={<Navigate to="/super-admin/login" replace />} />

          <Route
            path="/super-admin"
            element={
              <RequireRole roles={['super_admin']}>
                <SuperAdminShell />
              </RequireRole>
            }
          >
            <Route index element={<Navigate to="orgs" replace />} />
            <Route
              path="orgs"
              element={
                <Lazy>
                  <SuperAdminOrgsPage />
                </Lazy>
              }
            />
            <Route
              path="orgs/new"
              element={
                <Lazy>
                  <SuperAdminOrgCreatePage />
                </Lazy>
              }
            />
            <Route
              path="orgs/:orgId"
              element={
                <Lazy>
                  <SuperAdminOrgDetailPage />
                </Lazy>
              }
            />
            <Route
              path="orgs/:orgId/provision"
              element={
                <Lazy>
                  <SuperAdminProvisionPage />
                </Lazy>
              }
            />
            <Route
              path="health"
              element={
                <Lazy>
                  <SuperAdminHealthPage />
                </Lazy>
              }
            />
            <Route
              path="settings"
              element={
                <Lazy>
                  <SuperAdminSettingsPage />
                </Lazy>
              }
            />
          </Route>

          <Route path="*" element={<Navigate to="/super-admin/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
