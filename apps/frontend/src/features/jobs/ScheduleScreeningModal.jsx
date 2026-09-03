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

function pad(n) {
  return String(n).padStart(2, '0')
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
    setAdditionalEmails('')
    setComment('')
  }, [open, isReschedule, initialSlot])

  function resetAndClose() {
    if (submitting) return
    onClose?.()
  }

  async function onSubmit() {
    if (submitting) return
    const scheduledAt = localDatetimeToIso(scheduledLocal)
    if (!scheduledAt) {
      toast.error('Pick a valid date and time')
      return
    }
    if (new Date(scheduledAt).getTime() <= Date.now()) {
      toast.error('Screening time must be in the future')
      return
    }

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
          : 'Screening scheduled · invite sent',
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
        {candidateEmail ? (
          <>
            {' '}
            The candidate ({candidateEmail}) is included as a guest by default.
          </>
        ) : null}
      </p>

      <div className="space-y-md">
        <Input
          id="screening-scheduled-at"
          label="Date & time"
          type="datetime-local"
          value={scheduledLocal}
          onChange={(event) => setScheduledLocal(event.target.value)}
          required
        />
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
          onClick={() => void onSubmit()}
        >
          {isReschedule ? 'Reschedule screening' : 'Schedule screening'}
        </Button>
      </div>
    </Modal>
  )
}
