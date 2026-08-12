import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import {
  deactivateOrganization,
  getOrganization,
  listOrgUsers,
  updateOrganization,
} from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'

export function SuperAdminOrgDetailPage() {
  const { orgId = '' } = useParams()
  const { token } = useAuth()
  const [org, setOrg] = useState(null)
  const [admins, setAdmins] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!token || !orgId) return
    setError(null)
    try {
      const [organization, users] = await Promise.all([
        getOrganization(token, orgId),
        listOrgUsers(token, orgId),
      ])
      setOrg(organization)
      setAdmins(
        users.filter(
          (u) => u.role === 'organization_admin' || u.role === 'hr',
        ),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load organization')
    }
  }, [token, orgId])

  useEffect(() => {
    void load()
  }, [load])

  async function toggleActive() {
    if (!token || !org) return
    setBusy(true)
    try {
      if (org.is_active) {
        await deactivateOrganization(token, org.id)
      } else {
        await updateOrganization(token, org.id, { is_active: true })
      }
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Status update failed')
    } finally {
      setBusy(false)
    }
  }

  if (error && !org) {
    return <p className="text-body-sm text-error">{error}</p>
  }
  if (!org) {
    return <p className="text-body-sm text-on-surface-variant">Loading…</p>
  }

  const initial = org.name.charAt(0).toUpperCase()
  const created = org.created_at
    ? new Date(org.created_at).toLocaleDateString(undefined, {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : '—'

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-md mb-xl">
        <div className="flex items-center gap-md">
          <div className="w-14 h-14 rounded-xl bg-surface-container flex items-center justify-center font-headline-sm">
            {initial}
          </div>
          <div>
            <p className="text-label-md text-secondary mb-xs">
              <Link to="/super-admin/orgs">Organizations</Link>
            </p>
            <h1 className="font-headline-md text-headline-md">{org.name}</h1>
            <p className="text-body-sm text-on-surface-variant">
              {org.domain ? `${org.domain}.ezscreen.io` : 'No domain'} · Created {created}
            </p>
          </div>
        </div>
        <div className="flex gap-sm">
          <button
            type="button"
            disabled={busy}
            onClick={() => void toggleActive()}
            className="inline-flex items-center justify-center h-10 px-md border border-outline-variant text-on-surface rounded-DEFAULT font-label-md text-label-md hover:bg-surface-container-low transition-colors disabled:opacity-60"
          >
            {org.is_active ? 'Suspend' : 'Reactivate'}
          </button>
          <Link
            to={`/super-admin/orgs/${org.id}/provision`}
            className="inline-flex items-center justify-center h-10 px-md bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md hover:bg-on-primary-fixed-variant transition-colors"
          >
            Provision org admin
          </Link>
        </div>
      </div>

      {error ? (
        <p className="mb-md text-body-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="grid md:grid-cols-4 gap-md mb-xl">
        <Stat label="Status" value={org.is_active ? 'Active' : 'Suspended'} />
        <Stat label="Users" value={String(org.user_count)} />
        <Stat label="Active jobs" value={String(org.job_count)} />
        <Stat label="Applications" value={String(org.application_count)} />
      </div>

      <div className="grid lg:grid-cols-2 gap-lg">
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
          <h2 className="font-headline-sm text-headline-sm mb-md">Organization details</h2>
          <dl className="space-y-md text-body-sm">
            <div className="flex justify-between">
              <dt className="text-on-surface-variant">Name</dt>
              <dd>{org.name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-on-surface-variant">Domain</dt>
              <dd>{org.domain ? `${org.domain}.ezscreen.io` : '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-on-surface-variant">Logo</dt>
              <dd>{org.logo_url ? 'Configured' : 'Not set'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-on-surface-variant">Isolation</dt>
              <dd>organization_id scoped</dd>
            </div>
          </dl>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
          <h2 className="font-headline-sm text-headline-sm mb-md">Organization users</h2>
          {admins.length === 0 ? (
            <>
              <p className="text-body-sm text-on-surface-variant mb-md">
                No organization_admin or HR yet. Provision the first admin to unlock the workspace.
              </p>
              <Link
                to={`/super-admin/orgs/${org.id}/provision`}
                className="w-full flex items-center justify-center h-10 px-md bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md hover:bg-on-primary-fixed-variant transition-colors"
              >
                Invite organization admin
              </Link>
            </>
          ) : (
            <ul className="divide-y divide-outline-variant">
              {admins.map((user) => (
                <li key={user.id} className="py-md flex justify-between gap-md text-body-sm">
                  <div>
                    <p className="font-medium">
                      {[user.first_name, user.last_name].filter(Boolean).join(' ') ||
                        user.email}
                    </p>
                    <p className="text-label-md text-on-surface-variant">{user.email}</p>
                  </div>
                  <span className="text-label-md text-on-surface-variant">{user.role}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  )
}

function Stat({ label, value }) {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
      <p className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider mb-xs">
        {label}
      </p>
      <p className="font-headline-md text-headline-md text-on-surface">{value}</p>
    </div>
  )
}
