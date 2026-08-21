import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { JobForm } from '../../features/jobs/JobForm'
import { JobSkillsEditor } from '../../features/jobs/JobSkillsEditor'
import { updateJobRequest } from '../../features/jobs/api'
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
  jobToFormValues,
} from '../../features/jobs/jobFields'
import { skillsFromJob } from '../../features/jobs/jobParsedFields'
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
  const { fitLabels } = useOrgSettings()
  const topLabelId = topFitLabelId(fitLabels)
  const { invalidateJob, invalidateJobApplicants } = useJobQueryClient()
  const [submitting, setSubmitting] = useState(false)
  const [showEditJob, setShowEditJob] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [editSkills, setEditSkills] = useState({ must_have: [], good_to_have: [] })
  const [skillsSubmitting, setSkillsSubmitting] = useState(false)
  const [fitFilter, setFitFilter] = useState('all')
  const [queueWatch, setQueueWatch] = useState(null)
  const applicantsRef = useRef([])

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
  } = useJobApplicantsQuery(
    jobId,
    {},
    {
      refetchInterval: queueWatch ? POLL_INTERVAL_MS : false,
    },
  )

  applicantsRef.current = applicants

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
    if (showEditJob && job) {
      setEditSkills(skillsFromJob(job))
    }
  }, [showEditJob, job])

  useEffect(() => {
    if (!queueWatch) return undefined

    const screened = applicants.filter((item) => applicantScore(item) != null).length
    const remaining = Math.max(0, queueWatch.targetScreened - screened)
    const timedOut = Date.now() - queueWatch.startedAt >= POLL_TIMEOUT_MS

    if (remaining <= 0 || timedOut) {
      if (remaining <= 0) {
        toast.success('Resume processing finished')
      } else {
        toast.message('Still processing — use refresh to check again')
      }
      setQueueWatch(null)
    }
  }, [applicants, queueWatch])

  async function onSubmit(payload) {
    setSubmitting(true)
    try {
      await updateJobRequest(jobId, payload)
      toast.success('Job updated')
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      throw err instanceof ApiError ? err : new Error('Failed to update job')
    } finally {
      setSubmitting(false)
    }
  }

  async function onSkillsSubmit() {
    setSkillsSubmitting(true)
    try {
      await updateJobRequest(jobId, { skills: editSkills })
      toast.success('Skill years updated')
      await invalidateJob(jobId)
      await refetchJob()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to save skills')
    } finally {
      setSkillsSubmitting(false)
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
            <Button icon="upload_file" onClick={() => setShowUploadModal(true)}>
              Upload resumes
            </Button>
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
            processing={processingRemaining > 0}
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
            <h3 className="font-headline-sm text-headline-sm text-on-surface mb-md">Skill years</h3>
            <JobSkillsEditor
              skills={editSkills}
              onChange={setEditSkills}
              onSubmit={onSkillsSubmit}
              submitting={skillsSubmitting}
              submitLabel="Save skill years"
            />
          </div>
        </Panel>
      ) : null}
    </div>
  )
}
