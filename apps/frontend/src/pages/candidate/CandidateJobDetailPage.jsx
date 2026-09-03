import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { usePublicJobDetailQuery } from '../../features/candidate/usePublicJobs'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function CandidateJobDetailPage() {
  const { jobId } = useParams()
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false)

  const { data: job, isLoading, isError, error } = usePublicJobDetailQuery(jobId)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-margin-mobile py-lg md:px-lg md:py-2xl">
        <PageSkeleton />
      </div>
    )
  }

  if (isError || !job) {
    return (
      <div className="mx-auto max-w-4xl px-margin-mobile py-2xl text-center">
        <div className="rounded-2xl border border-error/30 bg-error-container/30 p-2xl">
          <h2 className="text-headline-md font-semibold text-on-surface">Position Not Found</h2>
          <p className="mt-xs text-body-md text-on-surface-variant max-w-md mx-auto">
            {error?.message || 'This job opening is no longer accepting applications.'}
          </p>
          <Link
            to="/jobs"
            className="mt-lg inline-flex items-center gap-xs rounded-xl bg-primary px-lg py-sm text-body-sm font-medium text-on-primary shadow-soft hover:bg-primary/90 transition-colors"
          >
            <span>Back to Open Roles</span>
          </Link>
        </div>
      </div>
    )
  }

  const formatBadge = (str) =>
    str ? str.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()) : ''

  const skillsData = job.skills || {}
  const mustHave = skillsData.must_have || []
  const goodToHave = skillsData.good_to_have || []

  return (
    <div className="mx-auto max-w-6xl px-margin-mobile py-lg md:px-lg md:py-xl">
      {/* Back Navigation */}
      <Link
        to="/jobs"
        className="inline-flex items-center gap-xs text-body-sm font-medium text-on-surface-variant hover:text-primary transition-colors mb-md"
      >
        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
        <span>Back to open positions</span>
      </Link>

      {/* Header Banner Card */}
      <div className="rounded-2xl bg-surface-container-lowest border border-outline-variant/70 p-lg md:p-xl shadow-lift mb-xl">
        <div className="flex items-center gap-sm mb-sm">
          {job.organization_logo_url ? (
            <img
              src={job.organization_logo_url}
              alt={job.organization_name || 'Company logo'}
              className="w-10 h-10 rounded-xl object-contain bg-surface border border-outline-variant/60 p-xs"
            />
          ) : (
            <div className="w-10 h-10 rounded-xl bg-primary-container text-on-primary-container font-headline-sm flex items-center justify-center">
              {(job.organization_name || 'E').charAt(0).toUpperCase()}
            </div>
          )}
          <span className="text-body-md font-semibold text-on-surface">
            {job.organization_name || 'EZScreen Partner'}
          </span>
        </div>

        <h1 className="text-headline-md font-bold text-on-surface tracking-tight">
          {job.title || 'Untitled Position'}
        </h1>

        {/* Quick Metadata badges */}
        <div className="flex flex-wrap items-center gap-sm mt-md text-body-sm text-on-surface-variant">
          {job.location ? (
            <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
              <span className="material-symbols-outlined text-primary text-[18px]">location_on</span>
              {job.location}
            </span>
          ) : null}

          {job.work_type ? (
            <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
              <span className="material-symbols-outlined text-primary text-[18px]">laptop_mac</span>
              {formatBadge(job.work_type)}
            </span>
          ) : null}

          {job.job_type ? (
            <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
              <span className="material-symbols-outlined text-primary text-[18px]">schedule</span>
              {formatBadge(job.job_type)}
            </span>
          ) : null}

          {(job.experience_min !== null || job.experience_max !== null) ? (
            <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
              <span className="material-symbols-outlined text-primary text-[18px]">badge</span>
              {job.experience_min ?? 0} - {job.experience_max ?? 'Any'} yrs exp
            </span>
          ) : null}
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid gap-xl lg:grid-cols-3">
        {/* Left Column: Job Description & Skills */}
        <div className="lg:col-span-2 space-y-xl">
          {/* Job Overview / Description */}
          <div className="rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-lg md:p-xl shadow-soft">
            <h2 className="text-headline-sm font-semibold text-on-surface mb-md">
              About the Role
            </h2>
            {job.description ? (
              <div
                className="rich-text text-body-md text-on-surface leading-relaxed whitespace-pre-line"
                dangerouslySetInnerHTML={{ __html: job.description }}
              />
            ) : (
              <p className="text-body-md text-on-surface-variant italic">No detailed description available.</p>
            )}
          </div>

          {/* Key Skills & Requirements */}
          {(mustHave.length > 0 || goodToHave.length > 0) && (
            <div className="rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-lg md:p-xl shadow-soft">
              <h2 className="text-headline-sm font-semibold text-on-surface mb-md">
                Required Skills
              </h2>

              {mustHave.length > 0 && (
                <div className="mb-lg">
                  <h3 className="text-body-sm font-semibold text-on-surface mb-sm">Must Have:</h3>
                  <div className="flex flex-wrap gap-xs">
                    {mustHave.map((item, idx) => {
                      const name = typeof item === 'string' ? item : item.skill
                      const yrs = typeof item === 'object' ? item.required_years : null
                      return (
                        <div
                          key={idx}
                          className="inline-flex items-center gap-xs rounded-xl bg-primary-container/70 border border-primary/20 px-md py-xs text-body-sm font-medium text-on-primary-container"
                        >
                          <span>{name}</span>
                          {yrs ? (
                            <span className="rounded-full bg-primary/20 px-xs py-[2px] text-label-md">
                              {yrs}+ yrs
                            </span>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {goodToHave.length > 0 && (
                <div>
                  <h3 className="text-body-sm font-semibold text-on-surface mb-sm">Good to Have:</h3>
                  <div className="flex flex-wrap gap-xs">
                    {goodToHave.map((item, idx) => {
                      const name = typeof item === 'string' ? item : item.skill
                      return (
                        <span
                          key={idx}
                          className="rounded-xl bg-surface-container-low border border-outline-variant/60 px-md py-xs text-body-sm font-medium text-on-surface"
                        >
                          {name}
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Single Apply Action & Job Summary Sidebar */}
        <div className="space-y-lg">
          <div className="sticky top-24 rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-lg shadow-lift space-y-md">
            <h3 className="text-headline-sm font-semibold text-on-surface">Job Summary</h3>

            <div className="space-y-sm text-body-sm">
              <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
                <span className="text-on-surface-variant">Company</span>
                <span className="font-medium text-on-surface">{job.organization_name || 'EZScreen Partner'}</span>
              </div>
              <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
                <span className="text-on-surface-variant">Location</span>
                <span className="font-medium text-on-surface">{job.location || 'Flexible'}</span>
              </div>
              <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
                <span className="text-on-surface-variant">Work Mode</span>
                <span className="font-medium text-on-surface">{formatBadge(job.work_type) || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
                <span className="text-on-surface-variant">Employment Type</span>
                <span className="font-medium text-on-surface">{formatBadge(job.job_type) || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
                <span className="text-on-surface-variant">Experience</span>
                <span className="font-medium text-on-surface">
                  {job.experience_min ?? 0} - {job.experience_max ?? 'Any'} Years
                </span>
              </div>
              <div className="flex items-center justify-between pt-xs">
                <span className="text-on-surface-variant">Posted Date</span>
                <span className="font-medium text-on-surface">
                  {job.published_at ? new Date(job.published_at).toLocaleDateString() : 'Recently'}
                </span>
              </div>
            </div>

            {/* Single Apply Button */}
            <button
              type="button"
              onClick={() => setIsApplyModalOpen(true)}
              className="w-full inline-flex items-center justify-center gap-xs rounded-xl bg-primary px-lg py-sm text-body-md font-semibold text-on-primary shadow-soft hover:bg-primary/90 transition-colors"
            >
              <span>Apply for this Role</span>
            </button>
          </div>
        </div>
      </div>

      {/* Application Modal */}
      {isApplyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 backdrop-blur-sm p-margin-mobile">
          <div className="w-full max-w-lg rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-xl shadow-lift">
            <div className="flex items-center justify-between mb-md">
              <h3 className="text-headline-sm font-semibold text-on-surface">Apply for {job.title}</h3>
              <button
                type="button"
                onClick={() => setIsApplyModalOpen(false)}
                className="rounded-lg p-xs text-on-surface-variant hover:bg-surface-container-low transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <p className="text-body-sm text-on-surface-variant mb-lg">
              Submit your application for <strong>{job.title}</strong> at <strong>{job.organization_name || 'EZScreen Partner'}</strong>.
            </p>

            <div className="flex justify-end gap-sm">
              <button
                type="button"
                onClick={() => setIsApplyModalOpen(false)}
                className="rounded-xl bg-surface-container-high px-lg py-sm text-body-sm font-medium text-on-surface hover:bg-outline-variant transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
