import { apiRequest, refreshSession } from '../../lib/api/client'
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

export function orgLoginRequest(email, password) {
  return apiRequest('/api/v1/auth/org/login', {
    method: 'POST',
    body: { email, password },
    skipAuthRetry: true,
  }).then((result) => {
    setAccessToken(result.access_token)
    return result
  })
}

export function refreshRequest() {
  return refreshSession().then((result) => {
    if (!result) {
      throw new Error('Refresh failed')
    }
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

export function changePasswordRequest(currentPassword, newPassword) {
  return apiRequest('/api/v1/auth/org/change-password', {
    method: 'POST',
    body: {
      current_password: currentPassword,
      new_password: newPassword,
    },
  })
}

export function forgotPasswordRequest(email) {
  return apiRequest('/api/v1/auth/org/forgot-password', {
    method: 'POST',
    body: { email },
    skipAuthRetry: true,
  })
}

export function resetPasswordRequest(token, newPassword) {
  return apiRequest('/api/v1/auth/org/reset-password', {
    method: 'POST',
    body: {
      token,
      new_password: newPassword,
    },
    skipAuthRetry: true,
  })
}
