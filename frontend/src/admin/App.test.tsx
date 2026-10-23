import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { AuthProvider } from './auth'
import { DEMO_EMAIL, DEMO_PASSWORD } from './LoginPage'

const OWNER = { id: 1, email: 'owner@example.com', name: 'Owner Name', role: 'owner' }
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
  localStorage.clear()
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

  it('"Ingat saya" keeps the login after the app is closed and fills in the email', async () => {
    let sent: unknown
    mockBackend({
      'POST /api/auth/login': (init) => {
        sent = JSON.parse(String(init?.body))
        return loginOk(init)
      },
      'GET /api/auth/me': meOk,
    })
    const { unmount } = renderApp()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct horse')
    await user.click(screen.getByRole('checkbox', { name: /Ingat saya/ }))
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Owner Name')).toBeInTheDocument()
    expect(sent).toEqual({ email: 'owner@example.com', password: 'correct horse', remember: true })
    expect(JSON.parse(localStorage.getItem(TOKEN_KEY) ?? '{}').token).toBe('tok-123')
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(JSON.stringify(localStorage)).not.toContain('correct horse') // never the password

    // Closing the app clears sessionStorage; the remembered login survives.
    unmount()
    sessionStorage.clear()
    const reopened = renderApp()
    expect(await screen.findByText('Owner Name')).toBeInTheDocument()

    // After signing out, the email is filled in and the box stays ticked.
    reopened.unmount()
    localStorage.removeItem(TOKEN_KEY)
    renderApp()
    expect(screen.getByLabelText('Email')).toHaveValue('owner@example.com')
    expect(screen.getByRole('checkbox', { name: /Ingat saya/ })).toBeChecked()
  })

  it('signs in to the demo account with one click', async () => {
    let sent: unknown
    mockBackend({
      'POST /api/auth/login': (init) => {
        sent = JSON.parse(String(init?.body))
        return loginOk(init)
      },
      'GET /api/auth/me': () => ({ status: 200, body: { ...OWNER, name: 'Demo visitor', role: 'demo' } }),
      'GET /api/business': () => ({ status: 200, body: { name: 'Kilau Carpet Care', demo: true, bookings: true } }),
    })
    renderApp()

    await userEvent.setup().click(await screen.findByRole('button', { name: 'Try the demo account' }))

    expect(await screen.findByText('Demo · read-only')).toBeInTheDocument()
    expect(sent).toEqual({ email: DEMO_EMAIL, password: DEMO_PASSWORD })
  })

  it('shows a real business its own name and never offers the demo login', async () => {
    mockBackend({ 'GET /api/business': () => ({ status: 200, body: { name: 'Cuci-Cuci Senawang', demo: false, bookings: false } }) })
    renderApp()

    expect(await screen.findByText('Cuci-Cuci Senawang')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try the demo account' })).toBeNull()
  })

  it('hides the demo login if it cannot tell which business this is', async () => {
    const requests = mockBackend({})
    renderApp()

    await vi.waitFor(() => expect(requests.some((r) => r.key === 'GET /api/business')).toBe(true))
    expect(screen.queryByRole('button', { name: 'Try the demo account' })).toBeNull()
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

  it('ignores an expired stored token without calling the server', async () => {
    sessionStorage.setItem(TOKEN_KEY, JSON.stringify({ token: 'old', expiresAt: Date.now() - 1 }))
    const requests = mockBackend({})

    renderApp()

    expect(screen.getByRole('heading', { name: 'Owner dashboard' })).toBeInTheDocument()
    // Only the public business info is fetched; the expired token is never sent.
    await vi.waitFor(() => expect(requests.map((r) => r.key)).toEqual(['GET /api/business']))
    expect(requests.every((r) => r.auth === null)).toBe(true)
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
