import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { LogoMark } from '../brand/LogoMark'
import { useAuth } from '../../features/auth/AuthContext'
import { OrgSettingsProvider } from '../../features/org-admin/OrgSettingsContext'
import { WorkspaceHealthProvider } from '../../features/system/WorkspaceHealthContext'
import { useWorkspaceHealthContext } from '../../features/system/WorkspaceHealthContext'
import { statusDotClass, statusSummary } from '../../features/system/healthUtils'
import { ServiceHealthBanner } from '../system/ServiceHealthBanner'
import { PageTransition } from '../motion/Motion'
import { cn } from '../../lib/cn'

function navClass({ isActive }) {
  return cn(
    'flex items-center gap-sm px-md py-sm rounded-xl text-body-sm relative transition-all',
    isActive
      ? 'bg-primary-container/80 text-on-primary-container font-medium shadow-soft'
      : 'text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface',
  )
}

export function OrgAdminShell() {
  return (
    <OrgSettingsProvider>
      <WorkspaceHealthProvider>
        <OrgAdminShellLayout />
      </WorkspaceHealthProvider>
    </OrgSettingsProvider>
  )
}

function OrgAdminShellLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const reduceMotion = useReducedMotion()
  const { health, status, services } = useWorkspaceHealthContext()
  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
    'Organization user'
  const roleLabel =
    user?.role === 'hr' ? 'HR' : user?.role === 'organization_admin' ? 'Org Admin' : user?.role
  const isOrgAdmin = user?.role === 'organization_admin'
  const initial = (user?.first_name?.[0] || user?.email?.[0] || 'O').toUpperCase()

  const asideProps = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, x: -16 },
        animate: { opacity: 1, x: 0 },
        transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] },
      }

  return (
    <div className="flex min-h-screen text-on-surface">
        <motion.aside
          className="hidden md:flex w-sidebar-width shrink-0 flex-col h-screen sticky top-0 border-r border-outline-variant/70 bg-surface-container-lowest/85 backdrop-blur-xl"
          {...asideProps}
        >
          <div className="h-14 shrink-0 flex items-center px-lg border-b border-outline-variant/70">
            <LogoMark subtitle="Workspace" />
          </div>
          <nav className="flex-1 px-sm py-md space-y-xs overflow-y-auto">
            <NavLink to="/org-admin" end className={navClass}>
              <span className="material-symbols-outlined text-[20px]">home</span>
              <span>Home</span>
            </NavLink>
            <NavLink to="/org-admin/jobs" className={navClass}>
              <span className="material-symbols-outlined text-[20px]">work</span>
              <span>Jobs</span>
            </NavLink>
            <NavLink to="/org-admin/settings" className={navClass}>
              <span className="material-symbols-outlined text-[20px]">tune</span>
              <span>Settings</span>
            </NavLink>
            {isOrgAdmin ? (
              <NavLink to="/org-admin/team" className={navClass}>
                <span className="material-symbols-outlined text-[20px]">groups</span>
                <span>Team</span>
              </NavLink>
            ) : null}
          </nav>
          <div className="p-md border-t border-outline-variant/70 space-y-sm">
            <div className="flex items-center gap-sm rounded-xl bg-surface-container-low/70 px-sm py-sm">
              <div className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center text-label-md font-label-md shadow-soft">
                {initial}
              </div>
              <div className="min-w-0">
                <p className="text-body-sm text-on-surface truncate font-medium">
                  {displayName}
                </p>
                <p className="text-label-md text-on-surface-variant truncate">
                  {roleLabel}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              className="w-full rounded-xl px-md py-sm text-left text-label-md text-on-surface-variant hover:bg-surface-container-low hover:text-secondary transition-colors"
            >
              Sign out
            </button>
          </div>
        </motion.aside>

        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-14 shrink-0 border-b border-outline-variant/70 bg-surface-container-lowest/75 backdrop-blur-xl sticky top-0 z-20 flex items-center justify-between px-margin-mobile md:px-lg">
            <div className="md:hidden">
              <LogoMark subtitle="Workspace" />
            </div>
            <div className="hidden md:flex items-center gap-sm text-body-sm text-on-surface-variant">
              <span
                className={cn(
                  'inline-flex h-2 w-2 rounded-full',
                  status ? statusDotClass(status) : 'bg-primary',
                )}
                title={status ? statusSummary(status) : 'Checking services…'}
              />
              Screening workspace
              {status && status !== 'healthy' ? (
                <span className="text-amber-800">· {statusSummary(status)}</span>
              ) : null}
            </div>
            <nav className="md:hidden flex items-center gap-xs">
              <NavLink
                to="/org-admin/jobs"
                className="rounded-lg px-sm py-xs text-label-md text-on-surface-variant"
              >
                Jobs
              </NavLink>
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded-lg px-sm py-xs text-label-md text-on-surface-variant"
              >
                Sign out
              </button>
            </nav>
          </header>
          <main className="flex-1 p-margin-mobile md:p-margin-desktop max-w-[1440px] w-full mx-auto">
            {health ? (
              <div className="mb-lg">
                <ServiceHealthBanner status={status} services={services} />
              </div>
            ) : null}
            <AnimatePresence mode="wait">
              <PageTransition key={location.pathname}>
                <Outlet />
              </PageTransition>
            </AnimatePresence>
          </main>
        </div>
    </div>
  )
}
