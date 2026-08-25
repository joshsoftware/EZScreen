import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { rerunJobFitRequest } from '../../features/jobs/api'
import {
  useApplicationQuery,
  useApplicationTimelineQuery,
  useJobQuery,
  useJobQueryClient,
} from '../../features/jobs/useJobQueries'
import { ApplicationDetailPanel } from '../../features/jobs/ApplicationDetailPanel'
import { useOrgSettings } from '../../features/org-admin/OrgSettingsContext'
import {
  candidateInitials,
  candidateName,
  fitLabel,
  fitTone,
  formatApplicationStatus,
  resolveMatchScore,
} from '../../features/jobs/applicationFields'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function OrgAdminApplicationDetailPage() {
  const { jobId = '', applicationId = '' } = useParams()
  const { fitLabels } = useOrgSettings()
  const { invalidateApplication, invalidateApplicationTimeline, invalidateJobApplicants } =
    useJobQueryClient()
  const [rerunning, setRerunning] = useState(false)

  const {
    data: job,
    isLoading: jobLoading,
    error: jobError,
  } = useJobQuery(jobId)

  const {
    data: detail,
    isLoading: detailLoading,
    error: detailError,
    refetch: refetchDetail,
  } = useApplicationQuery(applicationId)

  const {
    data: timeline = [],
    isLoading: timelineLoading,
    error: timelineQueryError,
    refetch: refetchTimeline,
  } = useApplicationTimelineQuery(applicationId)

  const mismatch =
    detail && detail.job_description_id !== jobId
      ? 'Application does not belong to this job'
      : null

  const loading = jobLoading || detailLoading
  const error =
    mismatch ||
    (detailError
      ? detailError instanceof ApiError
        ? detailError.message
        : 'Failed to load application'
      : null) ||
    (jobError
      ? jobError instanceof ApiError
        ? jobError.message
        : 'Failed to load job'
      : null)

  const applicantsHref = `/org-admin/jobs/${jobId}#applicants`
  const score = resolveMatchScore(detail)
  const canRerun = Boolean(detail?.parsed_resume) && !rerunning && !mismatch

  async function reload() {
    await Promise.all([refetchDetail(), refetchTimeline()])
  }

  async function onRerun() {
    if (!detail || rerunning) return
    setRerunning(true)
    try {
      await rerunJobFitRequest(jobId, detail.id)
      toast.success('Job-fit recalculated')
      await invalidateApplication(applicationId)
      await invalidateApplicationTimeline(applicationId)
      await invalidateJobApplicants(jobId)
      await reload()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rerun fit')
    } finally {
      setRerunning(false)
    }
  }

  if (loading) {
    return <PageSkeleton />
  }

  if (error && (!detail || mismatch)) {
    return (
      <div>
        <PageHeader
          breadcrumb={
            <p className="text-label-md text-secondary">
              <Link to="/org-admin/jobs" className="hover:underline">
                Jobs
              </Link>
              {' / '}
              <Link to={applicantsHref} className="hover:underline">
                Applicants
              </Link>
            </p>
          }
          title="Applicant"
        />
        <Alert>{error}</Alert>
        <div className="mt-md">
          <Button variant="secondary" size="sm" to={applicantsHref}>
            Back to job
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-lg">
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/org-admin/jobs" className="hover:underline">
              Jobs
            </Link>
            {' / '}
            <Link to={applicantsHref} className="hover:underline">
              {job?.title || 'Job'}
            </Link>
            {' / Applicants'}
          </p>
        }
        title={
          <div className="flex items-center gap-md">
            <div className="w-14 h-14 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-headline-sm">
              {candidateInitials(detail)}
            </div>
            <div>
              <h1 className="font-headline-md text-headline-md text-on-surface">
                {candidateName(detail)}
              </h1>
              <p className="text-body-sm text-on-surface-variant mt-xs">
                {[
                  detail?.email,
                  detail?.phone,
                  detail?.candidate_yoe != null ? `${detail.candidate_yoe} YOE` : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            </div>
          </div>
        }
        actions={
          <div className="flex flex-wrap items-center gap-sm">
            <Badge tone={fitTone(score, fitLabels)}>
              {fitLabel(score, fitLabels)}
            </Badge>
            <Badge tone="info">
              Status · {formatApplicationStatus(detail.status, detail.source)}
            </Badge>
            <Button
              icon="replay"
              loading={rerunning}
              disabled={!canRerun}
              onClick={onRerun}
            >
              Rerun fit
            </Button>
          </div>
        }
      />
      <ApplicationDetailPanel
        jobId={jobId}
        detail={detail}
        loading={false}
        error={null}
        timeline={timeline}
        timelineLoading={timelineLoading}
        timelineError={
          timelineQueryError
            ? timelineQueryError instanceof ApiError
              ? timelineQueryError.message
              : 'Failed to load timeline'
            : null
        }
        onRerunComplete={reload}
      />
    </div>
  )
}
