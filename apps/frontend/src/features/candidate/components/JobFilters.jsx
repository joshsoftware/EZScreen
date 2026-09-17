import { Button } from '../../../components/ui/Button'
import { Input, Select } from '../../../components/ui/Input'
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
    <div className="flex flex-wrap items-end gap-sm mb-md">
      <form onSubmit={onSearchSubmit} className="flex flex-wrap items-end gap-sm flex-1 min-w-[220px]">
        <div className="flex-1 min-w-[180px] max-w-sm">
          <Input
            id="candidate-job-search"
            label="Search"
            value={searchInput}
            onChange={(e) => onSearchInputChange(e.target.value)}
            placeholder="Title, location, or skill…"
            className="h-10"
          />
        </div>
        <Button type="submit" size="sm" icon="search">
          Search
        </Button>
      </form>

      <div className="w-[160px]">
        <Select
          id="job-type-filter"
          label="Job type"
          value={jobType}
          onChange={(e) => onJobTypeChange(e.target.value)}
          className="h-10"
        >
          {JOB_TYPES.map((t) => (
            <option key={t.value || 'all-types'} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="w-[160px]">
        <Select
          id="work-type-filter"
          label="Work mode"
          value={workType}
          onChange={(e) => onWorkTypeChange(e.target.value)}
          className="h-10"
        >
          {WORK_TYPES.map((w) => (
            <option key={w.value || 'all-modes'} value={w.value}>
              {w.label}
            </option>
          ))}
        </Select>
      </div>

      {hasActiveFilters ? (
        <Button type="button" variant="secondary" size="sm" icon="restart_alt" onClick={onClearFilters}>
          Reset
        </Button>
      ) : null}
    </div>
  )
}
