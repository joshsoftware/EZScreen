import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useAuth } from '../../features/auth/AuthContext'
import {
  getPlatformSettings,
  updatePlatformSettings,
} from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'
import { PageHeader, Panel } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'

const empty = {
  platform_name: 'EZScreen',
  support_email: 'support@ezscreen.io',
  timezone: 'Asia/Kolkata',
  extraction_model: 'gemma-parse-v2',
  screening_model: 'gemma-screen-v3',
  auto_retry_failed_jobs: true,
  require_mfa_super_admin: true,
  invite_expiry_days: 7,
}

export function SuperAdminSettingsPage() {
  const { token } = useAuth()
  const [form, setForm] = useState(empty)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token) return
    void getPlatformSettings(token)
      .then((data) => {
        setForm(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : 'Failed to load settings')
        setLoading(false)
      })
  }, [token])

  async function onSubmit(event) {
    event.preventDefault()
    if (!token) return
    setSubmitting(true)
    setError(null)
    try {
      const updated = await updatePlatformSettings(token, form)
      setForm(updated)
      toast.success('Settings saved')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to save settings'
      setError(message)
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <PageSkeleton />
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Platform settings"
        description="Global defaults for tenants, email, and AI models. Org Admins manage their own branding."
      />

      <form onSubmit={onSubmit} className="space-y-lg">
        <Panel title="General">
          <div className="space-y-md">
            <Input
              id="platform_name"
              label="Platform name"
              value={form.platform_name}
              onChange={(e) => setForm((f) => ({ ...f, platform_name: e.target.value }))}
            />
            <Input
              id="support_email"
              label="Default support email"
              type="email"
              value={form.support_email}
              onChange={(e) => setForm((f) => ({ ...f, support_email: e.target.value }))}
            />
            <Select
              id="timezone"
              label="Default timezone"
              value={form.timezone}
              onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
            >
              <option value="UTC">UTC</option>
              <option value="Asia/Kolkata">Asia/Kolkata</option>
              <option value="America/New_York">America/New_York</option>
            </Select>
          </div>
        </Panel>

        <Panel title="AI & pipelines">
          <div className="space-y-md">
            <Select
              id="extraction_model"
              label="Default extraction model"
              value={form.extraction_model}
              onChange={(e) =>
                setForm((f) => ({ ...f, extraction_model: e.target.value }))
              }
            >
              <option value="gemma-parse-v2">gemma-parse-v2</option>
              <option value="gemma-parse-v1">gemma-parse-v1</option>
            </Select>
            <Select
              id="screening_model"
              label="Screening evaluation model"
              value={form.screening_model}
              onChange={(e) =>
                setForm((f) => ({ ...f, screening_model: e.target.value }))
              }
            >
              <option value="gemma-screen-v3">gemma-screen-v3</option>
              <option value="gemma-screen-v2">gemma-screen-v2</option>
            </Select>
            <label className="flex items-center gap-sm text-body-sm">
              <input
                type="checkbox"
                checked={form.auto_retry_failed_jobs}
                onChange={(e) =>
                  setForm((f) => ({ ...f, auto_retry_failed_jobs: e.target.checked }))
                }
              />
              Auto-retry failed parse / bot jobs (max 3)
            </label>
          </div>
        </Panel>

        <Panel title="Security">
          <div className="space-y-md">
            <label className="flex items-center gap-sm text-body-sm">
              <input
                type="checkbox"
                checked={form.require_mfa_super_admin}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    require_mfa_super_admin: e.target.checked,
                  }))
                }
              />
              Require MFA for Super Admin accounts
            </label>
            <Input
              id="invite_expiry_days"
              label="Invite link expiry (days)"
              type="number"
              min={1}
              max={90}
              value={form.invite_expiry_days}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  invite_expiry_days: Number(e.target.value) || 7,
                }))
              }
            />
            {error ? <Alert>{error}</Alert> : null}
            <div className="flex gap-sm pt-md">
              <Button to="/super-admin/orgs" variant="secondary">
                Cancel
              </Button>
              <Button type="submit" loading={submitting}>
                {submitting ? 'Saving…' : 'Save settings'}
              </Button>
            </div>
          </div>
        </Panel>
      </form>
    </div>
  )
}
