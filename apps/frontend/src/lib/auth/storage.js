/** Remove legacy localStorage session from pre-refresh-token auth. */

const LEGACY_STORAGE_KEY = 'ezscreen.auth.v1'

export function clearLegacyAuthStorage() {
  try {
    localStorage.removeItem(LEGACY_STORAGE_KEY)
  } catch {
    // private browsing / disabled storage
  }
}
