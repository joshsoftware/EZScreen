import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import {
  getPlatformSettings,
  updatePlatformSettings,
} from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'

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
  const [saved, setSaved] = useState(false)
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
    setSaved(false)
    try {
      const updated = await updatePlatformSettings(token, form)
      setForm(updated)
      setSaved(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save settings')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <p className="text-body-sm text-on-surface-variant">Loading…</p>
  }

  return (
    <div className="max-w-2xl">
      <h1 className="font-headline-md text-headline-md mb-xs">Platform settings</h1>
      <p className="text-body-sm text-on-surface-variant mb-xl">
        Global defaults for tenants, email, and AI models. Org Admins manage their own branding.
      </p>

      <form onSubmit={onSubmit}>
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
          <h2 className="font-headline-sm text-headline-sm mb-md">General</h2>
          <div className="space-y-md">
            <Field
              label="Platform name"
              value={form.platform_name}
              onChange={(v) => setForm((f) => ({ ...f, platform_name: v }))}
            />
            <Field
              label="Default support email"
              type="email"
              value={form.support_email}
              onChange={(v) => setForm((f) => ({ ...f, support_email: v }))}
            />
            <div>
              <label className="block font-label-md text-label-md mb-xs">
                Default timezone
              </label>
              <select
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm bg-surface-container-lowest"
                value={form.timezone}
                onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
              >
                <option value="UTC">UTC</option>
                <option value="Asia/Kolkata">Asia/Kolkata</option>
                <option value="America/New_York">America/New_York</option>
              </select>
            </div>
          </div>
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg mt-lg">
          <h2 className="font-headline-sm text-headline-sm mb-md">AI & pipelines</h2>
          <div className="space-y-md">
            <div>
              <label className="block font-label-md text-label-md mb-xs">
                Default extraction model
              </label>
              <select
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm bg-surface-container-lowest"
                value={form.extraction_model}
                onChange={(e) =>
                  setForm((f) => ({ ...f, extraction_model: e.target.value }))
                }
              >
                <option value="gemma-parse-v2">gemma-parse-v2</option>
                <option value="gemma-parse-v1">gemma-parse-v1</option>
              </select>
            </div>
            <div>
              <label className="block font-label-md text-label-md mb-xs">
                Screening evaluation model
              </label>
              <select
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm bg-surface-container-lowest"
                value={form.screening_model}
                onChange={(e) =>
                  setForm((f) => ({ ...f, screening_model: e.target.value }))
                }
              >
                <option value="gemma-screen-v3">gemma-screen-v3</option>
                <option value="gemma-screen-v2">gemma-screen-v2</option>
              </select>
            </div>
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
        </div>

        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg mt-lg">
          <h2 className="font-headline-sm text-headline-sm mb-md">Security</h2>
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
            <div>
              <label className="block font-label-md text-label-md mb-xs">
                Invite link expiry (days)
              </label>
              <input
                type="number"
                min={1}
                max={90}
                className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
                value={form.invite_expiry_days}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    invite_expiry_days: Number(e.target.value) || 7,
                  }))
                }
              />
            </div>
            {error ? (
              <p className="text-body-sm text-error" role="alert">
                {error}
              </p>
            ) : null}
            {saved ? (
              <p className="text-body-sm text-[#065F46]">Settings saved.</p>
            ) : null}
            <div className="flex gap-sm pt-md">
              <Link
                to="/super-admin/orgs"
                className="inline-flex items-center justify-center h-10 px-md border border-outline-variant text-on-surface rounded-DEFAULT font-label-md text-label-md hover:bg-surface-container-low transition-colors"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={submitting}
                className="h-10 px-md bg-primary text-on-primary rounded-DEFAULT font-label-md text-label-md disabled:opacity-60"
              >
                {submitting ? 'Saving…' : 'Save settings'}
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text' }) {
  return (
    <div>
      <label className="block font-label-md text-label-md mb-xs">{label}</label>
      <input
        type={type}
        className="w-full h-11 px-md border border-outline-variant rounded-DEFAULT text-body-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}
