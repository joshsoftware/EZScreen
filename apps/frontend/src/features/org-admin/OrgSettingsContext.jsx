import { createContext, useCallback, useContext, useMemo } from 'react'
import { useAuth } from '../auth/AuthContext'
import { useOrganizationQuery, useOrganizationQueryClient } from './useOrganizationQuery'
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
  const { data: org, isPending, refetch } = useOrganizationQuery(orgId)
  const { setOrganizationData } = useOrganizationQueryClient()

  const fitLabels = useMemo(
    () => normalizeFitLabels(org?.fit_labels),
    [org?.fit_labels],
  )

  const refresh = useCallback(async () => {
    if (!orgId) return
    await refetch()
  }, [orgId, refetch])

  const setFitLabels = useCallback(
    (next) => {
      if (!orgId) return
      const labels = normalizeFitLabels(next)
      setOrganizationData(orgId, (current) =>
        current
          ? { ...current, fit_labels: labels }
          : { fit_labels: labels },
      )
    },
    [orgId, setOrganizationData],
  )

  const value = useMemo(
    () => ({
      fitLabels,
      loading: Boolean(orgId) && isPending && !org,
      refresh,
      setFitLabels,
    }),
    [fitLabels, orgId, isPending, org, refresh, setFitLabels],
  )

  return (
    <OrgSettingsContext.Provider value={value}>{children}</OrgSettingsContext.Provider>
  )
}

export function useOrgSettings() {
  return useContext(OrgSettingsContext)
}
