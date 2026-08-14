import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { LogoMark } from '../brand/LogoMark'
import { useAuth } from '../../features/auth/AuthContext'
import { PageTransition } from '../motion/Motion'
import { cn } from '../../lib/cn'

function navClass({ isActive }) {
  return cn(
    'flex items-center gap-sm px-md py-sm rounded-lg text-body-sm relative transition-colors',
    isActive
      ? 'bg-surface-container-low text-on-surface font-medium before:absolute before:left-0 before:top-1 before:bottom-1 before:w-0.5 before:bg-secondary before:rounded-full'
      : 'text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface',
  )
}

export function OrgAdminShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const reduceMotion = useReducedMotion()
  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
    'Organization user'
  const roleLabel =
    user?.role === 'hr' ? 'HR' : user?.role === 'organization_admin' ? 'Org Admin' : user?.role
  const initial = (user?.first_name?.[0] || user?.email?.[0] || 'O').toUpperCase()

  const asideProps = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, x: -16 },
        animate: { opacity: 1, x: 0 },
        transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] },
      }

  return (
    <div className="flex min-h-screen bg-surface text-on-surface">
      <motion.aside
        className="hidden md:flex w-sidebar-width shrink-0 flex-col h-screen sticky top-0 border-r border-outline-variant bg-surface-container-lowest"
        {...asideProps}
      >
        <div className="p-lg border-b border-outline-variant">
          <LogoMark subtitle="Workspace" />
        </div>
        <nav className="flex-1 px-sm pt-md space-y-xs overflow-y-auto">
          <NavLink to="/org-admin" end className={navClass}>
            <span className="material-symbols-outlined text-[20px]">home</span>
            <span>Home</span>
          </NavLink>
          <NavLink to="/org-admin/team" className={navClass}>
            <span className="material-symbols-outlined text-[20px]">groups</span>
            <span>Team</span>
          </NavLink>
        </nav>
        <div className="p-md border-t border-outline-variant">
          <div className="flex items-center gap-sm">
            <div className="w-9 h-9 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center text-label-md font-label-md">
              {initial}
            </div>
            <div className="min-w-0">
              <p className="text-body-sm text-on-surface truncate">{displayName}</p>
              <p className="text-label-md text-on-surface-variant truncate">
                {roleLabel} · {user?.email}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void logout()}
            className="mt-sm block text-label-md text-on-surface-variant hover:text-secondary text-left"
          >
            Sign out
          </button>
        </div>
      </motion.aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-outline-variant bg-surface-container-lowest/90 backdrop-blur sticky top-0 z-20 flex items-center justify-between px-margin-mobile md:px-margin-desktop">
          <div className="md:hidden">
            <LogoMark subtitle="Workspace" />
          </div>
          <div className="hidden md:block text-body-sm text-on-surface-variant">
            Organization · EZScreen
          </div>
          <button
            type="button"
            onClick={() => void logout()}
            className="md:hidden text-label-md text-on-surface-variant"
          >
            Sign out
          </button>
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
