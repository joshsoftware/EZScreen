import { apiBlobRequest, apiRequest } from '../../lib/api/client'

export function listJobsRequest({ status, page = 1, limit = 50 } = {}) {
  const search = new URLSearchParams()
  search.set('page', String(page))
  search.set('limit', String(limit))
  if (status) search.set('status', status)
  return apiRequest(`/api/v1/jobs?${search.toString()}`, {
    method: 'GET',
  })
}

export function getJobRequest(jobId) {
  return apiRequest(`/api/v1/jobs/${jobId}`, {
    method: 'GET',
  })
}

export function createJobRequest(body) {
  return apiRequest('/api/v1/jobs', {
    method: 'POST',
    body,
  })
}

export function cloneJobRequest(jobId) {
  return apiRequest(`/api/v1/jobs/${jobId}/clone`, {
    method: 'POST',
  })
}

export function updateJobRequest(jobId, body) {
  return apiRequest(`/api/v1/jobs/${jobId}`, {
    method: 'PUT',
    body,
  })
}

export function regenerateJobScreeningQuestionsRequest(jobId) {
  return apiRequest(`/api/v1/jobs/${jobId}/screening-questions/regenerate`, {
    method: 'POST',
  })
}

export function updateJobScreeningQuestionsRequest(jobId, questions) {
  return apiRequest(`/api/v1/jobs/${jobId}/screening-questions`, {
    method: 'PUT',
    body: { questions },
  })
}

export function getJobApplicantsRequest(jobId, { page = 1, limit = 50 } = {}) {
  const search = new URLSearchParams()
  search.set('page', String(page))
  search.set('limit', String(limit))
  return apiRequest(`/api/v1/jobs/${jobId}/applicants?${search.toString()}`, {
    method: 'GET',
  })
}

export function getApplicationDetailRequest(applicationId) {
  return apiRequest(`/api/v1/applications/${applicationId}`, {
    method: 'GET',
  })
}

export function getApplicationResumeRequest(applicationId) {
  return apiRequest(`/api/v1/applications/${applicationId}/resume`, {
    method: 'GET',
  })
}

/** Stream resume bytes via the API (avoids insecure MinIO HTTP downloads). */
export function fetchApplicationResumeFile(applicationId, disposition = 'inline') {
  const search = new URLSearchParams()
  search.set('disposition', disposition)
  return apiBlobRequest(
    `/api/v1/applications/${applicationId}/resume/file?${search.toString()}`,
    { method: 'GET' },
  )
}

export function getApplicationTimelineRequest(applicationId) {
  return apiRequest(`/api/v1/applications/${applicationId}/timeline`, {
    method: 'GET',
  })
}

export function rejectApplicationRequest(applicationId, body = {}) {
  return apiRequest(`/api/v1/applications/${applicationId}/reject`, {
    method: 'POST',
    body,
  })
}

export function scheduleInterviewSessionRequest(body) {
  return apiRequest('/api/v1/interview-sessions', {
    method: 'POST',
    body,
  })
}

export function rescheduleInterviewSessionRequest(sessionId, body) {
  return apiRequest(`/api/v1/interview-sessions/${sessionId}/reschedule`, {
    method: 'POST',
    body,
  })
}

export function getResumeUploadUrlsRequest(jobId, files) {
  return apiRequest(`/api/v1/jobs/${jobId}/applications/upload-urls`, {
    method: 'POST',
    body: { files },
  })
}

export function enqueueBulkResumesRequest(jobId, resumes) {
  return apiRequest(`/api/v1/jobs/${jobId}/applications/bulk`, {
    method: 'POST',
    body: { resumes },
  })
}

export function getResumeIngestErrorsRequest(jobId, { since } = {}) {
  const search = new URLSearchParams()
  if (since) search.set('since', since)
  const query = search.toString()
  return apiRequest(
    `/api/v1/jobs/${jobId}/applications/ingest-errors${query ? `?${query}` : ''}`,
    { method: 'GET' },
  )
}

export function rerunJobFitRequest(jobId, applicationId) {
  return apiRequest(`/api/v1/jobs/${jobId}/applications/${applicationId}/rerun-fit`, {
    method: 'POST',
  })
}
