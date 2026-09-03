import { Link, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { LogoMark } from '../brand/LogoMark'
import { PageTransition } from '../motion/Motion'

export function CandidateShell() {
  const location = useLocation()

  return (
    <div className="flex min-h-screen flex-col text-on-surface bg-surface">
      <header className="sticky top-0 z-30 shrink-0 border-b border-outline-variant/70 bg-surface-container-lowest/85 backdrop-blur-xl shadow-soft">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-margin-mobile md:px-lg">
          <Link to="/jobs" className="flex items-center gap-sm transition-opacity hover:opacity-90">
            <LogoMark subtitle="Career Portal" />
          </Link>

          <nav className="flex items-center gap-md">
            <Link
              to="/jobs"
              className="text-body-sm font-medium text-on-surface hover:text-primary transition-colors"
            >
              Open Roles
            </Link>
            <Link
              to="/org-admin/login"
              className="inline-flex items-center gap-xs rounded-xl border border-outline-variant/80 px-md py-xs text-label-md font-medium text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface transition-all shadow-soft"
            >
              <span className="material-symbols-outlined text-[16px]">business_center</span>
              <span>Employer Login</span>
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <AnimatePresence mode="wait">
          <PageTransition key={location.pathname}>
            <Outlet />
          </PageTransition>
        </AnimatePresence>
      </main>

      <footer className="border-t border-outline-variant/60 bg-surface-container-lowest py-lg">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-md px-margin-mobile sm:flex-row md:px-lg">
          <div className="flex items-center gap-sm text-label-md text-on-surface-variant">
            <span>Powered by</span>
            <span className="font-semibold text-primary">EZScreen AI Recruiting</span>
          </div>
          <p className="text-label-md text-on-surface-variant/80">
            © {new Date().getFullYear()} EZScreen. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
