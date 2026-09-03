import { Link } from 'react-router-dom'

export function JobCard({ job }) {
  const formatBadge = (str) =>
    str ? str.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()) : ''

  const mustHaveSkills = extractSkillsList(job.skills)

  return (
    <div className="group flex flex-col justify-between rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-lg shadow-soft hover:shadow-lift hover:border-primary/50 transition-all duration-300">
      <div>
        <div className="flex items-start justify-between gap-sm mb-sm">
          <div>
            <h3 className="text-headline-sm font-semibold text-on-surface group-hover:text-primary transition-colors line-clamp-2">
              {job.title || 'Untitled Position'}
            </h3>
            {job.organization_name ? (
              <p className="text-label-md text-on-surface-variant font-medium mt-0.5">
                {job.organization_name}
              </p>
            ) : null}
          </div>
          {job.job_type ? (
            <span className="shrink-0 rounded-full bg-primary-container px-sm py-xs text-label-md font-medium text-on-primary-container">
              {formatBadge(job.job_type)}
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-xs text-body-sm text-on-surface-variant my-md">
          {job.location ? (
            <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-label-md">
              <span className="material-symbols-outlined text-[14px] text-primary">location_on</span>
              {job.location}
            </span>
          ) : null}

          {job.work_type ? (
            <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-label-md">
              <span className="material-symbols-outlined text-[14px] text-primary">laptop_mac</span>
              {formatBadge(job.work_type)}
            </span>
          ) : null}

          {(job.experience_min !== null || job.experience_max !== null) ? (
            <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-label-md">
              <span className="material-symbols-outlined text-[14px] text-primary">badge</span>
              {job.experience_min ?? 0} - {job.experience_max ?? 'Any'} yrs
            </span>
          ) : null}
        </div>

        {mustHaveSkills.length > 0 ? (
          <div className="mb-lg">
            <p className="text-label-md font-medium text-on-surface-variant mb-xs">Top Requirements:</p>
            <div className="flex flex-wrap gap-xs">
              {mustHaveSkills.slice(0, 4).map((s, idx) => (
                <span
                  key={idx}
                  className="rounded-md bg-surface-container border border-outline-variant/50 px-xs py-[2px] text-label-md text-on-surface"
                >
                  {s}
                </span>
              ))}
              {mustHaveSkills.length > 4 ? (
                <span className="rounded-md bg-surface-container-high px-xs py-[2px] text-label-md text-on-surface-variant">
                  +{mustHaveSkills.length - 4} more
                </span>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <div className="pt-md border-t border-outline-variant/40 flex items-center justify-between mt-auto">
        <span className="text-label-md text-on-surface-variant">
          {job.published_at
            ? `Posted ${new Date(job.published_at).toLocaleDateString()}`
            : 'Active role'}
        </span>
        <Link
          to={`/jobs/${job.id}`}
          className="inline-flex items-center gap-xs text-body-sm font-medium text-primary group-hover:translate-x-1 transition-transform"
        >
          <span>View Role</span>
          <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
        </Link>
      </div>
    </div>
  )
}

function extractSkillsList(skills) {
  if (!skills) return []
  if (typeof skills === 'string') {
    return skills.split(',').map((s) => s.trim()).filter(Boolean)
  }
  if (typeof skills === 'object') {
    const must = skills.must_have || []
    const items = must.map((m) => (typeof m === 'string' ? m : m.skill)).filter(Boolean)
    if (items.length > 0) return items
    const good = skills.good_to_have || []
    return good.map((g) => (typeof g === 'string' ? g : g.skill)).filter(Boolean)
  }
  return []
}
