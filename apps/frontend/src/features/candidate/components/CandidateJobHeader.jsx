export function CandidateJobHeader({ job }) {
  const formatBadge = (str) =>
    str ? str.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()) : ''

  return (
    <div className="rounded-2xl bg-surface-container-lowest border border-outline-variant/70 p-lg md:p-xl shadow-lift mb-xl">
      <div className="flex items-center gap-sm mb-sm">
        {job.organization_logo_url ? (
          <img
            src={job.organization_logo_url}
            alt={job.organization_name || 'Company logo'}
            className="w-10 h-10 rounded-xl object-contain bg-surface border border-outline-variant/60 p-xs"
          />
        ) : (
          <div className="w-10 h-10 rounded-xl bg-primary-container text-on-primary-container font-headline-sm flex items-center justify-center">
            {(job.organization_name || 'E').charAt(0).toUpperCase()}
          </div>
        )}
        <span className="text-body-md font-semibold text-on-surface">
          {job.organization_name || 'EZScreen Partner'}
        </span>
      </div>

      <h1 className="text-headline-md font-bold text-on-surface tracking-tight">
        {job.title || 'Untitled Position'}
      </h1>

      {/* Quick Metadata badges */}
      <div className="flex flex-wrap items-center gap-sm mt-md text-body-sm text-on-surface-variant">
        {job.location ? (
          <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
            <span className="material-symbols-outlined text-primary text-[18px]">location_on</span>
            {job.location}
          </span>
        ) : null}

        {job.work_type ? (
          <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
            <span className="material-symbols-outlined text-primary text-[18px]">laptop_mac</span>
            {formatBadge(job.work_type)}
          </span>
        ) : null}

        {job.job_type ? (
          <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
            <span className="material-symbols-outlined text-primary text-[18px]">schedule</span>
            {formatBadge(job.job_type)}
          </span>
        ) : null}

        {(job.experience_min !== null || job.experience_max !== null) ? (
          <span className="inline-flex items-center gap-xs rounded-lg bg-surface-container-low px-sm py-xs text-body-sm font-medium text-on-surface">
            <span className="material-symbols-outlined text-primary text-[18px]">badge</span>
            {job.experience_min ?? 0} - {job.experience_max ?? 'Any'} yrs exp
          </span>
        ) : null}
      </div>
    </div>
  )
}
