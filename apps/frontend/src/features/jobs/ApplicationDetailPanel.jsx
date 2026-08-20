import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Panel, StatCard } from '../../components/ui/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { cn } from '../../lib/cn'
import { useOrgSettings } from '../org-admin/OrgSettingsContext'
import {
  candidateInitials,
  candidateName,
  fitLabel,
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
  detail,
  loading,
  error,
}) {
  const { fitLabels } = useOrgSettings()
  const score = resolveMatchScore(detail)
  const analysis = detail?.job_fit_analysis
  const parsed = detail?.parsed_resume
  const breakdownCards = scoreBreakdownCards(analysis)

  const reasoning = Array.isArray(analysis?.reasoning) ? analysis.reasoning : []
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

            {reasoning.length > 0 ? (
              <div className="mb-md">
                <p className="font-label-md text-label-md text-on-surface-variant tracking-wide mb-sm">
                  Summary
                </p>
                <ul className="text-body-sm text-on-surface space-y-xs list-disc pl-md">
                  {reasoning.map((point) => (
                    <li key={point} className="leading-relaxed">
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-body-sm text-on-surface-variant mb-md">
                AI match analysis is not available yet. Use rerun fit after the parsing service is
                connected.
              </p>
            )}

            {(mustTotal > 0 || goodTotal > 0) ? (
              <div className="space-y-md pt-md border-t border-outline-variant">
                <SkillGroup title="Must-have" matched={matchedMust} missing={missingMust} />
                <SkillGroup title="Nice-to-have" matched={matchedGood} missing={missingGood} />
              </div>
            ) : null}
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
    </div>
  )
}
