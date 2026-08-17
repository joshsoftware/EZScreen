import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { JobForm } from '../../features/jobs/JobForm'
import { getJobRequest, updateJobRequest } from '../../features/jobs/api'
import {
  formatJobStatus,
  jobStatusTone,
  jobToFormValues,
} from '../../features/jobs/jobFields'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

export function OrgAdminJobDetailPage() {
  const { jobId = '' } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

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

  useEffect(() => {
    void load()
  }, [load])

  async function onSubmit(payload) {
    setSubmitting(true)
    try {
      await updateJobRequest(jobId, payload)
      toast.success('Job updated')
      navigate('/org-admin/jobs', { replace: true })
    } catch (err) {
      throw err instanceof ApiError ? err : new Error('Failed to update job')
    } finally {
      setSubmitting(false)
    }
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

  return (
    <div className="max-w-2xl">
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/org-admin/jobs" className="hover:underline">
              Jobs
            </Link>{' '}
            / Edit
          </p>
        }
        title={job.title || 'Untitled job'}
        description="Update fields or change status. List skills below; mark must-have vs nice-to-have in the description."
        actions={
          <Badge tone={jobStatusTone(job.status)}>{formatJobStatus(job.status)}</Badge>
        }
      />
      <Panel>
        <JobForm
          key={job.id}
          initialValues={jobToFormValues(job)}
          onSubmit={onSubmit}
          submitting={submitting}
          submitLabel="Save changes"
        />
      </Panel>
    </div>
  )
}
