import { useState } from 'react'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Panel, StatCard } from '../../components/ui/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { cn } from '../../lib/cn'
import { ApplicationTimelinePanel } from './ApplicationTimelinePanel'
import { useOrgSettings } from '../org-admin/OrgSettingsContext'
import {
  candidateInitials,
  candidateName,
  fitLabel,
  fitTone,
  resolveMatchScore,
  scoreBreakdownCards,
} from './applicationFields'

function skillLabel(item) {
  if (typeof item === 'string') return item
  if (item && typeof item === 'object' && typeof item.skill === 'string') return item.skill
  return String(item ?? '')
}

function normalizeSkillList(items) {
  return (Array.isArray(items) ? items : []).map(skillLabel).filter(Boolean)
}

function CoverageBar({ label, matched, total, tone }) {
  const pct = total > 0 ? Math.round((matched / total) * 100) : 0
  const fill =
    tone === 'success'
      ? 'bg-success'
      : tone === 'warning'
        ? 'bg-warning'
        : 'bg-primary'

  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-baseline justify-between gap-sm mb-xs">
        <p className="font-label-md text-label-md text-on-surface-variant tracking-wide">{label}</p>
        <p className="text-body-sm font-medium text-on-surface">
          {matched}/{total}
          <span className="text-on-surface-variant font-normal"> · {pct}%</span>
        </p>
      </div>
      <div className="h-1.5 rounded-full bg-surface-container-high overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', fill)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function SkillGroup({ title, matched, missing }) {
  return (
    <div className="space-y-sm">
      <p className="font-label-md text-label-md text-on-surface">{title}</p>
      <div className="grid sm:grid-cols-2 gap-sm">
        <div className="rounded-lg border border-success-container/60 bg-success-container/20 p-md">
          <p className="font-label-md text-label-md text-on-success-container mb-sm">
            Matched · {matched.length}
          </p>
          {matched.length > 0 ? (
            <div className="flex flex-wrap gap-xs">
              {matched.map((item) => (
                <Badge key={item} tone="success">
                  {item}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-body-sm text-on-surface-variant">None matched</p>
          )}
        </div>
        <div className="rounded-lg border border-error-container/60 bg-error-container/20 p-md">
          <p className="font-label-md text-label-md text-on-error-container mb-sm">
            Missing · {missing.length}
          </p>
          {missing.length > 0 ? (
            <div className="flex flex-wrap gap-xs">
              {missing.map((item) => (
                <Badge key={item} tone="danger">
                  {item}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-body-sm text-on-surface-variant">None missing</p>
          )}
        </div>
      </div>
    </div>
  )
}

function AnalysisList({ title, items, tone = 'neutral' }) {
  if (!items?.length) return null

  const box =
    tone === 'success'
      ? 'border-success-container/60 bg-success-container/20'
      : tone === 'danger'
        ? 'border-error-container/60 bg-error-container/20'
        : 'border-outline-variant/80 bg-surface-container-low/40'
  const heading =
    tone === 'success'
      ? 'text-on-success-container'
      : tone === 'danger'
        ? 'text-on-error-container'
        : 'text-on-surface-variant'

  return (
    <div className={`rounded-lg border p-md ${box}`}>
      <p className={`font-label-md text-label-md tracking-wide mb-sm ${heading}`}>{title}</p>
      <ul className="text-body-sm text-on-surface space-y-xs list-disc pl-md">
        {items.map((point) => (
          <li key={point} className="leading-relaxed">
            {point}
          </li>
        ))}
      </ul>
    </div>
  )
}

function CollapsibleSection({ title, count, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-lg border border-outline-variant/80 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-sm px-md py-sm text-left hover:bg-surface-container-low/60"
        aria-expanded={open}
      >
        <span className="font-label-md text-label-md text-on-surface tracking-wide">
          {title}
          {count != null ? (
            <span className="text-on-surface-variant font-normal"> · {count}</span>
          ) : null}
        </span>
        <span className="material-symbols-outlined text-[20px] text-on-surface-variant" aria-hidden>
          {open ? 'expand_less' : 'expand_more'}
        </span>
      </button>
      {open ? <div className="px-md pb-md space-y-sm">{children}</div> : null}
    </div>
  )
}

function SkillChipList({ title, items, tone = 'neutral', previewCount = 14 }) {
  const [expanded, setExpanded] = useState(false)
  const total = items?.length ?? 0

  if (!total) {
    return (
      <div className="rounded-xl border border-outline-variant/70 bg-surface-container-low/40 p-md">
        <div className="flex items-baseline justify-between gap-sm mb-sm">
          <p className="font-label-md text-label-md text-on-surface tracking-wide">{title}</p>
          <span className="text-label-md text-on-surface-variant">0</span>
        </div>
        <p className="text-body-sm text-on-surface-variant">None listed</p>
      </div>
    )
  }

  const hidden = total > previewCount
  const visible = expanded || !hidden ? items : items.slice(0, previewCount)

  return (
    <div className="rounded-xl border border-outline-variant/70 bg-surface-container-low/40 p-md">
      <div className="flex items-baseline justify-between gap-sm mb-sm">
        <p className="font-label-md text-label-md text-on-surface tracking-wide">{title}</p>
        <span className="text-label-md text-on-surface-variant tabular-nums">{total}</span>
      </div>
      <div className="flex flex-wrap gap-xs content-start">
        {visible.map((item) => (
          <Badge key={item} tone={tone} className="max-w-full truncate">
            {item}
          </Badge>
        ))}
      </div>
      {hidden ? (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-sm text-label-md text-primary hover:underline"
        >
          {expanded ? 'Show less' : `Show ${total - previewCount} more`}
        </button>
      ) : null}
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
  detail,
  loading,
  error,
  timeline = [],
  timelineLoading = false,
  timelineError = null,
  scheduleAction = null,
}) {
  const { fitLabels } = useOrgSettings()
  const score = resolveMatchScore(detail)
  const analysis = detail?.job_fit_analysis
  const parsed = detail?.parsed_resume
  const breakdownCards = scoreBreakdownCards(analysis)
  const tone = fitTone(score, fitLabels)
  const weakFit = tone === 'danger'

  const reasoning = Array.isArray(analysis?.reasoning) ? analysis.reasoning : []
  const strengths = Array.isArray(analysis?.strengths) ? analysis.strengths : []
  const concerns = Array.isArray(analysis?.concerns) ? analysis.concerns : []
  const hasNarrative = reasoning.length > 0 || strengths.length > 0 || concerns.length > 0
  const matchedMust = normalizeSkillList(analysis?.matched_skills?.must_have)
  const matchedGood = normalizeSkillList(analysis?.matched_skills?.good_to_have)
  const missingMust = normalizeSkillList(analysis?.missing_skills?.must_have)
  const missingGood = normalizeSkillList(analysis?.missing_skills?.good_to_have)
  const mustTotal = matchedMust.length + missingMust.length
  const goodTotal = matchedGood.length + missingGood.length
  const primarySkills = normalizeSkillList(parsed?.primary_skills)
  const secondarySkills = normalizeSkillList(parsed?.secondary_skills)
  const roles = parsed?.experience?.roles ?? []
  const education = parsed?.education_certificates ?? []

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
            <div className="flex flex-wrap items-center justify-between gap-sm mb-md">
              <div className="flex items-center gap-xs">
                <span className="material-symbols-outlined text-secondary text-[18px]">
                  auto_awesome
                </span>
                <span className="font-label-md text-label-md text-secondary tracking-wide">
                  AI match
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-sm">
                <span className="text-body-sm font-medium text-on-surface">
                  {fitLabel(score, fitLabels)}
                  {score != null ? ` · ${score.toFixed(1)}/10` : ''}
                </span>
                {analysis?.experience_match != null ? (
                  <span className="text-body-sm text-on-surface-variant">
                    Experience {analysis.experience_match ? 'match' : 'gap'}
                  </span>
                ) : null}
              </div>
            </div>

            {(mustTotal > 0 || goodTotal > 0) ? (
              <div className="flex flex-col sm:flex-row gap-md mb-md">
                {mustTotal > 0 ? (
                  <CoverageBar
                    label="Must-have"
                    matched={matchedMust.length}
                    total={mustTotal}
                    tone="success"
                  />
                ) : null}
                {goodTotal > 0 ? (
                  <CoverageBar
                    label="Nice-to-have"
                    matched={matchedGood.length}
                    total={goodTotal}
                    tone="info"
                  />
                ) : null}
              </div>
            ) : null}

            {hasNarrative ? (
              <div className="mb-md space-y-sm">
                {reasoning.length > 0 ? (
                  <AnalysisList title="Summary" items={reasoning} />
                ) : null}

                {strengths.length > 0 || concerns.length > 0 ? (
                  <CollapsibleSection
                    title="Strengths & concerns"
                    count={strengths.length + concerns.length}
                    defaultOpen={false}
                  >
                    <div className="grid sm:grid-cols-2 gap-sm">
                      <AnalysisList title="Strengths" items={strengths} tone="success" />
                      <AnalysisList title="Concerns" items={concerns} tone="danger" />
                    </div>
                  </CollapsibleSection>
                ) : null}
              </div>
            ) : (
              <p className="text-body-sm text-on-surface-variant mb-md">
                AI match analysis is not available yet. Use rerun fit after the parsing service is
                connected.
              </p>
            )}

            {(mustTotal > 0 || goodTotal > 0) ? (
              <CollapsibleSection
                title="Skill coverage"
                count={mustTotal + goodTotal}
                defaultOpen={weakFit && missingMust.length > 0}
              >
                <SkillGroup title="Must-have" matched={matchedMust} missing={missingMust} />
                <SkillGroup title="Nice-to-have" matched={matchedGood} missing={missingGood} />
              </CollapsibleSection>
            ) : null}
          </Panel>

          <Panel title="Experience timeline">
            <ExperienceTimeline roles={roles} />
          </Panel>

          <Panel title="Resume skills">
            <div className="grid md:grid-cols-2 gap-md items-start">
              <SkillChipList title="Primary" items={primarySkills} tone="info" previewCount={12} />
              <SkillChipList
                title="Secondary"
                items={secondarySkills}
                tone="neutral"
                previewCount={12}
              />
            </div>
          </Panel>
        </div>

        <div className="space-y-lg lg:sticky lg:top-md lg:self-start">
          <ApplicationTimelinePanel
            events={timeline}
            source={detail.source}
            loading={timelineLoading}
            error={timelineError}
            scheduleAction={scheduleAction}
          />

          <Panel title="Candidate">
            <div className="flex items-start gap-md">
              <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-label-md shrink-0">
                {candidateInitials(detail)}
              </div>
              <div className="min-w-0 space-y-xs">
                <p className="text-body-sm font-medium text-on-surface">{candidateName(detail)}</p>
                <p className="text-label-md text-on-surface-variant break-all">
                  {detail.email || 'No email'}
                </p>
                <p className="text-label-md text-on-surface-variant">
                  {[detail.phone || null, detail.candidate_yoe != null ? `${detail.candidate_yoe} YOE` : null]
                    .filter(Boolean)
                    .join(' · ') || 'No phone'}
                </p>
              </div>
            </div>

            <div className="mt-md pt-md border-t border-outline-variant">
              <p className="font-label-md text-label-md text-on-surface-variant tracking-wide mb-sm">
                Education
              </p>
              {education.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant">No education extracted.</p>
              ) : (
                <ul className="space-y-sm">
                  {education.map((item) => (
                    <li key={`${item.name}-${item.year}`} className="text-body-sm">
                      <p className="font-medium text-on-surface">{item.name}</p>
                      <p className="text-label-md text-on-surface-variant">
                        {[item.issuer, item.year, item.type].filter(Boolean).join(' · ')}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
