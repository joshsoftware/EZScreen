import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import { ApiError } from '../../lib/api/client'
import { listOrganizations } from '../../features/super-admin/api'

export function SuperAdminOrgsPage() {
  const { token } = useAuth()
  const [orgs, setOrgs] = useState([])
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const data = await listOrganizations(token, {
        q: q.trim() || undefined,
        status,
      })
      setOrgs(data)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load organizations')
    } finally {
      setLoading(false)
    }
  }, [token, q, status])

  useEffect(() => {
    void load()
  }, [load])

  function onSearch(event) {
    event.preventDefault()
    void load()
  }

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-md mb-xl">
        <div>
          <h1 className="font-headline-md text-headline-md">Organizations</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">
            Platform home · all tenants on EZScreen.
          </p>
        </div>
        <Link
          to="/super-admin/orgs/new"
          className="inline-flex items-center justify-center h-10 px-md bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md hover:bg-on-primary-fixed-variant transition-colors"
        >
          Create Organization
        </Link>
      </div>

      <form className="flex flex-wrap gap-sm mb-md" onSubmit={onSearch}>
        <input
          className="h-10 px-md border border-outline-variant rounded-DEFAULT text-body-sm min-w-[240px] bg-surface-container-lowest"
          placeholder="Search organizations…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          className="h-10 px-md border border-outline-variant rounded-DEFAULT text-body-sm bg-surface-container-lowest"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
        <button
          type="submit"
          className="h-10 px-md border border-outline-variant rounded-DEFAULT font-label-md text-label-md hover:bg-surface-container-low"
        >
          Search
        </button>
      </form>

      {error ? (
        <p className="mb-md text-body-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface border-b border-outline-variant">
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Organization
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Domain
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Users
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Jobs
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-xl px-md text-center text-body-sm text-on-surface-variant">
                    Loading…
                  </td>
                </tr>
              ) : orgs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-xl px-md text-center text-body-sm text-on-surface-variant">
                    No organizations yet.{' '}
                    <Link className="text-secondary" to="/super-admin/orgs/new">
                      Create one
                    </Link>
                  </td>
                </tr>
              ) : (
                orgs.map((org) => (
                  <tr key={org.id} className="hover:bg-surface-container-low">
                    <td className="py-md px-md">
                      <Link
                        className="text-body-sm font-medium text-secondary"
                        to={`/super-admin/orgs/${org.id}`}
                      >
                        {org.name}
                      </Link>
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {org.domain ? `${org.domain}.ezscreen.io` : '—'}
                    </td>
                    <td className="py-md px-md text-body-sm">{org.user_count}</td>
                    <td className="py-md px-md text-body-sm">{org.job_count}</td>
                    <td className="py-md px-md">
                      {org.is_active ? (
                        <span className="text-label-md px-sm py-xs rounded-full bg-[#D1FAE5] text-[#065F46]">
                          Active
                        </span>
                      ) : (
                        <span className="text-label-md px-sm py-xs rounded-full bg-error-container text-on-error-container">
                          Suspended
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
