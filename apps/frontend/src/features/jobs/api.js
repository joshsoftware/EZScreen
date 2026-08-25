import { apiRequest } from '../../lib/api/client'

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

export function updateJobRequest(jobId, body) {
  return apiRequest(`/api/v1/jobs/${jobId}`, {
    method: 'PUT',
    body,
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

export function getApplicationTimelineRequest(applicationId) {
  return apiRequest(`/api/v1/applications/${applicationId}/timeline`, {
    method: 'GET',
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

export function rerunJobFitRequest(jobId, applicationId) {
  return apiRequest(`/api/v1/jobs/${jobId}/applications/${applicationId}/rerun-fit`, {
    method: 'POST',
  })
}
