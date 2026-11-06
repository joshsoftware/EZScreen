import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '../../components/ui/Button'
import { TextArea } from '../../components/ui/Input'
import { Modal } from '../../components/ui/Modal'
import { ApiError } from '../../lib/api/client'
import { reEvaluateScreeningRequest } from './api'

function draftsFrom(evaluations) {
  return evaluations.map((evaluation) => ({
    questionId: evaluation.question_id,
    question: evaluation.question || '',
    answer: evaluation.candidate_answer || '',
    followUps: (Array.isArray(evaluation.follow_ups) ? evaluation.follow_ups : []).map((fu) => ({
      question: fu.follow_up_question || '',
      answer: fu.follow_up_answer || '',
    })),
  }))
}

/** Only what HR changed; unchanged answers are re-scored as saved. */
function correctionsFrom(drafts, evaluations) {
  const corrections = []
  drafts.forEach((draft, index) => {
    const saved = evaluations[index]
    const answerChanged = draft.answer.trim() !== String(saved.candidate_answer || '').trim()
    const savedFollowUps = Array.isArray(saved.follow_ups) ? saved.follow_ups : []
    const followUpAnswers = draft.followUps.map((fu, i) =>
      fu.answer.trim() !== String(savedFollowUps[i]?.follow_up_answer || '').trim() ? fu.answer : null,
    )
    if (answerChanged || followUpAnswers.some((answer) => answer != null)) {
      corrections.push({
        question_id: draft.questionId,
        candidate_answer: answerChanged ? draft.answer : null,
        follow_up_answers: followUpAnswers,
      })
    }
  })
  return corrections
}

/**
 * HR re-scores a screening from its saved answers, first correcting any the
 * speech-to-text misheard. Scoring is the same as in the live interview.
 */
export function ReEvaluateScreeningModal({ open, onClose, sessionId, evaluations, onDone }) {
  const [drafts, setDrafts] = useState(() => draftsFrom(evaluations))
  const [submitting, setSubmitting] = useState(false)

  // Start from the saved answers each time the window opens, but not on a
  // background refetch while it is open: that would wipe HR's edits.
  useEffect(() => {
    if (open) setDrafts(draftsFrom(evaluations))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  function setAnswer(index, answer) {
    setDrafts((current) => current.map((d, i) => (i === index ? { ...d, answer } : d)))
  }

  function setFollowUpAnswer(index, fuIndex, answer) {
    setDrafts((current) =>
      current.map((d, i) =>
        i === index
          ? { ...d, followUps: d.followUps.map((fu, j) => (j === fuIndex ? { ...fu, answer } : fu)) }
          : d,
      ),
    )
  }

  async function onSubmit() {
    if (submitting) return
    setSubmitting(true)
    try {
      const corrections = correctionsFrom(drafts, evaluations)
      const result = await reEvaluateScreeningRequest(sessionId, corrections)
      const overall = Number(result?.analysis_result?.final_summary?.overall_score)
      toast.success(
        Number.isFinite(overall)
          ? `Screening re-evaluated · new score ${overall.toFixed(1)}/10`
          : 'Screening re-evaluated',
      )
      await onDone?.()
      onClose()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Re-evaluation failed. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={() => !submitting && onClose()} title="Re-evaluate screening">
      <div className="flex min-h-0 flex-col gap-md">
        <p className="text-body-sm text-on-surface-variant">
          The total and summary are recalculated with the current scoring rules. If the
          transcript misheard an answer, correct it below (check the recording): only answers
          you change are marked again by the AI; the others keep their marks. The original
          result is kept in the evaluation history.
        </p>
        <div className="min-h-0 space-y-md overflow-y-auto pr-xs" style={{ maxHeight: '50vh' }}>
          {drafts.map((draft, index) => (
            <section
              key={draft.questionId ?? index}
              className="space-y-sm rounded-xl border border-outline-variant/70 p-sm"
            >
              <p className="text-body-sm font-medium text-on-surface">
                Q{draft.questionId}. {draft.question}
              </p>
              <TextArea
                id={`re-eval-answer-${draft.questionId}`}
                label="Candidate's answer"
                value={draft.answer}
                disabled={submitting}
                onChange={(event) => setAnswer(index, event.target.value)}
              />
              {draft.followUps.map((fu, fuIndex) => (
                <div key={fuIndex} className="space-y-xs border-l-2 border-outline-variant pl-sm">
                  <p className="text-label-md text-on-surface-variant">Follow-up: {fu.question}</p>
                  <TextArea
                    id={`re-eval-followup-${draft.questionId}-${fuIndex}`}
                    label="Answer to the follow-up"
                    value={fu.answer}
                    disabled={submitting}
                    onChange={(event) => setFollowUpAnswer(index, fuIndex, event.target.value)}
                  />
                </div>
              ))}
            </section>
          ))}
        </div>
        <div className="flex flex-wrap justify-end gap-sm">
          <Button variant="secondary" disabled={submitting} onClick={onClose}>
            Cancel
          </Button>
          <Button icon="refresh" loading={submitting} onClick={onSubmit}>
            {submitting ? 'Re-evaluating…' : 'Re-evaluate'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
