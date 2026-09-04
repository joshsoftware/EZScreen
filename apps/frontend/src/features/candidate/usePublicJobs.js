import { useMutation, useQuery } from '@tanstack/react-query'
import {
  fetchPublicJobDetail,
  fetchPublicJobs,
  submitPublicJobApplication,
} from './api'
import { getResumeUploadUrlsRequest } from '../jobs/api'
import { queryKeys } from '../../lib/queryKeys'

export function usePublicJobsQuery(params = {}, options = {}) {
  return useQuery({
    queryKey: queryKeys.publicJobs(params),
    queryFn: async () => {
      const data = await fetchPublicJobs(params)
      return Array.isArray(data) ? data : []
    },
    ...options,
  })
}

export function usePublicJobDetailQuery(jobId, options = {}) {
  return useQuery({
    queryKey: queryKeys.publicJob(jobId),
    queryFn: () => fetchPublicJobDetail(jobId),
    enabled: Boolean(jobId),
    ...options,
  })
}

export function usePublicUploadUrlsMutation(options = {}) {
  return useMutation({
    mutationFn: ({ jobId, files }) => getResumeUploadUrlsRequest(jobId, files),
    ...options,
  })
}

export function useSubmitCandidateApplicationMutation(options = {}) {
  return useMutation({
    mutationFn: ({ jobId, payload }) => submitPublicJobApplication(jobId, payload),
    ...options,
  })
}

