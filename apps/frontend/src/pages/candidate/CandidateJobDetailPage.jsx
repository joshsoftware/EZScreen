import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { usePublicJobDetailQuery } from '../../features/candidate/usePublicJobs'
import { ORG_URL_SLUG } from '../../features/candidate/constants'
import { CandidateApplyModal } from '../../features/candidate/components/CandidateApplyModal'
import { CandidateJobHeader } from '../../features/candidate/components/CandidateJobHeader'
import { CandidateJobSkills } from '../../features/candidate/components/CandidateJobSkills'
import { CandidateJobSummarySidebar } from '../../features/candidate/components/CandidateJobSummarySidebar'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function CandidateJobDetailPage() {
  const { org = ORG_URL_SLUG, jobId } = useParams()
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false)
  const jobsPath = `/${org}/jobs`

  const { data: job, isLoading, isError, error } = usePublicJobDetailQuery(jobId, org)

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
            to={jobsPath}
            className="mt-lg inline-flex items-center gap-xs rounded-xl bg-primary px-lg py-sm text-body-sm font-medium text-on-primary shadow-soft hover:bg-primary/90 transition-colors"
          >
            <span>Back to Open Roles</span>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl px-margin-mobile py-lg md:px-lg md:py-xl">
      {/* Back Navigation */}
      <Link
        to={jobsPath}
        className="inline-flex items-center gap-xs text-body-sm font-medium text-on-surface-variant hover:text-primary transition-colors mb-md"
      >
        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
        <span>Back to open positions</span>
      </Link>

      {/* Header Banner */}
      <CandidateJobHeader job={job} />

      {/* Main Content Layout */}
      <div className="grid gap-xl lg:grid-cols-3">
        {/* Left Column: Job Overview & Required Skills */}
        <div className="lg:col-span-2 space-y-xl">
          {/* Job Description Panel */}
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

          {/* Key Skills & Requirements Panel */}
          <CandidateJobSkills skills={job.skills} />
        </div>

        {/* Right Column: Job Summary Sidebar */}
        <CandidateJobSummarySidebar
          job={job}
          onApply={() => setIsApplyModalOpen(true)}
        />
      </div>

      {/* Application Modal */}
      {isApplyModalOpen && (
        <CandidateApplyModal
          job={job}
          onClose={() => setIsApplyModalOpen(false)}
        />
      )}
    </div>
  )
}
