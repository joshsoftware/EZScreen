import { useEffect, useState } from 'react'
import { useAuth } from '../../features/auth/AuthContext'
import { getDetailedHealth } from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { PageHeader, Panel, StatCard } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { Stagger, StaggerItem } from '../../components/motion/Motion'

function statusTone(status) {
  if (status === 'healthy') return 'success'
  if (status === 'degraded') return 'warning'
  return 'danger'
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
    return <Alert>{error}</Alert>
  }
  if (!health) {
    return <PageSkeleton />
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
      <PageHeader
        title="System health"
        description="Platform services, workers, and AI pipeline status."
        actions={
          <Badge tone={statusTone(health.status)}>
            {health.status === 'healthy'
              ? 'All systems operational'
              : health.status === 'degraded'
                ? 'Degraded'
                : 'Issues detected'}
          </Badge>
        }
      />

      <Stagger className="grid md:grid-cols-4 gap-md mb-xl">
        <StaggerItem>
          <StatCard
            label="Organizations"
            value={String(health.stats.organizations ?? 0)}
          />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Users" value={String(health.stats.users ?? 0)} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Jobs" value={String(health.stats.jobs ?? 0)} />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="Uptime (s)"
            value={String(health.stats.uptime_seconds ?? 0)}
          />
        </StaggerItem>
      </Stagger>

      <Stagger className="grid lg:grid-cols-2 gap-lg">
        <StaggerItem>
          <Panel title="Services">
            <ul className="divide-y divide-outline-variant -mt-sm">
              {services.map((svc) => (
                <li key={svc.name} className="flex items-center justify-between py-md gap-md">
                  <div>
                    <p className="text-body-sm font-medium">{svc.name}</p>
                    <p className="text-label-md text-on-surface-variant">{svc.detail}</p>
                  </div>
                  <Badge tone={statusTone(svc.status)} className="shrink-0">
                    {svc.status}
                  </Badge>
                </li>
              ))}
            </ul>
          </Panel>
        </StaggerItem>
        <StaggerItem>
          <Panel title="Recent events">
            <ul className="space-y-md text-body-sm -mt-sm">
              {health.recent_events.map((ev) => (
                <li key={`${ev.time}-${ev.message}`} className="flex gap-sm">
                  <span className="text-label-md text-on-surface-variant w-16 shrink-0 font-mono-sm">
                    {ev.time}
                  </span>
                  <span>{ev.message}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </StaggerItem>
      </Stagger>
    </>
  )
}
