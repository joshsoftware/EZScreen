import { apiRequest } from '../../lib/api/client'
import { setAccessToken } from '../../lib/auth/session'

export function loginRequest(email, password) {
  return apiRequest('/api/v1/auth/login', {
    method: 'POST',
    body: { email, password },
    skipAuthRetry: true,
  }).then((result) => {
    setAccessToken(result.access_token)
    return result
  })
}

export function refreshRequest() {
  return apiRequest('/api/v1/auth/refresh', {
    method: 'POST',
    skipAuthRetry: true,
  }).then((result) => {
    setAccessToken(result.access_token)
    return result
  })
}

export function getMeRequest(token) {
  return apiRequest('/api/v1/auth/me', {
    method: 'GET',
    token,
  })
}

export function logoutRequest(token) {
  return apiRequest('/api/v1/auth/logout', {
    method: 'POST',
    token,
    body: {},
    skipAuthRetry: true,
  })
}
