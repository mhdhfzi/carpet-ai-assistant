// HTTP calls for the owner dashboard. Same origin by default (Vite proxies /api in
// development); set VITE_API_URL when the API is hosted elsewhere.

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, detail: string) {
    super(detail || `Request failed (${status})`)
    this.status = status
  }
}

export type Owner = { id: number; email: string; name: string; role: 'owner' | 'demo' }

export type TokenResponse = { access_token: string; token_type: string; expires_in: number }

type RequestOptions = { method?: string; body?: unknown; token?: string | null }

export async function api<T>(path: string, { method = 'GET', body, token }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) throw new ApiError(response.status, await errorDetail(response))
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

/** FastAPI errors look like {"detail": "..."} (or a list, for validation errors). */
async function errorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : ''
  } catch {
    return ''
  }
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return api<TokenResponse>('/api/auth/login', { method: 'POST', body: { email, password } })
}

export function fetchMe(token: string): Promise<Owner> {
  return api<Owner>('/api/auth/me', { token })
}
