import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import { getOrganizationRequest } from '../../features/org-admin/api'
import { PageHeader, Panel, StatCard } from '../../components/ui/PageHeader'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Skeleton } from '../../components/ui/Skeleton'
import { ApiError } from '../../lib/api/client'

const QUICK_LINKS = [
  {
    to: '/org-admin/jobs/new',
    icon: 'add_circle',
    title: 'Create a job',
    description: 'Paste a JD and let AI extract skills and requirements.',
  },
  {
    to: '/org-admin/jobs',
    icon: 'group',
    title: 'Review applicants',
    description: 'Open a role to screen resumes and compare AI fit scores.',
  },
  {
    to: '/org-admin/settings',
    icon: 'tune',
    title: 'Fit labels',
    description: 'Define custom Strong / Moderate / Weak score ranges.',
  },
]

export function OrgAdminHomePage() {
  const { user } = useAuth()
  const [org, setOrg] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(Boolean(user?.organization_id))

  useEffect(() => {
    let cancelled = false
    const orgId = user?.organization_id
    if (!orgId) {
      setLoading(false)
      return undefined
    }

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await getOrganizationRequest(orgId)
        if (!cancelled) setOrg(data)
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : 'Unable to load organization details.',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [user?.organization_id])

  const roleLabel =
    user?.role === 'hr' ? 'HR' : user?.role === 'organization_admin' ? 'Org Admin' : user?.role
  const firstName = user?.first_name?.trim() || 'there'
  const orgName = loading ? '…' : org?.name || 'your organization'

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${firstName}`}
        description={`You’re in ${orgName}. Create openings, screen applicants, and tune fit ratings.`}
        actions={
          <Button to="/org-admin/jobs/new" icon="add">
            Create job
          </Button>
        }
      />

      {error ? (
        <div className="mb-lg">
          <Alert>{error}</Alert>
        </div>
      ) : null}

      <div className="grid gap-md sm:grid-cols-2 lg:grid-cols-4 mb-xl">
        <StatCard
          label="Organization"
          value={loading ? '…' : org?.name || '—'}
          hint={org?.domain ? `${org.domain}.ezscreen.io` : roleLabel}
        />
        <StatCard
          label="Open jobs"
          value={loading ? '…' : String(org?.job_count ?? 0)}
          hint="Across your workspace"
        />
        <StatCard
          label="Applications"
          value={loading ? '…' : String(org?.application_count ?? 0)}
          hint="All roles"
        />
        <StatCard
          label="Workspace"
          value={loading ? '…' : org?.is_active ? 'Active' : 'Suspended'}
          hint={roleLabel}
        />
      </div>

      <Panel title="Get started">
        {loading ? (
          <div className="grid gap-md md:grid-cols-3">
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
          </div>
        ) : (
          <div className="grid gap-md md:grid-cols-3">
            {QUICK_LINKS.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="group rounded-xl border border-outline-variant/80 bg-surface-container-low/50 p-md shadow-soft transition-all hover:-translate-y-0.5 hover:border-secondary/50 hover:shadow-lift"
              >
                <span className="mb-sm inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary-container text-on-primary-container transition-colors group-hover:bg-primary group-hover:text-on-primary">
                  <span className="material-symbols-outlined text-[22px]">{item.icon}</span>
                </span>
                <p className="font-label-md text-label-md text-on-surface mb-xs">
                  {item.title}
                </p>
                <p className="text-body-sm text-on-surface-variant">{item.description}</p>
              </Link>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
