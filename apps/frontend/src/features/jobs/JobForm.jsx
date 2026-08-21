import { lazy, Suspense, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { Input, Label, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import {
  EMPTY_JOB_FORM,
  JOB_STATUS_OPTIONS,
  JOB_TYPE_OPTIONS,
  WORK_TYPE_OPTIONS,
  formValuesToPayload,
} from './jobFields'

const RichTextEditor = lazy(() =>
  import('../../components/ui/RichTextEditor').then((m) => ({
    default: m.RichTextEditor,
  })),
)

function RichTextEditorFallback({ id, label }) {
  return (
    <div>
      {label ? <Label htmlFor={id}>{label}</Label> : null}
      <Skeleton className="h-40 w-full rounded-lg" />
    </div>
  )
}

export function JobForm({
  initialValues = EMPTY_JOB_FORM,
  onSubmit,
  submitting = false,
  submitLabel = 'Save job',
  submittingLabel = 'Saving…',
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
      <Suspense
        fallback={
          <RichTextEditorFallback id="job-description" label="Description" />
        }
      >
        <RichTextEditor
          id="job-description"
          label="Description"
          value={values.description}
          onChange={(html) => setField('description', html)}
          placeholder="Role summary, responsibilities, must-have vs nice-to-have skills, and expected years per skill…"
        />
      </Suspense>
      <p className="text-label-md text-on-surface-variant -mt-sm">
        Include must-have and nice-to-have skills in the description, with expected years of
        experience where you know them. You can fine-tune years after parsing.
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
          {submitting ? submittingLabel : submitLabel}
        </Button>
      </div>
    </form>
  )
}
