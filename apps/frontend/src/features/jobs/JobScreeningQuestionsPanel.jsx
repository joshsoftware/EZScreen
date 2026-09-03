import { useMemo, useState } from 'react'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input, Select, TextArea } from '../../components/ui/Input'
import { Modal } from '../../components/ui/Modal'
import { Panel } from '../../components/ui/PageHeader'
import { cn } from '../../lib/cn'

const FILTERS = [
  { id: 'all', label: 'All', match: null },
  { id: 'must_have', label: 'Must-have', match: ['must_have', 'must_have_matched'] },
  { id: 'good_to_have', label: 'Good to have', match: ['good_to_have'] },
  { id: 'experience_domain', label: 'Role & domain', match: ['experience_domain'] },
  { id: 'lacking_skill', label: 'Skill gaps', match: ['lacking_skill'] },
]

const CATEGORY_OPTIONS = [
  { value: 'must_have', label: 'Must-have skill' },
  { value: 'good_to_have', label: 'Good to have' },
  { value: 'experience_domain', label: 'Role & domain' },
  { value: 'lacking_skill', label: 'Skill gap' },
]

const DEPTH_OPTIONS = [
  { value: 'aware', label: 'Awareness' },
  { value: 'partial_depth', label: 'Partial depth' },
  { value: 'full_depth', label: 'Full depth' },
]

const DEPTH_LABELS = Object.fromEntries(DEPTH_OPTIONS.map((o) => [o.value, o.label]))

const EMPTY_FORM = {
  question: '',
  skill_focus: '',
  category: 'must_have',
  answer_depth: 'partial_depth',
  expected_keywords: '',
}

function categoryKey(category) {
  const found = FILTERS.find((f) => f.match?.includes(category))
  return found?.id || category || 'general'
}

function toForm(question) {
  if (!question) return { ...EMPTY_FORM }
  return {
    question: question.question || '',
    skill_focus: question.skill_focus || '',
    category: categoryKey(question.category),
    answer_depth: question.answer_depth || 'partial_depth',
    expected_keywords: Array.isArray(question.expected_keywords)
      ? question.expected_keywords.join(', ')
      : '',
  }
}

function fromForm(form) {
  return {
    category: form.category,
    skill_focus: form.skill_focus.trim(),
    question: form.question.trim(),
    answer_depth: form.answer_depth,
    expected_keywords: form.expected_keywords
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  }
}

function QuestionFormModal({ open, onClose, initial, title, onSubmit, submitting }) {
  const [form, setForm] = useState(toForm(initial))

  function setField(name, value) {
    setForm((curr) => ({ ...curr, [name]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    onSubmit(fromForm(form))
  }

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form className="space-y-md" onSubmit={handleSubmit}>
        <TextArea
          id="sq-question"
          label="Question"
          required
          rows={4}
          value={form.question}
          onChange={(e) => setField('question', e.target.value)}
        />
        <div className="grid sm:grid-cols-2 gap-md">
          <Input
            id="sq-skill"
            label="Skill / topic"
            value={form.skill_focus}
            onChange={(e) => setField('skill_focus', e.target.value)}
            placeholder="e.g. Java Spring Boot"
          />
          <Select
            id="sq-category"
            label="Category"
            value={form.category}
            onChange={(e) => setField('category', e.target.value)}
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid sm:grid-cols-2 gap-md">
          <Select
            id="sq-depth"
            label="Answer depth"
            value={form.answer_depth}
            onChange={(e) => setField('answer_depth', e.target.value)}
          >
            {DEPTH_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
          <Input
            id="sq-keywords"
            label="Expected topics (comma-separated)"
            value={form.expected_keywords}
            onChange={(e) => setField('expected_keywords', e.target.value)}
            placeholder="keyword1, keyword2"
          />
        </div>
        <div className="flex justify-end gap-sm pt-sm">
          <Button type="button" variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Save question
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function QuestionRow({ question, index, onEdit, onDelete }) {
  const keywords = Array.isArray(question.expected_keywords)
    ? question.expected_keywords.filter(Boolean)
    : []

  return (
    <li className="group flex gap-md rounded-lg border border-transparent px-sm py-md hover:border-outline-variant/60 hover:bg-surface-container-low/40">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-container-high text-label-sm font-semibold text-on-surface-variant">
        {index}
      </span>
      <div className="min-w-0 flex-1">
        <div className="mb-xs flex flex-wrap items-center gap-x-sm gap-y-0.5 text-label-sm text-on-surface-variant">
          {question.skill_focus ? <span>{question.skill_focus}</span> : null}
          {question.skill_focus && question.answer_depth ? <span>·</span> : null}
          {question.answer_depth ? (
            <span>{DEPTH_LABELS[question.answer_depth] || question.answer_depth}</span>
          ) : null}
        </div>
        <p className="text-body-sm text-on-surface leading-relaxed">{question.question}</p>
        {keywords.length > 0 ? (
          <p className="mt-sm text-label-sm text-on-surface-variant">
            Topics: {keywords.join(' · ')}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-start gap-xs opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
        <button
          type="button"
          onClick={() => onEdit(question)}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container-high hover:text-primary"
          aria-label="Edit question"
        >
          <span className="material-symbols-outlined text-[18px]">edit</span>
        </button>
        <button
          type="button"
          onClick={() => onDelete(question)}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant hover:bg-error-container/40 hover:text-on-error-container"
          aria-label="Delete question"
        >
          <span className="material-symbols-outlined text-[18px]">delete</span>
        </button>
      </div>
    </li>
  )
}

export function JobScreeningQuestionsPanel({
  job,
  onRegenerate,
  regenerating = false,
  onSave,
  saving = false,
}) {
  const [filter, setFilter] = useState('all')
  const [editor, setEditor] = useState(null)

  const payload = job?.screening_questions
  const isPublished = job?.status === 'published'

  const questions = useMemo(() => {
    if (!payload || !Array.isArray(payload.questions)) return []
    return [...payload.questions].sort((a, b) => (a.id ?? 0) - (b.id ?? 0))
  }, [payload])

  const filtered = useMemo(() => {
    if (filter === 'all') return questions
    const cat = FILTERS.find((c) => c.id === filter)
    if (!cat?.match) return questions
    return questions.filter((q) => cat.match.includes(categoryKey(q.category)))
  }, [questions, filter])

  const counts = useMemo(() => {
    const map = { all: questions.length }
    for (const cat of FILTERS) {
      if (!cat.match) continue
      map[cat.id] = questions.filter((q) => cat.match.includes(categoryKey(q.category))).length
    }
    return map
  }, [questions])

  const status = payload?.status
  const hasError = status === 'error'
  const hasQuestions = questions.length > 0

  async function persist(nextQuestions) {
    const numbered = nextQuestions.map((q, idx) => ({ ...q, id: idx + 1 }))
    await onSave?.(numbered)
  }

  async function handleDelete(question) {
    if (!window.confirm('Delete this screening question?')) return
    const next = questions.filter((q) => q.id !== question.id)
    await persist(next)
  }

  async function handleFormSubmit(data) {
    let next
    if (editor?.mode === 'edit') {
      next = questions.map((q) => (q.id === editor.question.id ? { ...q, ...data } : q))
    } else {
      next = [...questions, { id: questions.length + 1, ...data }]
    }
    await persist(next)
    setEditor(null)
  }

  if (!isPublished) {
    return (
      <Panel title="Screening questions">
        <p className="text-body-sm text-on-surface-variant">
          Publish this job to generate and manage interview questions.
        </p>
      </Panel>
    )
  }

  return (
    <>
      <Panel
        title="Screening questions"
        actions={
          <div className="flex flex-wrap items-center gap-sm">
            <Button size="sm" icon="add" variant="secondary" onClick={() => setEditor({ mode: 'add' })}>
              Add
            </Button>
            {onRegenerate ? (
              <Button
                variant="secondary"
                size="sm"
                icon="refresh"
                loading={regenerating}
                onClick={onRegenerate}
              >
                Regenerate
              </Button>
            ) : null}
          </div>
        }
      >
        <p className="text-body-sm text-on-surface-variant mb-md">
          {hasQuestions
            ? `${questions.length} questions for AI screening — edit, add, or remove as needed.`
            : 'Generate a question bank or add questions manually.'}
          {payload?.updated_at || payload?.generated_at ? (
            <span className="block sm:inline sm:ml-sm text-label-sm">
              Last updated{' '}
              {new Date(payload.updated_at || payload.generated_at).toLocaleString()}
            </span>
          ) : null}
        </p>

        {hasError ? (
          <Alert tone="error" className="mb-md">
            {payload.error_message || 'Question generation failed.'}
          </Alert>
        ) : null}

        {!hasQuestions && !hasError ? (
          <div className="rounded-xl border border-dashed border-outline-variant py-lg text-center">
            <p className="text-body-sm text-on-surface-variant mb-md">No questions yet.</p>
            <div className="flex flex-wrap justify-center gap-sm">
              <Button size="sm" icon="add" onClick={() => setEditor({ mode: 'add' })}>
                Add question
              </Button>
              {onRegenerate ? (
                <Button size="sm" icon="auto_awesome" loading={regenerating} onClick={onRegenerate}>
                  Generate with AI
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        {hasQuestions ? (
          <>
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
                <QuestionRow
                  key={question.id ?? idx}
                  question={question}
                  index={question.id ?? idx + 1}
                  onEdit={(q) => setEditor({ mode: 'edit', question: q })}
                  onDelete={handleDelete}
                />
              ))}
            </ul>
            {saving ? (
              <p className="mt-sm text-label-sm text-on-surface-variant">Saving changes…</p>
            ) : null}
          </>
        ) : null}
      </Panel>

      <QuestionFormModal
        key={editor?.mode === 'edit' ? editor.question.id : 'add'}
        open={Boolean(editor)}
        onClose={() => setEditor(null)}
        initial={editor?.mode === 'edit' ? editor.question : null}
        title={editor?.mode === 'edit' ? 'Edit question' : 'Add question'}
        onSubmit={handleFormSubmit}
        submitting={saving}
      />
    </>
  )
}
