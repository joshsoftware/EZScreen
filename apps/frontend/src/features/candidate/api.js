import { apiRequest } from '../../lib/api/client'

export async function fetchPublicJobs({ orgSubdomain, search, jobType, workType, page = 1, limit = 20 } = {}) {
  const queryParams = new URLSearchParams()
  if (orgSubdomain) queryParams.set('org_subdomain', orgSubdomain)
  if (search) queryParams.set('search', search)
  if (jobType) queryParams.set('job_type', jobType)
  if (workType) queryParams.set('work_type', workType)
  if (page) queryParams.set('page', String(page))
  if (limit) queryParams.set('limit', String(limit))

  const queryString = queryParams.toString()
  const path = `/api/v1/public/jobs${queryString ? `?${queryString}` : ''}`
  return apiRequest(path, { method: 'GET' })
}

export async function fetchPublicJobDetail(jobId) {
  return apiRequest(`/api/v1/public/jobs/${jobId}`, { method: 'GET' })
}

export async function submitPublicJobApplication(jobId, payload) {
  return apiRequest(`/api/v1/public/jobs/${jobId}/apply`, {
    method: 'POST',
    body: payload,
  })
}

