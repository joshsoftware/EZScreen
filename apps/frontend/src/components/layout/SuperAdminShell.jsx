import { NavLink, Outlet, Link } from 'react-router-dom'
import { LogoMark } from '../brand/LogoMark'
import { useAuth } from '../../features/auth/AuthContext'

function navClass({ isActive }) {
  return [
    'flex items-center gap-sm px-md py-sm rounded-lg text-body-sm relative',
    isActive
      ? 'bg-surface-container-low text-on-surface font-medium before:absolute before:left-0 before:top-1 before:bottom-1 before:w-0.5 before:bg-secondary before:rounded-full'
      : 'text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface',
  ].join(' ')
}

export function SuperAdminShell() {
  const { user, logout } = useAuth()
  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
    'Platform Super Admin'
  const initial = (user?.first_name?.[0] || user?.email?.[0] || 'P').toUpperCase()

  return (
    <div className="flex min-h-screen bg-surface text-on-surface">
      <aside className="hidden md:flex w-sidebar-width shrink-0 flex-col h-screen sticky top-0 border-r border-outline-variant bg-surface-container-lowest">
        <div className="p-lg border-b border-outline-variant">
          <LogoMark subtitle="Platform Control" />
        </div>
        <div className="p-md">
          <Link
            to="/super-admin/orgs/new"
            className="w-full h-10 flex items-center justify-center gap-xs bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md hover:bg-on-primary-fixed-variant transition-colors"
          >
            <span className="material-symbols-outlined text-[18px] text-on-primary">
              add
            </span>
            Create Organization
          </Link>
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
        <div className="p-md border-t border-outline-variant">
          <div className="flex items-center gap-sm">
            <div className="w-9 h-9 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center text-label-md font-label-md">
              {initial}
            </div>
            <div className="min-w-0">
              <p className="text-body-sm text-on-surface truncate">{displayName}</p>
              <p className="text-label-md text-on-surface-variant truncate">
                {user?.email}
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
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-outline-variant bg-surface-container-lowest/90 backdrop-blur sticky top-0 z-20 flex items-center justify-between px-margin-mobile md:px-margin-desktop">
          <div className="md:hidden">
            <LogoMark />
          </div>
          <div className="hidden md:block text-body-sm text-on-surface-variant">
            Workspace · EZScreen
          </div>
          <div className="flex items-center gap-md">
            <span className="material-symbols-outlined text-[20px]">notifications</span>
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
          <Outlet />
        </main>
      </div>
    </div>
  )
}
