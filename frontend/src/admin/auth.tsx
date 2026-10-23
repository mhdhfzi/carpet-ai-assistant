import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, ApiError, fetchMe, login, type Owner } from './api'

// By default the token is kept in sessionStorage: it survives a page reload but is cleared
// when the tab closes, which suits a shared family computer. "Ingat saya" (remember me)
// keeps a longer-lived token in localStorage instead, so a worker's own phone stays signed
// in after the app is closed. The password itself is never stored; the server still checks
// every request.
const TOKEN_KEY = 'kilau-admin-token'
// The last email used with "Ingat saya", to fill the login form in after signing out.
const EMAIL_KEY = 'kilau-admin-email'

type Stored = { token: string; expiresAt: number }

function readToken(): string | null {
  for (const storage of [sessionStorage, localStorage]) {
    try {
      const stored: Stored | null = JSON.parse(storage.getItem(TOKEN_KEY) ?? 'null')
      if (stored && stored.expiresAt > Date.now()) return stored.token
    } catch {
      /* unreadable: try the other one */
    }
  }
  return null
}

function writeToken(stored: Stored | null, remember = false) {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(TOKEN_KEY)
    if (stored) (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, JSON.stringify(stored))
  } catch {
    /* storage unavailable: the session just won't survive a reload */
  }
}

// oxlint-disable-next-line react/only-export-components
export function rememberedEmail(): string {
  try {
    return localStorage.getItem(EMAIL_KEY) ?? ''
  } catch {
    return ''
  }
}

function rememberEmail(email: string | null) {
  try {
    if (email) localStorage.setItem(EMAIL_KEY, email)
    else localStorage.removeItem(EMAIL_KEY)
  } catch {
    /* storage unavailable: the form just starts empty */
  }
}

export type AuthState =
  | { status: 'checking' }
  | { status: 'signed-out'; notice?: string }
  | { status: 'signed-in'; owner: Owner; token: string }

type AuthContextValue = {
  state: AuthState
  /** remember: stay signed in on this device after the app is closed ("Ingat saya"). */
  signIn: (email: string, password: string, remember?: boolean) => Promise<void>
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

  const signIn = useCallback(async (email: string, password: string, remember = false) => {
    const { access_token, expires_in } = await login(email, password, remember)
    const owner = await fetchMe(access_token)
    writeToken({ token: access_token, expiresAt: Date.now() + expires_in * 1000 }, remember)
    rememberEmail(remember ? email : null)
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
