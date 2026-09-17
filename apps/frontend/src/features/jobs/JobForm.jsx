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

function SectionBlock({ title, hint, children }) {
  return (
    <section className="rounded-xl border border-outline-variant/70 bg-surface-container-low/30 p-md space-y-md">
      <div>
        <h3 className="font-headline-sm text-headline-sm text-on-surface tracking-tight">
          {title}
        </h3>
        {hint ? (
          <p className="text-label-md text-on-surface-variant mt-xs">{hint}</p>
        ) : null}
      </div>
      {children}
    </section>
  )
}

function BulletField({ id, label, value, onChange, placeholder, rows = 4 }) {
  return (
    <div>
      <TextArea
        id={id}
        label={label}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={rows}
      />
      <p className="text-label-md text-on-surface-variant mt-xs">One item per line.</p>
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
  const [values, setValues] = useState(() => ({ ...EMPTY_JOB_FORM, ...initialValues }))
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
    <form className="space-y-lg" onSubmit={(event) => void handleSubmit(event)}>
      <SectionBlock title="Role overview" hint="Title and a short summary of the role.">
        <Input
          id="job-title"
          label="Job title"
          required
          value={values.title}
          onChange={(e) => setField('title', e.target.value)}
          maxLength={255}
        />
        <TextArea
          id="role-summary"
          label="Role summary"
          value={values.role_summary}
          onChange={(e) => setField('role_summary', e.target.value)}
          placeholder="What this role owns and why it exists…"
          rows={3}
        />
      </SectionBlock>

      <SectionBlock
        title="About the company / team"
        hint="Optional context for candidates and parsing."
      >
        <TextArea
          id="about-company"
          label="Company or team"
          value={values.about_company}
          onChange={(e) => setField('about_company', e.target.value)}
          placeholder="Product, team size, mission…"
          rows={3}
        />
      </SectionBlock>

      <SectionBlock title="Employment basics">
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
      </SectionBlock>

      <SectionBlock title="Responsibilities" hint="What the person will do day to day.">
        <BulletField
          id="responsibilities"
          label="Responsibilities"
          value={values.responsibilities}
          onChange={(e) => setField('responsibilities', e.target.value)}
          placeholder={'Own CI/CD pipelines\nImprove production observability\n…'}
          rows={5}
        />
      </SectionBlock>

      <SectionBlock
        title="Skills for screening"
        hint="Step 2 will extract skills and years from these sections so you can fine-tune them."
      >
        <BulletField
          id="must-have-skills"
          label="Must-have skills"
          value={values.must_have_skills_text}
          onChange={(e) => setField('must_have_skills_text', e.target.value)}
          placeholder={'Kubernetes — 3 years\nTerraform\nAWS\n…'}
          rows={5}
        />
        <BulletField
          id="good-to-have-skills"
          label="Good-to-have skills"
          value={values.good_to_have_skills_text}
          onChange={(e) => setField('good_to_have_skills_text', e.target.value)}
          placeholder={'Python scripting\nAzure or GCP\n…'}
          rows={4}
        />
        <BulletField
          id="tools-stack"
          label="Tools & stack"
          value={values.tools_stack}
          onChange={(e) => setField('tools_stack', e.target.value)}
          placeholder={'Go or Python\nPostgreSQL\nGitHub Actions\n…'}
          rows={4}
        />
      </SectionBlock>

      <SectionBlock title="Qualifications" hint="Education, certifications, clearances — not skills.">
        <BulletField
          id="qualifications"
          label="Qualifications"
          value={values.qualifications}
          onChange={(e) => setField('qualifications', e.target.value)}
          placeholder={"Bachelor's in CS or related field\nAWS Solutions Architect preferred\n…"}
          rows={4}
        />
      </SectionBlock>

      <SectionBlock
        title="Domain / industry experience"
        hint="e.g. fintech, healthcare, multi-tenant SaaS."
      >
        <BulletField
          id="domain-experience"
          label="Domain experience"
          value={values.domain_experience}
          onChange={(e) => setField('domain_experience', e.target.value)}
          placeholder={'Multi-tenant SaaS\nHigh-compliance environments\n…'}
          rows={3}
        />
      </SectionBlock>

      {error ? <Alert>{error}</Alert> : null}
      <div className="flex gap-sm pt-sm">
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
