import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function RequireRole({ roles, children, loginPath = '/super-admin/login' }) {
  const { user, isBootstrapping } = useAuth()
  const location = useLocation()

  if (isBootstrapping) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface text-on-surface-variant text-body-sm">
        Loading session…
      </div>
    )
  }

  if (!user) {
    return <Navigate to={loginPath} replace state={{ from: location.pathname }} />
  }

  if (!roles.includes(user.role)) {
    return <Navigate to={loginPath} replace />
  }

  return children
}
