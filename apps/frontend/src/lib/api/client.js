import { API_BASE_URL } from '../../config/env'
import {
  getAccessToken,
  notifySessionExpired,
  setAccessToken,
} from '../auth/session'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const NO_REFRESH_PATHS = new Set([
  '/api/v1/auth/login',
  '/api/v1/auth/refresh',
  '/api/v1/auth/logout',
])

let refreshPromise = null

async function silentRefresh() {
  if (refreshPromise) {
    return refreshPromise
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        return null
      }
      const data = await response.json()
      setAccessToken(data.access_token)
      return data.access_token
    } catch {
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export async function apiRequest(path, options = {}) {
  const {
    body,
    token,
    skipAuthRetry = false,
    headers: initHeaders,
    ...rest
  } = options
  const headers = new Headers(initHeaders)
  const bearer = token ?? getAccessToken()

  if (body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (bearer) {
    headers.set('Authorization', `Bearer ${bearer}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers,
    credentials: 'include',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (
    response.status === 401 &&
    bearer &&
    !skipAuthRetry &&
    !NO_REFRESH_PATHS.has(path)
  ) {
    const newToken = await silentRefresh()
    if (newToken) {
      return apiRequest(path, {
        ...options,
        token: newToken,
        skipAuthRetry: true,
      })
    }
    notifySessionExpired()
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') {
        message = data.detail
      } else if (Array.isArray(data.detail) && data.detail[0]?.msg) {
        message = data.detail[0].msg
      }
    } catch {
      // keep default message
    }
    throw new ApiError(response.status, message)
  }

  if (response.status === 204) {
    return undefined
  }

  return response.json()
}
