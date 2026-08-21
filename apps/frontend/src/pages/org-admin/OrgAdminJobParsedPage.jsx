import { Link, useParams } from 'react-router-dom'
import { useJobQuery } from '../../features/jobs/useJobQueries'
import { JobParsedDetailPanel } from '../../features/jobs/JobParsedDetailPanel'
import { jobSubtitle } from '../../features/jobs/applicationFields'
import { formatJobStatus, jobStatusTone } from '../../features/jobs/jobFields'
import { jdHasContent } from '../../features/jobs/jobParsedFields'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function OrgAdminJobParsedPage() {
  const { jobId = '' } = useParams()
  const {
    data: job,
    isLoading,
    error: queryError,
  } = useJobQuery(jobId)

  const error = queryError
    ? queryError instanceof ApiError
      ? queryError.message
      : 'Failed to load job'
    : null

  const jobHref = `/org-admin/jobs/${jobId}`

  if (isLoading) {
    return <PageSkeleton />
  }

  if (error && !job) {
    return (
      <div>
        <PageHeader
          breadcrumb={
            <p className="text-label-md text-secondary">
              <Link to="/org-admin/jobs" className="hover:underline">
                Jobs
              </Link>
            </p>
          }
          title="Parsed job description"
        />
        <Alert>{error}</Alert>
      </div>
    )
  }

  const hasParsed = jdHasContent(job?.parsed_jd)

  return (
    <div className="space-y-lg">
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/org-admin/jobs" className="hover:underline">
              Jobs
            </Link>
            {' / '}
            <Link to={jobHref} className="hover:underline">
              {job?.title || 'Job'}
            </Link>
            {' / Parsed JD'}
          </p>
        }
        title="AI-parsed job requirements"
        description={
          jobSubtitle(job) ||
          'Structured requirements extracted from the job form for resume matching.'
        }
        actions={
          <div className="flex flex-wrap items-center gap-sm">
            <Badge tone={hasParsed ? 'success' : 'neutral'}>
              {hasParsed ? 'Parsed' : 'Not available'}
            </Badge>
            <Badge tone={jobStatusTone(job.status)}>{formatJobStatus(job.status)}</Badge>
            <Button variant="secondary" to={jobHref}>
              Back to job
            </Button>
          </div>
        }
      />
      <JobParsedDetailPanel job={job} loading={false} error={null} />
    </div>
  )
}
