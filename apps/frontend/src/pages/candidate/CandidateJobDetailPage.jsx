import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { usePublicJobDetailQuery } from '../../features/candidate/usePublicJobs'
import { ORG_URL_SLUG } from '../../features/candidate/constants'
import { CandidateApplyModal } from '../../features/candidate/components/CandidateApplyModal'
import { CandidateJobSkills } from '../../features/candidate/components/CandidateJobSkills'
import { CandidateJobSummarySidebar } from '../../features/candidate/components/CandidateJobSummarySidebar'
import {
  formatExperience,
  formatJobType,
  formatWorkType,
} from '../../features/jobs/jobFields'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { HtmlContent } from '../../components/ui/HtmlContent'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function CandidateJobDetailPage() {
  const { org = ORG_URL_SLUG, jobId } = useParams()
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false)
  const jobsPath = `/${org}/jobs`

  const { data: job, isLoading, isError, error } = usePublicJobDetailQuery(jobId, org)

  if (isLoading) {
    return <PageSkeleton />
  }

  if (isError || !job) {
    return (
      <div className="space-y-md">
        <PageHeader
          breadcrumb={
            <p className="text-label-md text-secondary">
              <Link to={jobsPath} className="hover:underline">
                Open positions
              </Link>
            </p>
          }
          title="Position not found"
        />
        <Alert>
          {error?.message || 'This job opening is no longer accepting applications.'}
        </Alert>
        <Button to={jobsPath} variant="secondary" icon="arrow_back">
          Back to open positions
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-lg">
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to={jobsPath} className="hover:underline">
              Open positions
            </Link>
          </p>
        }
        title={job.title || 'Untitled position'}
        description={job.organization_name || undefined}
        actions={
          <Button type="button" icon="send" onClick={() => setIsApplyModalOpen(true)}>
            Apply
          </Button>
        }
      />

      <div className="flex flex-wrap gap-xs -mt-sm mb-sm">
        {job.location ? <Badge tone="neutral">{job.location}</Badge> : null}
        {job.work_type ? <Badge tone="neutral">{formatWorkType(job.work_type)}</Badge> : null}
        {job.job_type ? <Badge tone="info">{formatJobType(job.job_type)}</Badge> : null}
        {job.experience_min != null || job.experience_max != null ? (
          <Badge tone="neutral">
            {formatExperience(job.experience_min, job.experience_max)}
          </Badge>
        ) : null}
      </div>

      <div className="grid gap-lg lg:grid-cols-3 items-start">
        <div className="lg:col-span-2 space-y-lg">
          <Panel title="About the role">
            {job.description ? (
              <HtmlContent html={job.description} empty="No detailed description available." />
            ) : (
              <p className="text-body-sm text-on-surface-variant italic">
                No detailed description available.
              </p>
            )}
          </Panel>
          <CandidateJobSkills skills={job.skills} />
        </div>

        <CandidateJobSummarySidebar
          job={job}
          onApply={() => setIsApplyModalOpen(true)}
        />
      </div>

      <CandidateApplyModal
        open={isApplyModalOpen}
        job={job}
        onClose={() => setIsApplyModalOpen(false)}
      />
    </div>
  )
}
