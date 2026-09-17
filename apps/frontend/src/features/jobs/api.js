import { apiBlobRequest, apiRequest } from '../../lib/api/client'
import { API_BASE_URL } from '../../config/env'
import {
  getAccessToken,
  notifySessionExpired,
  setAccessToken,
} from '../../lib/auth/session'

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

export function getInterviewSessionRequest(sessionId) {
  return apiRequest(`/api/v1/interview-sessions/${sessionId}`)
}

export function getInterviewAnalysisRequest(sessionId) {
  return apiRequest(`/api/v1/interview-sessions/${sessionId}/analysis`)
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

/**
 * Open an authenticated SSE stream for one bulk ingest batch.
 * Calls onEvent for each progress payload until done or aborted.
 */
export async function streamResumeIngestProgress(
  jobId,
  batchId,
  { onEvent, signal } = {},
) {
  const path = `/api/v1/jobs/${encodeURIComponent(jobId)}/applications/ingest-stream?batch_id=${encodeURIComponent(batchId)}`

  async function openStream(token) {
    const headers = new Headers({ Accept: 'text/event-stream' })
    if (token) headers.set('Authorization', `Bearer ${token}`)
    return fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers,
      credentials: 'include',
      signal,
    })
  }

  let bearer = getAccessToken()
  let response = await openStream(bearer)
  if (response.status === 401 && bearer) {
    const refresh = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      signal,
    })
    if (refresh.ok) {
      const data = await refresh.json()
      if (data?.access_token) {
        setAccessToken(data.access_token)
        bearer = data.access_token
        response = await openStream(bearer)
      }
    }
    if (response.status === 401) {
      notifySessionExpired()
      throw new Error('Session expired')
    }
  }

  if (!response.ok) {
    throw new Error(`Ingest stream failed (${response.status})`)
  }
  if (!response.body) {
    throw new Error('Ingest stream unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() || ''
    for (const chunk of chunks) {
      const dataLine = chunk
        .split('\n')
        .map((line) => line.trimEnd())
        .find((line) => line.startsWith('data:'))
      if (!dataLine) continue
      const jsonText = dataLine.replace(/^data:\s?/, '')
      if (!jsonText) continue
      let payload
      try {
        payload = JSON.parse(jsonText)
      } catch {
        continue
      }
      onEvent?.(payload)
      if (payload?.done) return
    }
  }
}

export function rerunJobFitRequest(jobId, applicationId) {
  return apiRequest(`/api/v1/jobs/${jobId}/applications/${applicationId}/rerun-fit`, {
    method: 'POST',
  })
}

export function reEvaluateApplicationRequest(jobId, applicationId) {
  return apiRequest(`/api/v1/jobs/${jobId}/applicants/${applicationId}/re-evaluate`, {
    method: 'POST',
  })
}

export function getReEvaluationStatusRequest(jobId, applicationId) {
  return apiRequest(
    `/api/v1/jobs/${jobId}/applicants/${applicationId}/re-evaluation-status`,
    { method: 'GET' },
  )
}
