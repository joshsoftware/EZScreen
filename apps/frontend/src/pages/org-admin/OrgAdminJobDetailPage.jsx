import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { JobForm } from '../../features/jobs/JobForm'
import { getJobApplicantsRequest, getJobRequest, updateJobRequest } from '../../features/jobs/api'
import { ApplicantsTable } from '../../features/jobs/ApplicantsTable'
import { ResumeBulkUpload } from '../../features/jobs/ResumeBulkUpload'
import { JobParsedDetailPanel } from '../../features/jobs/JobParsedDetailPanel'
import {
  applicantScore,
  isPendingApplicant,
  jobSubtitle,
} from '../../features/jobs/applicationFields'
import {
  formatJobStatus,
  jobStatusTone,
  jobToFormValues,
} from '../../features/jobs/jobFields'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { PageHeader, Panel, StatCard } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

const POLL_INTERVAL_MS = 3000
const POLL_TIMEOUT_MS = 120000

export function OrgAdminJobDetailPage() {
  const { jobId = '' } = useParams()
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [showEditJob, setShowEditJob] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [applicants, setApplicants] = useState([])
  const [applicantsLoading, setApplicantsLoading] = useState(true)
  const [applicantsError, setApplicantsError] = useState(null)
  const [applicantsRefreshing, setApplicantsRefreshing] = useState(false)
  const [fitFilter, setFitFilter] = useState('all')
  const [queueWatch, setQueueWatch] = useState(null)
  const applicantsRef = useRef(applicants)
  applicantsRef.current = applicants

  const load = useCallback(async () => {
    if (!jobId) return
    setError(null)
    try {
      const data = await getJobRequest(jobId)
      setJob(data)
    } catch (err) {
      setJob(null)
      setError(err instanceof ApiError ? err.message : 'Failed to load job')
    }
  }, [jobId])

  const loadApplicants = useCallback(
    async ({ refresh = false } = {}) => {
      if (!jobId) return
      if (refresh) {
        setApplicantsRefreshing(true)
      } else {
        setApplicantsLoading(true)
      }
      setApplicantsError(null)
      try {
        const data = await getJobApplicantsRequest(jobId)
        const list = Array.isArray(data) ? data : []
        setApplicants(list)
        return list
      } catch (err) {
        setApplicantsError(
          err instanceof ApiError ? err.message : 'Failed to load applicants',
        )
        return null
      } finally {
        if (refresh) {
          setApplicantsRefreshing(false)
        } else {
          setApplicantsLoading(false)
        }
      }
    },
    [jobId],
  )

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void loadApplicants()
  }, [loadApplicants])

  useEffect(() => {
    // If a job is published/closed, it becomes non-editable.
    // Ensure we don't keep the edit UI open.
    if (!job) return
    if (job.status !== 'draft') {
      setShowEditJob(false)
    }
  }, [job])

  useEffect(() => {
    if (!queueWatch || !jobId) return undefined

    let cancelled = false
    const startedAt = queueWatch.startedAt

    async function poll() {
      const data = await getJobApplicantsRequest(jobId).catch(() => null)
      if (cancelled || !data) return
      const list = Array.isArray(data) ? data : []
      setApplicants(list)

      const screened = list.filter((item) => applicantScore(item) != null).length
      const remaining = Math.max(0, queueWatch.targetScreened - screened)
      const timedOut = Date.now() - startedAt >= POLL_TIMEOUT_MS

      if (remaining <= 0 || timedOut) {
        if (remaining <= 0) {
          toast.success('Resume processing finished')
        } else {
          toast.message('Still processing — use refresh to check again')
        }
        setQueueWatch(null)
      }
    }

    const intervalId = window.setInterval(() => {
      void poll()
    }, POLL_INTERVAL_MS)
    void poll()

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [jobId, queueWatch])

  async function onSubmit(payload) {
    setSubmitting(true)
    try {
      await updateJobRequest(jobId, payload)
      toast.success('Job updated')
      await load()
      setShowEditJob(false)
    } catch (err) {
      throw err instanceof ApiError ? err : new Error('Failed to update job')
    } finally {
      setSubmitting(false)
    }
  }

  function handleQueued(queued) {
    const added = Number(queued) || 0
    if (added <= 0) return
    setQueueWatch((current) => ({
      targetScreened:
        (current?.targetScreened ??
          applicantsRef.current.filter((item) => applicantScore(item) != null).length) +
        added,
      startedAt: current?.startedAt ?? Date.now(),
    }))
    void loadApplicants({ refresh: true })
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

  if (!job) {
    return <PageSkeleton />
  }

  const canEditJd = job.status === 'draft'

  const screenedCount = applicants.filter((item) => applicantScore(item) != null).length
  const pendingCount = applicants.filter(isPendingApplicant).length
  const processingRemaining = queueWatch
    ? Math.max(
        0,
        queueWatch.targetScreened -
          applicants.filter((item) => applicantScore(item) != null).length,
      )
    : 0
  const topFit = applicants.reduce((max, item) => {
    const score = applicantScore(item)
    return score != null && score > max ? score : max
  }, 0)

  return (
    <div className="space-y-lg">
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
            <Button
              variant="primary"
              onClick={() => setShowUploadModal(true)}
            >
              Upload resumes
            </Button>
            {canEditJd ? (
              <Button
                variant="secondary"
                onClick={() => setShowEditJob((value) => !value)}
              >
                {showEditJob ? 'Hide job settings' : 'Edit job'}
              </Button>
            ) : null}
          </div>
        }
      />

      {processingRemaining > 0 ? (
        <Alert tone="info">
          Processing {processingRemaining} resume{processingRemaining === 1 ? '' : 's'}… new
          applicants will appear as each file finishes.
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
          selected={fitFilter === 'strong'}
          onClick={() => setFitFilter('strong')}
        />
      </div>

      <Panel title="Applicants">
        <div id="applicants">
          <ApplicantsTable
            jobId={jobId}
            applicants={applicants}
            loading={applicantsLoading}
            error={applicantsError}
            refreshing={applicantsRefreshing}
            fitFilter={fitFilter}
            onFitFilterChange={setFitFilter}
            processing={processingRemaining > 0}
            onRefresh={() => loadApplicants({ refresh: true })}
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

      {canEditJd && showEditJob ? (
        <Panel title="Edit job" className="max-w-3xl">
          <JobForm
            key={job.id}
            initialValues={jobToFormValues(job)}
            onSubmit={onSubmit}
            submitting={submitting}
            submitLabel="Save changes"
          />
        </Panel>
      ) : null}
    </div>
  )
}
