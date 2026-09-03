import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../lib/api/client'
import { getWorkspaceHealth } from './api'

const DEFAULT_POLL_MS = 60_000

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

  useEffect(() => {
    if (!pollMs) return undefined
    const timer = window.setInterval(() => {
      void refresh()
    }, pollMs)
    return () => window.clearInterval(timer)
  }, [pollMs, refresh])

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
