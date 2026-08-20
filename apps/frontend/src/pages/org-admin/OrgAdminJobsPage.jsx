import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listJobsRequest } from '../../features/jobs/api'
import {
  formatDate,
  formatExperience,
  formatJobStatus,
  formatJobType,
  formatWorkType,
  jobStatusTone,
} from '../../features/jobs/jobFields'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { Select } from '../../components/ui/Input'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Stagger, StaggerItem } from '../../components/motion/Motion'

export function OrgAdminJobsPage() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listJobsRequest({
        status: status || undefined,
      })
      setJobs(data)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Create and manage openings for your organization."
        actions={
          <Button to="/org-admin/jobs/new">
            <span className="material-symbols-outlined text-[18px]">add</span>
            Create job
          </Button>
        }
      />

      <div className="flex flex-wrap items-end gap-sm mb-md">
        <div className="w-[180px]">
          <Select
            id="job-status-filter"
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-10"
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
            <option value="closed">Closed</option>
          </Select>
        </div>
      </div>

      {error ? <Alert className="mb-md">{error}</Alert> : null}

      <Panel bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface border-b border-outline-variant">
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Title
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Type
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Work mode
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Location
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Experience
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Applicants
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Status
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Created
                </th>

              </tr>
            </thead>
            {loading ? (
              <tbody>
                <tr>
                  <td colSpan={9} className="p-0">
                    <TableSkeleton rows={5} cols={8} />
                  </td>
                </tr>
              </tbody>
            ) : jobs.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={9}>
                    <EmptyState
                      icon="work"
                      title="No jobs yet"
                      description="Fill in the job form to create a draft or publish an opening."
                      actionLabel="Create job"
                      actionTo="/org-admin/jobs/new"
                    />
                  </td>
                </tr>
              </tbody>
            ) : (
              <Stagger as="tbody" className="divide-y divide-outline-variant">
                {jobs.map((job) => (
                  <StaggerItem
                    as="tr"
                    key={job.id}
                    className="hover:bg-surface-container-low transition-colors cursor-pointer"
                    role="link"
                    tabIndex={0}
                    onClick={() => navigate(`/org-admin/jobs/${job.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        navigate(`/org-admin/jobs/${job.id}`)
                      }
                    }}
                  >
                    <td className="py-md px-md">
                      <span className="text-body-sm font-medium text-secondary">
                        {job.title || 'Untitled job'}
                      </span>
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {formatJobType(job.job_type)}
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {formatWorkType(job.work_type)}
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {job.location || '—'}
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {formatExperience(job.experience_min, job.experience_max)}
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {job.applicant_count ?? 0}
                    </td>
                    <td className="py-md px-md">
                      <Badge tone={jobStatusTone(job.status)}>
                        {formatJobStatus(job.status)}
                      </Badge>
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {formatDate(job.created_at)}
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
