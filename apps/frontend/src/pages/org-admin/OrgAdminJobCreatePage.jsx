import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { JobForm } from '../../features/jobs/JobForm'
import { createJobRequest } from '../../features/jobs/api'
import { ApiError } from '../../lib/api/client'
import { PageHeader, Panel } from '../../components/ui/PageHeader'

export function OrgAdminJobCreatePage() {
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(payload) {
    setSubmitting(true)
    try {
      await createJobRequest(payload)
      toast.success('Job created')
      navigate('/org-admin/jobs', { replace: true })
    } catch (err) {
      throw err instanceof ApiError ? err : new Error('Failed to create job')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/org-admin/jobs" className="hover:underline">
              Jobs
            </Link>{' '}
            / Create
          </p>
        }
        title="Create job"
        description="Fill in the opening details. List skills below; mark must-have vs nice-to-have in the description."
      />
      <Panel>
        <JobForm
          onSubmit={onSubmit}
          submitting={submitting}
          submitLabel="Create job"
        />
      </Panel>
    </div>
  )
}
