export function CandidateJobSummarySidebar({ job, onApply }) {
  const formatBadge = (str) =>
    str ? str.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()) : ''

  return (
    <div className="space-y-lg">
      <div className="sticky top-24 rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-lg shadow-lift space-y-md">
        <h3 className="text-headline-sm font-semibold text-on-surface">Job Summary</h3>

        <div className="space-y-sm text-body-sm">
          <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
            <span className="text-on-surface-variant">Company</span>
            <span className="font-medium text-on-surface">{job.organization_name || 'EZScreen Partner'}</span>
          </div>
          <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
            <span className="text-on-surface-variant">Location</span>
            <span className="font-medium text-on-surface">{job.location || 'Flexible'}</span>
          </div>
          <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
            <span className="text-on-surface-variant">Work Mode</span>
            <span className="font-medium text-on-surface">{formatBadge(job.work_type) || 'N/A'}</span>
          </div>
          <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
            <span className="text-on-surface-variant">Employment Type</span>
            <span className="font-medium text-on-surface">{formatBadge(job.job_type) || 'N/A'}</span>
          </div>
          <div className="flex items-center justify-between border-b border-outline-variant/50 pb-xs">
            <span className="text-on-surface-variant">Experience</span>
            <span className="font-medium text-on-surface">
              {job.experience_min ?? 0} - {job.experience_max ?? 'Any'} Years
            </span>
          </div>
          <div className="flex items-center justify-between pt-xs">
            <span className="text-on-surface-variant">Posted Date</span>
            <span className="font-medium text-on-surface">
              {job.published_at ? new Date(job.published_at).toLocaleDateString() : 'Recently'}
            </span>
          </div>
        </div>

        {/* Apply CTA Button */}
        <button
          type="button"
          onClick={onApply}
          className="w-full inline-flex items-center justify-center gap-xs rounded-xl bg-primary px-lg py-sm text-body-md font-semibold text-on-primary shadow-soft hover:bg-primary/90 transition-colors"
        >
          <span>Apply for this Role</span>
        </button>
      </div>
    </div>
  )
}
