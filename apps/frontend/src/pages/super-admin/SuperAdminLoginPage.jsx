import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { LogoMark } from '../../components/brand/LogoMark'
import { useAuth } from '../../features/auth/AuthContext'
import { ApiError } from '../../lib/api/client'

export function SuperAdminLoginPage() {
  const { login, logout, user, isBootstrapping } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('admin@ezscreen.io')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  if (!isBootstrapping && user?.role === 'super_admin') {
    return <Navigate to="/super-admin/orgs" replace />
  }

  async function onSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const loggedIn = await login(email.trim(), password)
      if (loggedIn.role !== 'super_admin') {
        await logout()
        setError('Not a platform admin. Use Org / HR login instead.')
        return
      }
      navigate('/super-admin/orgs', { replace: true })
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
      <main className="flex-1 flex flex-col justify-center px-margin-mobile md:px-margin-desktop lg:px-[120px] relative z-10 w-full md:max-w-[50%] lg:max-w-[45%] min-h-screen bg-surface-container-lowest">
        <header className="absolute top-0 left-0 w-full py-lg px-margin-mobile md:px-margin-desktop">
          <LogoMark />
        </header>

        <div className="w-full max-w-[400px] mx-auto mt-2xl md:mt-0">
          <div className="mb-xl">
            <h1 className="font-display-lg text-display-lg-mobile md:text-display-lg text-on-surface mb-sm">
              Platform access
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Sign in as Super Admin to manage organizations and platform health.
            </p>
          </div>

          <form className="flex flex-col gap-md" onSubmit={onSubmit} noValidate>
            <div>
              <label
                className="block font-label-md text-label-md text-on-surface mb-xs"
                htmlFor="email"
              >
                Admin email
              </label>
              <input
                className="w-full h-12 px-md border border-outline-variant rounded-DEFAULT font-body-sm bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-secondary/40"
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label
                className="block font-label-md text-label-md text-on-surface mb-xs"
                htmlFor="password"
              >
                Password
              </label>
              <input
                className="w-full h-12 px-md border border-outline-variant rounded-DEFAULT font-body-sm bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-secondary/40"
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error ? (
              <p
                className="text-body-sm text-error bg-error-container/60 border border-error-container rounded-DEFAULT px-md py-sm"
                role="alert"
              >
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={submitting}
              className="w-full h-12 bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md hover:bg-on-primary-fixed-variant disabled:opacity-60 transition-colors"
            >
              {submitting ? 'Signing in…' : 'Sign in as Super Admin'}
            </button>
          </form>

          <p className="mt-lg text-body-sm text-on-surface-variant">
            Not platform ops?{' '}
            <Link className="text-secondary hover:underline" to="/login">
              Org / HR login
            </Link>
          </p>
        </div>

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
      </main>

      <aside className="hidden md:flex flex-1 relative overflow-hidden bg-primary text-on-primary flex-col justify-end p-2xl">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%,#ffffff 0,transparent 40%),radial-gradient(circle at 80% 60%,#a8d0fa 0,transparent 35%)',
          }}
        />
        <div className="relative z-10 max-w-md">
          <p className="font-label-md text-label-md uppercase tracking-wider text-on-primary/90 mb-sm">
            EZScreen Platform
          </p>
          <h2 className="font-headline-md text-headline-md text-on-primary mb-md">
            Functional precision for recruitment intelligence.
          </h2>
          <p className="font-body-sm text-body-sm text-on-primary/90">
            Create tenants, provision organization admins, and monitor AI processing health
            across the platform.
          </p>
        </div>
      </aside>
    </div>
  )
}
