import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '../../features/auth/AuthContext'
import { listOrgUsersRequest } from '../../features/org-admin/api'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function OrgAdminTeamPage() {
  const { user } = useAuth()
  const orgId = user?.organization_id
  const isOrgAdmin = user?.role === 'organization_admin'
  const [members, setMembers] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!orgId) {
      setLoading(false)
      return
    }
    setError(null)
    try {
      const users = await listOrgUsersRequest(orgId)
      setMembers(users.filter((u) => u.role === 'organization_admin' || u.role === 'hr'))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load team')
    } finally {
      setLoading(false)
    }
  }, [orgId])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return <PageSkeleton />
  }

  return (
    <div>
      <PageHeader
        title="Team"
        description="Organization admins and HR users in your workspace."
        actions={
          isOrgAdmin ? (
            <Button to="/org-admin/team/invite">
              <span className="material-symbols-outlined text-[18px]">person_add</span>
              Invite user
            </Button>
          ) : null
        }
      />

      {error ? <Alert className="mb-md">{error}</Alert> : null}

      <Panel title="Members">
        {members.length === 0 ? (
          <EmptyState
            icon="groups"
            title="No team members yet"
            description={
              isOrgAdmin
                ? 'Invite organization admins or HR teammates for this workspace.'
                : 'Your organization admin can invite users.'
            }
            actionLabel={isOrgAdmin ? 'Invite user' : undefined}
            actionTo={isOrgAdmin ? '/org-admin/team/invite' : undefined}
            className="py-lg"
          />
        ) : (
          <ul className="divide-y divide-outline-variant">
            {members.map((member) => (
              <li key={member.id} className="py-md flex justify-between gap-md text-body-sm">
                <div>
                  <p className="font-medium">
                    {[member.first_name, member.last_name].filter(Boolean).join(' ') ||
                      member.email}
                  </p>
                  <p className="text-label-md text-on-surface-variant">{member.email}</p>
                </div>
                <span className="text-label-md text-on-surface-variant">{member.role}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {!isOrgAdmin ? (
        <p className="mt-lg text-body-sm text-on-surface-variant">
          HR accounts are created by your organization admin.{' '}
          <Link to="/org-admin" className="text-secondary hover:underline">
            Back to home
          </Link>
        </p>
      ) : null}
    </div>
  )
}
