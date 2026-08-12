import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import { getOrganization, provisionOrgUser } from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'

export function SuperAdminProvisionPage() {
  const { orgId = '' } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const [org, setOrg] = useState(null)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('organization_admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [tempPassword, setTempPassword] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token || !orgId) return
    void getOrganization(token, orgId)
      .then(setOrg)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load organization'),
      )
  }, [token, orgId])

  async function onSubmit(event) {
    event.preventDefault()
    if (!token || !orgId) return
    setSubmitting(true)
    setError(null)
    setTempPassword(null)
    try {
      const user = await provisionOrgUser(token, orgId, {
        email: email.trim(),
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
        role,
        password: password.trim() || undefined,
      })
      if (user.temporary_password) {
        setTempPassword(user.temporary_password)
      } else {
        navigate(`/super-admin/orgs/${orgId}`, { replace: true })
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to provision user')
    } finally {
      setSubmitting(false)
    }
  }

  if (!org && !error) {
    return <p className="text-body-sm text-on-surface-variant">Loading…</p>
  }

  return (
    <div className="max-w-xl">
      <p className="text-label-md text-secondary mb-xs">
        <Link to={`/super-admin/orgs/${orgId}`}>{org?.name ?? 'Organization'}</Link> /
        Provision admin
      </p>
      <h1 className="font-headline-md text-headline-md mb-xs">
        Provision organization admin
      </h1>
      <p className="text-body-sm text-on-surface-variant mb-xl">
        Creates an organization user for {org?.name ?? 'this tenant'}.
      </p>

      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
        {tempPassword ? (
          <div className="space-y-md">
            <p className="text-body-sm text-on-surface">
              User created. Share this one-time temporary password (not emailed yet):
            </p>
            <code className="block p-md bg-surface rounded-lg border border-outline-variant text-body-sm font-mono-sm">
              {tempPassword}
            </code>
            <Link
              to={`/super-admin/orgs/${orgId}`}
              className="inline-flex h-10 px-md items-center bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md"
            >
              Back to organization
            </Link>
          </div>
        ) : (
          <form className="space-y-md" onSubmit={onSubmit}>
            <div className="bg-surface rounded-lg p-md border border-outline-variant mb-md">
              <p className="text-label-md text-on-surface-variant">Organization</p>
              <p className="text-body-sm font-medium">
                {org?.name} · {org?.domain ? `${org.domain}.ezscreen.io` : 'no domain'}
              </p>
            </div>
            <div>
              <label className="block font-label-md text-label-md mb-xs" htmlFor="first">
                First name
              </label>
              <input
                id="first"
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div>
              <label className="block font-label-md text-label-md mb-xs" htmlFor="last">
                Last name
              </label>
              <input
                id="last"
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
            <div>
              <label className="block font-label-md text-label-md mb-xs" htmlFor="email">
                Work email
              </label>
              <input
                id="email"
                required
                type="email"
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="block font-label-md text-label-md mb-xs" htmlFor="role">
                Role
              </label>
              <select
                id="role"
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm bg-surface-container-lowest"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="organization_admin">organization_admin</option>
                <option value="hr">hr</option>
              </select>
            </div>
            <div>
              <label className="block font-label-md text-label-md mb-xs" htmlFor="password">
                Password (optional — auto-generated if empty)
              </label>
              <input
                id="password"
                type="password"
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
              />
            </div>
            {error ? (
              <p className="text-body-sm text-error" role="alert">
                {error}
              </p>
            ) : null}
            <div className="flex gap-sm pt-md">
              <Link
                to={`/super-admin/orgs/${orgId}`}
                className="inline-flex items-center justify-center h-10 px-md border border-outline-variant text-on-surface rounded-DEFAULT font-label-md text-label-md hover:bg-surface-container-low transition-colors"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={submitting}
                className="h-10 px-md bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md disabled:opacity-60"
              >
                {submitting ? 'Provisioning…' : 'Create user'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
