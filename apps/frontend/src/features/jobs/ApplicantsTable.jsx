import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'
import { EmptyState } from '../../components/ui/EmptyState'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Alert } from '../../components/ui/Alert'
import { useOrgSettings } from '../org-admin/OrgSettingsContext'
import {
  applicantScore,
  candidateName,
  fitBorderClass,
  fitFilterOptions,
  fitLabel,
  fitTone,
  formatApplicationStatus,
  matchesFitFilter,
  scoreTextClass,
} from './applicationFields'
import { formatDate } from './jobFields'

export function ApplicantsTable({
  jobId,
  applicants,
  loading,
  error,
  onRefresh,
  refreshing = false,
  fitFilter = 'all',
  onFitFilterChange,
  processing = false,
}) {
  const navigate = useNavigate()
  const { fitLabels } = useOrgSettings()
  const [query, setQuery] = useState('')
  const filterOptions = fitFilterOptions(fitLabels)

  const filteredApplicants = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return applicants.filter((applicant) => {
      if (!matchesFitFilter(applicant, fitFilter, fitLabels)) return false
      if (!needle) return true
      const haystack = [candidateName(applicant), applicant.email, applicant.phone]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [applicants, fitFilter, fitLabels, query])

  if (error) {
    return (
      <div className="space-y-md">
        <Alert>{error}</Alert>
        <Button variant="secondary" size="sm" loading={refreshing} onClick={onRefresh}>
          Try again
        </Button>
      </div>
    )
  }

  if (loading) {
    return <TableSkeleton rows={5} cols={6} />
  }

  if (applicants.length === 0) {
    return (
      <EmptyState
        icon="person_search"
        title={processing ? 'Processing resumes' : 'No applicants yet'}
        description={
          processing
            ? 'Queued files are being parsed. New applicants will appear here as processing completes.'
            : 'Upload resumes for this job to start screening candidates.'
        }
      />
    )
  }

  return (
    <div className="space-y-md">
      <div className="flex flex-wrap items-end justify-between gap-sm">
        <p className="text-body-sm text-on-surface-variant">
          Sorted by resume score · {filteredApplicants.length} shown
        </p>
        <div className="flex flex-wrap items-end gap-sm">
          <div className="w-[220px]">
            <Input
              id="applicant-search"
              label="Search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Name or email"
              className="h-10"
            />
          </div>
          <div className="w-[180px]">
            <Select
              id="applicant-fit-filter"
              label="Fit level"
              value={fitFilter}
              onChange={(event) => onFitFilterChange?.(event.target.value)}
              className="h-10"
            >
              {filterOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <Button
            variant="secondary"
            icon="refresh"
            loading={refreshing}
            onClick={onRefresh}
          >
            Refresh
          </Button>
        </div>
      </div>

      {filteredApplicants.length === 0 ? (
        <EmptyState
          icon="filter_alt"
          title="No applicants match this filter"
          description="Try another fit level, clear search, or refresh after processing completes."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-outline-variant/80 bg-surface-container-lowest/60">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-low/60 border-b border-outline-variant/80">
                <th className="ez-table-head">Candidate</th>
                <th className="ez-table-head">Score</th>
                <th className="ez-table-head">Fit</th>
                <th className="ez-table-head">YOE</th>
                <th className="ez-table-head">Status</th>
                <th className="ez-table-head">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/70">
              {filteredApplicants.map((applicant) => {
                const score = applicantScore(applicant)
                const name = candidateName(applicant)
                const href = `/org-admin/jobs/${jobId}/applicants/${applicant.id}`
                const initial = (name?.[0] || '?').toUpperCase()

                return (
                  <tr
                    key={applicant.id}
                    role="link"
                    tabIndex={0}
                    onClick={() => navigate(href)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        navigate(href)
                      }
                    }}
                    className={`ez-table-row cursor-pointer border-l-[3px] ${fitBorderClass(score, fitLabels)}`}
                  >
                    <td className="py-md px-md text-body-sm">
                      <div className="flex items-center gap-sm">
                        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-container text-label-md font-label-md text-on-primary-container">
                          {initial}
                        </span>
                        <div className="min-w-0">
                          <span className="font-medium text-on-surface">{name}</span>
                          <p className="text-on-surface-variant truncate">
                            {applicant.email || 'No email'}
                            {applicant.phone ? ` · ${applicant.phone}` : ''}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className={`py-md px-md text-body-sm font-medium ${scoreTextClass(score, fitLabels)}`}>
                      {score == null ? '—' : score.toFixed(1)}
                    </td>
                    <td className="py-md px-md">
                      <Badge tone={fitTone(score, fitLabels)}>
                        {fitLabel(score, fitLabels)}
                      </Badge>
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {applicant.candidate_yoe == null ? '—' : applicant.candidate_yoe}
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {formatApplicationStatus(applicant.status)}
                    </td>
                    <td className="py-md px-md text-body-sm text-on-surface-variant">
                      {formatDate(applicant.created_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
