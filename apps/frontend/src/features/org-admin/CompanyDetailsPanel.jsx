import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '../../components/ui/Button'
import { TextArea } from '../../components/ui/Input'
import { Panel } from '../../components/ui/PageHeader'
import { ApiError } from '../../lib/api/client'
import { updateOrganizationRequest } from './api'

export const COMPANY_DETAILS_MAX_LENGTH = 500

/**
 * A few sentences about the company. The AI interviewer reads them, as
 * written, at the start of every screening.
 */
export function CompanyDetailsPanel({ orgId, org, onSaved }) {
  const saved = org?.company_details ?? ''
  const [value, setValue] = useState(saved)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setValue(org?.company_details ?? '')
  }, [org?.company_details])

  async function onSubmit(event) {
    event.preventDefault()
    if (!orgId || submitting) return
    setSubmitting(true)
    try {
      const updated = await updateOrganizationRequest(orgId, {
        company_details: value.trim() || null,
      })
      onSaved?.(updated)
      toast.success('Company details saved')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Failed to save company details')
    } finally {
      setSubmitting(false)
    }
  }

  const changed = value.trim() !== saved.trim()

  return (
    <Panel title="Company details">
      <form onSubmit={onSubmit} className="space-y-md">
        <p className="text-body-sm text-on-surface-variant">
          A few sentences about your company. The AI interviewer reads this to the candidate,
          as written, when every screening starts, together with the job&apos;s role intro.
        </p>
        <TextArea
          id="company-details"
          label="About the company"
          value={value}
          maxLength={COMPANY_DETAILS_MAX_LENGTH}
          rows={4}
          disabled={submitting}
          placeholder="e.g. Josh Software builds web and mobile products for clients worldwide, with teams in Pune and Bangalore."
          onChange={(event) => setValue(event.target.value)}
        />
        <div className="flex items-center justify-between gap-sm">
          <span className="text-label-sm text-on-surface-variant">
            {value.length} / {COMPANY_DETAILS_MAX_LENGTH}
          </span>
          <Button type="submit" loading={submitting} disabled={!changed}>
            {submitting ? 'Saving…' : 'Save company details'}
          </Button>
        </div>
      </form>
    </Panel>
  )
}
