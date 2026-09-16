import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'

export function ResumeIngestErrorsBanner({
  errors = [],
  onDismiss,
}) {
  if (!errors.length) return null

  return (
    <Alert tone="warning">
      <div className="flex items-start justify-between gap-md">
        <div className="min-w-0">
          <p className="font-medium">
            {errors.length === 1
              ? 'In this upload, 1 resume could not be processed'
              : `In this upload, ${errors.length} resumes could not be processed`}
          </p>
          <p className="text-body-sm mt-xs opacity-90">
            Re-upload only the files listed below.
          </p>
          <ul className="text-body-sm mt-sm space-y-xs opacity-90 list-disc pl-md">
            {errors.map((item) => (
              <li key={`${item.file_name}-${item.created_at}-${item.message}`}>
                <span className="font-medium">{item.file_name}</span>
                {' — '}
                {item.message}
              </li>
            ))}
          </ul>
        </div>
        {typeof onDismiss === 'function' ? (
          <Button
            type="button"
            variant="ghost"
            className="shrink-0"
            onClick={onDismiss}
          >
            Dismiss
          </Button>
        ) : null}
      </div>
    </Alert>
  )
}
