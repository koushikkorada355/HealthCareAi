import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import Shell from '../layouts/Shell.jsx'

const HOME = { platform_admin: '/admin', hospital_admin: '/hospital', doctor: '/doctor', patient: '/app' }

export function Require({ roles, children }) {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return <div className="p-10 text-center text-ink-soft">Loading…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={HOME[user.role] || '/'} replace />
  return <Shell>{children}</Shell>
}
