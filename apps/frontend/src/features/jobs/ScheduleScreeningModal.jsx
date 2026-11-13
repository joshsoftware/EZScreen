import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '../../components/ui/Button'
import { Input, Select, TextArea } from '../../components/ui/Input'
import { Modal } from '../../components/ui/Modal'
import { ApiError } from '../../lib/api/client'
import {
  rescheduleInterviewSessionRequest,
  scheduleInterviewSessionRequest,
} from './api'
import { MIN_LEAD_MINUTES } from './screeningSchedule'

function pad(n) {
  return String(n).padStart(2, '0')
}


function toLocalInputValue(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** Field error for the date & time, or null when it is fine. */
export function scheduledAtError(value, now = new Date()) {
  const date = new Date(value)
  if (!value || Number.isNaN(date.getTime())) return 'Pick a valid date and time.'
  const earliest = new Date(now.getTime() + MIN_LEAD_MINUTES * 60_000)
  if (date.getTime() < earliest.getTime()) {
    return `Pick a time at least ${MIN_LEAD_MINUTES} minutes from now (${pad(earliest.getHours())}:${pad(earliest.getMinutes())} or later).`
  }
  return null
}

/** Default: tomorrow at 10:00 local, as datetime-local value. */
function defaultLocalSlot() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  d.setHours(10, 0, 0, 0)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function isoToLocalDatetimeInput(iso) {
  if (!iso) return defaultLocalSlot()
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return defaultLocalSlot()
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function localDatetimeToIso(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

function parseEmailList(raw) {
  const parts = String(raw || '')
    .split(/[\s,;]+/)
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean)
  return [...new Set(parts)]
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Extra invite recipients — leave empty in dev; backend injects override sink. */
const DEFAULT_ADDITIONAL_EMAILS = []

/** Normalize legacy IANA names from Intl (e.g. Asia/Calcutta → Asia/Kolkata). */
function normalizeTimeZone(tz) {
  if (!tz) return undefined
  if (tz === 'Asia/Calcutta') return 'Asia/Kolkata'
  return tz
}

export function ScheduleScreeningModal({
  open,
  onClose,
  mode = 'schedule',
  applicationId,
  sessionId = null,
  initialSlot = null,
  candidateLabel,
  candidateEmail,
  onScheduled,
}) {
  const isReschedule = mode === 'reschedule'
  const [scheduledLocal, setScheduledLocal] = useState(defaultLocalSlot)
  const [durationMinutes, setDurationMinutes] = useState('30')
  const [additionalEmails, setAdditionalEmails] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // Re-checked as time passes, so a slot that was fine when the window
  // opened can't be submitted once it is less than 5 minutes away.
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    if (!open) return undefined
    setNow(new Date())
    const timer = setInterval(() => setNow(new Date()), 15_000)
    return () => clearInterval(timer)
  }, [open])

  const timeError = scheduledAtError(scheduledLocal, now)
  const earliestLocal = toLocalInputValue(new Date(now.getTime() + MIN_LEAD_MINUTES * 60_000))

  useEffect(() => {
    if (!open) return
    if (isReschedule && initialSlot) {
      setScheduledLocal(isoToLocalDatetimeInput(initialSlot.scheduledAt))
      setDurationMinutes(String(initialSlot.durationMinutes ?? 30))
      setAdditionalEmails((initialSlot.additionalEmails || []).join(', '))
      setComment('')
      return
    }
    setScheduledLocal(defaultLocalSlot())
    setDurationMinutes('30')
    setAdditionalEmails(DEFAULT_ADDITIONAL_EMAILS.join(', '))
    setComment('')
  }, [open, isReschedule, initialSlot])

  function resetAndClose() {
    if (submitting) return
    onClose?.()
  }

  async function onSubmit() {
    if (submitting) return
    const error = scheduledAtError(scheduledLocal, new Date())
    if (error) {
      toast.error(error)
      return
    }
    const scheduledAt = localDatetimeToIso(scheduledLocal)

    const emails = parseEmailList(additionalEmails)
    if (emails.length > 20) {
      toast.error('You can add up to 20 additional emails')
      return
    }
    const invalid = emails.find((email) => !EMAIL_RE.test(email))
    if (invalid) {
      toast.error(`Invalid email: ${invalid}`)
      return
    }

    const payload = {
      scheduled_at: scheduledAt,
      duration_minutes: Number(durationMinutes),
      additional_emails: emails,
      comment: comment.trim() || undefined,
      time_zone: normalizeTimeZone(
        Intl.DateTimeFormat().resolvedOptions().timeZone,
      ),
    }

    setSubmitting(true)
    try {
      const session = isReschedule
        ? await rescheduleInterviewSessionRequest(sessionId, payload)
        : await scheduleInterviewSessionRequest({
            application_id: applicationId,
            interview_type: 'screening_ai',
            ...payload,
          })
      toast.success(
        isReschedule
          ? 'Screening rescheduled · updated invite sent'
          : `Screening scheduled · ${
              Array.isArray(session?.generated_questions)
                ? `${session.generated_questions.length} tailored questions · `
                : ''
            }invite sent`,
      )
      onClose?.()
      await onScheduled?.(session)
    } catch (err) {
      toast.error(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : isReschedule
            ? 'Failed to reschedule screening'
            : 'Failed to schedule screening',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={resetAndClose}
      title={isReschedule ? 'Reschedule screening' : 'Schedule screening'}
    >
      <p className="text-body-sm text-on-surface-variant mb-md">
        {isReschedule ? 'Pick a new slot' : 'Book an AI screening slot'}
        {candidateLabel ? (
          <>
            {' '}
            for <span className="text-on-surface font-medium">{candidateLabel}</span>
          </>
        ) : null}
        . A Google Meet link and calendar invite are{' '}
        {isReschedule ? 'updated' : 'created'} automatically.
        {!isReschedule ? (
          <>
            {' '}
            Screening questions are generated from the job description and this
            candidate&apos;s resume before the invite is sent.
          </>
        ) : null}
        {candidateEmail ? (
          <>
            {' '}
            The candidate ({candidateEmail}) is included as a guest by default.
          </>
        ) : null}
      </p>

      <div className="space-y-md">
        <div className="space-y-xs">
          <Input
            id="screening-scheduled-at"
            label="Date & time"
            type="datetime-local"
            value={scheduledLocal}
            min={earliestLocal}
            onChange={(event) => setScheduledLocal(event.target.value)}
            aria-invalid={timeError ? 'true' : undefined}
            aria-describedby="screening-scheduled-at-help"
            className={timeError ? 'border-error' : undefined}
            required
          />
          <p
            id="screening-scheduled-at-help"
            role={timeError ? 'alert' : undefined}
            className={timeError ? 'text-label-md text-error' : 'text-label-md text-on-surface-variant'}
          >
            {timeError ?? `At least ${MIN_LEAD_MINUTES} minutes from now.`}
          </p>
        </div>
        <Select
          id="screening-duration"
          label="Duration"
          value={durationMinutes}
          onChange={(event) => setDurationMinutes(event.target.value)}
        >
          <option value="30">30 min</option>
          <option value="45">45 min</option>
          <option value="60">60 min</option>
        </Select>
        <TextArea
          id="screening-additional-emails"
          label="Additional emails (optional)"
          value={additionalEmails}
          onChange={(event) => setAdditionalEmails(event.target.value)}
          placeholder="hiring.manager@company.com, interviewer@company.com"
          rows={2}
        />
        <p className="text-label-md text-on-surface-variant -mt-sm">
          Comma or space separated. Included on the invite with the Meet link.
        </p>
        <TextArea
          id="screening-comment"
          label="Comment (optional)"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="e.g. Focus on must-have skills"
          rows={3}
        />
      </div>

      <div className="flex flex-wrap justify-end gap-sm mt-md">
        <Button variant="secondary" disabled={submitting} onClick={resetAndClose}>
          Cancel
        </Button>
        <Button
          icon="event"
          loading={submitting}
          disabled={Boolean(timeError)}
          onClick={() => void onSubmit()}
        >
          {submitting
            ? isReschedule
              ? 'Rescheduling…'
              : 'Generating questions…'
            : isReschedule
              ? 'Reschedule screening'
              : 'Schedule screening'}
        </Button>
      </div>
      <p className="mt-sm text-right text-label-md text-on-surface-variant">
        Book at least {MIN_LEAD_MINUTES} minutes ahead so the AI interviewer is ready
        when the candidate joins.
      </p>
    </Modal>
  )
}
