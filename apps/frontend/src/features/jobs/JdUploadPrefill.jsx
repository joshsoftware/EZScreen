import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { ApiError } from '../../lib/api/client'
import { importJdFileRequest } from './api'
import { importFormToValues, normalizeNeedsReview } from './jobFields'

const ACCEPT = '.pdf,.docx,.txt,.md,application/pdf,text/plain'

export function JdUploadPrefill({ values, onPrefill, disabled = false }) {
  const inputRef = useRef(null)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState(null)
  const [needsReview, setNeedsReview] = useState([])
  const [fileName, setFileName] = useState(null)

  function formHasContent(formValues) {
    return [
      formValues.title,
      formValues.role_summary,
      formValues.about_company,
      formValues.responsibilities,
      formValues.must_have_skills_text,
      formValues.good_to_have_skills_text,
      formValues.qualifications,
      formValues.domain_experience,
      formValues.tools_stack,
      formValues.location,
      formValues.experience_min,
      formValues.experience_max,
    ].some((value) => String(value || '').trim())
  }

  async function handleFile(file) {
    if (!file || disabled || importing) return
    setError(null)

    if (formHasContent(values)) {
      const ok = window.confirm(
        'Replace the current form fields with content from this file?',
      )
      if (!ok) {
        if (inputRef.current) inputRef.current.value = ''
        return
      }
    }

    setImporting(true)
    try {
      const result = await importJdFileRequest(file)
      const form = result?.form
      if (!form) throw new Error('Import returned no form data')
      onPrefill(importFormToValues(form, values))
      const leftovers = normalizeNeedsReview(form.needs_review)
      setNeedsReview(leftovers)
      setFileName(file.name)
      toast.success(
        leftovers.length
          ? 'JD imported — review leftover content below'
          : 'JD imported into the form',
      )
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Failed to import JD'
      setError(message)
      toast.error(message)
    } finally {
      setImporting(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  async function copyBlock(content) {
    try {
      await navigator.clipboard.writeText(content)
      toast.success('Copied')
    } catch {
      toast.error('Could not copy')
    }
  }

  return (
    <section className="rounded-xl border border-outline-variant/70 bg-surface-container-low/30 p-md space-y-md">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-md">
        <div>
          <h3 className="font-headline-sm text-headline-sm text-on-surface tracking-tight">
            Upload JD
          </h3>
          <p className="text-label-md text-on-surface-variant mt-xs">
            PDF, DOCX, or TXT — we fill matching sections. Leftovers appear under Needs
            review.
          </p>
          {fileName ? (
            <p className="text-label-md text-secondary mt-xs">Last import: {fileName}</p>
          ) : null}
        </div>
        <div className="shrink-0">
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            disabled={disabled || importing}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void handleFile(file)
            }}
          />
          <Button
            type="button"
            variant="secondary"
            loading={importing}
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            {importing ? 'Importing…' : 'Choose file'}
          </Button>
        </div>
      </div>

      {error ? <Alert>{error}</Alert> : null}

      {needsReview.length > 0 ? (
        <div className="rounded-lg border border-outline-variant/80 bg-surface-container-lowest/80 p-md space-y-sm">
          <div>
            <h4 className="font-label-md text-label-md text-on-surface">Needs review</h4>
            <p className="text-label-md text-on-surface-variant mt-xs">
              Content that didn&apos;t map cleanly — copy into the right section above.
            </p>
          </div>
          <ul className="space-y-sm">
            {needsReview.map((item, index) => (
              <li
                key={`${item.label}-${index}`}
                className="rounded-md border border-outline-variant/60 bg-surface p-sm"
              >
                <div className="flex items-start justify-between gap-sm mb-xs">
                  <p className="font-label-md text-label-md text-on-surface">{item.label}</p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="shrink-0"
                    onClick={() => void copyBlock(item.content)}
                  >
                    Copy
                  </Button>
                </div>
                <pre className="whitespace-pre-wrap text-body-sm text-on-surface-variant font-sans m-0">
                  {item.content}
                </pre>
              </li>
            ))}
          </ul>
          <Button type="button" variant="ghost" size="sm" onClick={() => setNeedsReview([])}>
            Dismiss
          </Button>
        </div>
      ) : null}
    </section>
  )
}
