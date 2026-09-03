export function statusTone(status) {
  if (status === 'healthy') return 'success'
  if (status === 'degraded') return 'warning'
  return 'danger'
}

export function statusDotClass(status) {
  if (status === 'healthy') return 'bg-emerald-500'
  if (status === 'degraded') return 'bg-amber-500'
  return 'bg-red-500'
}

export function statusSummary(status) {
  if (status === 'healthy') return 'All services operational'
  if (status === 'degraded') return 'Some services degraded'
  return 'Service outage'
}

export function formatCheckedAt(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
