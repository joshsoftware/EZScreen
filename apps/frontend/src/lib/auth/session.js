/** In-memory access token (never persisted). */

let accessToken = null
const listeners = new Set()

export function getAccessToken() {
  return accessToken
}

export function setAccessToken(token) {
  accessToken = token
  for (const listener of listeners) {
    listener(accessToken)
  }
}

export function clearAccessToken() {
  setAccessToken(null)
}

export function subscribeAccessToken(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

let onSessionExpired = null

export function registerSessionExpiredHandler(handler) {
  onSessionExpired = handler
}

export function notifySessionExpired() {
  clearAccessToken()
  onSessionExpired?.()
}
