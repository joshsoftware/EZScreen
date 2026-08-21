import { useCallback, useState } from 'react'
import { Alert } from '../../components/ui/Alert'
import { HtmlContent } from '../../components/ui/HtmlContent'
import { Badge } from '../../components/ui/Badge'
import { Panel } from '../../components/ui/PageHeader'
import {
  formatExperience,
  formatJobType,
  formatWorkType,
} from './jobFields'
import {
  jdExperienceRange,
  jdSkillLists,
  jdStringList,
  skillsFromJob,
} from './jobParsedFields'

function safe(value) {
  if (typeof value === 'string') return value.trim() || null
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return null
}

const SECTION_KEYS = ['overview', 'skills', 'qualifications', 'responsibilities', 'description']
const DEFAULT_OPEN = { overview: true, skills: true, qualifications: false, responsibilities: false, description: false }

function Section({ title, open, onToggle, children }) {
  return (
    <div className="border-b border-outline-variant last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between py-sm text-left"
      >
        <span className="font-label-md text-label-md text-on-surface">{title}</span>
        <span
          className="material-symbols-outlined text-on-surface-variant text-[18px] transition-transform"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        >
          expand_more
        </span>
      </button>
      {open ? <div className="pb-md">{children}</div> : null}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex gap-md py-xs">
      <span className="text-label-md text-on-surface-variant w-40 shrink-0">{label}</span>
      <span className="text-body-sm text-on-surface">{value ?? '—'}</span>
    </div>
  )
}

export function JobParsedDetailPanel({ job, loading, error }) {
  const [sections, setSections] = useState(DEFAULT_OPEN)

  const toggle = useCallback((key) => {
    setSections((prev) => ({ ...prev, [key]: !prev[key] }))
  }, [])

  const anyOpen = SECTION_KEYS.some((k) => sections[k])

  function closeAll() {
    setSections({ overview: false, skills: false, qualifications: false, responsibilities: false, description: false })
  }

  if (loading) {
    return (
      <div className="space-y-lg animate-pulse">
        <div className="h-48 rounded-xl bg-surface-container-high" />
      </div>
    )
  }

  if (error) return <Alert>{error}</Alert>
  if (!job) return null

  const parsedJd = job.parsed_jd

  if (!parsedJd) {
    return (
      <Alert tone="info">
        No parsed job description yet. Parsed JD is generated when the job is created or updated.
      </Alert>
    )
  }

  const { mustHave, goodToHave } = jdSkillLists({
    skills: skillsFromJob(job),
  })
  const qualifications = jdStringList(parsedJd, 'qualifications')
  const responsibilities = jdStringList(parsedJd, 'responsibilities')
  const parsedExperience = jdExperienceRange(parsedJd)
  const formExperience = formatExperience(job.experience_min, job.experience_max)
  const companyDesc = safe(parsedJd.company_description)

  const collapseAction = anyOpen ? (
    <button
      type="button"
      onClick={closeAll}
      className="inline-flex items-center gap-xs text-label-md font-semibold text-primary hover:text-on-primary-fixed-variant transition-colors"
    >
      <span className="material-symbols-outlined text-[18px] leading-none">unfold_less</span>
      Collapse all
    </button>
  ) : null

  return (
    <Panel title="Job requirements (AI-parsed)" actions={collapseAction}>
      <div className="divide-y divide-outline-variant">
        <Section title="Overview" open={sections.overview} onToggle={() => toggle('overview')}>
          <div className="grid sm:grid-cols-2 gap-x-lg">
            <Row label="Title" value={safe(parsedJd.title) || job.title} />
            <Row label="Company" value={safe(parsedJd.company)} />
            <Row label="Location" value={safe(parsedJd.location) || job.location} />
            <Row
              label="Employment type"
              value={safe(parsedJd.employment_type) || formatJobType(job.job_type)}
            />
            <Row label="Experience" value={parsedExperience || formExperience} />
            <Row label="Work mode" value={formatWorkType(job.work_type)} />
          </div>
          {companyDesc ? (
            <p className="text-body-sm text-on-surface-variant mt-sm">{companyDesc}</p>
          ) : null}
        </Section>

        <Section
          title={`Skills — ${mustHave.length} must-have · ${goodToHave.length} nice-to-have`}
          open={sections.skills}
          onToggle={() => toggle('skills')}
        >
          {mustHave.length > 0 ? (
            <div className="mb-sm">
              <p className="text-label-md text-on-surface-variant mb-xs">Must-have</p>
              <div className="flex flex-wrap gap-xs">
                {mustHave.map((s) => (
                  <Badge key={s.skill} tone="success">
                    {s.skill}{s.years != null ? ` (${s.years}y)` : ''}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
          {goodToHave.length > 0 ? (
            <div>
              <p className="text-label-md text-on-surface-variant mb-xs">Nice-to-have</p>
              <div className="flex flex-wrap gap-xs">
                {goodToHave.map((s) => (
                  <Badge key={s.skill} tone="info">
                    {s.skill}{s.years != null ? ` (${s.years}y)` : ''}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
          {mustHave.length === 0 && goodToHave.length === 0 ? (
            <p className="text-body-sm text-on-surface-variant">No skills extracted</p>
          ) : null}
        </Section>

        <Section
          title={`Qualifications (${qualifications.length})`}
          open={sections.qualifications}
          onToggle={() => toggle('qualifications')}
        >
          {qualifications.length > 0 ? (
            <ul className="text-body-sm text-on-surface space-y-xs list-disc pl-md">
              {qualifications.map((q) => <li key={q}>{q}</li>)}
            </ul>
          ) : (
            <p className="text-body-sm text-on-surface-variant">None extracted</p>
          )}
        </Section>

        <Section
          title={`Responsibilities (${responsibilities.length})`}
          open={sections.responsibilities}
          onToggle={() => toggle('responsibilities')}
        >
          {responsibilities.length > 0 ? (
            <ul className="text-body-sm text-on-surface space-y-xs list-disc pl-md">
              {responsibilities.map((r) => <li key={r}>{r}</li>)}
            </ul>
          ) : (
            <p className="text-body-sm text-on-surface-variant">None extracted</p>
          )}
        </Section>

        <Section title="Description" open={sections.description} onToggle={() => toggle('description')}>
          <HtmlContent html={job.description} empty="No description entered." />
        </Section>
      </div>
    </Panel>
  )
}
