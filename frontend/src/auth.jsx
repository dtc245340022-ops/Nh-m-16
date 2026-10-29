import { useEffect, useMemo, useState } from 'react'
import { api, TOKEN_KEY } from './api.js'
import { AuthContext } from './auth-context.js'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem(TOKEN_KEY)))

  useEffect(() => {
    let active = true
    function handleExpired() {
      setUser(null)
      setLoading(false)
    }
    window.addEventListener('auth:expired', handleExpired)
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      return () => {
        active = false
        window.removeEventListener('auth:expired', handleExpired)
      }
    }
    api.get('/auth/me')
      .then(({ data }) => { if (active) setUser(data) })
      .catch(() => { if (active) setUser(null) })
      .finally(() => { if (active) setLoading(false) })

    return () => {
      active = false
      window.removeEventListener('auth:expired', handleExpired)
    }
  }, [])

  async function login(email, password) {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem(TOKEN_KEY, data.access_token)
    const profile = await api.get('/auth/me')
    setUser(profile.data)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
