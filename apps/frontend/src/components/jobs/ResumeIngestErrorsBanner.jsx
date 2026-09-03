import { Alert } from '../ui/Alert'

function formatIngestErrorSummary(errors) {
  if (!errors.length) return ''
  if (errors.length === 1) {
    const item = errors[0]
    return `${item.file_name} — ${item.message}`
  }
  return errors.map((item) => `${item.file_name}: ${item.message}`).join(' · ')
}

export function ResumeIngestErrorsBanner({ errors = [] }) {
  if (!errors.length) return null

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
