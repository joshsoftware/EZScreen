import { useEffect, useState } from 'react'
import { useAuth } from '../../features/auth/AuthContext'
import { getDetailedHealth } from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'

function statusPill(status) {
  if (status === 'healthy') {
    return 'bg-[#D1FAE5] text-[#065F46]'
  }
  if (status === 'degraded') {
    return 'bg-[#FEF3C7] text-[#92400E]'
  }
  return 'bg-error-container text-on-error-container'
}

export function SuperAdminHealthPage() {
  const { token } = useAuth()
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!token) return
    void getDetailedHealth(token)
      .then(setHealth)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load health'),
      )
  }, [token])

  if (error) {
    return <p className="text-body-sm text-error">{error}</p>
  }
  if (!health) {
    return <p className="text-body-sm text-on-surface-variant">Loading…</p>
  }

  const services = [
    health.api,
    health.parse_workers,
    health.screening_bot,
    health.object_storage,
    health.database,
  ]

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-md mb-xl">
        <div>
          <h1 className="font-headline-md text-headline-md">System health</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">
            Platform services, workers, and AI pipeline status.
          </p>
        </div>
        <span
          className={`text-label-md px-sm py-xs rounded-full ${statusPill(health.status)}`}
        >
          {health.status === 'healthy'
            ? 'All systems operational'
            : health.status === 'degraded'
              ? 'Degraded'
              : 'Issues detected'}
        </span>
      </div>

      <div className="grid md:grid-cols-4 gap-md mb-xl">
        <Stat
          label="Organizations"
          value={String(health.stats.organizations ?? 0)}
        />
        <Stat label="Users" value={String(health.stats.users ?? 0)} />
        <Stat label="Jobs" value={String(health.stats.jobs ?? 0)} />
        <Stat
          label="Uptime (s)"
          value={String(health.stats.uptime_seconds ?? 0)}
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-lg">
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
          <h2 className="font-headline-sm text-headline-sm mb-md">Services</h2>
          <ul className="divide-y divide-outline-variant">
            {services.map((svc) => (
              <li key={svc.name} className="flex items-center justify-between py-md gap-md">
                <div>
                  <p className="text-body-sm font-medium">{svc.name}</p>
                  <p className="text-label-md text-on-surface-variant">{svc.detail}</p>
                </div>
                <span
                  className={`text-label-md px-sm py-xs rounded-full shrink-0 ${statusPill(svc.status)}`}
                >
                  {svc.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
          <h2 className="font-headline-sm text-headline-sm mb-md">Recent events</h2>
          <ul className="space-y-md text-body-sm">
            {health.recent_events.map((ev) => (
              <li key={`${ev.time}-${ev.message}`} className="flex gap-sm">
                <span className="text-label-md text-on-surface-variant w-16 shrink-0 font-mono-sm">
                  {ev.time}
                </span>
                <span>{ev.message}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  )
}

function Stat({ label, value }) {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-lg">
      <p className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider mb-xs">
        {label}
      </p>
      <p className="font-headline-md text-headline-md text-on-surface">{value}</p>
    </div>
  )
}
