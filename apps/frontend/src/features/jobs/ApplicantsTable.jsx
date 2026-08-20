import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'
import { EmptyState } from '../../components/ui/EmptyState'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Alert } from '../../components/ui/Alert'
import {
  applicantScore,
  candidateName,
  fitBorderClass,
  fitLabel,
  fitTone,
  formatApplicationStatus,
  matchesFitFilter,
  scoreTextClass,
} from './applicationFields'
import { formatDate } from './jobFields'

const FIT_FILTERS = [
  { value: 'all', label: 'All fit levels' },
  { value: 'strong', label: 'Strong (8+)' },
  { value: 'moderate', label: 'Moderate (6–7.9)' },
  { value: 'weak', label: 'Weak (<6)' },
  { value: 'pending', label: 'Pending' },
  { value: 'screened', label: 'Scored' },
]

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
  const [query, setQuery] = useState('')

  const filteredApplicants = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return applicants.filter((applicant) => {
      if (!matchesFitFilter(applicant, fitFilter)) return false
      if (!needle) return true
      const haystack = [candidateName(applicant), applicant.email, applicant.phone]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [applicants, fitFilter, query])

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
              {FIT_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <Button variant="secondary" size="sm" loading={refreshing} onClick={onRefresh}>
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
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface border-b border-outline-variant">
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Candidate
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Score
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Fit
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  YOE
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Status
                </th>
                <th className="py-sm px-md font-label-md text-label-md text-on-surface-variant uppercase">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {filteredApplicants.map((applicant) => {
                const score = applicantScore(applicant)
                const name = candidateName(applicant)
                const href = `/org-admin/jobs/${jobId}/applicants/${applicant.id}`

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
                    className={`border-l-2 hover:bg-surface-container-low cursor-pointer ${fitBorderClass(score)}`}
                  >
                    <td className="py-md px-md text-body-sm">
                      <span className="font-medium text-secondary">{name}</span>
                      <p className="text-on-surface-variant">
                        {applicant.email || 'No email'}
                        {applicant.phone ? ` · ${applicant.phone}` : ''}
                      </p>
                    </td>
                    <td className={`py-md px-md text-body-sm font-medium ${scoreTextClass(score)}`}>
                      {score == null ? '—' : score.toFixed(1)}
                    </td>
                    <td className="py-md px-md">
                      <Badge tone={fitTone(score)}>{fitLabel(score)}</Badge>
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
