export function numericScore(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export const DEFAULT_FIT_LABELS = Object.freeze([
  Object.freeze({ id: 'strong', name: 'Strong', min_score: 8, max_score: 10 }),
  Object.freeze({ id: 'moderate', name: 'Moderate', min_score: 6, max_score: 7.9 }),
  Object.freeze({ id: 'weak', name: 'Weak', min_score: 0, max_score: 5.9 }),
])

function formatScoreBound(value) {
  return Number.isInteger(value) ? String(value) : Number(value).toFixed(1)
}

function rangesOverlap(aMin, aMax, bMin, bMax) {
  return aMin <= bMax && bMin <= aMax
}

export function normalizeFitLabels(value) {
  const source = Array.isArray(value) && value.length > 0 ? value : DEFAULT_FIT_LABELS
  const labels = []
  const seenIds = new Set()

  for (const item of source) {
    const name = typeof item?.name === 'string' ? item.name.trim() : ''
    const minScore = numericScore(item?.min_score)
    const maxScore = numericScore(item?.max_score)
    if (!name || minScore == null || maxScore == null) continue
    if (minScore < 0 || maxScore > 10 || minScore > maxScore) continue

    let id =
      typeof item?.id === 'string' && item.id.trim()
        ? item.id.trim()
        : name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') ||
          `label-${labels.length + 1}`
    while (seenIds.has(id)) id = `${id}-${labels.length + 1}`
    seenIds.add(id)

    labels.push({
      id,
      name,
      min_score: minScore,
      max_score: maxScore,
    })
  }

  if (labels.length === 0) {
    return DEFAULT_FIT_LABELS.map((item) => ({ ...item }))
  }

  const ordered = [...labels].sort(
    (a, b) => a.min_score - b.min_score || a.max_score - b.max_score,
  )
  for (let i = 0; i < ordered.length; i += 1) {
    for (let j = i + 1; j < ordered.length; j += 1) {
      if (
        rangesOverlap(
          ordered[i].min_score,
          ordered[i].max_score,
          ordered[j].min_score,
          ordered[j].max_score,
        )
      ) {
        return DEFAULT_FIT_LABELS.map((item) => ({ ...item }))
      }
    }
  }

  return labels
}

export function resolveFitBand(score, labels = DEFAULT_FIT_LABELS) {
  if (typeof score !== 'number') return null
  const bands = normalizeFitLabels(labels)
  return (
    bands.find((band) => score >= band.min_score && score <= band.max_score) ?? null
  )
}

export function topFitLabelId(labels = DEFAULT_FIT_LABELS) {
  const bands = normalizeFitLabels(labels)
  if (bands.length === 0) return null
  return [...bands].sort((a, b) => b.min_score - a.min_score)[0].id
}

function toneForBand(band, labels) {
  if (!band) return 'neutral'
  const bands = [...normalizeFitLabels(labels)].sort((a, b) => b.min_score - a.min_score)
  const index = bands.findIndex((item) => item.id === band.id)
  if (index <= 0) return 'success'
  if (index >= bands.length - 1) return 'danger'
  return 'warning'
}

export function isPendingApplicant(applicant) {
  return numericScore(applicant?.resume_score) == null
}

export function applicantScore(applicant) {
  return numericScore(applicant?.resume_score)
}

export function fitLabel(score, labels = DEFAULT_FIT_LABELS) {
  if (typeof score !== 'number') return 'Pending'
  return resolveFitBand(score, labels)?.name ?? 'Unrated'
}

export function fitTone(score, labels = DEFAULT_FIT_LABELS) {
  if (typeof score !== 'number') return 'neutral'
  return toneForBand(resolveFitBand(score, labels), labels)
}

export function fitBorderClass(score, labels = DEFAULT_FIT_LABELS) {
  const tone = fitTone(score, labels)
  if (tone === 'success') return 'border-l-emerald-500'
  if (tone === 'warning') return 'border-l-amber-500'
  if (tone === 'danger') return 'border-l-red-400'
  return 'border-l-outline-variant'
}

export function scoreTextClass(score, labels = DEFAULT_FIT_LABELS) {
  const tone = fitTone(score, labels)
  if (tone === 'success') return 'text-emerald-800'
  if (tone === 'warning') return 'text-amber-800'
  if (tone === 'danger') return 'text-red-700'
  return 'text-on-surface-variant'
}

export function matchesFitFilter(applicant, filter, labels = DEFAULT_FIT_LABELS) {
  const score = applicantScore(applicant)
  if (filter === 'all') return true
  if (filter === 'pending') return score == null
  if (filter === 'screened') return score != null
  if (score == null) return false
  const band = resolveFitBand(score, labels)
  return band?.id === filter
}

export function fitFilterOptions(labels = DEFAULT_FIT_LABELS) {
  const bands = [...normalizeFitLabels(labels)].sort((a, b) => b.min_score - a.min_score)
  return [
    { value: 'all', label: 'All fit levels' },
    ...bands.map((band) => ({
      value: band.id,
      label: `${band.name} (${formatScoreBound(band.min_score)}–${formatScoreBound(band.max_score)})`,
    })),
    { value: 'pending', label: 'Pending' },
    { value: 'screened', label: 'Scored' },
  ]
}

export function candidateName(applicant) {
  const name = [applicant?.first_name, applicant?.last_name].filter(Boolean).join(' ')
  return name || applicant?.email || 'Unknown'
}

export function candidateInitials(applicant) {
  const first = applicant?.first_name?.trim()?.[0] ?? ''
  const last = applicant?.last_name?.trim()?.[0] ?? ''
  const initials = `${first}${last}`.toUpperCase()
  if (initials) return initials
  const email = applicant?.email?.trim()?.[0]
  return email ? email.toUpperCase() : '?'
}

const STATUS_LABELS = {
  applied: 'Applied',
  interview_scheduled: 'Interview scheduled',
  interview_completed: 'Interview completed',
  shortlist_for_l1: 'Shortlisted for L1',
  rejected: 'Rejected',
}

export function formatApplicationStatus(status, source) {
  if (!status) return '—'
  if (status === 'applied' && source === 'hr_bulk') return 'Scored'
  if (status === 'applied' && source === 'candidate') return 'Applied'
  return STATUS_LABELS[status] ?? status.replaceAll('_', ' ')
}

export function resolveMatchScore(detail) {
  const direct = numericScore(detail?.resume_score)
  if (direct != null) return direct
  const analysis = detail?.job_fit_analysis
  if (analysis && typeof analysis === 'object') {
    return numericScore(analysis.match_score)
  }
  return null
}

export function scoreBreakdownCards(analysis) {
  if (!analysis || typeof analysis !== 'object') return []

  const breakdown = analysis.score_breakdown
  if (!breakdown || typeof breakdown !== 'object') {
    const overall = numericScore(analysis.match_score)
    return overall == null
      ? []
      : [{ label: 'Overall', value: `${overall.toFixed(1)}/10` }]
  }

  const mustHave = numericScore(breakdown.must_have_skills_score) ?? 0
  const goodToHave = numericScore(breakdown.good_to_have_skills_score) ?? 0
  const experience = numericScore(breakdown.experience_score) ?? 0
  const qualifications = numericScore(breakdown.qualifications_score) ?? 0
  const overall = numericScore(analysis.match_score)

  const toTen = (value, max) => `${((value / max) * 10).toFixed(1)}/10`

  return [
    {
      label: 'Overall',
      value: overall == null ? '—' : `${overall.toFixed(1)}/10`,
    },
    {
      label: 'Skills',
      value: toTen(mustHave + goodToHave, 60),
    },
    {
      label: 'Experience',
      value: toTen(experience, 30),
    },
    {
      label: 'Qualifications',
      value: toTen(qualifications, 10),
    },
  ]
}

export function jobSubtitle(job) {
  if (!job) return ''
  return [
    job.location,
    formatWorkType(job.work_type),
    formatJobType(job.job_type),
    formatExperienceRange(job.experience_min, job.experience_max),
  ]
    .filter((part) => part && part !== '—')
    .join(' · ')
}

function formatJobType(value) {
  const labels = {
    full_time: 'Full-time',
    part_time: 'Part-time',
    contract: 'Contract',
  }
  return labels[value] || null
}

function formatWorkType(value) {
  const labels = {
    onsite: 'On-site',
    hybrid: 'Hybrid',
    remote: 'Remote',
  }
  return labels[value] || null
}

function formatExperienceRange(min, max) {
  if (min == null && max == null) return null
  if (min != null && max != null) return `${min}–${max} YOE`
  if (min != null) return `${min}+ YOE`
  return `Up to ${max} YOE`
}
