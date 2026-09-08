import { JOB_TYPES, WORK_TYPES } from '../constants'

export function JobFilters({
  searchInput,
  onSearchInputChange,
  onSearchSubmit,
  jobType,
  onJobTypeChange,
  workType,
  onWorkTypeChange,
  onClearFilters,
  hasActiveFilters,
}) {
  return (
    <div className="mt-lg border-t border-outline-variant/50 pt-md space-y-md">
      <form onSubmit={onSearchSubmit} className="flex flex-col sm:flex-row gap-sm">
        <div className="relative flex-1">
          <span className="material-symbols-outlined absolute left-md top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]">
            search
          </span>
          <input
            type="text"
            value={searchInput}
            onChange={(e) => onSearchInputChange(e.target.value)}
            placeholder="Search by job title, location, or required skill..."
            className="w-full rounded-xl border border-outline-variant/80 bg-surface pl-11 pr-md py-sm text-body-sm text-on-surface placeholder:text-on-surface-variant/60 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
          />
        </div>
        <button
          type="submit"
          className="inline-flex items-center justify-center gap-xs rounded-xl bg-primary px-lg py-sm text-body-sm font-medium text-on-primary shadow-soft hover:bg-primary/90 transition-colors"
        >
          <span>Search</span>
        </button>
      </form>

      <div className="flex flex-wrap items-center gap-md">
        {/* Job Type Dropdown */}
        <div className="flex items-center gap-xs">
          <label htmlFor="job-type-filter" className="text-label-md font-medium text-on-surface-variant shrink-0">
            Job Type:
          </label>
          <select
            id="job-type-filter"
            value={jobType}
            onChange={(e) => onJobTypeChange(e.target.value)}
            className="rounded-xl border border-outline-variant/80 bg-surface px-md py-xs text-body-sm text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 cursor-pointer"
          >
            {JOB_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Work Type Dropdown */}
        <div className="flex items-center gap-xs">
          <label htmlFor="work-type-filter" className="text-label-md font-medium text-on-surface-variant shrink-0">
            Work Mode:
          </label>
          <select
            id="work-type-filter"
            value={workType}
            onChange={(e) => onWorkTypeChange(e.target.value)}
            className="rounded-xl border border-outline-variant/80 bg-surface px-md py-xs text-body-sm text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 cursor-pointer"
          >
            {WORK_TYPES.map((w) => (
              <option key={w.value} value={w.value}>
                {w.label}
              </option>
            ))}
          </select>
        </div>

        {hasActiveFilters && (
          <button
            type="button"
            onClick={onClearFilters}
            className="inline-flex items-center gap-xs text-label-md font-medium text-primary hover:underline transition-all"
          >
            <span className="material-symbols-outlined text-[16px]">restart_alt</span>
            <span>Reset Filters</span>
          </button>
        )}
      </div>
    </div>
  )
}
