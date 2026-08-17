import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import { getOrganizationRequest } from '../../features/org-admin/api'
import { PageHeader, Panel, StatCard } from '../../components/ui/PageHeader'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Skeleton } from '../../components/ui/Skeleton'
import { ApiError } from '../../lib/api/client'

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

  return (
    <div>
      <PageHeader
        title="Workspace home"
        description="You are signed into your organization tenant."
        actions={
          <Button to="/org-admin/jobs/new">
            <span className="material-symbols-outlined text-[18px]">add</span>
            Create job
          </Button>
        }
      />

      {error ? (
        <div className="mb-lg">
          <Alert>{error}</Alert>
        </div>
      ) : null}

      <div className="grid gap-md md:grid-cols-3 mb-xl">
        <StatCard label="Signed in as" value={roleLabel || '—'} />
        <StatCard
          label="Organization"
          value={loading ? '…' : org?.name || '—'}
        />
        <StatCard
          label="Jobs"
          value={loading ? '…' : org?.job_count ?? '—'}
        />
      </div>

      <Panel title="Session">
        {loading ? (
          <div className="space-y-sm">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-5 w-1/2" />
          </div>
        ) : (
          <dl className="grid gap-md sm:grid-cols-2 text-body-sm">
            <div>
              <dt className="text-on-surface-variant mb-xs">Email</dt>
              <dd className="text-on-surface">{user?.email}</dd>
            </div>
            <div>
              <dt className="text-on-surface-variant mb-xs">Role</dt>
              <dd>
                <Badge>{roleLabel}</Badge>
              </dd>
            </div>
            <div>
              <dt className="text-on-surface-variant mb-xs">Organization ID</dt>
              <dd className="font-mono text-label-md break-all">
                {user?.organization_id || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-on-surface-variant mb-xs">Domain</dt>
              <dd className="text-on-surface">{org?.domain || '—'}</dd>
            </div>
            <div>
              <dt className="text-on-surface-variant mb-xs">Organization status</dt>
              <dd>
                {org ? (
                  <Badge tone={org.is_active ? 'success' : 'danger'}>
                    {org.is_active ? 'Active' : 'Suspended'}
                  </Badge>
                ) : (
                  '—'
                )}
              </dd>
            </div>
          </dl>
        )}
      </Panel>

      <p className="mt-lg text-body-sm text-on-surface-variant">
        Open{' '}
        <Link to="/org-admin/jobs" className="text-secondary hover:underline">
          Jobs
        </Link>{' '}
        to list, create, or update openings. Applicants and interviews come next.
      </p>
    </div>
  )
}
