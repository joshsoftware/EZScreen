import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AuthProvider } from './features/auth/AuthContext'
import { RequireRole } from './features/auth/RequireRole'
import { SuperAdminShell } from './components/layout/SuperAdminShell'
import { SuperAdminLoginPage } from './pages/super-admin/SuperAdminLoginPage'
import { PageSkeleton } from './components/ui/Skeleton'

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

function Lazy({ children }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            className: 'font-body-sm text-body-sm',
            style: {
              background: '#ffffff',
              color: '#0f2740',
              border: '1px solid #c5d8ea',
            },
          }}
        />
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
