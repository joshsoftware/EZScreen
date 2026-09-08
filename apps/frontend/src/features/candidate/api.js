import { apiRequest } from '../../lib/api/client'
import { ORG_URL_SLUG } from './constants'

export async function fetchPublicJobs({ orgName = ORG_URL_SLUG, search, jobType, workType, page = 1, limit = 20 } = {}) {
  const queryParams = new URLSearchParams()
  if (search) queryParams.set('search', search)
  if (jobType) queryParams.set('job_type', jobType)
  if (workType) queryParams.set('work_type', workType)
  if (page) queryParams.set('page', String(page))
  if (limit) queryParams.set('limit', String(limit))

  const queryString = queryParams.toString()
  const path = `/api/v1/public/${encodeURIComponent(orgName)}/jobs${queryString ? `?${queryString}` : ''}`
  return apiRequest(path, { method: 'GET' })
}

export async function fetchPublicJobDetail(jobId, orgName = ORG_URL_SLUG) {
  return apiRequest(`/api/v1/public/${encodeURIComponent(orgName)}/jobs/${jobId}`, { method: 'GET' })
}

export async function submitPublicJobApplication(jobId, payload, orgName = ORG_URL_SLUG) {
  return apiRequest(`/api/v1/public/${encodeURIComponent(orgName)}/jobs/${jobId}/apply`, {
    method: 'POST',
    body: payload,
  })
}

