import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  getMeRequest,
  loginRequest,
  logoutRequest,
  refreshRequest,
} from './api'
import { ApiError } from '../../lib/api/client'
import {
  clearAccessToken,
  getAccessToken,
  registerSessionExpiredHandler,
  setAccessToken,
  subscribeAccessToken,
} from '../../lib/auth/session'
import { clearLegacyAuthStorage } from '../../lib/auth/storage'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => getAccessToken())
  const [isBootstrapping, setIsBootstrapping] = useState(true)

  useEffect(() => {
    return subscribeAccessToken((nextToken) => {
      setToken(nextToken)
    })
  }, [])

  useEffect(() => {
    registerSessionExpiredHandler(() => {
      setUser(null)
      setToken(null)
    })
  }, [])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      clearLegacyAuthStorage()

      try {
        await refreshRequest()
        if (cancelled) return
        const me = await getMeRequest(getAccessToken())
        if (cancelled) return
        setUser(me)
      } catch {
        clearAccessToken()
        if (!cancelled) {
          setUser(null)
        }
      } finally {
        if (!cancelled) setIsBootstrapping(false)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const result = await loginRequest(email, password)
    setAccessToken(result.access_token)
    setUser(result.user)
    return result.user
  }, [])

  const logout = useCallback(async () => {
    const currentToken = getAccessToken()
    clearAccessToken()
    setUser(null)
    if (!currentToken) return
    try {
      await logoutRequest(currentToken)
    } catch (err) {
      if (!(err instanceof ApiError)) {
        // no-op
      }
    }
  }, [])

  const isRole = useCallback((role) => user?.role === role, [user])

  const value = useMemo(
    () => ({ user, token, isBootstrapping, login, logout, isRole }),
    [user, token, isBootstrapping, login, logout, isRole],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
