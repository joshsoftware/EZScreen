import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getApplicationDetailRequest,
  getJobApplicantsRequest,
  getJobRequest,
} from './api'
import { queryKeys } from '../../lib/queryKeys'

export function useJobQuery(jobId, options = {}) {
  return useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => getJobRequest(jobId),
    enabled: Boolean(jobId),
    ...options,
  })
}

export function useJobApplicantsQuery(jobId, params = {}, options = {}) {
  const page = params.page ?? 1
  const limit = params.limit ?? 50
  return useQuery({
    queryKey: queryKeys.jobApplicants(jobId, { page, limit }),
    queryFn: async () => {
      const data = await getJobApplicantsRequest(jobId, { page, limit })
      return Array.isArray(data) ? data : []
    },
    enabled: Boolean(jobId),
    ...options,
  })
}

export function useApplicationQuery(applicationId, options = {}) {
  return useQuery({
    queryKey: queryKeys.application(applicationId),
    queryFn: () => getApplicationDetailRequest(applicationId),
    enabled: Boolean(applicationId),
    ...options,
  })
}

export function useJobQueryClient() {
  const queryClient = useQueryClient()

  return {
    setJobData(jobId, updater) {
      if (!jobId) return
      queryClient.setQueryData(queryKeys.job(jobId), updater)
    },
    invalidateJob(jobId) {
      if (!jobId) return
      return queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) })
    },
    invalidateJobApplicants(jobId) {
      if (!jobId) return
      return queryClient.invalidateQueries({
        queryKey: ['job', jobId, 'applicants'],
      })
    },
    invalidateApplication(applicationId) {
      if (!applicationId) return
      return queryClient.invalidateQueries({
        queryKey: queryKeys.application(applicationId),
      })
    },
  }
}
