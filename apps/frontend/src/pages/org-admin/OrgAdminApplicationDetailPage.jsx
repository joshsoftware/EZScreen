import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  getApplicationDetailRequest,

  getJobRequest,
  rerunJobFitRequest,
} from '../../features/jobs/api'
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
  const [job, setJob] = useState(null)
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [rerunning, setRerunning] = useState(false)

  const load = useCallback(async () => {
    if (!jobId || !applicationId) return
    setLoading(true)
    setError(null)
    try {
      const [jobData, applicationData] = await Promise.all([
        getJobRequest(jobId),
        getApplicationDetailRequest(applicationId),
      ])
      if (applicationData.job_description_id !== jobId) {
        setJob(jobData)
        setDetail(null)
        setError('Application does not belong to this job')
        return
      }
      setJob(jobData)
      setDetail(applicationData)
    } catch (err) {
      setJob(null)
      setDetail(null)
      setError(err instanceof ApiError ? err.message : 'Failed to load application')
    } finally {
      setLoading(false)
    }
  }, [jobId, applicationId])

  useEffect(() => {
    void load()
  }, [load])

  const applicantsHref = `/org-admin/jobs/${jobId}#applicants`
  const score = resolveMatchScore(detail)
  const canRerun = Boolean(detail?.parsed_resume) && !rerunning

  async function onRerun() {
    if (!detail || rerunning) return
    setRerunning(true)
    try {
      await rerunJobFitRequest(jobId, detail.id)
      toast.success('Job-fit recalculated')
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rerun fit')
    } finally {
      setRerunning(false)
    }
  }

  if (loading) {
    return <PageSkeleton />
  }

  if (error && !detail) {
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
            <Badge tone="info">Status · {formatApplicationStatus(detail.status)}</Badge>
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
        onRerunComplete={load}
      />
    </div>
  )
}
