import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'
import { EmptyState } from '../../components/ui/EmptyState'
import { Spinner } from '../../components/ui/Spinner'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Alert } from '../../components/ui/Alert'
import { cn } from '../../lib/cn'
import { useOrgSettings } from '../org-admin/OrgSettingsContext'
import { interviewScoreTone } from './InterviewAnalysisPanel'
import {
  APPLICANT_TABS,
  applicantScore,
  applicantTab,
  candidateName,
  fitBorderClass,
  fitFilterOptions,
  fitLabel,
  fitTone,
  formatApplicationStatus,
  matchesFitFilter,
  numericScore,
  scoreTextClass,
} from './applicationFields'
import { formatDateTime } from './jobFields'
import { getReEvaluationStatusRequest, reEvaluateApplicationRequest } from './api'
import { useJobQueryClient } from './useJobQueries'
import { ApiError } from '../../lib/api/client'
import { toast } from 'sonner'

const HEADER = {
  candidate: { key: 'candidate', label: 'Candidate', hint: 'YOE' },
  fit: { key: 'fit', label: 'Fit', hint: 'status' },
  fitScore: { key: 'fit-score', label: 'Job analysis', hint: 'score' },
  interview: { key: 'interview', label: 'Interview', hint: 'score' },
  status: { key: 'status', label: 'Status' },
  rejectedStatus: { key: 'rejected-status', label: 'Rejected', hint: 'status' },
  interviewDate: { key: 'interview-date', label: 'Interview', hint: 'date' },
  uploaded: { key: 'uploaded', label: 'Uploaded', hint: 'date' },
  updated: { key: 'updated', label: 'Updated', hint: 'at' },
  actions: { key: 'actions', label: 'Actions' },
}

/** Columns per applicant list tab. */
const TAB_HEADERS = {
  interviews: [
    HEADER.candidate,
    HEADER.fit,
    HEADER.fitScore,
    HEADER.interview,
    HEADER.status,
    HEADER.interviewDate,
  ],
  scored: [HEADER.candidate, HEADER.fit, HEADER.fitScore, HEADER.uploaded, HEADER.actions],
  rejected: [
    HEADER.candidate,
    HEADER.fit,
    HEADER.fitScore,
    HEADER.interview,
    HEADER.rejectedStatus,
    HEADER.updated,
  ],
}

const TAB_EMPTY = {
  interviews: {
    icon: 'event',
    title: 'No screenings yet',
    description: 'Applicants appear here once a screening interview is scheduled.',
  },
  scored: {
    icon: 'person_search',
    title: 'No applicants awaiting a decision',
    description: 'Scored applicants who are not yet scheduled for screening appear here.',
  },
  rejected: {
    icon: 'person_off',
    title: 'No rejected applicants',
    description: 'Applicants you reject, before or after screening, appear here.',
  },
}

const TAB_ORDER_NOTE = {
  interviews: 'Latest interview first',
  scored: 'Oldest upload first',
  rejected: 'Latest update first',
}

function timeMs(value) {
  if (!value) return null
  const ms = new Date(value).getTime()
  return Number.isNaN(ms) ? null : ms
}

/** Sort by a date field; rows without one go last either way. */
function byDate(field, direction) {
  return (a, b) => {
    const left = timeMs(a[field])
    const right = timeMs(b[field])
    if (left == null && right == null) return 0
    if (left == null) return 1
    if (right == null) return -1
    return direction === 'asc' ? left - right : right - left
  }
}

const TAB_SORT = {
  interviews: byDate('interview_scheduled_at', 'desc'),
  scored: byDate('created_at', 'asc'),
  rejected: byDate('updated_at', 'desc'),
}

function isApplicantTab(value) {
  return APPLICANT_TABS.some((tab) => tab.id === value)
}

function interviewScoreTextClass(score) {
  const tone = interviewScoreTone(score)
  if (tone === 'success') return 'text-emerald-800'
  if (tone === 'warning') return 'text-amber-800'
  if (tone === 'danger') return 'text-red-700'
  return 'text-on-surface-variant'
}
const REEVALUATION_POLL_INTERVAL_MS = 2000
const REEVALUATION_TIMEOUT_MS = 120000

function ApplicantTabs({ activeTab, counts, onChange }) {
  return (
    <div
      role="tablist"
      aria-label="Applicant lists"
      className="flex flex-wrap gap-xs border-b border-outline-variant/80"
    >
      {APPLICANT_TABS.map((tab) => {
        const selected = tab.id === activeTab
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`applicant-tab-${tab.id}`}
            aria-selected={selected}
            aria-controls="applicant-tab-panel"
            onClick={() => onChange(tab.id)}
            className={cn(
              '-mb-px inline-flex items-center gap-xs border-b-2 px-md py-sm text-label-md font-label-md transition-colors',
              selected
                ? 'border-primary text-primary'
                : 'border-transparent text-on-surface-variant hover:text-on-surface',
            )}
          >
            {tab.label}
            <span
              className={cn(
                'rounded-full px-xs text-label-sm tabular-nums',
                selected
                  ? 'bg-primary-container text-on-primary-container'
                  : 'bg-surface-container-high text-on-surface-variant',
              )}
            >
              {counts[tab.id] ?? 0}
            </span>
          </button>
        )
      })}
    </div>
  )
}

function ApplicantsTableShell({ headers, children }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-outline-variant/80 bg-surface-container-lowest/60">
      <table className="w-full text-left">
        <thead>
          <tr className="bg-surface-container-low/60 border-b border-outline-variant/80">
            {headers.map((header) => (
              <th key={header.key} className="ez-table-head whitespace-nowrap">
                <span className="block">{header.label}</span>
                {header.hint ? <span className="block font-normal">{header.hint}</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-outline-variant/70">{children}</tbody>
      </table>
    </div>
  )
}

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
  processingRemaining = 0,
}) {
  const navigate = useNavigate()
  const { fitLabels } = useOrgSettings()
  const [query, setQuery] = useState('')
  const [reevaluatingId, setReevaluatingId] = useState(null)
  const [reevaluationStartedAt, setReevaluationStartedAt] = useState(null)
  const pollInFlightRef = useRef(false)
  const onRefreshRef = useRef(onRefresh)
  const { invalidateApplication } = useJobQueryClient()
  const invalidateApplicationRef = useRef(invalidateApplication)
  invalidateApplicationRef.current = invalidateApplication
  onRefreshRef.current = onRefresh
  const filterOptions = fitFilterOptions(fitLabels)
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const activeTab = isApplicantTab(requestedTab) ? requestedTab : 'interviews'
  const headers = TAB_HEADERS[activeTab]
  const statusLabel = (applicant) =>
    formatApplicationStatus(applicant.status, applicant.source, undefined, applicant.screening_status)

  const tabCounts = useMemo(() => {
    const counts = Object.fromEntries(APPLICANT_TABS.map((tab) => [tab.id, 0]))
    applicants.forEach((applicant) => {
      counts[applicantTab(applicant)] += 1
    })
    return counts
  }, [applicants])

  const tabApplicants = useMemo(
    () => applicants.filter((applicant) => applicantTab(applicant) === activeTab),
    [applicants, activeTab],
  )

  const statusOptions = useMemo(
    () => [...new Set(tabApplicants.map(statusLabel))].sort(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tabApplicants],
  )
  // Scored-tab applicants all share one status, so the filter only helps elsewhere.
  const showStatusFilter = activeTab !== 'scored'

  function selectTab(tabId) {
    setStatusFilter('all')
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('tab', tabId)
        return next
      },
      { replace: true },
    )
  }

  // New uploads and the "Awaiting score" filter are only visible on the
  // Scored tab, so follow them there.
  const awaitingScore = processing || fitFilter === 'pending'
  useEffect(() => {
    if (awaitingScore && activeTab !== 'scored') selectTab('scored')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awaitingScore])

  const filteredApplicants = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const matching = tabApplicants.filter((applicant) => {
      if (!matchesFitFilter(applicant, fitFilter, fitLabels)) return false
      if (showStatusFilter && statusFilter !== 'all' && statusLabel(applicant) !== statusFilter) {
        return false
      }
      if (!needle) return true
      const haystack = [candidateName(applicant), applicant.email, applicant.phone]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
    return [...matching].sort(TAB_SORT[activeTab])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabApplicants, activeTab, fitFilter, fitLabels, query, statusFilter, showStatusFilter])

  useEffect(() => {
    if (!reevaluatingId || !reevaluationStartedAt) return undefined

    const poll = async () => {
      if (pollInFlightRef.current) return
      if (Date.now() - reevaluationStartedAt >= REEVALUATION_TIMEOUT_MS) {
        setReevaluatingId(null)
        setReevaluationStartedAt(null)
        toast.error('Resume re-evaluation is taking longer than expected')
        return
      }

      pollInFlightRef.current = true
      try {
        const pipeline = await getReEvaluationStatusRequest(jobId, reevaluatingId)
        if (pipeline?.status === 'failed') {
          setReevaluatingId(null)
          setReevaluationStartedAt(null)
          toast.error(`Resume re-evaluation failed: ${pipeline.error || 'Unknown error'}`)
          return
        }
        if (pipeline?.status === 'completed') {
          // Also drop this applicant's cached profile (and timeline), or
          // opening it shows the pre-evaluation analysis until a refresh.
          await invalidateApplicationRef.current(reevaluatingId)
          await onRefreshRef.current?.()
          setReevaluatingId(null)
          setReevaluationStartedAt(null)
          toast.success('Resume re-evaluation completed')
          return
        }
      } catch {
        // Continue polling so a transient status request failure does not stop tracking.
      } finally {
        pollInFlightRef.current = false
      }
    }

    void poll()
    const intervalId = window.setInterval(poll, REEVALUATION_POLL_INTERVAL_MS)
    return () => window.clearInterval(intervalId)
  }, [jobId, reevaluatingId, reevaluationStartedAt])

  async function onReevaluate(event, applicant) {
    event.stopPropagation()
    if (reevaluatingId) return
    setReevaluatingId(applicant.id)
    setReevaluationStartedAt(Date.now())
    try {
      await reEvaluateApplicationRequest(jobId, applicant.id)
      toast.success('Resume re-evaluation queued')
    } catch (err) {
      setReevaluatingId(null)
      setReevaluationStartedAt(null)
      toast.error(err instanceof ApiError ? err.message : 'Failed to re-evaluate resume')
    }
  }

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
    return <TableSkeleton rows={5} cols={7} />
  }

  const remainingLabel =
    processingRemaining > 0
      ? `${processingRemaining} resume${processingRemaining === 1 ? '' : 's'} remaining`
      : 'Queued files are being parsed'

  if (applicants.length === 0 && processing) {
    return (
      <ApplicantsTableShell headers={TAB_HEADERS.scored}>
        <tr>
          <td colSpan={TAB_HEADERS.scored.length} className="py-2xl px-md">
            <div
              className="flex flex-col items-center justify-center gap-sm text-center"
              role="status"
              aria-live="polite"
            >
              <Spinner className="h-8 w-8 text-primary" />
              <p className="font-medium text-on-surface">Processing resumes</p>
              <p className="text-body-sm text-on-surface-variant max-w-sm">
                {remainingLabel}. New applicants will appear here as each file finishes.
              </p>
            </div>
          </td>
        </tr>
      </ApplicantsTableShell>
    )
  }

  if (applicants.length === 0) {
    return (
      <EmptyState
        icon="person_search"
        title="No applicants yet"
        description="Upload resumes for this job to start screening candidates."
      />
    )
  }

  const showProcessingRow = processing && activeTab === 'scored'
  const emptyTab = TAB_EMPTY[activeTab]

  return (
    <div className="space-y-md">
      <ApplicantTabs activeTab={activeTab} counts={tabCounts} onChange={selectTab} />

      <div className="flex flex-wrap items-end justify-between gap-sm">
        <p className="text-body-sm text-on-surface-variant">
          {TAB_ORDER_NOTE[activeTab]} · {filteredApplicants.length} shown
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
          {showStatusFilter ? (
            <div className="w-[200px]">
              <Select
                id="applicant-status-filter"
                label="Status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="h-10"
              >
                <option value="all">All statuses</option>
                {statusOptions.map((label) => (
                  <option key={label} value={label}>
                    {label}
                  </option>
                ))}
              </Select>
            </div>
          ) : null}
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

      <div id="applicant-tab-panel" role="tabpanel" aria-labelledby={`applicant-tab-${activeTab}`}>
        {filteredApplicants.length === 0 && !showProcessingRow ? (
          tabApplicants.length === 0 ? (
            <EmptyState
              icon={emptyTab.icon}
              title={emptyTab.title}
              description={emptyTab.description}
            />
          ) : (
            <EmptyState
              icon="filter_alt"
              title="No applicants match this filter"
              description="Try another fit level, clear search, or refresh after processing completes."
            />
          )
        ) : (
          <ApplicantsTableShell headers={headers}>
            {showProcessingRow ? (
              <tr className="bg-primary-container/20">
                <td colSpan={headers.length} className="py-md px-md">
                  <div
                    className="flex items-center justify-center gap-sm text-body-sm text-on-surface"
                    role="status"
                    aria-live="polite"
                  >
                    <Spinner className="h-5 w-5 text-primary" />
                    <span>
                      Processing resumes — {remainingLabel}. New applicants will appear as each
                      file finishes.
                    </span>
                  </div>
                </td>
              </tr>
            ) : null}
            {filteredApplicants.map((applicant) => {
              const score = applicantScore(applicant)
              const interviewScore = numericScore(applicant.interview_score)
              const name = candidateName(applicant)
              const contact = [applicant.email, applicant.phone].filter(Boolean).join(' · ')
              const href = `/org-admin/jobs/${jobId}/applicants/${applicant.id}`
              const initial = (name?.[0] || '?').toUpperCase()
              const yoe =
                applicant.candidate_yoe == null ? null : `${applicant.candidate_yoe} yrs`
  
              const cells = {
                candidate: (
                  <td key="candidate" className="py-md px-md text-body-sm">
                    <div className="flex items-center gap-sm">
                      <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-container text-label-md font-label-md text-on-primary-container">
                        {initial}
                      </span>
                      <div className="min-w-0">
                        <span className="flex max-w-[18rem] items-baseline gap-xs">
                          <span className="truncate font-medium text-on-surface" title={name}>
                            {name}
                          </span>
                          <span className="shrink-0 text-on-surface-variant tabular-nums">
                            · {yoe ?? 'YOE —'}
                          </span>
                        </span>
                        <p
                          className="max-w-[18rem] truncate text-on-surface-variant"
                          title={contact || undefined}
                        >
                          {applicant.email || 'No email'}
                          {applicant.phone ? ` · ${applicant.phone}` : ''}
                        </p>
                      </div>
                    </div>
                  </td>
                ),
                fit: (
                  <td key="fit" className="py-md px-md">
                    <Badge tone={fitTone(score, fitLabels)}>{fitLabel(score, fitLabels)}</Badge>
                  </td>
                ),
                'fit-score': (
                  <td
                    key="fit-score"
                    className={`py-md px-md text-body-sm font-medium ${scoreTextClass(score, fitLabels)}`}
                  >
                    {score == null ? '—' : score.toFixed(1)}
                  </td>
                ),
                interview: (
                  <td
                    key="interview"
                    className={`py-md px-md text-body-sm font-medium tabular-nums ${interviewScoreTextClass(interviewScore)}`}
                  >
                    {interviewScore == null ? '—' : interviewScore.toFixed(1)}
                  </td>
                ),
                status: (
                  <td key="status" className="py-md px-md text-body-sm text-on-surface-variant">
                    {statusLabel(applicant)}
                  </td>
                ),
                'rejected-status': (
                  <td key="rejected-status" className="py-md px-md">
                    <Badge tone="danger">{statusLabel(applicant)}</Badge>
                  </td>
                ),
                'interview-date': (
                  <td key="interview-date" className="py-md px-md text-body-sm text-on-surface-variant">
                    {formatDateTime(applicant.interview_scheduled_at)}
                  </td>
                ),
                uploaded: (
                  <td key="uploaded" className="py-md px-md text-body-sm text-on-surface-variant">
                    {formatDateTime(applicant.created_at)}
                  </td>
                ),
                updated: (
                  <td key="updated" className="py-md px-md text-body-sm text-on-surface-variant">
                    {formatDateTime(applicant.updated_at)}
                  </td>
                ),
                actions: (
                  <td key="actions" className="py-md px-md">
                    {score == null ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        icon="refresh"
                        loading={reevaluatingId === applicant.id}
                        onClick={(event) => onReevaluate(event, applicant)}
                      >
                        {reevaluatingId === applicant.id ? 'Evaluating…' : 'Re-evaluate'}
                      </Button>
                    ) : null}
                  </td>
                ),
              }
  
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
                  {headers.map((header) => cells[header.key])}
                </tr>
              )
            })}
          </ApplicantsTableShell>
        )}
      </div>
    </div>
  )
}
