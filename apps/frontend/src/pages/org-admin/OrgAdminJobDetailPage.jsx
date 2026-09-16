import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { JobForm } from '../../features/jobs/JobForm'
import { JobSkillsEditor } from '../../features/jobs/JobSkillsEditor'
import {
  updateJobRequest,
  getJobRequest,
  listJobsRequest,
  streamResumeIngestProgress,
} from '../../features/jobs/api'
import {
  useJobApplicantsQuery,
  useJobQuery,
  useJobQueryClient,
} from '../../features/jobs/useJobQueries'
import { ApplicantsTable } from '../../features/jobs/ApplicantsTable'
import { ResumeBulkUpload } from '../../features/jobs/ResumeBulkUpload'
import { JobParsedDetailPanel } from '../../features/jobs/JobParsedDetailPanel'
import {
  applicantScore,
  isPendingApplicant,
  jobSubtitle,
  topFitLabelId,
} from '../../features/jobs/applicationFields'
import { useOrgSettings } from '../../features/org-admin/OrgSettingsContext'
import {
  formatJobStatus,
  jobStatusTone,
  jobToCloneFormValues,
  jobToFormValues,
} from '../../features/jobs/jobFields'
import { syncSkillsAfterReparse, skillsFromJob } from '../../features/jobs/jobParsedFields'
import {
  clearResumeQueueWatch,
  peekResumeQueueWatch,
  saveResumeQueueWatch,
} from '../../features/jobs/resumeQueueWatch'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { PageHeader, Panel, StatCard } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { ResumeIngestErrorsBanner } from '../../components/jobs/ResumeIngestErrorsBanner'

const POLL_TIMEOUT_MS = 900000

function ingestErrorCreatedAtMs(value) {
  if (value == null) return 0
  if (typeof value === 'number') return value
  const raw = String(value).trim()
  if (!raw) return 0
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(raw) ? raw : `${raw}Z`
  const ms = Date.parse(normalized)
  return Number.isFinite(ms) ? ms : 0
}

export function OrgAdminJobDetailPage() {
  const { jobId = '' } = useParams()
  const navigate = useNavigate()
  const { fitLabels } = useOrgSettings()
  const topLabelId = topFitLabelId(fitLabels)
  const { invalidateJob, invalidateJobApplicants } = useJobQueryClient()
  const [submitting, setSubmitting] = useState(false)
  const [closing, setClosing] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)
  const [showEditJob, setShowEditJob] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [editSkills, setEditSkills] = useState({ must_have: [], good_to_have: [] })
  const [skillsSubmitting, setSkillsSubmitting] = useState(false)
  const [fitFilter, setFitFilter] = useState('all')
  const [queueWatch, setQueueWatch] = useState(null)
  const [ingestErrors, setIngestErrors] = useState([])
  /** Keep filtering by the latest upload even after the queue watch ends. */
  const [attemptStartedAt, setAttemptStartedAt] = useState(null)
  const [activeBatchId, setActiveBatchId] = useState(null)
  const [ingestProgress, setIngestProgress] = useState(null)
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const applicantsRef = useRef([])
  const wasProcessingRef = useRef(false)
  const editSkillsInitializedRef = useRef(false)
  const lastErrorToastSigRef = useRef('')
  const lastCompletedRef = useRef(0)

  const activeQueueWatch = queueWatch ?? peekResumeQueueWatch(jobId, POLL_TIMEOUT_MS)
  const errorWindowStart = activeQueueWatch?.startedAt ?? attemptStartedAt
  const recentIngestErrors =
    errorWindowStart == null
      ? []
      : ingestErrors.filter(
          (item) => ingestErrorCreatedAtMs(item.created_at) >= errorWindowStart - 5000,
        )
  const failedCount =
    ingestProgress?.failed ?? recentIngestErrors.length
  const visibleIngestErrors = bannerDismissed ? [] : recentIngestErrors

  const {
    data: job,
    isLoading: jobLoading,
    error: jobQueryError,
    refetch: refetchJob,
  } = useJobQuery(jobId)

  const {
    data: applicants = [],
    isLoading: applicantsLoading,
    isFetching: applicantsFetching,
    error: applicantsQueryError,
    refetch: refetchApplicants,
  } = useJobApplicantsQuery(jobId, {})

  applicantsRef.current = applicants

  const screenedCount = applicants.filter((item) => applicantScore(item) != null).length
  const pendingCount = applicants.filter(isPendingApplicant).length
  const pendingIngestCount = applicants.filter(
    (item) => item.source === 'hr_bulk' && applicantScore(item) == null
  ).length
  const streamRemaining =
    ingestProgress && !ingestProgress.done
      ? Math.max(0, Number(ingestProgress.remaining) || 0)
      : null
  const queueRemaining = activeQueueWatch
    ? Math.max(0, activeQueueWatch.targetScreened - screenedCount - failedCount)
    : 0
  const processingRemaining = Math.max(
    streamRemaining ?? 0,
    queueRemaining,
    activeBatchId ? pendingIngestCount : 0,
  )
  const isProcessingResumes =
    Boolean(activeBatchId) || processingRemaining > 0 || Boolean(streamRemaining)

  useEffect(() => {
    if (!jobId || !activeBatchId) return undefined

    const controller = new AbortController()
    let cancelled = false

    async function runStream() {
      try {
        await streamResumeIngestProgress(jobId, activeBatchId, {
          signal: controller.signal,
          onEvent(event) {
            if (cancelled || !event || typeof event !== 'object') return
            setIngestProgress(event)
            const errors = Array.isArray(event.errors) ? event.errors : []
            setIngestErrors(errors)

            const completed = Number(event.completed) || 0
            if (completed > lastCompletedRef.current) {
              lastCompletedRef.current = completed
              void refetchApplicants()
            }

            if (errors.length > 0) {
              const signature = errors
                .map((item) => `${item.file_name}|${item.message}|${item.created_at}`)
                .join(';')
              if (signature !== lastErrorToastSigRef.current) {
                lastErrorToastSigRef.current = signature
                setBannerDismissed(false)
                toast.error(
                  errors.length === 1
                    ? `1 resume failed: ${errors[0].file_name}`
                    : `${errors.length} resumes could not be processed`,
                )
              }
            }

            if (event.done) {
              clearResumeQueueWatch(jobId)
              setQueueWatch(null)
              setActiveBatchId(null)
              void refetchApplicants()
            }
          },
        })
      } catch (err) {
        if (cancelled || controller.signal.aborted) return
        toast.error(
          err instanceof Error ? err.message : 'Lost connection to resume progress',
        )
        setActiveBatchId(null)
        void refetchApplicants()
      }
    }

    void runStream()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [activeBatchId, jobId, refetchApplicants])

  const error = jobQueryError
    ? jobQueryError instanceof ApiError
      ? jobQueryError.message
      : 'Failed to load job'
    : null
  const applicantsError = applicantsQueryError
    ? applicantsQueryError instanceof ApiError
      ? applicantsQueryError.message
      : 'Failed to load applicants'
    : null

  useEffect(() => {
    if (!job) return
    if (job.status !== 'draft') {
      setShowEditJob(false)
    }
  }, [job])

  useEffect(() => {
    if (!showEditJob) {
      editSkillsInitializedRef.current = false
      return
    }
    if (job && !editSkillsInitializedRef.current) {
      setEditSkills(skillsFromJob(job))
      editSkillsInitializedRef.current = true
    }
  }, [showEditJob, job])

  useEffect(() => {
    if (!jobId) {
      setQueueWatch(null)
      setIngestErrors([])
      setAttemptStartedAt(null)
      setActiveBatchId(null)
      setIngestProgress(null)
      setBannerDismissed(false)
      lastErrorToastSigRef.current = ''
      lastCompletedRef.current = 0
      return
    }
    wasProcessingRef.current = false
    const stored = peekResumeQueueWatch(jobId, POLL_TIMEOUT_MS)
    setQueueWatch(stored)
    setAttemptStartedAt(stored?.startedAt ?? null)
    setActiveBatchId(stored?.batchId || null)
    setIngestErrors([])
    setIngestProgress(null)
    setBannerDismissed(false)
    lastErrorToastSigRef.current = ''
    lastCompletedRef.current = 0
  }, [jobId])

  useEffect(() => {
    if (queueWatch) {
      saveResumeQueueWatch(jobId, queueWatch)
    }
  }, [jobId, queueWatch])

  useEffect(() => {
    if (isProcessingResumes) {
      wasProcessingRef.current = true
      return undefined
    }
    if (wasProcessingRef.current) {
      wasProcessingRef.current = false
      if (failedCount === 0) {
        toast.success('Resume processing finished')
      } else {
        toast.error(
          failedCount === 1
            ? 'Resume processing finished with 1 failure'
            : `Resume processing finished with ${failedCount} failures`,
        )
      }
    }
  }, [failedCount, isProcessingResumes])

  useEffect(() => {
    if (!activeQueueWatch || activeBatchId) return undefined

    if (activeQueueWatch.targetScreened <= screenedCount + failedCount) {
      clearResumeQueueWatch(jobId)
      setQueueWatch(null)
      return undefined
    }

    const timedOut = Date.now() - activeQueueWatch.startedAt >= POLL_TIMEOUT_MS
    if (timedOut) {
      clearResumeQueueWatch(jobId)
      setQueueWatch(null)
      toast.message('Still processing — use refresh to check again')
    }
  }, [activeBatchId, activeQueueWatch, failedCount, jobId, screenedCount])

  async function onSubmit(payload) {
    setSubmitting(true)
    try {
      const previousParsed = job?.parsed_jd ?? null
      await updateJobRequest(jobId, payload)
      const full = await getJobRequest(jobId)
      setEditSkills((current) =>
        syncSkillsAfterReparse(current, previousParsed, full.parsed_jd),
      )
      toast.success('Job updated')
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      throw err instanceof ApiError ? err : new Error('Failed to update job')
    } finally {
      setSubmitting(false)
    }
  }

  async function onSkillsSubmit(nextSkills = editSkills) {
    setSkillsSubmitting(true)
    try {
      await updateJobRequest(jobId, { skills: nextSkills })
      toast.success('Skills updated')
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to save skills')
    } finally {
      setSkillsSubmitting(false)
    }
  }

  async function onCloseJob() {
    if (closing) return
    setClosing(true)
    try {
      await updateJobRequest(jobId, { status: 'closed' })
      toast.success('Job closed')
      setShowCloseConfirm(false)
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to close job')
    } finally {
      setClosing(false)
    }
  }

  async function onPublishJob() {
    if (publishing) return
    setPublishing(true)
    try {
      await updateJobRequest(jobId, { status: 'published' })
      toast.success('Job published')
      setShowEditJob(false)
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to publish job')
    } finally {
      setPublishing(false)
    }
  }

  async function onCloneJob() {
    let existingTitles = []
    try {
      const pageSize = 50
      let page = 1
      while (page <= 20) {
        const batch = await listJobsRequest({ page, limit: pageSize })
        const jobs = Array.isArray(batch) ? batch : []
        existingTitles = existingTitles.concat(
          jobs.map((item) => item.title).filter(Boolean),
        )
        if (jobs.length < pageSize) break
        page += 1
      }
    } catch {
      // Fall through with empty titles — still produce Copy 1.
    }
    navigate('/org-admin/jobs/new', {
      state: {
        cloneInitialValues: jobToCloneFormValues(job, existingTitles),
      },
    })
  }

  function handleQueued(payload) {
    const added =
      typeof payload === 'object' && payload != null
        ? Number(payload.queued)
        : Number(payload)
    const batchId =
      typeof payload === 'object' && payload != null
        ? String(payload.batchId || '').trim()
        : ''
    if (!Number.isFinite(added) || added <= 0) return
    wasProcessingRef.current = false
    const startedAt = Date.now()
    const scoredNow = applicantsRef.current.filter(
      (item) => applicantScore(item) != null,
    ).length
    const pendingNow = applicantsRef.current.filter(
      (item) => item.source === 'hr_bulk' && applicantScore(item) == null,
    ).length
    setIngestErrors([])
    setIngestProgress({
      queued: added,
      completed: 0,
      failed: 0,
      remaining: added,
      done: false,
      errors: [],
    })
    setAttemptStartedAt(startedAt)
    setBannerDismissed(false)
    lastErrorToastSigRef.current = ''
    lastCompletedRef.current = 0
    setQueueWatch({
      targetScreened: scoredNow + pendingNow + added,
      startedAt,
      batchId: batchId || null,
    })
    setActiveBatchId(batchId || null)
    void invalidateJobApplicants(jobId)
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
          title="Job"
        />
        <Alert>{error}</Alert>
      </div>
    )
  }

  if (jobLoading || !job) {
    return <PageSkeleton />
  }

  const canEditJd = job.status === 'draft'
  const canPublishJob = job.status === 'draft'
  const canUploadResumes = job.status === 'published'
  const canCloseJob = job.status === 'published'

  const topFit = applicants.reduce((max, item) => {
    const score = applicantScore(item)
    return score != null && score > max ? score : max
  }, 0)

  return (
    <div className="space-y-lg">
      <ResumeIngestErrorsBanner
        errors={visibleIngestErrors}
        onDismiss={() => setBannerDismissed(true)}
      />

      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/org-admin/jobs" className="hover:underline">
              Jobs
            </Link>
          </p>
        }
        title={job.title || 'Untitled job'}
        description={jobSubtitle(job) || 'Manage applicants and job settings for this opening.'}
        actions={
          <div className="flex flex-wrap items-center gap-sm">
            <Badge tone={jobStatusTone(job.status)}>{formatJobStatus(job.status)}</Badge>
            <Button variant="secondary" icon="content_copy" onClick={onCloneJob}>
              Clone
            </Button>
            {canUploadResumes ? (
              <Button icon="upload_file" onClick={() => setShowUploadModal(true)}>
                Upload resumes
              </Button>
            ) : null}
            {canCloseJob ? (
              <Button
                variant="danger"
                icon="cancel"
                onClick={() => setShowCloseConfirm(true)}
              >
                Close job
              </Button>
            ) : null}
            {canPublishJob ? (
              <Button icon="publish" loading={publishing} onClick={onPublishJob}>
                {publishing ? 'Generating questions…' : 'Publish'}
              </Button>
            ) : null}
            {canEditJd ? (
              <Button
                variant="secondary"
                icon={showEditJob ? 'close' : 'edit'}
                onClick={() => setShowEditJob((value) => !value)}
              >
                {showEditJob ? 'Hide job settings' : 'Edit job'}
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-md">
        <StatCard
          label="Applicants"
          value={String(applicants.length)}
          selected={fitFilter === 'all'}
          onClick={() => setFitFilter('all')}
        />
        <StatCard
          label="Scored"
          value={String(screenedCount)}
          selected={fitFilter === 'screened'}
          onClick={() => setFitFilter('screened')}
        />
        <StatCard
          label="Awaiting score"
          value={String(pendingCount)}
          selected={fitFilter === 'pending'}
          onClick={() => setFitFilter('pending')}
        />
        <StatCard
          label="Top fit"
          value={topFit > 0 ? topFit.toFixed(1) : '—'}
          selected={fitFilter === topLabelId}
          onClick={() => setFitFilter(topLabelId || 'all')}
        />
      </div>

      <Panel title="Applicants">
        <div id="applicants">
          <ApplicantsTable
            jobId={jobId}
            applicants={applicants}
            loading={applicantsLoading}
            error={applicantsError}
            refreshing={applicantsFetching && !applicantsLoading}
            fitFilter={fitFilter}
            onFitFilterChange={setFitFilter}
            processing={isProcessingResumes}
            processingRemaining={processingRemaining}
            onRefresh={() => {
              void refetchApplicants()
            }}
          />
        </div>
      </Panel>

      <JobParsedDetailPanel job={job} loading={false} error={null} />

      <Modal
        open={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        title="Upload resumes"
      >
        <p className="text-body-sm text-on-surface-variant mb-md">
          Upload resumes in bulk. Each file is parsed asynchronously and scored against this job.
        </p>
        <ResumeBulkUpload
          jobId={jobId}
          onQueued={(count) => {
            setShowUploadModal(false)
            handleQueued(count)
          }}
        />
      </Modal>

      <Modal
        open={showCloseConfirm}
        onClose={() => {
          if (!closing) setShowCloseConfirm(false)
        }}
        title="Close this job?"
      >
        <p className="text-body-sm text-on-surface-variant mb-md">
          Closed jobs stop accepting new resume uploads. Existing applicants stay available for
          review.
        </p>
        <div className="flex flex-wrap justify-end gap-sm">
          <Button
            variant="secondary"
            disabled={closing}
            onClick={() => setShowCloseConfirm(false)}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            icon="cancel"
            loading={closing}
            onClick={onCloseJob}
          >
            Close job
          </Button>
        </div>
      </Modal>

      {canEditJd && showEditJob ? (
        <Panel title="Edit job" className="max-w-3xl">
          <JobForm
            key={job.id}
            initialValues={jobToFormValues(job)}
            onSubmit={onSubmit}
            submitting={submitting}
            submitLabel="Save details"
            submittingLabel="Parsing skills…"
          />
          <div className="mt-lg pt-lg border-t border-outline-variant">
            <h3 className="font-headline-sm text-headline-sm text-on-surface mb-md">Skills</h3>
            <JobSkillsEditor
              skills={editSkills}
              onChange={setEditSkills}
              onSubmit={onSkillsSubmit}
              submitting={skillsSubmitting}
              submitLabel="Save skills"
            />
          </div>
        </Panel>
      ) : null}
    </div>
  )
}
