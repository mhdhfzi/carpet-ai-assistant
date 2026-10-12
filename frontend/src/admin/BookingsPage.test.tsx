import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { AuthProvider } from './auth'
import type { Booking, Conversation } from './types'

type Call = { method: string; path: string; query: URLSearchParams; body: unknown }
type Reply = { status?: number; body?: unknown }
type Handler = (call: Call) => Reply

/** Fake backend matched on "METHOD /path" (query string ignored); records every call. */
function mockBackend(routes: Record<string, Handler>) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const parsed = new URL(url, 'http://test')
      const call = {
        method: init?.method ?? 'GET',
        path: parsed.pathname,
        query: parsed.searchParams,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      }
      calls.push(call)
      const handler = routes[`${call.method} ${call.path}`]
      const { status = 200, body } = handler ? handler(call) : { status: 404 }
      return new Response(body === undefined ? null : JSON.stringify(body), { status })
    }),
  )
  return calls
}

function booking(overrides: Partial<Booking> = {}): Booking {
  return {
    id: 1,
    customer: { id: 7, name: 'Aminah Rahman', phone: '+60300000001', area: 'Seremban 2', address: '1, Jalan Contoh 1' },
    conversation_id: 11,
    scheduled_start: '2026-10-15T02:00:00Z', // Thu 15 Oct, 10:00 in Malaysia
    scheduled_end: '2026-10-15T02:30:00Z',
    location: 'customer_home',
    status: 'pending',
    estimated_price: '250.00',
    estimated_price_max: '400.00',
    notes: null,
    items: [
      {
        id: 1,
        service: { id: 3, name: 'Karpet Handmade' },
        quantity: '100.00',
        unit_price: '2.50',
        unit_price_max: '4.00',
        line_total: '250.00',
        line_total_max: '400.00',
      },
    ],
    created_at: '2026-10-12T02:00:00Z',
    ...overrides,
  }
}

const CONVERSATION: Conversation = {
  id: 11,
  channel: 'whatsapp',
  handed_off: false,
  handoff_reason: null,
  customer: { id: 7, name: 'Aminah Rahman', phone: '+60300000001' },
  created_at: '2026-10-12T02:00:00Z',
  messages: [
    { id: 1, role: 'customer', content: 'Harga karpet handmade?', sources: null, grounded: null, created_at: '2026-10-12T02:00:00Z' },
    {
      id: 2,
      role: 'assistant',
      content: 'RM2.50 to RM4.00 per square foot.',
      sources: [{ source: 'price list', title: 'Price list', heading: 'Karpet Handmade', cited_text: 'RM2.50' }],
      grounded: true,
      created_at: '2026-10-12T02:00:05Z',
    },
    { id: 3, role: 'assistant', content: 'The owner will confirm.', sources: [], grounded: false, created_at: '2026-10-12T02:00:09Z' },
  ],
}

const signedIn = { 'GET /api/auth/me': () => ({ body: { id: 1, email: 'o@example.com', name: 'Owner' } }) }

function renderDashboard() {
  sessionStorage.setItem('kilau-admin-token', JSON.stringify({ token: 't', expiresAt: Date.now() + 60_000 }))
  render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
  return userEvent.setup()
}

beforeEach(() => {
  sessionStorage.clear()
  window.location.hash = '#/bookings'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('bookings page', () => {
  it('lists upcoming bookings with their details', async () => {
    const calls = mockBackend({ ...signedIn, 'GET /api/bookings': () => ({ body: [booking()] }) })
    renderDashboard()

    const card = await screen.findByRole('listitem', { name: /Booking 1/ })
    expect(card).toHaveTextContent('Aminah Rahman')
    expect(card).toHaveTextContent('Karpet Handmade × 100')
    expect(card).toHaveTextContent('RM250.00 – RM400.00')
    expect(card).toHaveTextContent('Thu, 15 Oct')
    expect(card).toHaveTextContent('Home visit')
    expect(card).toHaveTextContent('Pending')
    const query = calls.find((c) => c.path === '/api/bookings')?.query
    expect(query?.get('start_from')).toMatch(/T00:00:00\+08:00$/)
  })

  it('filters by date range and status', async () => {
    const calls = mockBackend({
      ...signedIn,
      'GET /api/bookings': (call) => ({
        body: call.query.get('start_to') ? [booking({ id: 1 }), booking({ id: 2 })] : [],
      }),
    })
    const user = renderDashboard()
    await screen.findByText('No bookings here.')

    await user.click(screen.getByRole('button', { name: 'Past' }))
    const cards = await screen.findAllByRole('listitem', { name: /Booking/ })
    expect(cards.map((c) => c.getAttribute('aria-label'))).toEqual([
      'Booking 2, Aminah Rahman', // newest first for past bookings
      'Booking 1, Aminah Rahman',
    ])

    await user.selectOptions(screen.getByLabelText('Status'), 'done')
    await waitFor(() => expect(calls.at(-1)?.query.get('status')).toBe('done'))
  })

  it('confirms a pending booking', async () => {
    const calls = mockBackend({
      ...signedIn,
      'GET /api/bookings': () => ({ body: [booking()] }),
      'PATCH /api/bookings/1': () => ({ body: booking({ status: 'confirmed' }) }),
    })
    const user = renderDashboard()
    const card = await screen.findByRole('listitem', { name: /Booking 1/ })

    await user.click(within(card).getByRole('button', { name: 'Confirm' }))

    expect(await within(card).findByText('Confirmed')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'confirmed' })
    expect(within(card).getByRole('button', { name: 'Mark done' })).toBeInTheDocument()
  })

  it('asks before cancelling', async () => {
    const calls = mockBackend({
      ...signedIn,
      'GET /api/bookings': () => ({ body: [booking()] }),
      'PATCH /api/bookings/1': () => ({ body: booking({ status: 'cancelled' }) }),
    })
    const user = renderDashboard()
    const card = await screen.findByRole('listitem', { name: /Booking 1/ })

    await user.click(within(card).getByRole('button', { name: 'Cancel booking' }))
    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
    await user.click(within(card).getByRole('button', { name: 'Keep booking' }))
    expect(within(card).getByRole('button', { name: 'Cancel booking' })).toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: 'Cancel booking' }))
    await user.click(within(card).getByRole('button', { name: 'Yes, cancel it' }))

    expect(await within(card).findByText('Cancelled')).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: /Confirm|Mark done|Cancel/ })).not.toBeInTheDocument()
  })

  it('shows an error when an update fails', async () => {
    mockBackend({
      ...signedIn,
      'GET /api/bookings': () => ({ body: [booking()] }),
      'PATCH /api/bookings/1': () => ({ status: 409, body: { detail: 'Cannot change' } }),
    })
    const user = renderDashboard()
    const card = await screen.findByRole('listitem', { name: /Booking 1/ })

    await user.click(within(card).getByRole('button', { name: 'Confirm' }))

    expect(await within(card).findByRole('alert')).toHaveTextContent("Couldn't update")
    expect(within(card).getByText('Pending')).toBeInTheDocument()
  })

  it('shows the customer, services and the chat with its sources', async () => {
    mockBackend({
      ...signedIn,
      'GET /api/bookings': () => ({ body: [booking()] }),
      'GET /api/conversations/11': () => ({ body: CONVERSATION }),
    })
    const user = renderDashboard()
    await user.click(await screen.findByRole('button', { name: 'View details' }))

    const panel = screen.getByRole('dialog', { name: 'Booking 1 details' })
    expect(within(panel).getByRole('link', { name: 'WhatsApp' })).toHaveAttribute('href', 'https://wa.me/60300000001')
    expect(within(panel).getByText('1, Jalan Contoh 1')).toBeInTheDocument()
    expect(await within(panel).findByText('Harga karpet handmade?')).toBeInTheDocument()
    expect(within(panel).getByText('Sources: Price list › Karpet Handmade')).toBeInTheDocument()
    expect(within(panel).getByText('Not grounded in the knowledge base')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('says when a booking did not come from the chat', async () => {
    mockBackend({ ...signedIn, 'GET /api/bookings': () => ({ body: [booking({ conversation_id: null })] }) })
    const user = renderDashboard()

    await user.click(await screen.findByRole('button', { name: 'View details' }))

    expect(screen.getByText('Booked directly, not through the chat.')).toBeInTheDocument()
  })

  it('shows an error when bookings cannot load', async () => {
    mockBackend({ ...signedIn, 'GET /api/bookings': () => ({ status: 500 }) })
    renderDashboard()

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load bookings")
  })

  it('signs out when the session has expired', async () => {
    mockBackend({ ...signedIn, 'GET /api/bookings': () => ({ status: 401 }) })
    renderDashboard()

    expect(await screen.findByRole('status')).toHaveTextContent('session has expired')
    expect(screen.getByRole('heading', { name: 'Owner dashboard' })).toBeInTheDocument()
  })
})
