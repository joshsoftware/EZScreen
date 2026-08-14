import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '../../features/auth/AuthContext'
import {
  deactivateOrganization,
  getOrganization,
  listOrgUsers,
  updateOrganization,
} from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader, Panel, StatCard } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { Stagger, StaggerItem } from '../../components/motion/Motion'

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
        toast.success('Organization suspended')
      } else {
        await updateOrganization(token, org.id, { is_active: true })
        toast.success('Organization reactivated')
      }
      await load()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Status update failed'
      setError(message)
      toast.error(message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !org) {
    return <Alert>{error}</Alert>
  }
  if (!org) {
    return <PageSkeleton />
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
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/super-admin/orgs" className="hover:underline">
              Organizations
            </Link>
          </p>
        }
        title={
          <span className="flex items-center gap-md">
            <span className="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center font-headline-sm text-headline-sm">
              {initial}
            </span>
            <span>{org.name}</span>
          </span>
        }
        description={`${org.domain ? `${org.domain}.ezscreen.io` : 'No domain'} · Created ${created}`}
        actions={
          <>
            <Button variant="secondary" loading={busy} onClick={() => void toggleActive()}>
              {org.is_active ? 'Suspend' : 'Reactivate'}
            </Button>
            <Button to={`/super-admin/orgs/${org.id}/provision`}>
              Provision org admin
            </Button>
          </>
        }
      />

      {error ? <Alert className="mb-md">{error}</Alert> : null}

      <Stagger className="grid md:grid-cols-4 gap-md mb-xl">
        <StaggerItem>
          <StatCard label="Status" value={org.is_active ? 'Active' : 'Suspended'} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Users" value={String(org.user_count)} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Active jobs" value={String(org.job_count)} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Applications" value={String(org.application_count)} />
        </StaggerItem>
      </Stagger>

      <Stagger className="grid lg:grid-cols-2 gap-lg">
        <StaggerItem>
          <Panel title="Organization details">
            <dl className="space-y-md text-body-sm">
              <div className="flex justify-between gap-md">
                <dt className="text-on-surface-variant">Name</dt>
                <dd>{org.name}</dd>
              </div>
              <div className="flex justify-between gap-md">
                <dt className="text-on-surface-variant">Domain</dt>
                <dd>{org.domain ? `${org.domain}.ezscreen.io` : '—'}</dd>
              </div>
              <div className="flex justify-between gap-md">
                <dt className="text-on-surface-variant">Logo</dt>
                <dd>{org.logo_url ? 'Configured' : 'Not set'}</dd>
              </div>
              <div className="flex justify-between gap-md">
                <dt className="text-on-surface-variant">Isolation</dt>
                <dd>organization_id scoped</dd>
              </div>
            </dl>
          </Panel>
        </StaggerItem>
        <StaggerItem>
          <Panel title="Organization users" bodyClassName="pt-md">
            {admins.length === 0 ? (
              <EmptyState
                icon="person_add"
                title="No admins yet"
                description="Provision the first organization_admin or HR user to unlock the workspace."
                actionLabel="Invite organization admin"
                actionTo={`/super-admin/orgs/${org.id}/provision`}
                className="py-lg"
              />
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
          </Panel>
        </StaggerItem>
      </Stagger>
    </>
  )
}
