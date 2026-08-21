import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getOrganizationRequest } from './api'
import { queryKeys } from '../../lib/queryKeys'

export function useOrganizationQuery(organizationId, options = {}) {
  return useQuery({
    queryKey: queryKeys.organization(organizationId),
    queryFn: () => getOrganizationRequest(organizationId),
    enabled: Boolean(organizationId),
    ...options,
  })
}

export function useOrganizationQueryClient() {
  const queryClient = useQueryClient()

  return {
    setOrganizationData(organizationId, updater) {
      if (!organizationId) return
      queryClient.setQueryData(queryKeys.organization(organizationId), updater)
    },
    invalidateOrganization(organizationId) {
      if (!organizationId) return
      return queryClient.invalidateQueries({
        queryKey: queryKeys.organization(organizationId),
      })
    },
  }
}
