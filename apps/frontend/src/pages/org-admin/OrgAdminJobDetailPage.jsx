import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { JobForm } from '../../features/jobs/JobForm'
import { JobSkillsEditor } from '../../features/jobs/JobSkillsEditor'
import { updateJobRequest, regenerateJobScreeningQuestionsRequest, updateJobScreeningQuestionsRequest, getResumeIngestErrorsRequest, getJobRequest } from '../../features/jobs/api'
import {
  useJobApplicantsQuery,
  useJobQuery,
  useJobQueryClient,
} from '../../features/jobs/useJobQueries'
import { ApplicantsTable } from '../../features/jobs/ApplicantsTable'
import { ResumeBulkUpload } from '../../features/jobs/ResumeBulkUpload'
import { JobParsedDetailPanel } from '../../features/jobs/JobParsedDetailPanel'
import { JobScreeningQuestionsPanel } from '../../features/jobs/JobScreeningQuestionsPanel'
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

const POLL_INTERVAL_MS = 3000
const POLL_TIMEOUT_MS = 120000

export function OrgAdminJobDetailPage() {
  const { jobId = '' } = useParams()
  const { fitLabels } = useOrgSettings()
  const topLabelId = topFitLabelId(fitLabels)
  const { invalidateJob, invalidateJobApplicants } = useJobQueryClient()
  const [submitting, setSubmitting] = useState(false)
  const [closing, setClosing] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [regeneratingQuestions, setRegeneratingQuestions] = useState(false)
  const [savingQuestions, setSavingQuestions] = useState(false)
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)
  const [showEditJob, setShowEditJob] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [editSkills, setEditSkills] = useState({ must_have: [], good_to_have: [] })
  const [skillsSubmitting, setSkillsSubmitting] = useState(false)
  const [fitFilter, setFitFilter] = useState('all')
  const [queueWatch, setQueueWatch] = useState(null)
  const [ingestErrors, setIngestErrors] = useState([])
  const applicantsRef = useRef([])
  const wasProcessingRef = useRef(false)
  const editSkillsInitializedRef = useRef(false)

  const activeQueueWatch = queueWatch ?? peekResumeQueueWatch(jobId, POLL_TIMEOUT_MS)
  const recentIngestErrors = ingestErrors.filter((item) => {
    if (!activeQueueWatch) return true
    return new Date(item.created_at).getTime() >= activeQueueWatch.startedAt
  })
  const failedCount = recentIngestErrors.length

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
  const queueRemaining = activeQueueWatch
    ? Math.max(0, activeQueueWatch.targetScreened - screenedCount - failedCount)
    : 0
  const processingRemaining = Math.max(queueRemaining, pendingCount)
  const isProcessingResumes = processingRemaining > 0

  useEffect(() => {
    if (!jobId) {
      setIngestErrors([])
      return undefined
    }
    if (!activeQueueWatch && ingestErrors.length === 0) {
      return undefined
    }

    let cancelled = false

    async function pollIngestErrors() {
      try {
        const since = activeQueueWatch
          ? new Date(activeQueueWatch.startedAt).toISOString()
          : undefined
        const data = await getResumeIngestErrorsRequest(jobId, since ? { since } : {})
        if (cancelled) return
        const errors = Array.isArray(data?.errors) ? data.errors : []
        if (errors.length > 0) {
          setIngestErrors(errors)
        }
      } catch {
        // Polling should not interrupt the rest of the page.
      }
    }

    void pollIngestErrors()
    if (!activeQueueWatch) return undefined

    const id = window.setInterval(pollIngestErrors, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [activeQueueWatch, ingestErrors.length, jobId])

  useEffect(() => {
    if (!isProcessingResumes) return undefined
    void refetchApplicants()
    const id = window.setInterval(() => {
      void refetchApplicants()
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [isProcessingResumes, refetchApplicants])

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
      return
    }
    wasProcessingRef.current = false
    const stored = peekResumeQueueWatch(jobId, POLL_TIMEOUT_MS)
    setQueueWatch(stored)
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
      }
    }
  }, [failedCount, isProcessingResumes])

  useEffect(() => {
    if (!activeQueueWatch) return undefined

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
  }, [activeQueueWatch, failedCount, jobId, screenedCount])

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
      const updated = await updateJobRequest(jobId, { status: 'published' })
      const questions = updated?.screening_questions
      if (questions?.status === 'success' && questions.count > 0) {
        toast.success(`Job published · ${questions.count} screening questions ready`)
      } else if (questions?.status === 'error') {
        toast.warning('Job published, but question generation failed. Use Regenerate to retry.')
      } else {
        toast.success('Job published')
      }
      setShowEditJob(false)
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to publish job')
    } finally {
      setPublishing(false)
    }
  }

  async function onSaveQuestions(questions) {
    setSavingQuestions(true)
    try {
      await updateJobScreeningQuestionsRequest(jobId, questions)
      toast.success('Screening questions saved')
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to save questions')
      throw err
    } finally {
      setSavingQuestions(false)
    }
  }

  async function onRegenerateQuestions() {
    if (regeneratingQuestions) return
    setRegeneratingQuestions(true)
    try {
      const updated = await regenerateJobScreeningQuestionsRequest(jobId)
      const questions = updated?.screening_questions
      if (questions?.status === 'success' && questions.count > 0) {
        toast.success(`Generated ${questions.count} screening questions`)
      } else {
        toast.error(questions?.error_message || 'Failed to generate questions')
      }
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to regenerate questions')
    } finally {
      setRegeneratingQuestions(false)
    }
  }

  function handleQueued(queued) {
    const added = Number(queued) || 0
    if (added <= 0) return
    wasProcessingRef.current = false
    setIngestErrors([])
    setQueueWatch((current) => ({
      targetScreened:
        (current?.targetScreened ??
          applicantsRef.current.filter((item) => applicantScore(item) != null).length) +
        added,
      startedAt: current?.startedAt ?? Date.now(),
    }))
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
      <ResumeIngestErrorsBanner errors={recentIngestErrors} />

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

      {isProcessingResumes ? (
        <Alert tone="info">
          Processing resumes — {processingRemaining} remaining. New applicants will appear as
          each file finishes.
        </Alert>
      ) : null}

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
            onRefresh={() => {
              void refetchApplicants()
            }}
          />
        </div>
      </Panel>

      <JobScreeningQuestionsPanel
        job={job}
        onRegenerate={job.status === 'published' ? onRegenerateQuestions : undefined}
        regenerating={regeneratingQuestions}
        onSave={job.status === 'published' ? onSaveQuestions : undefined}
        saving={savingQuestions}
      />

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
