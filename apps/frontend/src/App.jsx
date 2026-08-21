import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AuthProvider } from './features/auth/AuthContext'
import { RequireRole } from './features/auth/RequireRole'
import { SuperAdminShell } from './components/layout/SuperAdminShell'
import { OrgAdminShell } from './components/layout/OrgAdminShell'
import { SuperAdminLoginPage } from './pages/super-admin/SuperAdminLoginPage'
import { OrgAdminLoginPage } from './pages/org-admin/OrgAdminLoginPage'
import { OrgAdminForgotPasswordPage } from './pages/org-admin/OrgAdminForgotPasswordPage'
import { OrgAdminResetPasswordPage } from './pages/org-admin/OrgAdminResetPasswordPage'
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
const OrgAdminHomePage = lazy(() =>
  import('./pages/org-admin/OrgAdminHomePage').then((m) => ({
    default: m.OrgAdminHomePage,
  })),
)
const OrgAdminTeamPage = lazy(() =>
  import('./pages/org-admin/OrgAdminTeamPage').then((m) => ({
    default: m.OrgAdminTeamPage,
  })),
)
const OrgAdminProvisionHrPage = lazy(() =>
  import('./pages/org-admin/OrgAdminProvisionHrPage').then((m) => ({
    default: m.OrgAdminProvisionHrPage,
  })),
)
const OrgAdminJobsPage = lazy(() =>
  import('./pages/org-admin/OrgAdminJobsPage').then((m) => ({
    default: m.OrgAdminJobsPage,
  })),
)
const OrgAdminJobCreatePage = lazy(() =>
  import('./pages/org-admin/OrgAdminJobCreatePage').then((m) => ({
    default: m.OrgAdminJobCreatePage,
  })),
)
const OrgAdminJobDetailPage = lazy(() =>
  import('./pages/org-admin/OrgAdminJobDetailPage').then((m) => ({
    default: m.OrgAdminJobDetailPage,
  })),
)
const OrgAdminApplicationDetailPage = lazy(() =>
  import('./pages/org-admin/OrgAdminApplicationDetailPage').then((m) => ({
    default: m.OrgAdminApplicationDetailPage,
  })),
)
const OrgAdminSettingsPage = lazy(() =>
  import('./pages/org-admin/OrgAdminSettingsPage').then((m) => ({
    default: m.OrgAdminSettingsPage,
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
          <Route path="/org-admin/login" element={<OrgAdminLoginPage />} />
          <Route
            path="/org-admin/forgot-password"
            element={<OrgAdminForgotPasswordPage />}
          />
          <Route
            path="/org-admin/reset-password"
            element={<OrgAdminResetPasswordPage />}
          />
          <Route path="/login" element={<Navigate to="/org-admin/login" replace />} />

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

          <Route
            path="/org-admin"
            element={
              <RequireRole
                roles={['organization_admin', 'hr']}
                loginPath="/org-admin/login"
              >
                <OrgAdminShell />
              </RequireRole>
            }
          >
            <Route
              index
              element={
                <Lazy>
                  <OrgAdminHomePage />
                </Lazy>
              }
            />
            <Route
              path="jobs"
              element={
                <Lazy>
                  <OrgAdminJobsPage />
                </Lazy>
              }
            />
            <Route
              path="jobs/new"
              element={
                <Lazy>
                  <OrgAdminJobCreatePage />
                </Lazy>
              }
            />
            <Route
              path="jobs/:jobId"
              element={
                <Lazy>
                  <OrgAdminJobDetailPage />
                </Lazy>
              }
            />
            <Route
              path="jobs/:jobId/applicants/:applicationId"
              element={
                <Lazy>
                  <OrgAdminApplicationDetailPage />
                </Lazy>
              }
            />
            <Route
              path="team"
              element={
                <RequireRole
                  roles={['organization_admin']}
                  loginPath="/org-admin"
                >
                  <Lazy>
                    <OrgAdminTeamPage />
                  </Lazy>
                </RequireRole>
              }
            />
            <Route
              path="team/invite"
              element={
                <RequireRole
                  roles={['organization_admin']}
                  loginPath="/org-admin/team"
                >
                  <Lazy>
                    <OrgAdminProvisionHrPage />
                  </Lazy>
                </RequireRole>
              }
            />
            <Route
              path="settings"
              element={
                <Lazy>
                  <OrgAdminSettingsPage />
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
