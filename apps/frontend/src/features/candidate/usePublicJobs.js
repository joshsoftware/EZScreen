import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
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
    // { items, total } — total drives the page numbers.
    queryFn: () => fetchPublicJobs(params),
    // Keep the current page on screen while the next one loads.
    placeholderData: keepPreviousData,
    ...options,
  })
}

export function usePublicJobDetailQuery(jobId, orgName, options = {}) {
  return useQuery({
    queryKey: queryKeys.publicJob(jobId, orgName),
    queryFn: () => fetchPublicJobDetail(jobId, orgName),
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
    mutationFn: ({ jobId, payload, orgName }) =>
      submitPublicJobApplication(jobId, payload, orgName),
    ...options,
  })
}

