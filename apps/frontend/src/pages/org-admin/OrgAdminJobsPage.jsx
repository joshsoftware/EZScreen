import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { listJobsPageRequest } from '../../features/jobs/api'
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
import { Pagination } from '../../components/ui/Pagination'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Stagger, StaggerItem } from '../../components/motion/Motion'

const PAGE_SIZE = 20
const STATUS_FILTERS = new Set(['draft', 'published', 'closed'])

export function OrgAdminJobsPage() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  // Filter and page live in the URL (?status=draft&page=2) so a refresh,
  // Back, or returning from a job keeps them, like the candidate portal.
  const [searchParams, setSearchParams] = useSearchParams()
  const statusParam = searchParams.get('status') || ''
  const status = STATUS_FILTERS.has(statusParam) ? statusParam : ''
  const page = Math.max(1, Number(searchParams.get('page')) || 1)

  const updateParams = useCallback(
    (changes) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          Object.entries(changes).forEach(([key, value]) => {
            if (value && !(key === 'page' && Number(value) <= 1)) {
              next.set(key, String(value))
            } else {
              next.delete(key)
            }
          })
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Without paging only the first page of jobs was ever shown (Suggestion-005).
      const { items, total: count } = await listJobsPageRequest({
        status: status || undefined,
        page,
        limit: PAGE_SIZE,
      })
      const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE))
      if (page > lastPage) {
        updateParams({ page: lastPage }) // e.g. the filter now has fewer pages
        return
      }
      setJobs(items)
      setTotal(count)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [page, status, updateParams])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Create and manage openings for your organization."
        actions={
          <Button to="/org-admin/jobs/new" icon="add">
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
            onChange={(e) => {
              updateParams({ status: e.target.value, page: null })
            }}
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

      <Panel bodyClassName="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-low/60 border-b border-outline-variant/80">
                <th className="ez-table-head">Title</th>
                <th className="ez-table-head">Type</th>
                <th className="ez-table-head">Work mode</th>
                <th className="ez-table-head">Location</th>
                <th className="ez-table-head">Experience</th>
                <th className="ez-table-head">Applicants</th>
                <th className="ez-table-head">Status</th>
                <th className="ez-table-head">Posted / created</th>
              </tr>
            </thead>
            {loading ? (
              <tbody>
                <tr>
                  <td colSpan={8} className="p-0">
                    <TableSkeleton rows={5} cols={8} />
                  </td>
                </tr>
              </tbody>
            ) : jobs.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={8}>
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
              <Stagger as="tbody" className="divide-y divide-outline-variant/70">
                {jobs.map((job) => (
                  <StaggerItem
                    as="tr"
                    key={job.id}
                    className="ez-table-row cursor-pointer"
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
                      <span className="text-body-sm font-medium text-on-surface group-hover:text-secondary [overflow-wrap:anywhere]">
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
                      {/* Long unbroken text pushed the table off-screen (Bug-027). */}
                      <span className="block max-w-[14rem] truncate" title={job.location || undefined}>
                        {job.location || '—'}
                      </span>
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {formatExperience(job.experience_min, job.experience_max)}
                    </td>
                    <td className="py-md px-md">
                      <span className="inline-flex min-w-[1.75rem] justify-center rounded-full bg-primary-container/80 px-sm py-xs text-label-md text-on-primary-container">
                        {job.applicant_count ?? 0}
                      </span>
                    </td>
                    <td className="py-md px-md">
                      <Badge tone={jobStatusTone(job.status)}>
                        {formatJobStatus(job.status)}
                      </Badge>
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {/* Same "Posted" date the candidate portal shows (Bug-019);
                          drafts that were never published show when they were created. */}
                      {job.published_at ? (
                        <>
                          {formatDate(job.published_at)}
                          <span className="block text-label-md">Posted</span>
                        </>
                      ) : (
                        <>
                          {formatDate(job.created_at)}
                          <span className="block text-label-md">Created</span>
                        </>
                      )}
                    </td>
                  </StaggerItem>
                ))}
              </Stagger>
            )}
          </table>
        </div>
        {!loading ? (
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={(next) => {
              updateParams({ page: next })
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
          />
        ) : null}
      </Panel>
    </>
  )
}
