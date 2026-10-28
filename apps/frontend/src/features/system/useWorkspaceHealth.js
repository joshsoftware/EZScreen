import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../lib/api/client'
import { getWorkspaceHealth } from './api'

const DEFAULT_POLL_MS = 60_000
// While a service is reported unhealthy, check again sooner so the banner
// clears on its own once it recovers (e.g. ai-core restarting) instead of
// staying up until the next minute's poll or a page refresh.
const UNHEALTHY_POLL_MS = 10_000

export function useWorkspaceHealth(pollMs = DEFAULT_POLL_MS) {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const data = await getWorkspaceHealth()
      setHealth(data)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load service status')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const unhealthy = (health && health.status !== 'healthy') || Boolean(error)

  useEffect(() => {
    if (!pollMs) return undefined
    const interval = unhealthy ? Math.min(pollMs, UNHEALTHY_POLL_MS) : pollMs
    const timer = window.setInterval(() => {
      void refresh()
    }, interval)
    return () => window.clearInterval(timer)
  }, [pollMs, refresh, unhealthy])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [refresh])

  return {
    health,
    error,
    loading,
    refreshing,
    refresh,
    status: health?.status ?? null,
    services: health?.services ?? [],
  }
}
