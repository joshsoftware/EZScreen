import { Link } from 'react-router-dom'
import { Alert } from '../ui/Alert'
import { statusSummary } from '../../features/system/healthUtils'

export function ServiceHealthBanner({ status, services = [] }) {
  if (!status || status === 'healthy') return null

  const down = services.filter((svc) => svc.status === 'down')
  const degraded = services.filter((svc) => svc.status === 'degraded')
  const affected = [...down, ...degraded]
  const names = affected.map((svc) => svc.name).join(', ')

  return (
    <Alert tone={down.length > 0 ? 'error' : 'warning'}>
      <div className="flex flex-col gap-xs sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium">{statusSummary(status)}</p>
          <p className="text-body-sm mt-xs opacity-90">
            {names
              ? `${names} — resume scoring, JD parsing, or uploads may fail.`
              : 'Some platform services are unavailable.'}
          </p>
        </div>
        <Link
          to="/org-admin/settings#system-status"
          className="text-body-sm font-medium underline underline-offset-2 shrink-0"
        >
          View details
        </Link>
      </div>
    </Alert>
  )
}
