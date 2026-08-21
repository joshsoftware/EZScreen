import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { LogoMark } from '../../components/brand/LogoMark'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { PasswordInput } from '../../components/ui/Input'
import { FadeIn, FadeSlide } from '../../components/motion/Motion'
import { resetPasswordRequest } from '../../features/auth/api'
import { ApiError } from '../../lib/api/client'

export function OrgAdminResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = useMemo(() => searchParams.get('token')?.trim() || '', [searchParams])
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    setError(null)

    if (!token) {
      setError('This reset link is missing a token. Request a new one.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      await resetPasswordRequest(token, password)
      toast.success('Password updated')
      navigate('/org-admin/login', { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Unable to reset password. Try requesting a new link.',
      )
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

        <FadeIn delay={0.08} className="w-full max-w-[400px] mx-auto mt-2xl md:mt-0">
          <div className="mb-xl">
            <h1 className="font-display-lg text-display-lg-mobile md:text-display-lg text-on-surface mb-sm">
              Set new password
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Choose a new password for your Organization Admin or HR account.
            </p>
          </div>

          {!token ? (
            <div className="space-y-md">
              <Alert>This reset link is invalid or incomplete.</Alert>
              <Link
                className="inline-block text-body-sm text-secondary hover:underline"
                to="/org-admin/forgot-password"
              >
                Request a new reset link
              </Link>
            </div>
          ) : (
            <form className="flex flex-col gap-md" onSubmit={onSubmit} noValidate>
              <PasswordInput
                id="reset-password"
                label="New password"
                name="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12"
                required
                minLength={8}
              />
              <PasswordInput
                id="reset-confirm"
                label="Confirm password"
                name="confirm"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="h-12"
                required
                minLength={8}
              />
              {error ? <Alert>{error}</Alert> : null}
              <Button type="submit" size="lg" className="w-full" loading={submitting}>
                {submitting ? 'Updating…' : 'Update password'}
              </Button>
              <p className="text-body-sm text-on-surface-variant">
                <Link className="text-secondary hover:underline" to="/org-admin/login">
                  Back to sign in
                </Link>
              </p>
            </form>
          )}
        </FadeIn>
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
            Secure access
          </p>
          <h2 className="font-headline-md text-headline-md text-on-primary mb-md">
            One-time link, new credentials.
          </h2>
          <p className="font-body-sm text-body-sm text-on-primary/90">
            After updating, sign in with your email and new password.
          </p>
        </FadeIn>
      </FadeSlide>
    </div>
  )
}
