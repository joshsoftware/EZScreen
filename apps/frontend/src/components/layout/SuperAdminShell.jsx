import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { LogoMark } from '../brand/LogoMark'
import { useAuth } from '../../features/auth/AuthContext'
import { Button } from '../ui/Button'
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

export function SuperAdminShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const reduceMotion = useReducedMotion()
  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
    'Platform Super Admin'
  const initial = (user?.first_name?.[0] || user?.email?.[0] || 'P').toUpperCase()

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
          <LogoMark subtitle="Platform Control" />
        </div>
        <div className="p-md">
          <Button to="/super-admin/orgs/new" className="w-full" icon="add">
            Create Organization
          </Button>
        </div>
        <nav className="flex-1 px-sm space-y-xs overflow-y-auto">
          <NavLink to="/super-admin/orgs" end className={navClass}>
            <span className="material-symbols-outlined text-[20px]">domain</span>
            <span>Organizations</span>
          </NavLink>
          <NavLink to="/super-admin/health" className={navClass}>
            <span className="material-symbols-outlined text-[20px]">monitoring</span>
            <span>System Health</span>
          </NavLink>
          <NavLink to="/super-admin/settings" className={navClass}>
            <span className="material-symbols-outlined text-[20px]">settings</span>
            <span>Settings</span>
          </NavLink>
        </nav>
        <div className="p-md border-t border-outline-variant/70 space-y-sm">
          <div className="flex items-center gap-sm rounded-xl bg-surface-container-low/70 px-sm py-sm">
            <div className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center text-label-md font-label-md shadow-soft">
              {initial}
            </div>
            <div className="min-w-0">
              <p className="text-body-sm text-on-surface truncate font-medium">{displayName}</p>
              <p className="text-label-md text-on-surface-variant truncate">
                {user?.email}
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
            <LogoMark />
          </div>
          <div className="hidden md:flex items-center gap-sm text-body-sm text-on-surface-variant">
            <span className="inline-flex h-2 w-2 rounded-full bg-primary" />
            Platform control
          </div>
          <div className="flex items-center gap-md">
            <span className="material-symbols-outlined text-[20px] text-on-surface-variant">
              notifications
            </span>
            <button
              type="button"
              onClick={() => void logout()}
              className="md:hidden text-label-md text-on-surface-variant"
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 p-margin-mobile md:p-margin-desktop max-w-[1440px] w-full mx-auto">
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
