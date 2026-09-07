import { useMemo, useState } from 'react'
import { Alert } from '../../components/ui/Alert'
import { Panel } from '../../components/ui/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { cn } from '../../lib/cn'

const FILTERS = [
  { id: 'all', label: 'All', match: null },
  { id: 'must_have', label: 'Must-have', match: ['must_have', 'must_have_matched'] },
  { id: 'good_to_have', label: 'Good to have', match: ['good_to_have'] },
  { id: 'experience_domain', label: 'Role & domain', match: ['experience_domain'] },
  { id: 'lacking_skill', label: 'Skill gaps', match: ['lacking_skill'] },
]

const DEPTH_LABELS = {
  aware: 'Awareness',
  partial_depth: 'Partial depth',
  full_depth: 'Full depth',
}

function categoryBucket(category) {
  const found = FILTERS.find((f) => f.match?.includes(category))
  return found?.id || 'all'
}

function normalizeQuestions(raw) {
  if (Array.isArray(raw)) return raw.filter((q) => q && typeof q === 'object' && q.question)
  if (raw && typeof raw === 'object' && Array.isArray(raw.questions)) {
    return raw.questions.filter((q) => q && typeof q === 'object' && q.question)
  }
  return []
}

/**
 * Read-only list of per-candidate screening questions from the interview session.
 */
export function CandidateScreeningQuestionsPanel({
  questions: rawQuestions,
  loading = false,
  error = null,
  scheduled = false,
}) {
  const [filter, setFilter] = useState('all')

  const questions = useMemo(() => {
    const list = normalizeQuestions(rawQuestions)
    return [...list].sort((a, b) => (a.id ?? 0) - (b.id ?? 0))
  }, [rawQuestions])

  const filtered = useMemo(() => {
    if (filter === 'all') return questions
    const cat = FILTERS.find((c) => c.id === filter)
    if (!cat?.match) return questions
    return questions.filter((q) => cat.match.includes(categoryBucket(q.category)))
  }, [questions, filter])

  const counts = useMemo(() => {
    const map = { all: questions.length }
    for (const cat of FILTERS) {
      if (!cat.match) continue
      map[cat.id] = questions.filter((q) =>
        cat.match.includes(categoryBucket(q.category)),
      ).length
    }
    return map
  }, [questions])

  if (!scheduled && !loading) {
    return (
      <Panel title="Screening questions">
        <p className="text-body-sm text-on-surface-variant">
          Questions are generated from this job and the candidate&apos;s resume when you schedule
          AI screening.
        </p>
      </Panel>
    )
  }

  if (loading) {
    return (
      <Panel title="Screening questions">
        <Skeleton className="h-32 rounded-xl" />
      </Panel>
    )
  }

  if (error) {
    return (
      <Panel title="Screening questions">
        <Alert>{error}</Alert>
      </Panel>
    )
  }

  if (questions.length === 0) {
    return (
      <Panel title="Screening questions">
        <p className="text-body-sm text-on-surface-variant rounded-xl border border-dashed border-outline-variant px-md py-lg text-center">
          No questions on this screening session yet.
        </p>
      </Panel>
    )
  }

  return (
    <Panel title="Screening questions">
      <p className="text-body-sm text-on-surface-variant mb-md">
        {questions.length} questions tailored to this candidate&apos;s resume and the job
        description. The AI interviewer will ask from this set.
      </p>

      <div className="mb-md flex flex-wrap gap-xs">
        {FILTERS.filter((c) => c.id === 'all' || counts[c.id] > 0).map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => setFilter(cat.id)}
            className={cn(
              'rounded-full px-3 py-1 text-label-sm transition-colors',
              filter === cat.id
                ? 'bg-primary text-white'
                : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest',
            )}
          >
            {cat.label}
            <span className="ml-1 opacity-80">{counts[cat.id] ?? 0}</span>
          </button>
        ))}
      </div>

      <ul className="max-h-[28rem] space-y-1 overflow-y-auto rounded-xl border border-outline-variant/60 bg-surface-container-lowest/50 p-sm">
        {filtered.map((question, idx) => (
          <li
            key={question.id ?? idx}
            className="rounded-lg px-sm py-sm hover:bg-surface-container-low/80"
          >
            <div className="flex flex-wrap items-baseline gap-xs mb-xs">
              <span className="text-label-sm text-on-surface-variant">
                {question.id ?? idx + 1}.
              </span>
              {question.skill_focus ? (
                <span className="text-label-sm text-secondary">{question.skill_focus}</span>
              ) : null}
              {question.answer_depth && DEPTH_LABELS[question.answer_depth] ? (
                <span className="text-label-sm text-on-surface-variant">
                  · {DEPTH_LABELS[question.answer_depth]}
                </span>
              ) : null}
            </div>
            <p className="text-body-sm text-on-surface">{question.question}</p>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
