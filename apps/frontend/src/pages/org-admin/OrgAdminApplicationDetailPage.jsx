import { lazy, Suspense, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  rejectApplicationRequest,
  rerunJobFitRequest,
} from '../../features/jobs/api'
import {
  useApplicationQuery,
  useApplicationTimelineQuery,
  useJobQuery,
  useJobQueryClient,
} from '../../features/jobs/useJobQueries'
import { ApplicationDetailPanel } from '../../features/jobs/ApplicationDetailPanel'
import { ResumePreviewButton } from '../../features/jobs/ResumeActions'
import { useOrgSettings } from '../../features/org-admin/OrgSettingsContext'
import {
  canRejectApplication,
  canScheduleScreening,
  candidateInitials,
  candidateName,
  fitLabel,
  fitTone,
  formatApplicationStatus,
  resolveMatchScore,
} from '../../features/jobs/applicationFields'
import { ApiError } from '../../lib/api/client'
import { ActionMenu } from '../../components/ui/ActionMenu'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Modal } from '../../components/ui/Modal'
import { PageHeader } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

const ScheduleScreeningModal = lazy(() =>
  import('../../features/jobs/ScheduleScreeningModal').then((mod) => ({
    default: mod.ScheduleScreeningModal,
  })),
)

export function OrgAdminApplicationDetailPage() {
  const { jobId = '', applicationId = '' } = useParams()
  const { fitLabels } = useOrgSettings()
  const { invalidateApplication, invalidateApplicationTimeline, invalidateJobApplicants } =
    useJobQueryClient()
  const [rerunning, setRerunning] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [showRejectConfirm, setShowRejectConfirm] = useState(false)
  const [showSchedule, setShowSchedule] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

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
  const busy = rerunning || rejecting
  const canRerun =
    Boolean(detail?.parsed_resume) &&
    !busy &&
    !mismatch &&
    detail?.status !== 'rejected'
  const showScheduleBtn =
    Boolean(detail) && !mismatch && canScheduleScreening(detail, timeline)
  const showReject = Boolean(detail) && !mismatch && canRejectApplication(detail, timeline)

  async function reload() {
    await Promise.all([refetchDetail(), refetchTimeline()])
  }

  async function refreshAfterAction() {
    await Promise.all([
      invalidateApplication(applicationId),
      invalidateApplicationTimeline(applicationId),
      invalidateJobApplicants(jobId),
    ])
    await reload()
  }

  async function onRerun() {
    if (!detail || busy) return
    setRerunning(true)
    try {
      await rerunJobFitRequest(jobId, detail.id)
      toast.success('Job-fit recalculated')
      await refreshAfterAction()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rerun fit')
    } finally {
      setRerunning(false)
    }
  }

  async function onReject() {
    if (!detail || busy) return
    setRejecting(true)
    try {
      await rejectApplicationRequest(detail.id, {
        reason: rejectReason.trim() || undefined,
      })
      toast.success('Applicant rejected')
      setShowRejectConfirm(false)
      setRejectReason('')
      await refreshAfterAction()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to reject applicant')
    } finally {
      setRejecting(false)
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

  const moreItems = [
    showScheduleBtn
      ? {
          id: 'schedule',
          label: 'Schedule screening',
          icon: 'event',
          disabled: busy,
          onSelect: () => setShowSchedule(true),
        }
      : null,
    canRerun || Boolean(detail?.parsed_resume)
      ? {
          id: 'rerun',
          label: 'Rerun fit',
          icon: 'replay',
          disabled: !canRerun,
          loading: rerunning,
          onSelect: onRerun,
        }
      : null,
    showReject
      ? {
          id: 'reject',
          label: 'Reject applicant',
          icon: 'person_off',
          danger: true,
          disabled: busy,
          onSelect: () => setShowRejectConfirm(true),
        }
      : null,
  ].filter(Boolean)

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
            <Badge tone={detail.status === 'rejected' ? 'danger' : 'info'}>
              Status · {formatApplicationStatus(detail.status, detail.source, timeline)}
            </Badge>
            <ResumePreviewButton
              applicationId={detail.id}
              hasResume={Boolean(detail.has_resume)}
              fileName={detail.resume_file_name}
            />
            <ActionMenu items={moreItems} />
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
        scheduleAction={{
          visible: showScheduleBtn,
          disabled: busy,
          onClick: () => setShowSchedule(true),
        }}
        onRerunComplete={reload}
      />

      {showSchedule ? (
        <Suspense fallback={null}>
          <ScheduleScreeningModal
            open={showSchedule}
            onClose={() => setShowSchedule(false)}
            applicationId={detail.id}
            candidateLabel={candidateName(detail)}
            candidateEmail={detail.email || null}
            onScheduled={refreshAfterAction}
          />
        </Suspense>
      ) : null}

      <Modal
        open={showRejectConfirm}
        onClose={() => {
          if (!rejecting) {
            setShowRejectConfirm(false)
            setRejectReason('')
          }
        }}
        title="Reject this applicant?"
      >
        <p className="text-body-sm text-on-surface-variant mb-md">
          This marks the application as rejected and updates the screening timeline. You can add an
          optional reason for your records.
        </p>
        <Input
          id="reject-reason"
          label="Reason (optional)"
          value={rejectReason}
          onChange={(event) => setRejectReason(event.target.value)}
          placeholder="e.g. Experience gap on must-have skills"
        />
        <div className="flex flex-wrap justify-end gap-sm mt-md">
          <Button
            variant="secondary"
            disabled={rejecting}
            onClick={() => {
              setShowRejectConfirm(false)
              setRejectReason('')
            }}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            icon="person_off"
            loading={rejecting}
            onClick={onReject}
          >
            Reject applicant
          </Button>
        </div>
      </Modal>
    </div>
  )
}
