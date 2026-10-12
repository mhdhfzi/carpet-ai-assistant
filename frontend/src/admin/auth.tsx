import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, ApiError, fetchMe, login, type Owner } from './api'

// The token is kept in sessionStorage: it survives a page reload but is cleared when the
// tab closes, which suits a shared family computer. The server still checks every request.
const TOKEN_KEY = 'kilau-admin-token'

type Stored = { token: string; expiresAt: number }

function readToken(): string | null {
  try {
    const stored: Stored | null = JSON.parse(sessionStorage.getItem(TOKEN_KEY) ?? 'null')
    return stored && stored.expiresAt > Date.now() ? stored.token : null
  } catch {
    return null
  }
}

function writeToken(stored: Stored | null) {
  try {
    if (stored) sessionStorage.setItem(TOKEN_KEY, JSON.stringify(stored))
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable: the session just won't survive a reload */
  }
}

export type AuthState =
  | { status: 'checking' }
  | { status: 'signed-out'; notice?: string }
  | { status: 'signed-in'; owner: Owner; token: string }

type AuthContextValue = {
  state: AuthState
  signIn: (email: string, password: string) => Promise<void>
  signOut: (notice?: string) => void
  /** The public demo login: it can look but not change anything (the server enforces this). */
  readOnly: boolean
  /** Calls the API as the logged-in owner; a 401 signs the owner out. */
  request: <T>(path: string, options?: { method?: string; body?: unknown }) => Promise<T>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() =>
    readToken() ? { status: 'checking' } : { status: 'signed-out' },
  )

  const signOut = useCallback((notice?: string) => {
    writeToken(null)
    setState({ status: 'signed-out', notice })
  }, [])

  // On load, confirm a stored token is still accepted (it may have expired or the
  // account may have been removed).
  useEffect(() => {
    const token = readToken()
    if (!token) return
    let cancelled = false
    fetchMe(token)
      .then((owner) => !cancelled && setState({ status: 'signed-in', owner, token }))
      .catch(() => !cancelled && signOut())
    return () => {
      cancelled = true
    }
  }, [signOut])

  const signIn = useCallback(async (email: string, password: string) => {
    const { access_token, expires_in } = await login(email, password)
    const owner = await fetchMe(access_token)
    writeToken({ token: access_token, expiresAt: Date.now() + expires_in * 1000 })
    setState({ status: 'signed-in', owner, token: access_token })
  }, [])

  const token = state.status === 'signed-in' ? state.token : null
  const request = useCallback(
    async <T,>(path: string, options: { method?: string; body?: unknown } = {}) => {
      try {
        return await api<T>(path, { ...options, token })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          signOut('Your session has expired. Please sign in again.')
        }
        throw error
      }
    },
    [token, signOut],
  )

  const readOnly = state.status === 'signed-in' && state.owner.role === 'demo'
  const value = useMemo(
    () => ({ state, signIn, signOut, request, readOnly }),
    [state, signIn, signOut, request, readOnly],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// The provider and its hook live together (the usual context pattern).
// oxlint-disable-next-line react/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
