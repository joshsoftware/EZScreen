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

export const EMPTY_JOB_FORM = {
  title: '',
  description: '',
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

export function jobToFormValues(job) {
  return {
    title: job.title ?? '',
    description: job.description ?? '',
    job_type: job.job_type ?? '',
    work_type: job.work_type ?? '',
    location: job.location ?? '',
    experience_min: job.experience_min == null ? '' : String(job.experience_min),
    experience_max: job.experience_max == null ? '' : String(job.experience_max),
    status: job.status ?? 'draft',
  }
}

/** Prefill Create Job step 1 from an existing job (always draft). */
export function jobToCloneFormValues(job) {
  const values = jobToFormValues(job)
  const base = values.title.trim() || 'Untitled job'
  const suffix = ' (Copy)'
  return {
    ...values,
    title: base.endsWith(suffix) ? base : `${base}${suffix}`,
    status: 'draft',
  }
}

function emptyToNull(value) {
  const trimmed = typeof value === 'string' ? value.trim() : value
  return trimmed ? trimmed : null
}

function emptyHtmlToNull(value) {
  if (typeof value !== 'string') return null
  const text = value.replace(/<[^>]*>/g, '').replace(/&nbsp;/gi, ' ').trim()
  return text ? value : null
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

  return {
    title,
    description: emptyHtmlToNull(values.description),
    job_type: emptyToNull(values.job_type),
    work_type: emptyToNull(values.work_type),
    location: emptyToNull(values.location),
    experience_min: experienceMin,
    experience_max: experienceMax,
    status: values.status || 'draft',
  }
}
