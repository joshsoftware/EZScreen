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
