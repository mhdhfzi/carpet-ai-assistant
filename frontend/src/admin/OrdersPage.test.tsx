import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { AuthProvider } from './auth'
import type { Order, Service } from './types'

type Call = { method: string; path: string; query: URLSearchParams; body: unknown }
type Handler = (call: Call) => { status?: number; body?: unknown }

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

const REAL_BUSINESS = { name: 'Cuci-Cuci Senawang', demo: false, bookings: false, orders: true }
const me = (role: 'owner' | 'staff') => () => ({ body: { id: 1, email: 'x@example.com', name: role === 'owner' ? 'Herman' : 'Pekerja', role } })

const SERVICES: Service[] = [
  { id: 1, name: 'Karpet Biasa', pricing_unit: 'per_sqft', unit_price: '1.80', unit_price_max: null, is_active: true },
  { id: 2, name: 'Karpet Handmade', pricing_unit: 'per_sqft', unit_price: '2.50', unit_price_max: '4.00', is_active: true },
  { id: 3, name: 'Cucian Sofa', pricing_unit: 'per_item', unit_price: '60.00', unit_price_max: null, is_active: true },
]

function order(overrides: Partial<Order> = {}): Order {
  return {
    id: 7,
    number: 412,
    customer: { id: 3, name: 'Ali', phone: '+60123456789', area: 'Seremban 2', address: '5, Jalan A' },
    received_on: '2026-10-10',
    status: 'received',
    return_method: null,
    deposit: '50.00',
    discount: '0.00',
    notes: null,
    washed_on: null,
    ready_on: null,
    completed_on: null,
    ready_from: null,
    ready_by: null,
    price_pending: false,
    subtotal: '144.00',
    total: '144.00',
    balance: '94.00',
    items: [
      {
        id: 1,
        position: 1,
        tag: '412-1',
        service: { id: 1, name: 'Karpet Biasa', pricing_unit: 'per_sqft' },
        length_ft: '8.00',
        width_ft: '10.00',
        quantity: '80.00',
        unit_price: '1.80',
        line_total: '144.00',
        notes: 'tompok kopi',
      },
    ],
    events: [{ status: 'received', note: null, by: 'Pekerja', at: '2026-10-10T02:00:00Z' }],
    created_at: '2026-10-10T02:00:00Z',
    ...overrides,
  }
}

function renderSignedIn(hash = '') {
  sessionStorage.setItem('kilau-admin-token', JSON.stringify({ token: 't', expiresAt: Date.now() + 60_000 }))
  window.location.hash = hash
  render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
  return userEvent.setup()
}

beforeEach(() => {
  sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('back office', () => {
  it('shows staff only the orders, starting with what still needs washing', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [order()] }),
    })
    renderSignedIn()

    const card = await screen.findByRole('link', { name: /Pesanan 412, Ali/ })
    expect(card).toHaveTextContent('Karpet Biasa 8 x 10 kaki')
    expect(card).toHaveTextContent('Diterima')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Pesanan'])
    expect(calls.find((c) => c.path === '/api/orders')?.query.get('status')).toBe('received')
  })

  it('gives the owner orders and analytics, and no bookings for an answers-only business', async () => {
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [] }),
    })
    renderSignedIn()

    await screen.findByText('Tiada pesanan di sini.')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Pesanan', 'Analytics'])
  })

  it('records a new order with a live price and opens it', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/services': () => ({ body: SERVICES }),
      'GET /api/customers': () => ({ body: [] }),
      'POST /api/orders': () => ({ status: 201, body: order() }),
    })
    const user = renderSignedIn('#/orders/new')

    await user.type(await screen.findByLabelText('No. telefon'), '012-345 6789')
    await user.type(screen.getByLabelText('Nama'), 'Ali')
    await user.selectOptions(screen.getByLabelText('Jenis'), 'Karpet Biasa')
    await user.type(screen.getByLabelText('Panjang (kaki)'), '8')
    await user.type(screen.getByLabelText('Lebar (kaki)'), '10')
    await user.type(screen.getByLabelText('Deposit (RM)'), '50')

    expect(screen.getByText('80 kaki persegi · RM144.00')).toBeInTheDocument()
    expect(screen.queryByLabelText('Diskaun (RM)')).toBeNull() // owner only
    await user.click(screen.getByRole('button', { name: 'Simpan pesanan' }))

    await waitFor(() => expect(window.location.hash).toBe('#/orders/7'))
    const posted = calls.find((c) => c.method === 'POST')?.body as Record<string, unknown>
    expect(posted.items).toEqual([{ service_id: 1, length_ft: '8', width_ft: '10' }])
    expect(posted.deposit).toBe('50')
    expect(posted).not.toHaveProperty('discount')
  })

  it('fills in a returning customer from their phone number', async () => {
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/services': () => ({ body: SERVICES }),
      'GET /api/customers': () => ({
        body: [{ id: 3, name: 'Ali', phone: '+60123456789', area: 'Seremban 2', address: '5, Jalan A', orders: 2, last_order_on: '2026-09-01' }],
      }),
    })
    const user = renderSignedIn('#/orders/new')

    await user.type(await screen.findByLabelText('No. telefon'), '0123456789')

    expect(await screen.findByText('Pelanggan lama: Ali (2 pesanan)')).toBeInTheDocument()
    expect(screen.getByLabelText('Nama')).toHaveValue('Ali')
    expect(screen.getByLabelText('Kawasan')).toHaveValue('Seremban 2')
  })

  it('says handmade carpet is priced by the owner', async () => {
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/services': () => ({ body: SERVICES }),
    })
    const user = renderSignedIn('#/orders/new')

    await user.selectOptions(await screen.findByLabelText('Jenis'), 'Karpet Handmade')
    await user.type(screen.getByLabelText('Panjang (kaki)'), '5')
    await user.type(screen.getByLabelText('Lebar (kaki)'), '8')

    expect(screen.getByText(/Harga ditetapkan oleh pemilik/)).toBeInTheDocument()
  })

  it('moves an order to the next step with one button', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7': () => ({ body: order() }),
      'PATCH /api/orders/7': () => ({ body: order({ status: 'washed', ready_from: '2026-10-15', ready_by: '2026-10-17' }) }),
    })
    const user = renderSignedIn('#/orders/7')

    expect(await screen.findByText('412-1')).toBeInTheDocument()
    expect(screen.queryByText('Pemilik sahaja')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Tanda sudah dicuci' }))

    expect(await screen.findByText(/Jangka kering: 15 Oct – 17 Oct/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'washed' })
    expect(screen.getByRole('button', { name: 'Tanda siap (kering)' })).toBeInTheDocument()
  })

  it('shows the server explanation when a change is refused', async () => {
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7': () => ({ body: order() }),
      'PATCH /api/orders/7': () => ({ status: 403, body: { detail: 'Only the owner can give a discount' } }),
    })
    const user = renderSignedIn('#/orders/7')

    await user.click(await screen.findByRole('button', { name: 'Tanda sudah dicuci' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Only the owner can give a discount')
  })
})
