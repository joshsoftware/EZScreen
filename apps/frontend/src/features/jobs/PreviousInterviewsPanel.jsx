import { useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { Panel } from '../../components/ui/PageHeader'
import { TranscriptTurn } from './InterviewAnalysisPanel'
import { formatDateTime } from './jobFields'

const ATTEMPT_OUTCOMES = {
  no_show: { label: 'No-show', tone: 'warning' },
  completed: { label: 'No answers scored', tone: 'warning' },
  failed: { label: 'Screening failed', tone: 'danger' },
  // Rescheduled while the bot was still waiting in the meeting.
  in_progress: { label: 'Stopped for reschedule', tone: 'neutral' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
}

function attemptOutcome(status) {
  return ATTEMPT_OUTCOMES[status] ?? { label: String(status).replaceAll('_', ' '), tone: 'neutral' }
}

function AttemptRecording({ attempt }) {
  if (attempt.recording_url) {
    return (
      <div className="flex flex-col gap-xs">
        <video
          controls
          preload="metadata"
          src={attempt.recording_url}
          className="w-full aspect-video rounded-lg bg-black"
        >
          Your browser cannot play this recording.
        </video>
        <a
          href={attempt.recording_url}
          target="_blank"
          rel="noreferrer"
          className="text-label-md text-primary hover:underline"
        >
          Open recording in a new tab
        </a>
      </div>
    )
  }
  const saving = attempt.recording_status === 'pending' || attempt.recording_status === 'in_progress'
  return (
    <p className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-outline-variant px-sm text-center text-body-sm text-on-surface-variant italic">
      {saving ? 'Recording is still being saved…' : 'No recording available.'}
    </p>
  )
}

function transcriptOf(attempt) {
  return Array.isArray(attempt?.conversation_transcript) ? attempt.conversation_transcript : []
}

/** Earlier attempts of a rescheduled screening, Screening 1 first, each with its recording. */
export function PreviousInterviewsPanel({ attempts }) {
  const [transcriptAttempt, setTranscriptAttempt] = useState(null)
  if (!Array.isArray(attempts) || attempts.length === 0) return null
  const ordered = [...attempts].sort((a, b) => a.attempt - b.attempt)
  const openTranscript = transcriptOf(transcriptAttempt)

  return (
    <Panel title="Earlier screenings">
      <div className="grid gap-md sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {ordered.map((attempt) => {
          const outcome = attemptOutcome(attempt.status)
          const turns = transcriptOf(attempt).length
          return (
            <section
              key={attempt.attempt}
              className="flex flex-col gap-sm rounded-xl border border-outline-variant/70 bg-surface-container-low/40 p-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-xs">
                <h3 className="font-medium text-body-sm text-on-surface">
                  Screening {attempt.attempt}
                </h3>
                <Badge tone={outcome.tone}>{outcome.label}</Badge>
              </div>
              <p className="text-label-md text-on-surface-variant">
                {formatDateTime(attempt.scheduled_at)}
              </p>
              <AttemptRecording attempt={attempt} />
              {turns > 0 ? (
                <button
                  type="button"
                  onClick={() => setTranscriptAttempt(attempt)}
                  className="self-start text-label-md text-primary hover:underline"
                >
                  View transcript · {turns}
                </button>
              ) : null}
            </section>
          )
        })}
      </div>

      <Modal
        open={transcriptAttempt != null}
        onClose={() => setTranscriptAttempt(null)}
        title={transcriptAttempt ? `Screening ${transcriptAttempt.attempt} · Transcript` : ''}
      >
        <div className="max-h-[65vh] overflow-y-auto">
          {openTranscript.map((turn, index) => (
            <TranscriptTurn key={`prev-t-${index}`} turn={turn} />
          ))}
        </div>
      </Modal>
    </Panel>
  )
}
