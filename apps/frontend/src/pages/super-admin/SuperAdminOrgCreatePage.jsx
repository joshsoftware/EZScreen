import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import { createOrganization } from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'

export function SuperAdminOrgCreatePage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [domain, setDomain] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    if (!token) return
    setSubmitting(true)
    setError(null)
    try {
      const org = await createOrganization(token, {
        name: name.trim(),
        domain: domain.trim() || null,
        logo_url: logoUrl.trim() || null,
      })
      navigate(`/super-admin/orgs/${org.id}`, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create organization')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-xl">
      <p className="text-label-md text-secondary mb-xs">
        <Link to="/super-admin/orgs">Organizations</Link> / Create
      </p>
      <h1 className="font-headline-md text-headline-md mb-xs">Create organization</h1>
      <p className="text-body-sm text-on-surface-variant mb-xl">
        Provision a new tenant with domain and branding.
      </p>
      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
        <form className="space-y-md" onSubmit={onSubmit}>
          <div>
            <label className="block font-label-md text-label-md mb-xs" htmlFor="name">
              Company name
            </label>
            <input
              id="name"
              required
              className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block font-label-md text-label-md mb-xs" htmlFor="domain">
              Subdomain
            </label>
            <div className="flex items-center gap-sm">
              <input
                id="domain"
                className="flex-1 h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="acme"
              />
              <span className="text-body-sm text-on-surface-variant">.ezscreen.io</span>
            </div>
          </div>
          <div>
            <label className="block font-label-md text-label-md mb-xs" htmlFor="logo">
              Logo URL (optional)
            </label>
            <input
              id="logo"
              className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://…"
            />
          </div>
          {error ? (
            <p className="text-body-sm text-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="flex gap-sm pt-md">
            <Link
              to="/super-admin/orgs"
              className="inline-flex items-center justify-center h-10 px-md border border-outline-variant text-on-surface rounded-DEFAULT font-label-md text-label-md hover:bg-surface-container-low transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting}
              className="h-10 px-md bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md disabled:opacity-60"
            >
              {submitting ? 'Creating…' : 'Create organization'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
