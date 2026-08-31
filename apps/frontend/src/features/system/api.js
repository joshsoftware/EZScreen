import { apiRequest } from '../../lib/api/client'

export function getWorkspaceHealth() {
  return apiRequest('/api/v1/system/health/status', {
    method: 'GET',
  })
}
