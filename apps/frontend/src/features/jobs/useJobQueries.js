import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getApplicationDetailRequest,
  getApplicationTimelineRequest,
  getInterviewAnalysisRequest,
  getInterviewSessionRequest,
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

// The API returns at most 50 applicants per page.
const APPLICANTS_PAGE_SIZE = 50
const MAX_APPLICANT_PAGES = 100

/** All of a job's applicants. The list is sorted by score, so a new low-scoring
 * candidate on a job with 50+ applicants was beyond page 1 and never shown (Bug-026). */
export function useJobApplicantsQuery(jobId, options = {}) {
  return useQuery({
    queryKey: queryKeys.jobApplicants(jobId),
    queryFn: async () => {
      const all = []
      for (let page = 1; page <= MAX_APPLICANT_PAGES; page += 1) {
        const data = await getJobApplicantsRequest(jobId, { page, limit: APPLICANTS_PAGE_SIZE })
        const rows = Array.isArray(data) ? data : []
        all.push(...rows)
        if (rows.length < APPLICANTS_PAGE_SIZE) break
      }
      return all
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

export function useApplicationTimelineQuery(applicationId, options = {}) {
  return useQuery({
    queryKey: queryKeys.applicationTimeline(applicationId),
    queryFn: async () => {
      const data = await getApplicationTimelineRequest(applicationId)
      return Array.isArray(data) ? data : []
    },
    enabled: Boolean(applicationId),
    ...options,
  })
}

export function useInterviewSessionQuery(sessionId, options = {}) {
  return useQuery({
    queryKey: queryKeys.interviewSession(sessionId),
    queryFn: () => getInterviewSessionRequest(sessionId),
    enabled: Boolean(sessionId),
    ...options,
  })
}

export function useInterviewAnalysisQuery(sessionId, options = {}) {
  return useQuery({
    queryKey: queryKeys.interviewAnalysis(sessionId),
    queryFn: () => getInterviewAnalysisRequest(sessionId),
    enabled: Boolean(sessionId),
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
    invalidateApplicationTimeline(applicationId) {
      if (!applicationId) return
      return queryClient.invalidateQueries({
        queryKey: queryKeys.applicationTimeline(applicationId),
      })
    },
    invalidateInterviewSession(sessionId) {
      if (!sessionId) return
      return queryClient.invalidateQueries({
        queryKey: queryKeys.interviewSession(sessionId),
      })
    },
    invalidateInterviewAnalysis(sessionId) {
      if (!sessionId) return
      return queryClient.invalidateQueries({
        queryKey: queryKeys.interviewAnalysis(sessionId),
      })
    },
  }
}
