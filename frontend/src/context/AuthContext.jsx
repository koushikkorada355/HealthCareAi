import React, { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api/client.js'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

const DEMOS = [
  { label: 'System Admin', email: 'admin@gmail.com', password: '12345' },
  { label: 'Hospital admin', email: 'admin@citycare-general.org' },
  { label: 'Doctor', email: 'doc0@example.org' },
  { label: 'Patient', email: 'aarav@example.org' },
]
export { DEMOS }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    const t = localStorage.getItem('ca_token')
    if (!t) { setLoading(false); return }
    api('/auth/me').then(setUser).catch(() => localStorage.removeItem('ca_token')).finally(() => setLoading(false))
  }, [])
  const login = async (email, password) => {
    const r = await api('/auth/login', { method: 'POST', body: { email, password }, auth: false })
    localStorage.setItem('ca_token', r.access_token); setUser(r.user); return r.user
  }
  const register = async (payload) => {
    const r = await api('/auth/register', { method: 'POST', body: payload, auth: false })
    localStorage.setItem('ca_token', r.access_token); setUser(r.user); return r.user
  }
  const logout = () => {
    localStorage.removeItem('ca_token')
    setUser(null)
  }
  const home = () => !user ? '/' : user.role === 'platform_admin' ? '/admin' : user.role === 'hospital_admin' ? '/hospital' : user.role === 'doctor' ? '/doctor' : '/app'
  return <Ctx.Provider value={{ user, loading, login, register, logout, home }}>{children}</Ctx.Provider>
}
