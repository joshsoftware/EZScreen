import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { usePublicJobsQuery } from '../../features/candidate/usePublicJobs'
import { JobCard } from '../../features/candidate/components/JobCard'
import { JobFilters } from '../../features/candidate/components/JobFilters'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function CandidateJobsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const orgSubdomain = searchParams.get('org_subdomain') || ''
  const search = searchParams.get('search') || ''
  const jobType = searchParams.get('job_type') || ''
  const workType = searchParams.get('work_type') || ''

  const [searchInput, setSearchInput] = useState(search)

  const { data: jobs = [], isLoading, isError, error } = usePublicJobsQuery({
    orgSubdomain,
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

  const firstOrg = jobs[0]
  const orgName = firstOrg?.organization_name || (orgSubdomain ? orgSubdomain.toUpperCase() : null)
  const orgLogo = firstOrg?.organization_logo_url
  const hasActiveFilters = Boolean(search || jobType || workType || orgSubdomain)

  return (
    <div className="mx-auto max-w-7xl px-margin-mobile py-lg md:px-lg md:py-xl">
      {/* Header & Filter Card */}
      <div className="mb-lg rounded-2xl bg-surface-container-lowest border border-outline-variant/70 p-lg shadow-lift">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-md">
          <div>
            {orgName ? (
              <div className="flex items-center gap-sm mb-xs">
                {orgLogo ? (
                  <img
                    src={orgLogo}
                    alt={orgName}
                    className="w-8 h-8 rounded-lg object-contain bg-surface border border-outline-variant/60 p-xs"
                  />
                ) : null}
                <span className="text-body-md font-semibold text-on-surface">{orgName}</span>
              </div>
            ) : null}
            <h1 className="text-headline-md font-bold text-on-surface tracking-tight">
              Open Positions
            </h1>
          </div>

          <div className="inline-flex items-center gap-xs rounded-xl bg-surface-container-low border border-outline-variant/60 px-md py-xs text-body-sm font-medium text-on-surface">
            <span>{isLoading ? '...' : `${jobs.length} Role${jobs.length === 1 ? '' : 's'}`}</span>
          </div>
        </div>

        {/* Filter Controls */}
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
      </div>

      {/* Jobs Grid */}
      {isLoading ? (
        <PageSkeleton />
      ) : isError ? (
        <div className="rounded-2xl border border-error/30 bg-error-container/30 p-xl text-center">
          <h3 className="text-headline-sm font-semibold text-on-surface">Unable to load job listings</h3>
          <p className="mt-xs text-body-sm text-on-surface-variant">
            {error?.message || 'Failed to fetch public jobs. Please try again later.'}
          </p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-2xl text-center shadow-soft">
          <h3 className="text-headline-sm font-semibold text-on-surface">No open positions found</h3>
          <p className="mt-xs text-body-md text-on-surface-variant">
            No active job postings match your filter criteria.
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="mt-md inline-flex items-center gap-xs rounded-xl bg-surface-container-high px-md py-sm text-body-sm font-medium text-on-surface hover:bg-outline-variant transition-colors"
            >
              <span>Clear Filters</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-md md:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </div>
  )
}
