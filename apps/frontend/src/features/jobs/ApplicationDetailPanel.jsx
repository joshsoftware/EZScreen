import { useState } from 'react'
import { toast } from 'sonner'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Panel, StatCard } from '../../components/ui/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { rerunJobFitRequest } from './api'
import {
  candidateInitials,
  candidateName,
  fitLabel,
  fitTone,
  formatApplicationStatus,
  resolveMatchScore,
  scoreBreakdownCards,
} from './applicationFields'

function SkillRow({ matchedLabel, matchedItems, matchedTone, missingLabel, missingItems, missingTone }) {
  return (
    <div className="flex flex-col gap-sm">
      <div className="flex flex-wrap items-start gap-md">
        <div className="min-w-0 flex-1">
          <p className="font-label-md text-label-md text-on-surface-variant mb-xs">{matchedLabel}</p>
          {matchedItems.length > 0 ? (
            <div className="flex flex-wrap gap-xs">
              {matchedItems.map((item) => (
                <Badge key={item} tone={matchedTone}>{item}</Badge>
              ))}
            </div>
          ) : (
            <p className="text-body-sm text-on-surface-variant">None</p>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-label-md text-label-md text-on-surface-variant mb-xs">{missingLabel}</p>
          {missingItems.length > 0 ? (
            <div className="flex flex-wrap gap-xs">
              {missingItems.map((item) => (
                <Badge key={item} tone={missingTone}>{item}</Badge>
              ))}
            </div>
          ) : (
            <p className="text-body-sm text-on-surface-variant">None</p>
          )}
        </div>
      </div>
    </div>
  )
}

function SkillList({ title, items, tone = 'neutral' }) {
  if (!items?.length) {
    return (
      <div>
        <p className="font-label-md text-label-md text-on-surface-variant mb-sm">{title}</p>
        <p className="text-body-sm text-on-surface-variant">None listed</p>
      </div>
    )
  }

  return (
    <div>
      <p className="font-label-md text-label-md text-on-surface-variant mb-sm">{title}</p>
      <div className="flex flex-wrap gap-xs">
        {items.map((item) => (
          <Badge key={item} tone={tone}>
            {item}
          </Badge>
        ))}
      </div>
    </div>
  )
}

function ExperienceTimeline({ roles }) {
  if (!roles?.length) {
    return <p className="text-body-sm text-on-surface-variant">No experience extracted.</p>
  }

  return (
    <div className="space-y-md border-l border-outline-variant pl-md">
      {roles.map((role) => {
        const period = [role.start_date, role.end_date || 'present'].filter(Boolean).join(' – ')
        return (
          <div key={`${role.title}-${role.company}-${period}`}>
            <p className="text-body-sm font-medium text-on-surface">
              {role.title}
              {role.company ? ` · ${role.company}` : ''}
            </p>
            <p className="text-label-md text-on-surface-variant">{period}</p>
            {Array.isArray(role.highlights) && role.highlights.length > 0 ? (
              <ul className="mt-xs text-body-sm text-on-surface-variant list-disc pl-md space-y-xs">
                {role.highlights.slice(0, 3).map((highlight) => (
                  <li key={highlight}>{highlight}</li>
                ))}
              </ul>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

export function ApplicationDetailPanel({
  jobId,
  detail,
  loading,
  error,
  onRerunComplete,
  showRaw = false,
  onToggleRaw,
}) {
  const [rerunning, setRerunning] = useState(false)
  const [localShowRaw, setLocalShowRaw] = useState(false)
  const rawVisible = onToggleRaw ? showRaw : localShowRaw
  const toggleRaw = onToggleRaw ?? (() => setLocalShowRaw((v) => !v))

  const score = resolveMatchScore(detail)
  const analysis = detail?.job_fit_analysis
  const parsed = detail?.parsed_resume
  const breakdownCards = scoreBreakdownCards(analysis)
  const canRerun = Boolean(detail?.parsed_resume) && !rerunning

  const reasoning = Array.isArray(analysis?.reasoning) ? analysis.reasoning : []
  const matchedMust = analysis?.matched_skills?.must_have ?? []
  const matchedGood = analysis?.matched_skills?.good_to_have ?? []
  const missingMust = analysis?.missing_skills?.must_have ?? []
  const missingGood = analysis?.missing_skills?.good_to_have ?? []
  const primarySkills = parsed?.primary_skills ?? []
  const secondarySkills = parsed?.secondary_skills ?? []
  const roles = parsed?.experience?.roles ?? []
  const education = parsed?.education_certificates ?? []

  async function onRerun() {
    if (!detail || rerunning) return
    setRerunning(true)
    try {
      await rerunJobFitRequest(jobId, detail.id)
      toast.success('Job-fit recalculated')
      if (onRerunComplete) {
        await onRerunComplete()
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rerun fit')
    } finally {
      setRerunning(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-lg">
        <Skeleton className="h-24 rounded-xl" />
        <div className="grid md:grid-cols-4 gap-md">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (error) {
    return <Alert>{error}</Alert>
  }

  if (!detail) {
    return null
  }

  return (
    <div className="space-y-lg">
      {breakdownCards.length > 0 ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-md">
          {breakdownCards.map((card) => (
            <StatCard key={card.label} label={card.label} value={card.value} />
          ))}
        </div>
      ) : null}

      <div className="grid lg:grid-cols-3 gap-lg">
        <div className="lg:col-span-2 space-y-lg">
          <Panel>
            <div className="flex items-center gap-xs mb-md">
              <span className="material-symbols-outlined text-secondary text-[18px]">
                auto_awesome
              </span>
              <span className="text-label-md text-secondary">AI Match Generated</span>
            </div>
            <div className="flex flex-wrap items-center gap-sm mb-md">
              <Badge tone={fitTone(score)}>{fitLabel(score)}</Badge>
              <Badge tone="info">{formatApplicationStatus(detail.status)}</Badge>
              {analysis?.experience_match != null ? (
                <Badge tone={analysis.experience_match ? 'success' : 'warning'}>
                  Experience match: {analysis.experience_match ? 'Yes' : 'No'}
                </Badge>
              ) : null}
            </div>
            {reasoning.length > 0 ? (
              <ul className="text-body-sm text-on-surface space-y-xs list-disc pl-md mb-md">
                {reasoning.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            ) : (
              <p className="text-body-sm text-on-surface-variant mb-md">
                AI match analysis is not available yet. Use rerun fit after the parsing service is
                connected.
              </p>
            )}
            <div className="space-y-md">
              <hr className="border-outline-variant" />
              <SkillRow
                matchedLabel={`Matched must-have (${matchedMust.length})`}
                matchedItems={matchedMust}
                matchedTone="success"
                missingLabel={`Missing must-have (${missingMust.length})`}
                missingItems={missingMust}
                missingTone="danger"
              />
              <hr className="border-outline-variant" />
              <SkillRow
                matchedLabel={`Matched nice-to-have (${matchedGood.length})`}
                matchedItems={matchedGood}
                matchedTone="info"
                missingLabel={`Missing nice-to-have (${missingGood.length})`}
                missingItems={missingGood}
                missingTone="warning"
              />
            </div>
          </Panel>

          <Panel title="Experience timeline">
            <ExperienceTimeline roles={roles} />
          </Panel>

          <Panel title="Resume skills">
            <div className="grid md:grid-cols-2 gap-md">
              <SkillList title="Primary skills" items={primarySkills} tone="info" />
              <SkillList title="Secondary skills" items={secondarySkills} tone="neutral" />
            </div>
          </Panel>
        </div>

        <div className="space-y-lg">
          <Panel title="Candidate">
            <div className="flex items-center gap-md mb-md">
              <div className="w-12 h-12 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-headline-sm">
                {candidateInitials(detail)}
              </div>
              <div>
                <p className="text-body-sm font-medium text-on-surface">{candidateName(detail)}</p>
                <p className="text-body-sm text-on-surface-variant">{detail.email || 'No email'}</p>
                <p className="text-body-sm text-on-surface-variant">{detail.phone || 'No phone'}</p>
              </div>
            </div>
            <p className="text-body-sm text-on-surface-variant">
              YOE: {detail.candidate_yoe ?? '—'}
            </p>
          </Panel>

          <Panel title="Education">
            {education.length === 0 ? (
              <p className="text-body-sm text-on-surface-variant">No education extracted.</p>
            ) : (
              <ul className="space-y-sm">
                {education.map((item) => (
                  <li key={`${item.name}-${item.year}`} className="text-body-sm">
                    <p className="font-medium text-on-surface">{item.name}</p>
                    <p className="text-on-surface-variant">
                      {[item.issuer, item.year, item.type].filter(Boolean).join(' · ')}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

        </div>
      </div>

      {rawVisible ? (
        <Panel title="Raw AI data">
          <div className="grid lg:grid-cols-2 gap-md">
            <div>
              <p className="font-label-md text-label-md text-on-surface-variant uppercase mb-xs">
                Job fit analysis
              </p>
              <pre className="text-mono-sm whitespace-pre-wrap break-words rounded-DEFAULT border border-outline-variant bg-surface p-md max-h-80 overflow-auto">
                {JSON.stringify(analysis, null, 2)}
              </pre>
            </div>
            <div>
              <p className="font-label-md text-label-md text-on-surface-variant uppercase mb-xs">
                Parsed resume
              </p>
              <pre className="text-mono-sm whitespace-pre-wrap break-words rounded-DEFAULT border border-outline-variant bg-surface p-md max-h-80 overflow-auto">
                {JSON.stringify(parsed, null, 2)}
              </pre>
            </div>
          </div>
        </Panel>
      ) : null}
    </div>
  )
}
