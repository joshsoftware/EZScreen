import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { JobForm } from '../../features/jobs/JobForm'
import { JobSkillsEditor } from '../../features/jobs/JobSkillsEditor'
import { createJobRequest, getJobRequest, updateJobRequest } from '../../features/jobs/api'
import { useJobQueryClient } from '../../features/jobs/useJobQueries'
import { EMPTY_JOB_FORM, jobToFormValues } from '../../features/jobs/jobFields'
import { syncSkillsAfterReparse } from '../../features/jobs/jobParsedFields'
import { ApiError } from '../../lib/api/client'
import { PageHeader, Panel } from '../../components/ui/PageHeader'

function StepLabel({ n, label, active }) {
  return (
    <span className={active ? 'text-on-surface' : 'text-on-surface-variant'}>
      <span className="font-medium">{n}</span> {label}
    </span>
  )
}

export function OrgAdminJobCreatePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setJobData } = useJobQueryClient()
  const cloneInitialValues = location.state?.cloneInitialValues
  const isClone = Boolean(cloneInitialValues)
  const [step, setStep] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [skillsError, setSkillsError] = useState(null)
  const [job, setJob] = useState(null)
  const [skills, setSkills] = useState({ must_have: [], good_to_have: [] })
  const [detailsInitial] = useState(() =>
    cloneInitialValues && typeof cloneInitialValues === 'object'
      ? { ...EMPTY_JOB_FORM, ...cloneInitialValues, status: 'draft' }
      : undefined,
  )

  async function onDetailsSubmit(payload) {
    setSubmitting(true)
    try {
      const previousParsed = job?.parsed_jd ?? null
      const saved = job
        ? await updateJobRequest(job.id, payload)
        : await createJobRequest(payload)
      setJob((current) => current ?? saved)
      const full = await getJobRequest(saved.id)
      setJobData(full.id, full)
      setJob(full)
      setSkills((current) =>
        syncSkillsAfterReparse(current, previousParsed, full.parsed_jd),
      )
      setStep(2)
    } catch (err) {
      throw err instanceof ApiError ? err : new Error('Failed to parse job details')
    } finally {
      setSubmitting(false)
    }
  }

  async function onSkillsSubmit(nextSkills = skills) {
    if (!job?.id) return
    setSubmitting(true)
    setSkillsError(null)
    try {
      await updateJobRequest(job.id, { skills: nextSkills })
      toast.success('Job created')
      navigate('/org-admin/jobs', { replace: true })
    } catch (err) {
      setSkillsError(err instanceof ApiError ? err.message : 'Failed to save skills')
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
            / {isClone ? 'Clone' : 'Create'}
          </p>
        }
        title={isClone ? 'Clone job' : 'Create job'}
        description={
          isClone ? (
            <>
              Step 1 is prefilled from the source job.
              <br />
              Review details, then continue to skills.
            </>
          ) : (
            <>
              Step 1 captures the opening.
              <br />
              Step 2 lets you edit, add, or remove skills and set expected years.
            </>
          )
        }
      />
      <p className="text-label-md mb-md">
        <StepLabel n="1." label="Details" active={step === 1} />
        <span className="mx-sm text-outline-variant">/</span>
        <StepLabel n="2." label="Skills" active={step === 2} />
      </p>
      <Panel>
        {step === 1 ? (
          <JobForm
            key={detailsInitial ? 'clone' : job?.id ?? 'new'}
            initialValues={
              job ? jobToFormValues(job) : detailsInitial ?? undefined
            }
            onSubmit={onDetailsSubmit}
            submitting={submitting}
            submitLabel="Continue"
            submittingLabel="Parsing skills…"
          />
        ) : (
          <JobSkillsEditor
            skills={skills}
            onChange={setSkills}
            onBack={() => setStep(1)}
            onSubmit={onSkillsSubmit}
            submitting={submitting}
            error={skillsError}
            submitLabel="Create job"
          />
        )}
      </Panel>
    </div>
  )
}
