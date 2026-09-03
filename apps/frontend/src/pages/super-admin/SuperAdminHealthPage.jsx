import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../features/auth/AuthContext'
import { getDetailedHealth } from '../../features/super-admin/api'
import { ApiError } from '../../lib/api/client'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader, Panel, StatCard } from '../../components/ui/PageHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { Stagger, StaggerItem } from '../../components/motion/Motion'

const POLL_INTERVAL_MS = 60_000

function statusTone(status) {
  if (status === 'healthy') return 'success'
  if (status === 'degraded') return 'warning'
  return 'danger'
}

function formatCheckedAt(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function SuperAdminHealthPage() {
  const { token } = useAuth()
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const loadHealth = useCallback(async () => {
    if (!token) return
    setRefreshing(true)
    try {
      const data = await getDetailedHealth(token)
      setHealth(data)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load health')
    } finally {
      setRefreshing(false)
    }
  }, [token])

  useEffect(() => {
    void loadHealth()
  }, [loadHealth])

  useEffect(() => {
    if (!token) return undefined
    const timer = window.setInterval(() => {
      void loadHealth()
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [token, loadHealth])

  if (error && !health) {
    return <Alert>{error}</Alert>
  }
  if (!health) {
    return <PageSkeleton />
  }

  const services = [
    health.database,
    health.api,
    health.ai_core_services ?? health.parse_workers,
    health.object_storage,
    health.screening_bot,
  ]

  const hasDown = services.some((svc) => svc.status === 'down')

  return (
    <>
      <PageHeader
        title="System health"
        description="Live status of database, AI services, and storage."
        actions={
          <div className="flex flex-wrap items-center gap-sm">
            <span className="text-label-md text-on-surface-variant">
              Last checked {formatCheckedAt(health.checked_at)}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={refreshing}
              onClick={() => void loadHealth()}
            >
              Refresh
            </Button>
            <Badge tone={statusTone(health.status)}>
              {health.status === 'healthy'
                ? 'All systems operational'
                : health.status === 'degraded'
                  ? 'Degraded'
                  : 'Issues detected'}
            </Badge>
          </div>
        }
      />

      {error ? (
        <div className="mb-lg">
          <Alert>{error}</Alert>
        </div>
      ) : null}

      {hasDown ? (
        <div className="mb-lg">
          <Alert>
            One or more services are down. JD parsing, resume scoring, and file uploads may
            fail until they recover.
          </Alert>
        </div>
      ) : null}

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
