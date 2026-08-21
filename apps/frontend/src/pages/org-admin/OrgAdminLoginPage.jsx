import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { LogoMark } from '../../components/brand/LogoMark'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input, PasswordInput } from '../../components/ui/Input'
import { FadeIn, FadeSlide } from '../../components/motion/Motion'
import { useAuth } from '../../features/auth/AuthContext'
import { ApiError } from '../../lib/api/client'

const ORG_WORKSPACE_ROLES = new Set(['organization_admin', 'hr'])

export function OrgAdminLoginPage() {
  const { loginOrg, logout, user, isBootstrapping } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  if (!isBootstrapping && ORG_WORKSPACE_ROLES.has(user?.role)) {
    return <Navigate to="/org-admin" replace />
  }

  async function onSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const loggedIn = await loginOrg(email.trim(), password)
      if (!ORG_WORKSPACE_ROLES.has(loggedIn.role)) {
        await logout()
        setError('Use platform Super Admin login for this account.')
        return
      }
      toast.success('Signed in')
      navigate('/org-admin', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Unable to sign in. Check that the API is running.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="h-full min-h-screen bg-surface text-on-surface antialiased flex flex-col md:flex-row">
      <FadeSlide
        from="left"
        className="flex-1 flex flex-col justify-center px-margin-mobile md:px-margin-desktop lg:px-[120px] relative z-10 w-full md:max-w-[50%] lg:max-w-[45%] min-h-screen bg-surface-container-lowest"
      >
        <header className="absolute top-0 left-0 w-full py-lg px-margin-mobile md:px-margin-desktop">
          <LogoMark subtitle="Organization" />
        </header>

        <FadeIn
          delay={0.08}
          className="w-full max-w-[400px] mx-auto mt-2xl md:mt-0"
        >
          <div className="mb-xl">
            <h1 className="font-display-lg text-display-lg-mobile md:text-display-lg text-on-surface mb-sm">
              Workspace access
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Sign in as Organization Admin or HR to manage your hiring workspace.
            </p>
          </div>

          <form className="flex flex-col gap-md" onSubmit={onSubmit} noValidate>
            <Input
              id="org-email"
              label="Work email"
              name="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-12"
              required
            />
            <PasswordInput
              id="org-password"
              label="Password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-12"
              required
            />

            <div className="-mt-xs flex justify-end">
              <Link
                className="text-body-sm text-secondary hover:underline"
                to="/org-admin/forgot-password"
              >
                Forgot password?
              </Link>
            </div>

            {error ? <Alert>{error}</Alert> : null}

            <Button type="submit" size="lg" className="w-full" loading={submitting}>
              {submitting ? 'Signing in…' : 'Sign in to workspace'}
            </Button>
          </form>

          <p className="mt-lg text-body-sm text-on-surface-variant">
            Platform operator?{' '}
            <Link className="text-secondary hover:underline" to="/super-admin/login">
              Super Admin login
            </Link>
          </p>
        </FadeIn>

        <footer className="absolute bottom-0 left-0 w-full py-lg px-margin-mobile md:px-margin-desktop">
          <div className="flex flex-wrap gap-lg">
            <span className="font-label-md text-label-md text-on-surface-variant">
              Terms
            </span>
            <span className="font-label-md text-label-md text-on-surface-variant">
              Privacy
            </span>
            <Link
              className="font-label-md text-label-md text-on-surface-variant hover:text-on-surface"
              to="/"
            >
              Home
            </Link>
          </div>
        </footer>
      </FadeSlide>

      <FadeSlide
        from="right"
        delay={0.1}
        className="hidden md:flex flex-1 relative overflow-hidden bg-primary text-on-primary flex-col justify-end p-2xl"
      >
        <div
          className="absolute inset-0 opacity-45"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%,#ffffff 0,transparent 42%),radial-gradient(circle at 80% 60%,#4a9cf5 0,transparent 38%)',
          }}
        />
        <FadeIn delay={0.25} className="relative z-10 max-w-md">
          <p className="font-label-md text-label-md uppercase tracking-wider text-on-primary/90 mb-sm">
            Organization workspace
          </p>
          <h2 className="font-headline-md text-headline-md text-on-primary mb-md">
            Hire with clarity inside your tenant.
          </h2>
          <p className="font-body-sm text-body-sm text-on-primary/90">
            Manage your organization profile, invite HR teammates, and prepare for
            job screening workflows.
          </p>
        </FadeIn>
      </FadeSlide>
    </div>
  )
}
