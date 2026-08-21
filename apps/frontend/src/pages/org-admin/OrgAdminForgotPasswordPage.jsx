import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { LogoMark } from '../../components/brand/LogoMark'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { FadeIn, FadeSlide } from '../../components/motion/Motion'
import { forgotPasswordRequest } from '../../features/auth/api'
import { ApiError } from '../../lib/api/client'

export function OrgAdminForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const [resetUrl, setResetUrl] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const result = await forgotPasswordRequest(email.trim())
      setSubmitted(true)
      setResetUrl(result?.reset_url ?? null)
      toast.success('Request received')
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Unable to request a reset. Check that the API is running.',
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
              Forgot password
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Enter your work email. If an Organization Admin or HR account exists,
              a reset link will be generated.
            </p>
          </div>

          {submitted ? (
            <div className="space-y-md">
              <Alert>
                If an account exists for that email, a password reset link has been
                generated. Check your email or ask your administrator.
              </Alert>
              {resetUrl ? (
                <div className="rounded-xl border border-outline-variant bg-surface-container-low/50 p-md space-y-sm">
                  <p className="text-label-md text-on-surface-variant">
                    Dev reset link (email not configured yet):
                  </p>
                  <a
                    href={resetUrl}
                    className="break-all text-body-sm text-secondary hover:underline"
                  >
                    {resetUrl}
                  </a>
                </div>
              ) : null}
              <Link
                className="inline-block text-body-sm text-secondary hover:underline"
                to="/org-admin/login"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <form className="flex flex-col gap-md" onSubmit={onSubmit} noValidate>
              <Input
                id="forgot-email"
                label="Work email"
                name="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12"
                required
              />
              {error ? <Alert>{error}</Alert> : null}
              <Button type="submit" size="lg" className="w-full" loading={submitting}>
                {submitting ? 'Sending…' : 'Send reset link'}
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
            Account recovery
          </p>
          <h2 className="font-headline-md text-headline-md text-on-primary mb-md">
            Reset access to your hiring workspace.
          </h2>
          <p className="font-body-sm text-body-sm text-on-primary/90">
            Links expire after one hour and can only be used once.
          </p>
        </FadeIn>
      </FadeSlide>
    </div>
  )
}
