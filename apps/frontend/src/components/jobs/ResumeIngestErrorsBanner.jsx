import { useEffect, useState } from 'react'
import { Alert } from '../ui/Alert'

const DEFAULT_DISMISS_MS = 10000

function formatIngestErrorSummary(errors) {
  if (!errors.length) return ''
  if (errors.length === 1) {
    const item = errors[0]
    return `${item.file_name} — ${item.message}`
  }
  return errors.map((item) => `${item.file_name}: ${item.message}`).join(' · ')
}

function errorsSignature(errors) {
  return errors
    .map((item) => `${item.file_name ?? ''}|${item.message ?? ''}|${item.created_at ?? ''}`)
    .join(';')
}

export function ResumeIngestErrorsBanner({
  errors = [],
  dismissAfterMs = DEFAULT_DISMISS_MS,
}) {
  const signature = errorsSignature(errors)
  const [dismissedSignature, setDismissedSignature] = useState(null)

  useEffect(() => {
    if (!errors.length) {
      setDismissedSignature(null)
      return undefined
    }

    setDismissedSignature(null)
    const id = window.setTimeout(() => {
      setDismissedSignature(signature)
    }, dismissAfterMs)

    return () => window.clearTimeout(id)
  }, [signature, dismissAfterMs, errors.length])

  if (!errors.length || dismissedSignature === signature) return null

  return (
    <Alert tone="warning">
      <div>
        <p className="font-medium">
          {errors.length === 1
            ? 'A resume could not be processed'
            : `${errors.length} resumes could not be processed`}
        </p>
        <p className="text-body-sm mt-xs opacity-90">{formatIngestErrorSummary(errors)}</p>
      </div>
    </Alert>
  )
}
