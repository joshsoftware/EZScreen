import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import { ApiError } from '../../lib/api/client'
import { listOrganizations } from '../../features/super-admin/api'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Select } from '../../components/ui/Input'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Stagger, StaggerItem } from '../../components/motion/Motion'

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
      <PageHeader
        title="Organizations"
        description="Platform home · all tenants on EZScreen."
        actions={
          <Button to="/super-admin/orgs/new">Create Organization</Button>
        }
      />

      <form className="flex flex-wrap items-end gap-sm mb-md" onSubmit={onSearch}>
        <div className="min-w-[240px] flex-1">
          <Input
            id="org-search"
            placeholder="Search organizations…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-10"
          />
        </div>
        <div className="w-[160px]">
          <Select
            id="org-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-10"
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </Select>
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {error ? <Alert className="mb-md">{error}</Alert> : null}

      <Panel bodyClassName="p-0">
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
            {loading ? (
              <tbody>
                <tr>
                  <td colSpan={5} className="p-0">
                    <TableSkeleton rows={5} cols={5} />
                  </td>
                </tr>
              </tbody>
            ) : orgs.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={5}>
                    <EmptyState
                      icon="domain"
                      title="No organizations yet"
                      description="Create the first tenant to start provisioning org admins."
                      actionLabel="Create organization"
                      actionTo="/super-admin/orgs/new"
                    />
                  </td>
                </tr>
              </tbody>
            ) : (
              <Stagger as="tbody" className="divide-y divide-outline-variant">
                {orgs.map((org) => (
                  <StaggerItem
                    as="tr"
                    key={org.id}
                    className="hover:bg-surface-container-low transition-colors"
                  >
                    <td className="py-md px-md">
                      <Link
                        className="text-body-sm font-medium text-secondary hover:underline"
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
                      <Badge tone={org.is_active ? 'success' : 'danger'}>
                        {org.is_active ? 'Active' : 'Suspended'}
                      </Badge>
                    </td>
                  </StaggerItem>
                ))}
              </Stagger>
            )}
          </table>
        </div>
      </Panel>
    </>
  )
}
