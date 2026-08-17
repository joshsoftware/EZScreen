import { useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { Input, Select, TextArea } from '../../components/ui/Input'
import {
  EMPTY_JOB_FORM,
  JOB_STATUS_OPTIONS,
  JOB_TYPE_OPTIONS,
  WORK_TYPE_OPTIONS,
  formValuesToPayload,
} from './jobFields'

export function JobForm({
  initialValues = EMPTY_JOB_FORM,
  onSubmit,
  submitting = false,
  submitLabel = 'Save job',
  cancelTo = '/org-admin/jobs',
}) {
  const [values, setValues] = useState(initialValues)
  const [error, setError] = useState(null)

  function setField(name, value) {
    setValues((curr) => ({ ...curr, [name]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    let payload
    try {
      payload = formValuesToPayload(values)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check the form and try again.')
      return
    }
    try {
      await onSubmit(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save job.')
    }
  }

  return (
    <form className="space-y-md" onSubmit={(event) => void handleSubmit(event)}>
      <Input
        id="job-title"
        label="Job title"
        required
        value={values.title}
        onChange={(e) => setField('title', e.target.value)}
        maxLength={255}
      />
      <TextArea
        id="job-description"
        label="Description"
        rows={8}
        value={values.description}
        onChange={(e) => setField('description', e.target.value)}
        placeholder="Role summary, responsibilities, and which skills are must-have vs nice-to-have…"
      />
      <p className="text-label-md text-on-surface-variant -mt-sm">
        In the description, specify which listed skills are must-have and which are nice-to-have.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
        <Select
          id="job-type"
          label="Job type"
          value={values.job_type}
          onChange={(e) => setField('job_type', e.target.value)}
        >
          {JOB_TYPE_OPTIONS.map((option) => (
            <option key={option.value || 'none'} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        <Select
          id="work-type"
          label="Work mode"
          value={values.work_type}
          onChange={(e) => setField('work_type', e.target.value)}
        >
          {WORK_TYPE_OPTIONS.map((option) => (
            <option key={option.value || 'none'} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>
      <Input
        id="job-location"
        label="Location"
        value={values.location}
        onChange={(e) => setField('location', e.target.value)}
        maxLength={255}
        placeholder="Bangalore, Remote — India…"
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
        <Input
          id="experience-min"
          label="Min experience (years)"
          type="number"
          min={0}
          max={50}
          value={values.experience_min}
          onChange={(e) => setField('experience_min', e.target.value)}
        />
        <Input
          id="experience-max"
          label="Max experience (years)"
          type="number"
          min={0}
          max={50}
          value={values.experience_max}
          onChange={(e) => setField('experience_max', e.target.value)}
        />
      </div>
      <TextArea
        id="job-skills"
        label="Skills"
        rows={3}
        value={values.skills}
        onChange={(e) => setField('skills', e.target.value)}
        placeholder="Java, Spring Boot, PostgreSQL, Docker"
      />
      <Select
        id="job-status"
        label="Status"
        value={values.status}
        onChange={(e) => setField('status', e.target.value)}
      >
        {JOB_STATUS_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
      {error ? <Alert>{error}</Alert> : null}
      <div className="flex gap-sm pt-md">
        <Button to={cancelTo} variant="secondary">
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
      </div>
    </form>
  )
}
