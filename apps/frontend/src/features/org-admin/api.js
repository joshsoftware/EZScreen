import { apiRequest } from '../../lib/api/client'

export function getOrganizationRequest(organizationId) {
  return apiRequest(`/api/v1/organizations/${organizationId}`, {
    method: 'GET',
  })
}

export function updateOrganizationRequest(organizationId, body) {
  return apiRequest(`/api/v1/organizations/${organizationId}`, {
    method: 'PUT',
    body,
  })
}

export function listOrgUsersRequest(organizationId) {
  return apiRequest(`/api/v1/organizations/${organizationId}/users`, {
    method: 'GET',
  })
}

export function provisionOrgUserRequest(organizationId, body) {
  return apiRequest(`/api/v1/organizations/${organizationId}/users`, {
    method: 'POST',
    body,
  })
}
