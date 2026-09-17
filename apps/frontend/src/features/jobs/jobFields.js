export function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export const JOB_TYPE_OPTIONS = [
  { value: '', label: 'Select type' },
  { value: 'full_time', label: 'Full time' },
  { value: 'part_time', label: 'Part time' },
  { value: 'contract', label: 'Contract' },
]

export const WORK_TYPE_OPTIONS = [
  { value: '', label: 'Select work mode' },
  { value: 'onsite', label: 'On-site' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'remote', label: 'Remote' },
]

export const JOB_STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'published', label: 'Published' },
  { value: 'closed', label: 'Closed' },
]

/** Stable H2 titles used when assembling / splitting structured JD HTML. */
export const JD_SECTION_DEFS = [
  {
    key: 'role_summary',
    heading: 'Role overview',
    list: false,
  },
  {
    key: 'about_company',
    heading: 'About the company',
    list: false,
  },
  {
    key: 'responsibilities',
    heading: 'Responsibilities',
    list: true,
  },
  {
    key: 'must_have_skills_text',
    heading: 'Must-have skills',
    list: true,
  },
  {
    key: 'good_to_have_skills_text',
    heading: 'Good-to-have skills',
    list: true,
  },
  {
    key: 'qualifications',
    heading: 'Qualifications',
    list: true,
  },
  {
    key: 'domain_experience',
    heading: 'Domain / industry experience',
    list: true,
  },
  {
    key: 'tools_stack',
    heading: 'Tools & stack',
    list: true,
  },
]

export const EMPTY_JOB_FORM = {
  title: '',
  role_summary: '',
  about_company: '',
  responsibilities: '',
  must_have_skills_text: '',
  good_to_have_skills_text: '',
  qualifications: '',
  domain_experience: '',
  tools_stack: '',
  job_type: '',
  work_type: '',
  location: '',
  experience_min: '',
  experience_max: '',
  status: 'draft',
}

const JOB_TYPE_LABELS = {
  full_time: 'Full time',
  part_time: 'Part time',
  contract: 'Contract',
}

const WORK_TYPE_LABELS = {
  onsite: 'On-site',
  hybrid: 'Hybrid',
  remote: 'Remote',
}

const STATUS_LABELS = {
  draft: 'Draft',
  published: 'Published',
  closed: 'Closed',
}

const HEADING_TO_KEY = Object.fromEntries(
  JD_SECTION_DEFS.map((section) => [section.heading.toLowerCase(), section.key]),
)

export function formatJobType(value) {
  return JOB_TYPE_LABELS[value] || '—'
}

export function formatWorkType(value) {
  return WORK_TYPE_LABELS[value] || '—'
}

export function formatJobStatus(value) {
  return STATUS_LABELS[value] || value || '—'
}

export function jobStatusTone(status) {
  if (status === 'published') return 'success'
  if (status === 'closed') return 'neutral'
  return 'warning'
}

export function formatExperience(min, max) {
  if (min == null && max == null) return '—'
  if (min != null && max != null) return `${min}–${max} yrs`
  if (min != null) return `${min}+ yrs`
  return `Up to ${max} yrs`
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function decodeBasicEntities(text) {
  return String(text)
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
}

function htmlToPlainText(html) {
  if (!html || typeof html !== 'string') return ''
  return decodeBasicEntities(
    html
      .replace(/<\s*br\s*\/?>/gi, '\n')
      .replace(/<\/\s*p\s*>/gi, '\n')
      .replace(/<\/\s*div\s*>/gi, '\n')
      .replace(/<\/\s*li\s*>/gi, '\n')
      .replace(/<\/\s*h[1-6]\s*>/gi, '\n')
      .replace(/<[^>]+>/g, '')
  )
    .split(/\n+/)
    .map((line) => line.replace(/^[•\-\*\u2022]\s*/, '').trim())
    .filter(Boolean)
    .join('\n')
}

function linesFromText(value) {
  if (typeof value !== 'string') return []
  return value
    .split(/\n+/)
    .map((line) => line.replace(/^[•\-\*\u2022]\s*/, '').trim())
    .filter(Boolean)
}

function sectionHtml(heading, body, { list }) {
  const lines = linesFromText(body)
  if (lines.length === 0) return ''
  const title = `<h2>${escapeHtml(heading)}</h2>`
  if (list) {
    const items = lines.map((line) => `<li>${escapeHtml(line)}</li>`).join('')
    return `${title}<ul>${items}</ul>`
  }
  return `${title}${lines.map((line) => `<p>${escapeHtml(line)}</p>`).join('')}`
}

/** Build stored description HTML from structured section fields. */
export function assembleJobDescriptionHtml(values) {
  const parts = JD_SECTION_DEFS.map((section) =>
    sectionHtml(section.heading, values[section.key], { list: section.list }),
  ).filter(Boolean)
  return parts.length > 0 ? parts.join('') : null
}

/**
 * Split stored description HTML back into section fields.
 * Legacy free-form JDs (no matching H2s) land in role_summary.
 */
export function splitJobDescriptionHtml(html) {
  const sections = Object.fromEntries(JD_SECTION_DEFS.map((s) => [s.key, '']))
  if (!html || typeof html !== 'string') return sections

  const normalized = html.trim()
  if (!normalized) return sections

  const headingPattern = /<h2[^>]*>([\s\S]*?)<\/h2>/gi
  const matches = [...normalized.matchAll(headingPattern)]

  if (matches.length === 0) {
    sections.role_summary = htmlToPlainText(normalized)
    return sections
  }

  for (let i = 0; i < matches.length; i += 1) {
    const match = matches[i]
    const headingText = htmlToPlainText(match[1]).trim().toLowerCase()
    const key = HEADING_TO_KEY[headingText]
    const start = match.index + match[0].length
    const end = i + 1 < matches.length ? matches[i + 1].index : normalized.length
    const bodyHtml = normalized.slice(start, end)
    if (!key) continue
    sections[key] = htmlToPlainText(bodyHtml)
  }

  const anyFilled = JD_SECTION_DEFS.some((s) => sections[s.key])
  if (!anyFilled) {
    sections.role_summary = htmlToPlainText(normalized)
  }

  return sections
}

export function jobToFormValues(job) {
  const sections = splitJobDescriptionHtml(job?.description ?? '')
  return {
    title: job.title ?? '',
    ...sections,
    job_type: job.job_type ?? '',
    work_type: job.work_type ?? '',
    location: job.location ?? '',
    experience_min: job.experience_min == null ? '' : String(job.experience_min),
    experience_max: job.experience_max == null ? '' : String(job.experience_max),
    status: job.status ?? 'draft',
  }
}

/** Prefill Create Job step 1 from an existing job (always draft). */
export function stripCloneSuffix(title) {
  const base = (title || '').trim() || 'Untitled job'
  return base.replace(/ \(Copy(?: \d+)?\)$/i, '').trim() || 'Untitled job'
}

/**
 * Next unique `{root} (Copy N)` title given existing org titles.
 * Unnumbered `(Copy)` is treated as Copy 1 already taken.
 */
export function nextCloneTitle(sourceTitle, existingTitles = []) {
  const root = stripCloneSuffix(sourceTitle)
  const escaped = root.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const pattern = new RegExp(`^${escaped} \\(Copy(?: (\\d+))?\\)$`, 'i')
  const used = new Set()
  for (const title of existingTitles) {
    const match = String(title || '')
      .trim()
      .match(pattern)
    if (!match) continue
    used.add(match[1] ? Number(match[1]) : 1)
  }
  let n = 1
  while (used.has(n)) n += 1
  return `${root} (Copy ${n})`
}

/** Prefill Create Job step 1 from an existing job (always draft). */
export function jobToCloneFormValues(job, existingTitles = []) {
  const values = jobToFormValues(job)
  return {
    ...values,
    title: nextCloneTitle(values.title, existingTitles),
    status: 'draft',
  }
}

function emptyToNull(value) {
  const trimmed = typeof value === 'string' ? value.trim() : value
  return trimmed ? trimmed : null
}

function parseOptionalInt(value) {
  if (value === '' || value == null) return null
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error('Experience years must be a whole number from 0 to 50.')
  }
  if (parsed > 50) {
    throw new Error('Experience years must be 50 or less.')
  }
  return parsed
}

export function formValuesToPayload(values) {
  const title = values.title.trim()
  if (!title) {
    throw new Error('Title is required.')
  }

  const experienceMin = parseOptionalInt(values.experience_min)
  const experienceMax = parseOptionalInt(values.experience_max)
  if (experienceMin != null && experienceMax != null && experienceMin > experienceMax) {
    throw new Error('Minimum experience cannot be greater than maximum.')
  }

  const description = assembleJobDescriptionHtml(values)
  if (!description) {
    throw new Error('Add at least one JD section (overview, responsibilities, or skills).')
  }

  return {
    title,
    description,
    job_type: emptyToNull(values.job_type),
    work_type: emptyToNull(values.work_type),
    location: emptyToNull(values.location),
    experience_min: experienceMin,
    experience_max: experienceMax,
    status: values.status || 'draft',
  }
}
