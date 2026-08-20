export function numericScore(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export function isPendingApplicant(applicant) {
  return numericScore(applicant?.resume_score) == null
}

export function applicantScore(applicant) {
  return numericScore(applicant?.resume_score)
}

export function fitLabel(score) {
  if (typeof score !== 'number') return 'Pending'
  if (score >= 8) return 'Strong'
  if (score >= 6) return 'Moderate'
  return 'Weak'
}

export function fitTone(score) {
  if (typeof score !== 'number') return 'neutral'
  if (score >= 8) return 'success'
  if (score >= 6) return 'warning'
  return 'danger'
}

export function fitBorderClass(score) {
  if (typeof score !== 'number') return 'border-l-outline-variant'
  if (score >= 8) return 'border-l-emerald-500'
  if (score >= 6) return 'border-l-amber-500'
  return 'border-l-red-400'
}

export function scoreTextClass(score) {
  if (typeof score !== 'number') return 'text-on-surface-variant'
  if (score >= 8) return 'text-emerald-800'
  if (score >= 6) return 'text-amber-800'
  return 'text-red-700'
}

export function matchesFitFilter(applicant, filter) {
  const score = applicantScore(applicant)
  if (filter === 'all') return true
  if (filter === 'pending') return score == null
  if (filter === 'screened') return score != null
  if (score == null) return false
  if (filter === 'strong') return score >= 8
  if (filter === 'moderate') return score >= 6 && score < 8
  if (filter === 'weak') return score < 6
  return true
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
  scored: 'Scored',
  interview_scheduled: 'Interview scheduled',
  interview_completed: 'Interview completed',
  shortlisted_l2: 'Shortlisted for L2',
  rejected: 'Rejected',
}

export function formatApplicationStatus(status) {
  if (!status) return '—'
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
