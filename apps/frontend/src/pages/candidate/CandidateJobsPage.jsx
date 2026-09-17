import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useState } from 'react'
import { usePublicJobsQuery } from '../../features/candidate/usePublicJobs'
import { ORG_URL_SLUG } from '../../features/candidate/constants'
import { JobFilters } from '../../features/candidate/components/JobFilters'
import {
  formatDate,
  formatExperience,
  formatJobType,
  formatWorkType,
} from '../../features/jobs/jobFields'
import { Alert } from '../../components/ui/Alert'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Stagger, StaggerItem } from '../../components/motion/Motion'

export function CandidateJobsPage() {
  const navigate = useNavigate()
  const { org = ORG_URL_SLUG } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()

  const search = searchParams.get('search') || ''
  const jobType = searchParams.get('job_type') || ''
  const workType = searchParams.get('work_type') || ''

  const [searchInput, setSearchInput] = useState(search)

  const { data: jobs = [], isLoading, isError, error } = usePublicJobsQuery({
    orgName: org,
    search,
    jobType,
    workType,
  })

  const updateParam = (key, val) => {
    const next = new URLSearchParams(searchParams)
    if (val) {
      next.set(key, val)
    } else {
      next.delete(key)
    }
    setSearchParams(next)
  }

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    updateParam('search', searchInput)
  }

  const handleClearFilters = () => {
    setSearchInput('')
    setSearchParams({})
  }

  const orgName = jobs[0]?.organization_name
  const hasActiveFilters = Boolean(search || jobType || workType)

  return (
    <>
      <PageHeader
        title="Open positions"
        description={
          orgName
            ? `Published roles at ${orgName}. Apply with your resume.`
            : 'Browse published roles and apply with your resume.'
        }
      />

      <JobFilters
        searchInput={searchInput}
        onSearchInputChange={setSearchInput}
        onSearchSubmit={handleSearchSubmit}
        jobType={jobType}
        onJobTypeChange={(val) => updateParam('job_type', val)}
        workType={workType}
        onWorkTypeChange={(val) => updateParam('work_type', val)}
        onClearFilters={handleClearFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {isError ? <Alert className="mb-md">{error?.message || 'Failed to load jobs'}</Alert> : null}

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
                <th className="ez-table-head">Posted</th>
              </tr>
            </thead>
            {isLoading ? (
              <tbody>
                <tr>
                  <td colSpan={6} className="p-0">
                    <TableSkeleton rows={5} cols={6} />
                  </td>
                </tr>
              </tbody>
            ) : jobs.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={6}>
                    <EmptyState
                      icon="work"
                      title="No open positions"
                      description={
                        hasActiveFilters
                          ? 'No active job postings match your filters.'
                          : 'There are no published roles right now. Check back soon.'
                      }
                      actionLabel={hasActiveFilters ? 'Clear filters' : undefined}
                      onAction={hasActiveFilters ? handleClearFilters : undefined}
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
                    onClick={() => navigate(`/${org}/jobs/${job.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        navigate(`/${org}/jobs/${job.id}`)
                      }
                    }}
                  >
                    <td className="py-md px-md">
                      <span className="text-body-sm font-medium text-on-surface group-hover:text-secondary">
                        {job.title || 'Untitled position'}
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
                      {formatDate(job.published_at || job.created_at)}
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
