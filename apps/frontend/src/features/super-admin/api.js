import { apiRequest } from '../../lib/api/client'

export function listOrganizations(token, params) {
  const search = new URLSearchParams()
  if (params?.q) search.set('q', params.q)
  if (params?.status && params.status !== 'all') search.set('status', params.status)
  const qs = search.toString()
  return apiRequest(`/api/v1/organizations${qs ? `?${qs}` : ''}`, {
    method: 'GET',
    token,
  })
}

export function createOrganization(token, body) {
  return apiRequest('/api/v1/organizations', {
    method: 'POST',
    token,
    body,
  })
}

export function getOrganization(token, id) {
  return apiRequest(`/api/v1/organizations/${id}`, {
    method: 'GET',
    token,
  })
}

export function updateOrganization(token, id, body) {
  return apiRequest(`/api/v1/organizations/${id}`, {
    method: 'PUT',
    token,
    body,
  })
}

export function deactivateOrganization(token, id) {
  return apiRequest(`/api/v1/organizations/${id}`, {
    method: 'DELETE',
    token,
  })
}

export function listOrgUsers(token, orgId) {
  return apiRequest(`/api/v1/organizations/${orgId}/users`, {
    method: 'GET',
    token,
  })
}

export function provisionOrgUser(token, orgId, body) {
  return apiRequest(`/api/v1/organizations/${orgId}/users`, {
    method: 'POST',
    token,
    body,
  })
}

export function getDetailedHealth(token) {
  return apiRequest('/api/v1/system/health/detailed', {
    method: 'GET',
    token,
  })
}

export function getPlatformSettings(token) {
  return apiRequest('/api/v1/system/settings', {
    method: 'GET',
    token,
  })
}

export function updatePlatformSettings(token, body) {
  return apiRequest('/api/v1/system/settings', {
    method: 'PUT',
    token,
    body,
  })
}
