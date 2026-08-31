import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Panel } from '../ui/PageHeader'
import {
  formatCheckedAt,
  statusSummary,
  statusTone,
} from '../../features/system/healthUtils'

export function ServiceHealthPanel({
  health,
  error,
  loading,
  refreshing,
  onRefresh,
}) {
  if (loading && !health) {
    return (
      <Panel title="System status">
        <p className="text-body-sm text-on-surface-variant">Checking services…</p>
      </Panel>
    )
  }

  const services = health?.services ?? []

  return (
    <Panel title="System status">
      <p className="text-body-sm text-on-surface-variant mb-md">
        Live status of AI processing and file storage used by your workspace.
      </p>
      <div className="mb-md flex flex-wrap items-center justify-between gap-sm">
        <div className="flex flex-wrap items-center gap-sm">
          {health?.status ? (
            <Badge tone={statusTone(health.status)}>{statusSummary(health.status)}</Badge>
          ) : null}
          {health?.checked_at ? (
            <span className="text-label-md text-on-surface-variant">
              Last checked {formatCheckedAt(health.checked_at)}
            </span>
          ) : null}
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={refreshing}
          onClick={() => void onRefresh?.()}
        >
          Refresh
        </Button>
      </div>

      {error ? (
        <p className="text-body-sm text-red-700 mb-md">{error}</p>
      ) : null}

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
  )
}
