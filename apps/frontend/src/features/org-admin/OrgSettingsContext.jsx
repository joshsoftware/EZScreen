import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { getOrganizationRequest } from './api'
import {
  DEFAULT_FIT_LABELS,
  normalizeFitLabels,
} from '../jobs/applicationFields'

const OrgSettingsContext = createContext({
  fitLabels: DEFAULT_FIT_LABELS.map((item) => ({ ...item })),
  loading: false,
  refresh: async () => {},
  setFitLabels: () => {},
})

export function OrgSettingsProvider({ children }) {
  const { user } = useAuth()
  const orgId = user?.organization_id
  const [fitLabels, setFitLabelsState] = useState(() =>
    DEFAULT_FIT_LABELS.map((item) => ({ ...item })),
  )
  const [loading, setLoading] = useState(Boolean(orgId))

  const refresh = useCallback(async () => {
    if (!orgId) {
      setFitLabelsState(DEFAULT_FIT_LABELS.map((item) => ({ ...item })))
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const org = await getOrganizationRequest(orgId)
      setFitLabelsState(normalizeFitLabels(org?.fit_labels))
    } catch {
      setFitLabelsState(DEFAULT_FIT_LABELS.map((item) => ({ ...item })))
    } finally {
      setLoading(false)
    }
  }, [orgId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const setFitLabels = useCallback((next) => {
    setFitLabelsState(normalizeFitLabels(next))
  }, [])

  const value = useMemo(
    () => ({
      fitLabels,
      loading,
      refresh,
      setFitLabels,
    }),
    [fitLabels, loading, refresh, setFitLabels],
  )

  return (
    <OrgSettingsContext.Provider value={value}>{children}</OrgSettingsContext.Provider>
  )
}

export function useOrgSettings() {
  return useContext(OrgSettingsContext)
}
