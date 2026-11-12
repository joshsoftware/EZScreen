import { useState } from 'react'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Panel } from '../../components/ui/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { cn } from '../../lib/cn'
import { formatDateTime } from './jobFields'
import { ReEvaluateScreeningModal } from './ReEvaluateScreeningModal'

function asNumber(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function interviewScoreTone(score) {
  if (score == null) return 'neutral'
  if (score >= 7) return 'success'
  if (score >= 5) return 'warning'
  return 'danger'
}

export function interviewDecisionLabel(score, evaluatedCount = null) {
  if (score == null) return 'Awaiting score'
  // Nothing was assessed (silent / left / skipped everything): a 0 isn't a verdict.
  if (evaluatedCount === 0) return 'No answers scored'
  if (score >= 7) return 'Strong fit'
  if (score >= 5) return 'Borderline'
  return 'Not a strong fit'
}

/** Pull overall score + decision label from a GET /analysis payload. */
export function interviewAnalysisHeader(analysis) {
  const summary =
    analysis?.analysis_result?.final_summary &&
    typeof analysis.analysis_result.final_summary === 'object'
      ? analysis.analysis_result.final_summary
      : null
  const overall = asNumber(summary?.overall_score)
  if (overall == null && !summary) return null
  const evaluations = analysis?.analysis_result?.evaluations
  return {
    overall,
    label: interviewDecisionLabel(overall, Array.isArray(evaluations) ? evaluations.length : null),
    tone: interviewScoreTone(overall),
  }
}

// Same weights as the screening summary. An unasked category gives its
// weight to Must-have, matching calculate_final_weighted_score.
const SCREENING_CATEGORIES = [
  { key: 'must_have_matched', label: 'Must-have', field: 'raw_must_have_score', weight: 60 },
  { key: 'experience_domain', label: 'Domain', field: 'raw_domain_expertise_score', weight: 20 },
  { key: 'good_to_have', label: 'Good to have', field: 'raw_good_to_have_score', weight: 10 },
  { key: 'lacking_skill', label: 'Skill gaps', field: 'raw_lacking_skill_score', weight: 10 },
]

function formatShare(percent) {
  if (percent == null || !Number.isFinite(percent)) return '—'
  const rounded = Math.round(percent * 10) / 10
  return Number.isInteger(rounded) ? `${rounded}%` : `${rounded.toFixed(1)}%`
}

function screeningCategoryBreakdown(summary, evaluations) {
  const counts = Object.fromEntries(SCREENING_CATEGORIES.map((item) => [item.key, 0]))
  for (const evaluation of evaluations) {
    const key = evaluation?.category
    if (key in counts) counts[key] += 1
  }
  const knowsWhatWasAsked = Object.values(counts).some((count) => count > 0)

  const weights = Object.fromEntries(SCREENING_CATEGORIES.map((item) => [item.key, item.weight]))
  if (knowsWhatWasAsked) {
    for (const item of SCREENING_CATEGORIES) {
      if (item.key === 'must_have_matched' || counts[item.key] > 0) continue
      weights.must_have_matched += weights[item.key]
      weights[item.key] = 0
    }
  }

  return SCREENING_CATEGORIES.flatMap((item) => {
    const value = asNumber(summary?.[item.field])
    const weight = weights[item.key]
    const asked = knowsWhatWasAsked ? counts[item.key] > 0 : weight > 0 && value != null
    if (value == null && !asked) return []
    const percent = weight > 0 && value != null ? (value / weight) * 100 : null
    return [{ label: item.label, value, weight, percent, asked }]
  })
}

function categoryLabel(category) {
  const map = {
    must_have_matched: 'Must-have',
    good_to_have: 'Good to have',
    experience_domain: 'Role & domain',
    lacking_skill: 'Skill gap',
  }
  return map[category] || String(category || 'Question').replaceAll('_', ' ')
}

function decisionBadgeLabel(decision) {
  if (!decision) return null
  return String(decision).replaceAll('_', ' ')
}

function recommendationLines(text) {
  if (!text || typeof text !== 'string') return []
  const trimmed = text.trim()
  if (!trimmed) return []
  const lines = trimmed
    .split('\n')
    .map((line) => line.replace(/^[•\-\*\s]+/, '').trim())
    .filter(Boolean)
  return lines.length > 0 ? lines : [trimmed]
}

function summaryRecommendationText(summary) {
  if (!summary || typeof summary !== 'object') return ''
  const primary = summary.final_recommendation
  if (typeof primary === 'string' && primary.trim()) return primary
  const fallback = summary.recommendation
  if (typeof fallback === 'string' && fallback.trim()) return fallback
  return ''
}

function FinalSummarySection({ summary, overall, lines, evaluated = null }) {
  if (!summary && lines.length === 0) return null

  return (
    <section className="rounded-xl border border-outline-variant/70 bg-surface-container-lowest/60 p-md space-y-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-sm">
        <p className="font-label-md text-label-md text-on-surface tracking-wide">
          Final summary
        </p>
        {overall != null ? (
          <p className="text-body-sm text-on-surface-variant">
            Overall ·{' '}
            <span className="font-medium text-on-surface tabular-nums">
              {overall.toFixed(1)} / 10
            </span>
            <span className="mx-xs">·</span>
            {interviewDecisionLabel(overall, evaluated)}
          </p>
        ) : null}
      </div>

      {lines.length === 1 ? (
        <p className="text-body-sm text-on-surface leading-relaxed whitespace-pre-wrap">
          {lines[0]}
        </p>
      ) : lines.length > 1 ? (
        <ul className="text-body-sm text-on-surface space-y-xs list-disc pl-md">
          {lines.map((point) => (
            <li key={point.slice(0, 80)} className="leading-relaxed">
              {point}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body-sm text-on-surface-variant italic">
          No written recommendation in the final summary.
        </p>
      )}
    </section>
  )
}

function KeywordInline({ found = [], missing = [] }) {
  const hasFound = found.length > 0
  const hasMissing = missing.length > 0
  if (!hasFound && !hasMissing) return null

  return (
    <p className="text-label-md text-on-surface-variant leading-relaxed">
      {hasFound ? (
        <>
          <span className="text-on-success-container font-medium">Covered</span>
          {': '}
          {found.join(', ')}
        </>
      ) : null}
      {hasFound && hasMissing ? <span className="mx-xs text-outline-variant">·</span> : null}
      {hasMissing ? (
        <>
          <span className="text-on-error-container font-medium">Missing</span>
          {': '}
          {missing.join(', ')}
        </>
      ) : null}
    </p>
  )
}

function SectionToggle({ title, count, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-t border-outline-variant/70 pt-md">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-sm text-left"
        aria-expanded={open}
      >
        <span className="font-label-md text-label-md text-on-surface tracking-wide">
          {title}
          {count != null ? (
            <span className="text-on-surface-variant font-normal"> · {count}</span>
          ) : null}
        </span>
        <span
          className="material-symbols-outlined text-[20px] text-on-surface-variant"
          aria-hidden
        >
          {open ? 'expand_less' : 'expand_more'}
        </span>
      </button>
      {open ? <div className="mt-sm space-y-sm">{children}</div> : null}
    </div>
  )
}

function EvaluationRow({ evaluation, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const score = asNumber(evaluation?.score)
  const followUps = Array.isArray(evaluation?.follow_ups) ? evaluation.follow_ups : []
  const bestFollowUp = followUps.reduce((best, item) => {
    const next = asNumber(item?.score)
    if (next == null) return best
    if (best == null || next > best) return next
    return best
  }, null)
  const tone = interviewScoreTone(score)

  return (
    <div className="border-b border-outline-variant/60 last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-md py-md text-left hover:bg-surface-container-low/40 -mx-xs px-xs rounded-lg"
        aria-expanded={open}
      >
        <div
          className={cn(
            'shrink-0 w-12 text-center rounded-lg py-xs tabular-nums',
            tone === 'success'
              ? 'bg-success-container/40 text-on-success-container'
              : tone === 'warning'
                ? 'bg-warning-container/40 text-on-warning-container'
                : tone === 'danger'
                  ? 'bg-error-container/40 text-on-error-container'
                  : 'bg-surface-container-high text-on-surface-variant',
          )}
        >
          <p className="font-headline-sm text-headline-sm leading-none">
            {score != null ? score.toFixed(1) : '—'}
          </p>
          <p className="text-[10px] uppercase tracking-wide mt-xs opacity-80">/10</p>
        </div>
        <div className="min-w-0 flex-1 space-y-xs">
          <div className="flex flex-wrap items-center gap-xs">
            <Badge tone="info">{categoryLabel(evaluation?.category)}</Badge>
            {evaluation?.decision ? (
              <span className="text-label-md text-on-surface-variant">
                {decisionBadgeLabel(evaluation.decision)}
              </span>
            ) : null}
            {bestFollowUp != null && bestFollowUp !== score ? (
              <span className="text-label-md text-on-surface-variant">
                Follow-up · {bestFollowUp.toFixed(1)}
              </span>
            ) : null}
          </div>
          <p className="text-body-sm font-medium text-on-surface leading-snug line-clamp-2">
            {evaluation?.question}
          </p>
          {!open && evaluation?.candidate_answer ? (
            <p className="text-body-sm text-on-surface-variant line-clamp-1">
              {evaluation.candidate_answer}
            </p>
          ) : null}
        </div>
        <span
          className="material-symbols-outlined text-[20px] text-on-surface-variant shrink-0 mt-xs"
          aria-hidden
        >
          {open ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {open ? (
        <div className="pb-md pl-[3.75rem] space-y-sm">
          {evaluation?.candidate_answer ? (
            <div>
              <p className="font-label-md text-label-md text-on-surface-variant mb-xs">Answer</p>
              <p className="text-body-sm text-on-surface whitespace-pre-wrap leading-relaxed">
                {evaluation.candidate_answer}
              </p>
            </div>
          ) : null}
          {evaluation?.feedback ? (
            <p className="text-body-sm text-on-surface-variant leading-relaxed">
              {evaluation.feedback}
            </p>
          ) : null}
          <KeywordInline
            found={evaluation?.keywords_found}
            missing={evaluation?.keywords_missing}
          />

          {followUps.map((followUp, index) => {
            const fuScore = asNumber(followUp?.score)
            return (
              <div
                key={`${evaluation?.question_id}-fu-${index}`}
                className="border-l-2 border-outline-variant pl-md space-y-xs"
              >
                <div className="flex flex-wrap items-center gap-xs">
                  <span className="font-label-md text-label-md text-on-surface">
                    Follow-up {index + 1}
                  </span>
                  {fuScore != null ? (
                    <Badge tone={interviewScoreTone(fuScore)}>{fuScore.toFixed(1)}</Badge>
                  ) : null}
                </div>
                {followUp?.follow_up_question ? (
                  <p className="text-body-sm text-on-surface leading-snug">
                    {followUp.follow_up_question}
                  </p>
                ) : null}
                {followUp?.follow_up_answer ? (
                  <p className="text-body-sm text-on-surface-variant whitespace-pre-wrap">
                    {followUp.follow_up_answer}
                  </p>
                ) : null}
                {followUp?.feedback ? (
                  <p className="text-body-sm text-on-surface-variant leading-relaxed">
                    {followUp.feedback}
                  </p>
                ) : null}
                <KeywordInline
                  found={followUp?.keywords_found}
                  missing={followUp?.keywords_missing}
                />
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

function ChatBubble({ side, children, muted = false }) {
  const isBot = side === 'left'
  return (
    <div className={cn('flex w-full', isBot ? 'justify-start' : 'justify-end')}>
      <div
        className={cn(
          'max-w-[85%] sm:max-w-[75%] rounded-2xl px-md py-sm text-body-sm leading-relaxed whitespace-pre-wrap',
          isBot
            ? 'rounded-bl-md bg-surface-container-high text-on-surface'
            : muted
              ? 'rounded-br-md bg-primary-container/40 text-on-surface-variant italic'
              : 'rounded-br-md bg-primary-container text-on-primary-container',
        )}
      >
        {children}
      </div>
    </div>
  )
}

export function TranscriptTurn({ turn }) {
  const type = turn?.interaction_type || 'turn'
  const followUps = Array.isArray(turn?.follow_ups) ? turn.follow_ups : []
  const typeLabel = String(type).replaceAll('_', ' ')
  const showEmptyCandidate =
    !turn?.candidate_answer &&
    (type === 'silence_prompt' || type === 'closing' || type === 'question')

  return (
    <div className="space-y-sm py-md border-b border-outline-variant/40 last:border-b-0">
      <div className="flex flex-wrap items-center gap-xs px-xs">
        <span className="text-label-md text-on-surface-variant capitalize">{typeLabel}</span>
      </div>

      {turn?.bot_speech ? <ChatBubble side="left">{turn.bot_speech}</ChatBubble> : null}

      {turn?.candidate_answer ? (
        <ChatBubble side="right">{turn.candidate_answer}</ChatBubble>
      ) : showEmptyCandidate ? (
        <ChatBubble side="right" muted>
          No answer
        </ChatBubble>
      ) : null}

      {followUps.map((fu, index) => (
        <div key={`t-fu-${index}`} className="space-y-sm">
          {fu?.bot_speech ? <ChatBubble side="left">{fu.bot_speech}</ChatBubble> : null}
          {fu?.candidate_answer ? (
            <ChatBubble side="right">{fu.candidate_answer}</ChatBubble>
          ) : fu?.bot_speech ? (
            <ChatBubble side="right" muted>
              No answer
            </ChatBubble>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function Scorecard({
  overall,
  tone,
  breakdown,
  planned,
  evaluated,
  silenceEnded,
  sessionStatus,
  summary,
  recordingUrl,
}) {
  const toneBox =
    tone === 'success'
      ? 'border-success-container/50 bg-success-container/15'
      : tone === 'warning'
        ? 'border-warning-container/50 bg-warning-container/15'
        : 'border-error-container/50 bg-error-container/15'

  return (
    <aside className={cn('rounded-xl border p-md space-y-md', toneBox)}>
      <div>
        <p className="font-label-md text-label-md text-on-surface-variant tracking-wide">
          Screening score
        </p>
        <p className="font-headline-md text-headline-md text-on-surface tabular-nums leading-none mt-xs">
          {overall != null ? overall.toFixed(1) : '—'}
          <span className="text-body-sm text-on-surface-variant font-normal"> / 10</span>
        </p>
        <p className="text-body-sm font-medium text-on-surface mt-sm">
          {interviewDecisionLabel(overall, evaluated)}
        </p>
      </div>

      <div className="flex flex-wrap gap-xs">
        {sessionStatus ? (
          <Badge tone="neutral">{String(sessionStatus).replaceAll('_', ' ')}</Badge>
        ) : null}
        {planned > 0 ? (
          <Badge tone="neutral">
            {evaluated}/{planned} evaluated
          </Badge>
        ) : null}
        {silenceEnded ? <Badge tone="warning">Ended early · silence</Badge> : null}
      </div>

      {summary?.total_score != null && summary?.max_possible_score != null ? (
        <p className="text-label-md text-on-surface-variant">
          Raw score · {asNumber(summary.total_score) ?? '—'} /{' '}
          {asNumber(summary.max_possible_score) ?? '—'}
        </p>
      ) : null}

      {breakdown.length > 0 ? (
        <div className="space-y-xs">
          <p className="font-label-md text-label-md text-on-surface-variant tracking-wide">
            Category totals
          </p>
          {breakdown.map((item) => (
            <div key={item.label} className="space-y-0.5">
              <div className="flex items-baseline justify-between gap-sm text-body-sm">
                <span className="text-on-surface-variant">{item.label}</span>
                <span className="font-medium text-on-surface tabular-nums">
                  {item.asked ? formatShare(item.percent) : 'Not asked'}
                </span>
              </div>
              {item.weight > 0 && item.value != null ? (
                <p className="text-label-md text-on-surface-variant tabular-nums">
                  Weight {item.weight} · {item.value.toFixed(1)} pts
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {recordingUrl ? (
        <div className="flex flex-col gap-xs pt-xs border-t border-outline-variant/50">
          <p className="font-label-md text-label-md text-on-surface-variant tracking-wide">
            Session recording
          </p>
          <video
            controls
            preload="metadata"
            src={recordingUrl}
            className="w-full rounded-lg bg-black"
          >
            Your browser cannot play this recording.
          </video>
          <a
            href={recordingUrl}
            target="_blank"
            rel="noreferrer"
            className="text-label-md text-primary hover:underline"
          >
            Open recording in a new tab
          </a>
        </div>
      ) : null}
    </aside>
  )
}

function scoreText(value) {
  const n = asNumber(value)
  return n == null ? '—' : `${n.toFixed(1)}/10`
}

/**
 * Every scoring of this screening, oldest first: the bot's original result,
 * then each HR re-evaluation with who, when, and the score it produced.
 */
function EvaluationHistory({ reEvaluations }) {
  const rows = [
    {
      key: 'original',
      label: 'Original screening',
      detail: 'Scored by the AI interviewer',
      score: reEvaluations[0]?.previous_overall_score,
    },
    ...reEvaluations.map((run, index) => {
      const edited = Array.isArray(run.edited_question_ids) ? run.edited_question_ids : []
      return {
        key: `${run.at}-${index}`,
        label: `Re-evaluation ${index + 1}`,
        detail: [
          `by ${run.by_name || 'HR'} on ${formatDateTime(run.at)}`,
          `before: ${scoreText(run.previous_overall_score)}`,
          edited.length ? `corrected Q${edited.join(', Q')}` : 'no answers corrected',
        ].join(' · '),
        score: run.overall_score,
      }
    }),
  ]

  return (
    <SectionToggle title="Evaluation history" count={rows.length} defaultOpen>
      <ol className="rounded-xl border border-outline-variant/70 divide-y divide-outline-variant/50">
        {rows.map((row, index) => (
          <li key={row.key} className="flex flex-wrap items-baseline justify-between gap-xs px-md py-sm">
            <div className="min-w-0">
              <p className="text-body-sm font-medium text-on-surface">
                {row.label}
                {index === rows.length - 1 ? (
                  <span className="ml-xs text-label-md font-normal text-primary">· current</span>
                ) : null}
              </p>
              <p className="text-label-md text-on-surface-variant">{row.detail}</p>
            </div>
            <span className="text-body-sm font-medium text-on-surface tabular-nums">
              {scoreText(row.score)}
            </span>
          </li>
        ))}
      </ol>
    </SectionToggle>
  )
}

/**
 * Post-screening AI analysis report for org-admin applicant detail.
 * Layout: sticky scorecard (left) + evidence (right) on lg+.
 */
export function InterviewAnalysisPanel({
  analysis,
  loading = false,
  error = null,
  visible = false,
  attemptNumber = 1,
  sessionId = null,
  onReEvaluated,
}) {
  const [showReEvaluate, setShowReEvaluate] = useState(false)
  if (!visible && !loading) return null
  // After a reschedule, name the attempt so it lines up with "Earlier screenings".
  const panelTitle =
    attemptNumber > 1 ? `Screening ${attemptNumber} · Analysis` : 'Screening analysis'

  if (loading) {
    return (
      <Panel title={panelTitle}>
        <div className="grid lg:grid-cols-[minmax(240px,280px)_minmax(0,1fr)] gap-md">
          <Skeleton className="h-56 rounded-xl" />
          <Skeleton className="h-56 rounded-xl" />
        </div>
      </Panel>
    )
  }

  if (error) {
    return (
      <Panel title={panelTitle}>
        <Alert>{error}</Alert>
      </Panel>
    )
  }

  if (!analysis) {
    return (
      <Panel title={panelTitle}>
        <p className="text-body-sm text-on-surface-variant rounded-xl border border-dashed border-outline-variant px-md py-lg text-center">
          Analysis is not available yet for this screening session.
        </p>
      </Panel>
    )
  }

  const summary =
    analysis.analysis_result?.final_summary &&
    typeof analysis.analysis_result.final_summary === 'object'
      ? analysis.analysis_result.final_summary
      : null
  const overall = asNumber(summary?.overall_score)
  const evaluations = Array.isArray(analysis.analysis_result?.evaluations)
    ? analysis.analysis_result.evaluations
    : []
  const transcript = Array.isArray(analysis.conversation_transcript)
    ? analysis.conversation_transcript
    : []
  const lines = recommendationLines(summaryRecommendationText(summary))
  const silenceEnded = transcript.some((t) => t?.interaction_type === 'silence_prompt')
  const planned = Number(analysis.questions_planned) || 0
  const evaluated = evaluations.length
  const tone = interviewScoreTone(overall)

  const breakdown = screeningCategoryBreakdown(summary, evaluations)

  const reEvaluations = Array.isArray(analysis.re_evaluations) ? analysis.re_evaluations : []
  const canReEvaluate = Boolean(sessionId) && evaluations.length > 0

  return (
    <Panel
      title={panelTitle}
      actions={
        canReEvaluate ? (
          <Button
            variant="secondary"
            size="sm"
            icon="refresh"
            onClick={() => setShowReEvaluate(true)}
          >
            Re-evaluate
          </Button>
        ) : null
      }
    >
      <div className="space-y-md">
        {reEvaluations.length > 0 ? <EvaluationHistory reEvaluations={reEvaluations} /> : null}
        <FinalSummarySection
          summary={summary}
          overall={overall}
          lines={lines}
          evaluated={evaluated}
        />

        <div className="grid lg:grid-cols-[minmax(240px,300px)_minmax(0,1fr)] gap-lg items-start">
          <div className="lg:sticky lg:top-20 self-start">
            <Scorecard
              overall={overall}
              tone={tone}
              breakdown={breakdown}
              planned={planned}
              evaluated={evaluated}
              silenceEnded={silenceEnded}
              sessionStatus={analysis.session_status}
              summary={summary}
              recordingUrl={analysis.recording_url}
            />
          </div>

          <div className="min-w-0">
            <p className="font-label-md text-label-md text-on-surface tracking-wide mb-xs">
              Evaluated questions
              <span className="text-on-surface-variant font-normal"> · {evaluated}</span>
            </p>
            {evaluations.length > 0 ? (
              <div className="rounded-xl border border-outline-variant/70 px-md bg-surface-container-lowest/60">
                {evaluations.map((evaluation) => (
                  <EvaluationRow
                    key={evaluation?.question_id ?? evaluation?.question}
                    evaluation={evaluation}
                  />
                ))}
              </div>
            ) : (
              <p className="text-body-sm text-on-surface-variant">
                No per-question evaluations yet.
              </p>
            )}
          </div>
        </div>

        {transcript.length > 0 ? (
          <SectionToggle title="Full transcript" count={transcript.length} defaultOpen={false}>
            <div className="rounded-xl border border-outline-variant/70 px-md py-sm bg-surface-container-low/50">
              {transcript.map((turn, index) => (
                <TranscriptTurn key={`${turn?.interaction_type}-${index}`} turn={turn} />
              ))}
            </div>
          </SectionToggle>
        ) : null}
      </div>
      {canReEvaluate ? (
        <ReEvaluateScreeningModal
          open={showReEvaluate}
          onClose={() => setShowReEvaluate(false)}
          sessionId={sessionId}
          evaluations={evaluations}
          onDone={onReEvaluated}
        />
      ) : null}
    </Panel>
  )
}
