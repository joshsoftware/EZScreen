import { Link, Outlet, useLocation, useParams } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { LogoMark } from '../brand/LogoMark'
import { PageTransition } from '../motion/Motion'
import { ORG_URL_SLUG } from '../../features/candidate/constants'

export function CandidateShell() {
  const location = useLocation()
  const { org = ORG_URL_SLUG } = useParams()
  const jobsPath = `/${org}/jobs`

  return (
    <div className="flex min-h-screen flex-col text-on-surface">
      <header className="h-14 shrink-0 border-b border-outline-variant/70 bg-surface-container-lowest/75 backdrop-blur-xl sticky top-0 z-30 flex items-center justify-between px-margin-mobile md:px-lg">
        <Link to={jobsPath} className="flex items-center gap-sm">
          <LogoMark subtitle="Careers" />
        </Link>
        <span className="hidden sm:inline text-body-sm text-on-surface-variant">
          Open positions
        </span>
      </header>

      <main className="flex-1 p-margin-mobile md:p-margin-desktop max-w-[1440px] w-full mx-auto">
        <AnimatePresence mode="wait">
          <PageTransition key={location.pathname}>
            <Outlet />
          </PageTransition>
        </AnimatePresence>
      </main>
    </div>
  )
}
