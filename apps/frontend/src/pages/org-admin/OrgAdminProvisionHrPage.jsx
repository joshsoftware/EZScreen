import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '../../features/auth/AuthContext'
import {
  getOrganizationRequest,
  provisionOrgUserRequest,
} from '../../features/org-admin/api'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function OrgAdminProvisionHrPage() {
  const { user } = useAuth()
  const orgId = user?.organization_id
  const navigate = useNavigate()
  const [org, setOrg] = useState(null)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('hr')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [tempPassword, setTempPassword] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!orgId) return
    void getOrganizationRequest(orgId)
      .then(setOrg)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load organization'),
      )
  }, [orgId])

  async function onSubmit(event) {
    event.preventDefault()
    if (!orgId) return
    setSubmitting(true)
    setError(null)
    setTempPassword(null)
    try {
      const created = await provisionOrgUserRequest(orgId, {
        email: email.trim(),
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
        role,
        password: password.trim() || undefined,
      })
      toast.success('User invited')
      if (created.temporary_password) {
        setTempPassword(created.temporary_password)
      } else {
        navigate('/org-admin/team', { replace: true })
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to invite user')
    } finally {
      setSubmitting(false)
    }
  }

  if (!org && !error) {
    return <PageSkeleton />
  }

  return (
    <div className="max-w-xl">
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/org-admin/team" className="hover:underline">
              Team
            </Link>{' '}
            / Invite user
          </p>
        }
        title="Invite user"
        description={`Provision organization_admin or HR for ${org?.name ?? 'your organization'}.`}
      />

      <Panel>
        {tempPassword ? (
          <div className="space-y-md">
            <Alert tone="success">
              User created. Share this one-time temporary password (not emailed yet):
            </Alert>
            <code className="block p-md bg-surface rounded-lg border border-outline-variant text-body-sm font-mono-sm select-all">
              {tempPassword}
            </code>
            <Button to="/org-admin/team">Back to team</Button>
          </div>
        ) : (
          <form className="space-y-md" onSubmit={onSubmit}>
            <div className="bg-surface rounded-lg p-md border border-outline-variant">
              <p className="text-label-md text-on-surface-variant">Organization</p>
              <p className="text-body-sm font-medium">{org?.name ?? '—'}</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
              <Input
                id="first"
                label="First name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
              <Input
                id="last"
                label="Last name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
            <Input
              id="email"
              label="Work email"
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Select
              id="role"
              label="Role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="hr">hr</option>
              <option value="organization_admin">organization_admin</option>
            </Select>
            <Input
              id="password"
              label="Password (optional — auto-generated if empty)"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
            />
            {error ? <Alert>{error}</Alert> : null}
            <div className="flex gap-sm pt-md">
              <Button to="/org-admin/team" variant="secondary">
                Cancel
              </Button>
              <Button type="submit" loading={submitting}>
                {submitting ? 'Inviting…' : 'Create user'}
              </Button>
            </div>
          </form>
        )}
      </Panel>
    </div>
  )
}
