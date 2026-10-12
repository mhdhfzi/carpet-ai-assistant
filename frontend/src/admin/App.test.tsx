import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { AuthProvider } from './auth'

const OWNER = { id: 1, email: 'owner@example.com', name: 'Owner Name' }
const TOKEN_KEY = 'kilau-admin-token'

type Handler = (init: RequestInit | undefined) => { status: number; body?: unknown }

/** A fake backend keyed by "METHOD /path"; records the requests it receives. */
function mockBackend(routes: Record<string, Handler>) {
  const requests: { key: string; auth: string | null }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${url}`
      const headers = (init?.headers ?? {}) as Record<string, string>
      requests.push({ key, auth: headers.Authorization ?? null })
      const handler = routes[key]
      const { status, body } = handler ? handler(init) : { status: 404 }
      return new Response(body === undefined ? null : JSON.stringify(body), { status })
    }),
  )
  return requests
}

const loginOk: Handler = () => ({ status: 200, body: { access_token: 'tok-123', token_type: 'bearer', expires_in: 3600 } })
const meOk: Handler = () => ({ status: 200, body: OWNER })

function renderApp() {
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
}

async function signIn(password = 'correct horse') {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), 'owner@example.com')
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  return user
}

beforeEach(() => {
  sessionStorage.clear()
  window.location.hash = ''
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('owner dashboard', () => {
  it('shows the login page when signed out', () => {
    mockBackend({})
    renderApp()

    expect(screen.getByRole('heading', { name: 'Owner dashboard' })).toBeInTheDocument()
  })

  it('signs in, stores the session, and sends the token', async () => {
    const requests = mockBackend({ 'POST /api/auth/login': loginOk, 'GET /api/auth/me': meOk })
    renderApp()

    await signIn()

    expect(await screen.findByText('Owner Name')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Bookings' })).toBeInTheDocument()
    expect(requests.find((r) => r.key === 'GET /api/auth/me')?.auth).toBe('Bearer tok-123')
    expect(JSON.parse(sessionStorage.getItem(TOKEN_KEY) ?? '{}').token).toBe('tok-123')
  })

  it('shows a clear error for wrong credentials', async () => {
    mockBackend({ 'POST /api/auth/login': () => ({ status: 401, body: { detail: 'Incorrect email or password' } }) })
    renderApp()

    await signIn('wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('shows a generic error when the server is unavailable', async () => {
    mockBackend({ 'POST /api/auth/login': () => ({ status: 503 }) })
    renderApp()

    await signIn()

    expect(await screen.findByRole('alert')).toHaveTextContent('unavailable')
  })

  it('restores a stored session after a reload', async () => {
    sessionStorage.setItem(TOKEN_KEY, JSON.stringify({ token: 'tok-123', expiresAt: Date.now() + 60_000 }))
    mockBackend({ 'GET /api/auth/me': meOk })

    renderApp()

    expect(await screen.findByText('Owner Name')).toBeInTheDocument()
  })

  it('discards a stored session the server no longer accepts', async () => {
    sessionStorage.setItem(TOKEN_KEY, JSON.stringify({ token: 'old', expiresAt: Date.now() + 60_000 }))
    mockBackend({ 'GET /api/auth/me': () => ({ status: 401 }) })

    renderApp()

    expect(await screen.findByRole('heading', { name: 'Owner dashboard' })).toBeInTheDocument()
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('ignores an expired stored token without calling the server', () => {
    sessionStorage.setItem(TOKEN_KEY, JSON.stringify({ token: 'old', expiresAt: Date.now() - 1 }))
    mockBackend({})

    renderApp()

    expect(screen.getByRole('heading', { name: 'Owner dashboard' })).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('signs out', async () => {
    mockBackend({ 'POST /api/auth/login': loginOk, 'GET /api/auth/me': meOk })
    renderApp()
    const user = await signIn()
    await screen.findByText('Owner Name')

    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(screen.getByRole('heading', { name: 'Owner dashboard' })).toBeInTheDocument()
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('switches pages with the navigation', async () => {
    mockBackend({ 'POST /api/auth/login': loginOk, 'GET /api/auth/me': meOk })
    renderApp()
    await signIn()
    await screen.findByText('Owner Name')

    act(() => {
      window.location.hash = '#/analytics'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })

    expect(screen.getByRole('heading', { name: 'Analytics' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analytics' })).toHaveAttribute('aria-current', 'page')
  })
})
