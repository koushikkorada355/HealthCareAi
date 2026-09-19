const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
export function token() { return localStorage.getItem('ca_token') || '' }
export async function api(path, { method = 'GET', body, auth = true, timeout = 20000 } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth && token()) headers.Authorization = `Bearer ${token()}`
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  let res
  try {
    res = await fetch(`${BASE}/api/v1${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined, signal: ctrl.signal })
  } catch (e) {
    if (e?.name === 'AbortError') throw new Error('Request timed out — please retry.')
    throw new Error('Network error — is the server reachable?')
  } finally { clearTimeout(timer) }
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = { raw: text } }
  if (!res.ok) throw new Error((data && data.detail) || `HTTP ${res.status}`)
  return data
}
export const health = () => fetch(`${BASE}/health`).then(r => r.json()).catch(() => ({ ok: false }))
