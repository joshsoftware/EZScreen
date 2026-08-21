import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useAuth } from '../../features/auth/AuthContext'
import { changePasswordRequest } from '../../features/auth/api'
import { useOrgSettings } from '../../features/org-admin/OrgSettingsContext'
import {
  getOrganizationRequest,
  updateOrganizationRequest,
} from '../../features/org-admin/api'
import {
  DEFAULT_FIT_LABELS,
  normalizeFitLabels,
  numericScore,
} from '../../features/jobs/applicationFields'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input, PasswordInput } from '../../components/ui/Input'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

function newLabelRow() {
  return {
    id: `label-${crypto.randomUUID().slice(0, 8)}`,
    name: '',
    min_score: '',
    max_score: '',
  }
}

function rangesOverlap(aMin, aMax, bMin, bMax) {
  return aMin <= bMax && bMin <= aMax
}

function validateLabels(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return { error: 'Add at least one fit label.' }
  }
  if (rows.length > 12) {
    return { error: 'You can define at most 12 fit labels.' }
  }

  const labels = []
  const seenNames = new Set()
  const seenIds = new Set()

  for (const row of rows) {
    const name = String(row.name ?? '').trim()
    const minScore = numericScore(row.min_score)
    const maxScore = numericScore(row.max_score)
    if (!name) return { error: 'Each label needs a name.' }
    if (minScore == null || maxScore == null) {
      return { error: `“${name || 'Label'}” needs a valid min and max score.` }
    }
    if (minScore < 0 || maxScore > 10 || minScore > maxScore) {
      return {
        error: `“${name}” range must be between 0 and 10, with min ≤ max.`,
      }
    }
    const nameKey = name.toLowerCase()
    if (seenNames.has(nameKey)) {
      return { error: `Duplicate label name: ${name}` }
    }
    seenNames.add(nameKey)

    let id = String(row.id ?? '').trim()
    if (!id) {
      id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'label'
    }
    while (seenIds.has(id)) id = `${id}-x`
    seenIds.add(id)

    labels.push({ id, name, min_score: minScore, max_score: maxScore })
  }

  const ordered = [...labels].sort(
    (a, b) => a.min_score - b.min_score || a.max_score - b.max_score,
  )
  for (let i = 0; i < ordered.length; i += 1) {
    for (let j = i + 1; j < ordered.length; j += 1) {
      if (
        rangesOverlap(
          ordered[i].min_score,
          ordered[i].max_score,
          ordered[j].min_score,
          ordered[j].max_score,
        )
      ) {
        return {
          error: `Ranges overlap between “${ordered[i].name}” and “${ordered[j].name}”.`,
        }
      }
    }
  }

  return { labels }
}

export function OrgAdminSettingsPage() {
  const { user } = useAuth()
  const orgId = user?.organization_id
  const { setFitLabels } = useOrgSettings()
  const [rows, setRows] = useState(() =>
    DEFAULT_FIT_LABELS.map((item) => ({ ...item })),
  )
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState(null)
  const [passwordSubmitting, setPasswordSubmitting] = useState(false)

  useEffect(() => {
    if (!orgId) {
      setLoading(false)
      return
    }
    let cancelled = false
    void getOrganizationRequest(orgId)
      .then((org) => {
        if (cancelled) return
        setRows(normalizeFitLabels(org?.fit_labels))
        setLoading(false)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Failed to load settings')
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [orgId])

  function updateRow(index, patch) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  function addRow() {
    setRows((prev) => [...prev, newLabelRow()])
  }

  function removeRow(index) {
    setRows((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)))
  }

  async function onSubmit(event) {
    event.preventDefault()
    if (!orgId) return

    const result = validateLabels(rows)
    if (result.error) {
      setError(result.error)
      toast.error(result.error)
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const updated = await updateOrganizationRequest(orgId, {
        fit_labels: result.labels,
      })
      const saved = normalizeFitLabels(updated?.fit_labels)
      setRows(saved)
      setFitLabels(saved)
      toast.success('Fit labels saved')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to save settings'
      setError(message)
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  async function onChangePassword(event) {
    event.preventDefault()
    setPasswordError(null)

    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.')
      return
    }

    setPasswordSubmitting(true)
    try {
      await changePasswordRequest(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast.success('Password updated')
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Failed to update password'
      setPasswordError(message)
      toast.error(message)
    } finally {
      setPasswordSubmitting(false)
    }
  }

  if (loading) {
    return <PageSkeleton />
  }

  return (
    <div className="max-w-3xl space-y-2xl">
      <PageHeader
        title="Settings"
        description="Manage your account password and organization screening labels."
      />

      <Panel title="Change password">
        <form onSubmit={onChangePassword} className="space-y-md max-w-md">
          <PasswordInput
            id="current-password"
            label="Current password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
          <PasswordInput
            id="new-password"
            label="New password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
          />
          <PasswordInput
            id="confirm-password"
            label="Confirm new password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
          />
          {passwordError ? <Alert>{passwordError}</Alert> : null}
          <Button type="submit" loading={passwordSubmitting}>
            {passwordSubmitting ? 'Updating…' : 'Update password'}
          </Button>
        </form>
      </Panel>

      {error ? (
        <div>
          <Alert>{error}</Alert>
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="space-y-lg">
        <Panel title="Fit rating labels">
          <p className="text-body-sm text-on-surface-variant mb-md">
            Applicants are tagged with the label whose range includes their AI match score.
            Ranges are inclusive and must not overlap.
          </p>

          <div className="space-y-sm">
            {rows.map((row, index) => (
              <div
                key={row.id}
                className="rounded-xl border border-outline-variant/80 bg-surface-container-low/40 p-md shadow-soft"
              >
                <div className="mb-sm flex items-center justify-between gap-sm">
                  <p className="font-label-md text-label-md text-on-surface-variant">
                    Label {index + 1}
                  </p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={rows.length <= 1}
                    onClick={() => removeRow(index)}
                  >
                    Remove
                  </Button>
                </div>
                <div className="grid gap-sm sm:grid-cols-[minmax(0,1.4fr)_minmax(0,0.8fr)_minmax(0,0.8fr)]">
                  <Input
                    id={`fit-label-name-${row.id}`}
                    label="Name"
                    placeholder="e.g. Strong"
                    required
                    value={row.name}
                    onChange={(e) => updateRow(index, { name: e.target.value })}
                  />
                  <Input
                    id={`fit-label-min-${row.id}`}
                    label="Min score"
                    type="number"
                    min={0}
                    max={10}
                    step={0.1}
                    required
                    value={row.min_score}
                    onChange={(e) => updateRow(index, { min_score: e.target.value })}
                  />
                  <Input
                    id={`fit-label-max-${row.id}`}
                    label="Max score"
                    type="number"
                    min={0}
                    max={10}
                    step={0.1}
                    required
                    value={row.max_score}
                    onChange={(e) => updateRow(index, { max_score: e.target.value })}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-md">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={rows.length >= 12}
              onClick={addRow}
            >
              Add label
            </Button>
          </div>
        </Panel>

        <div className="flex justify-end">
          <Button type="submit" loading={submitting}>
            {submitting ? 'Saving…' : 'Save labels'}
          </Button>
        </div>
      </form>
    </div>
  )
}
