import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { AuthProvider } from './auth'
import type { Order, Receipt, Service } from './types'

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
    discount: '0.00',
    notes: null,
    washed_on: null,
    ready_on: null,
    completed_on: null,
    ready_from: null,
    ready_by: null,
    items_washed: 0,
    items_ready: 0,
    price_pending: false,
    subtotal: '144.00',
    total: '144.00',
    paid: '50.00',
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
        status: 'received',
        washed_on: null,
        ready_on: null,
        ready_from: null,
        ready_by: null,
      },
    ],
    events: [{ status: 'received', item_tag: null, note: null, by: 'Pekerja', at: '2026-10-10T02:00:00Z' }],
    payments: [
      { id: 1, amount: '50.00', method: 'transfer', paid_on: '2026-10-10', note: 'Deposit', received_by: 'Pekerja', voided: false, void_reason: null },
    ],
    created_at: '2026-10-10T02:00:00Z',
    ...overrides,
  }
}

function receipt(overrides: Partial<Order> = {}): Receipt {
  return {
    business: {
      name: 'Cuci-Cuci Senawang',
      reg_no: '201903262495 (NS0229212-P)',
      address: '89-G, Jalan Bandar Senawang 5',
      phone: '019-276 2890',
      payment_details: 'Maybank 1234 (Rizqiman Gemilang Legacy)',
    },
    order: order(overrides),
    issued_on: '2026-10-17',
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
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Pesanan', 'Pelanggan'])
    expect(calls.find((c) => c.path === '/api/orders')?.query.getAll('status')).toEqual(['received'])
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
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Pesanan', 'Pelanggan', 'Analytics'])
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
        body: [{ id: 3, name: 'Ali', phone: '+60123456789', area: 'Seremban 2', address: '5, Jalan A', orders: 2, last_order_on: '2026-09-01', total_value: '200.00', unpaid: '0' }],
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
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
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
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
      'PATCH /api/orders/7': () => ({ status: 403, body: { detail: 'Only the owner can give a discount' } }),
    })
    const user = renderSignedIn('#/orders/7')

    await user.click(await screen.findByRole('button', { name: 'Tanda sudah dicuci' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Only the owner can give a discount')
  })

  it('moves picked-up and cancelled orders to the history tab', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': (call) => ({
        body: call.query.getAll('status').includes('completed')
          ? [order({ status: 'completed', completed_on: '2026-10-20' })]
          : [],
      }),
    })
    const user = renderSignedIn()

    await screen.findByText('Tiada pesanan di sini.')
    await user.click(screen.getByRole('button', { name: 'Sejarah' }))

    const card = await screen.findByRole('link', { name: /Pesanan 412/ })
    expect(card).toHaveTextContent('Selesai')
    expect(card).toHaveTextContent('selesai 20 Oct')
    expect(calls.at(-1)?.query.getAll('status')).toEqual(['completed', 'cancelled'])
  })

  it('lists every customer in one table', async () => {
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/customers': () => ({
        body: [
          { id: 3, name: 'Ali', phone: '+60123456789', area: 'Seremban 2', address: '5, Jalan A', orders: 2, last_order_on: '2026-10-10', total_value: '324.00', unpaid: '100.00' },
          { id: 4, name: 'Siti', phone: '+60191112222', area: null, address: null, orders: 0, last_order_on: null, total_value: '0', unpaid: '0' },
        ],
      }),
    })
    renderSignedIn('#/customers')

    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(within(rows[0]).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Nama', 'Telefon', 'Kawasan', 'Alamat', 'Pesanan', 'Terakhir', 'Jumlah', 'Baki',
    ])
    expect(rows[1]).toHaveTextContent('Ali+60123456789Seremban 25, Jalan A210 OctRM324.00RM100.00')
    expect(within(rows[1]).getByRole('link', { name: 'Ali' })).toHaveAttribute('href', '#/customers/3')
    expect(rows[2]).toHaveTextContent('Siti+60191112222––0–RM0.00–')
  })

  it('records the balance at pickup and offers the receipt on WhatsApp', async () => {
    const paidUp = { paid: '144.00', balance: '0.00', status: 'ready' as const }
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({ body: receipt({ status: 'ready' }) }),
      'POST /api/orders/7/payments': () => ({ status: 201, body: order(paidUp) }),
    })
    const user = renderSignedIn('#/orders/7')

    expect(await screen.findByText(/Baki RM94.00 belum dibayar/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Bayar penuh baki (RM94.00)' }))
    await user.click(screen.getByRole('button', { name: 'Tunai' }))
    await user.click(screen.getByRole('button', { name: 'Simpan bayaran' }))

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ amount: '94.00', method: 'cash' })
    await waitFor(() => expect(screen.queryByText(/belum dibayar/)).toBeNull())
    const ready = screen.getByRole('link', { name: 'WhatsApp: barang siap' })
    const text = decodeURIComponent(ready.getAttribute('href')?.split('?text=')[1] ?? '')
    expect(ready.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/60123456789\?text=/)
    expect(text).toContain('Assalamualaikum Ali')
    expect(text).toContain('412-1 Karpet Biasa 8 x 10 kaki: RM144.00')
    expect(text).toContain('Telah dibayar sepenuhnya')
  })

  it('lets only the owner void a payment', async () => {
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
    })
    renderSignedIn('#/orders/7')

    const list = await screen.findByRole('list', { name: 'Senarai bayaran' })
    expect(list).toHaveTextContent('Pindahan bank · Deposit')
    expect(within(list).queryByRole('button', { name: 'Batalkan' })).toBeNull()
  })

  it('prints a receipt with the business details and payments', async () => {
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
    })
    renderSignedIn('#/orders/7/resit')

    const receiptCard = await screen.findByRole('article')
    expect(receiptCard).toHaveTextContent('No. SSM: 201903262495 (NS0229212-P)')
    expect(receiptCard).toHaveTextContent('RESITNo. 412')
    expect(receiptCard).toHaveTextContent('Dibayar 10 Oct (Pindahan bank, Deposit)− RM50.00')
    expect(receiptCard).toHaveTextContent('BakiRM94.00')
    expect(receiptCard).toHaveTextContent('Bayaran: Maybank 1234 (Rizqiman Gemilang Legacy)')
    expect(screen.getByRole('button', { name: 'Cetak / simpan PDF' })).toBeInTheDocument()
  })

  it('moves each carpet on its own and shows its drying window', async () => {
    const second = {
      ...order().items[0],
      id: 2,
      position: 2,
      tag: '412-2',
      service: { id: 3, name: 'Karpet Shaggy', pricing_unit: 'per_sqft' as const },
    }
    const twoCarpets = order({ items: [order().items[0], second] })
    const firstWashed = order({
      items: [
        { ...order().items[0], status: 'washed', washed_on: '2026-10-10', ready_from: '2026-10-15', ready_by: '2026-10-17' },
        second,
      ],
      items_washed: 1,
    })
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({ body: { ...receipt(), order: twoCarpets } }),
      'PATCH /api/orders/7/items/1': () => ({ body: firstWashed }),
    })
    const user = renderSignedIn('#/orders/7')

    expect(await screen.findByRole('button', { name: 'Tanda semua sudah dicuci' })).toBeInTheDocument()
    const lines = screen.getAllByRole('listitem').filter((li) => /412-\d/.test(li.textContent ?? ''))
    await user.click(within(lines[0]).getByRole('button', { name: 'Dicuci' }))

    expect(calls.find((c) => c.method === 'PATCH')?.path).toBe('/api/orders/7/items/1')
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'washed' })
    expect(await screen.findByText('dicuci 10 Oct · kering 15 Oct–17 Oct')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Undur' })).toBeNull() // owner only
  })

  it('shows how many carpets of an order are done on the list', async () => {
    const items = [order().items[0], { ...order().items[0], id: 2, position: 2, tag: '412-2' }, { ...order().items[0], id: 3, position: 3, tag: '412-3' }]
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [order({ items, items_washed: 1 })] }),
    })
    renderSignedIn()

    const card = await screen.findByRole('link', { name: /Pesanan 412/ })
    expect(card).toHaveTextContent('1 / 3 dicuci')
  })

  it('shows the business numbers and hides AI booking sections for an answers-only business', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/analytics': () => ({
        body: {
          days: 30, start: '2026-09-13', end: '2026-10-12', conversations: 12, handed_off: 1, bookings: 0,
          conversion_rate: 0, conversion: [], busy_days: [], top_topics: [],
          open_unanswered: { no_answer: 2, handed_off: 0, gave_up: 0 },
        },
      }),
      'GET /api/unanswered-questions': () => ({ body: [] }),
      'GET /api/analytics/business': () => ({
        body: {
          days: 30, start: '2026-09-13', end: '2026-10-12',
          revenue: '1244.00', revenue_by_method: { cash: '744.00', transfer: '500.00', duitnow: '0' },
          revenue_over_time: [{ label: '5 Oct', start: '2026-10-05', amount: '1244.00' }],
          orders: 9, order_value: '1500.00', cancelled: 1, unpaid: '256.00', unpaid_orders: 2,
          in_progress: { received: 3, washed: 4, ready: 1 },
          services: [{ name: 'Karpet Biasa', items: 7, value: '980.00' }],
          busy_days: [{ weekday: 'Sat', orders: 5 }], average_days_to_ready: 6.4,
        },
      }),
    })
    renderSignedIn('#/analytics')

    const business = await screen.findByRole('region', { name: 'Perniagaan' })
    expect(business).toHaveTextContent('Hasil diterimaRM1244.00')
    expect(business).toHaveTextContent('Baki belum dibayarRM256.002 pesanan')
    expect(business).toHaveTextContent('Purata masa siap6.4 hari')
    expect(business).toHaveTextContent('Sedang kering4')
    expect(await screen.findByText('Chats')).toBeInTheDocument()
    expect(screen.queryByText('Bookings made')).toBeNull()
    expect(screen.queryByText('Chat to booking, by channel')).toBeNull()
    expect(calls.find((c) => c.path === '/api/analytics/business')?.query.get('days')).toBe('30')
  })
})
