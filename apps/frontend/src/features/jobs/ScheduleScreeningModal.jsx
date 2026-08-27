import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '../../components/ui/Button'
import { Input, Select, TextArea } from '../../components/ui/Input'
import { Modal } from '../../components/ui/Modal'
import { ApiError } from '../../lib/api/client'
import { scheduleInterviewSessionRequest } from './api'

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

export function ScheduleScreeningModal({
  open,
  onClose,
  applicationId,
  candidateLabel,
  candidateEmail,
  onScheduled,
}) {
  const [scheduledLocal, setScheduledLocal] = useState(defaultLocalSlot)
  const [durationMinutes, setDurationMinutes] = useState('30')
  const [gmeetLink, setGmeetLink] = useState('')
  const [additionalEmails, setAdditionalEmails] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function resetFields() {
    setScheduledLocal(defaultLocalSlot())
    setDurationMinutes('30')
    setGmeetLink('')
    setAdditionalEmails('')
    setComment('')
  }

  function resetAndClose() {
    if (submitting) return
    resetFields()
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

    const link = gmeetLink.trim()
    if (link && !link.toLowerCase().startsWith('https://')) {
      toast.error('Meet link must start with https://')
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

    setSubmitting(true)
    try {
      const session = await scheduleInterviewSessionRequest({
        application_id: applicationId,
        interview_type: 'screening_ai',
        scheduled_at: scheduledAt,
        duration_minutes: Number(durationMinutes),
        gmeet_link: link || undefined,
        additional_emails: emails,
        comment: comment.trim() || undefined,
        time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || undefined,
      })
      toast.success('Screening scheduled · invite sent')
      resetFields()
      onClose?.()
      await onScheduled?.(session)
    } catch (err) {
      toast.error(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : 'Failed to schedule screening',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={resetAndClose} title="Schedule screening">
      <p className="text-body-sm text-on-surface-variant mb-md">
        Book an AI screening slot
        {candidateLabel ? (
          <>
            {' '}
            for <span className="text-on-surface font-medium">{candidateLabel}</span>
          </>
        ) : null}
        . Paste a Meet link or leave it blank to generate one. The invite is sent
        automatically.
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
        <Input
          id="screening-gmeet"
          label="Meet link (optional)"
          type="url"
          value={gmeetLink}
          onChange={(event) => setGmeetLink(event.target.value)}
          placeholder="https://meet.google.com/…"
        />
        <p className="text-label-md text-on-surface-variant -mt-sm">
          Leave blank to auto-generate a join link.
        </p>
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
          Schedule screening
        </Button>
      </div>
    </Modal>
  )
}
