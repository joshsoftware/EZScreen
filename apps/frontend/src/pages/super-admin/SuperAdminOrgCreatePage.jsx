import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '../../features/auth/AuthContext'
import { createOrganization } from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { PageHeader, Panel } from '../../components/ui/PageHeader'

export function SuperAdminOrgCreatePage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [domain, setDomain] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    if (!token) return
    setSubmitting(true)
    setError(null)
    try {
      const org = await createOrganization(token, {
        name: name.trim(),
        domain: domain.trim() || null,
        logo_url: logoUrl.trim() || null,
      })
      toast.success(`${org.name} created`)
      navigate(`/super-admin/orgs/${org.id}`, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create organization')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-xl">
      <PageHeader
        breadcrumb={
          <p className="text-label-md text-secondary">
            <Link to="/super-admin/orgs" className="hover:underline">
              Organizations
            </Link>{' '}
            / Create
          </p>
        }
        title="Create organization"
        description="Provision a new tenant with domain and branding."
      />
      <Panel>
        <form className="space-y-md" onSubmit={onSubmit}>
          <Input
            id="name"
            label="Company name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div>
            <Input
              id="domain"
              label="Subdomain"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="acme"
            />
            <p className="mt-xs text-label-md text-on-surface-variant">
              Becomes {domain.trim() || 'subdomain'}.ezscreen.io
            </p>
          </div>
          <Input
            id="logo"
            label="Logo URL (optional)"
            value={logoUrl}
            onChange={(e) => setLogoUrl(e.target.value)}
            placeholder="https://…"
          />
          {error ? <Alert>{error}</Alert> : null}
          <div className="flex gap-sm pt-md">
            <Button to="/super-admin/orgs" variant="secondary">
              Cancel
            </Button>
            <Button type="submit" loading={submitting}>
              {submitting ? 'Creating…' : 'Create organization'}
            </Button>
          </div>
        </form>
      </Panel>
    </div>
  )
}
