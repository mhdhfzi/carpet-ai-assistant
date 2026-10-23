import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Turning the receipt into a picture needs a real browser; here it returns a tiny JPEG.
vi.mock('html-to-image', () => ({ toJpeg: vi.fn(async () => 'data:image/jpeg;base64,/9j/') }))
import { App } from './App'
import { AuthProvider } from './auth'
import { formatShortDate, todayInMalaysia } from './format'
import type { Order, Receipt, Service, WorkItem } from './types'

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

const REAL_BUSINESS = {
  name: 'Cuci-Cuci Senawang',
  demo: false,
  bookings: false,
  orders: true,
  brand: 'Dobi Karpet Xpress',
  logo: 'RGL',
  logo_image: '',
  address: 'No.89, Jalan Bandar Senawang 5',
}
const me = (role: 'owner' | 'staff') => () => ({ body: { id: 1, email: 'x@example.com', name: role === 'owner' ? 'Herman' : 'Pekerja', role } })

const SERVICES: Service[] = [
  { id: 1, name: 'Karpet Biasa', pricing_unit: 'per_sqft', unit_price: '1.80', unit_price_max: null, on_site: false, is_active: true },
  { id: 2, name: 'Karpet Handmade', pricing_unit: 'per_sqft', unit_price: '2.50', unit_price_max: '4.00', on_site: false, is_active: true },
  { id: 3, name: 'Cucian Sofa', pricing_unit: 'per_item', unit_price: '60.00', unit_price_max: null, on_site: true, is_active: true },
]

const NEXT: Record<Order['status'], Order['next_status']> = {
  received: 'washed',
  washed: 'ready',
  ready: 'completed',
  completed: null,
  cancelled: null,
}

function order(overrides: Partial<Order> = {}): Order {
  return {
    id: 7,
    kind: 'shop',
    number: 412,
    code: '412',
    customer: { id: 3, name: 'Ali', phone: '+60123456789', area: 'Seremban 2', address: '5, Jalan A' },
    received_on: '2026-10-10',
    visit_at: null,
    status: 'received',
    next_status: NEXT[overrides.status ?? 'received'],
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
        service: { id: 1, name: 'Karpet Biasa', pricing_unit: 'per_sqft', needs_fold: false, on_site: false },
        length_ft: '8.00',
        width_ft: '10.00',
        quantity: '80.00',
        unit_price: '1.80',
        line_total: '144.00',
        notes: 'tompok kopi',
        status: 'received',
        washed_on: null,
        washed_by: null,
        wash_note: null,
        ready_on: null,
        packed_by: null,
        fold: null,
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
      name: 'Dobi Karpet Xpress',
      logo: 'RGL',
      logo_image: '',
      reg_no: '201903262495 (NS0229212-P)',
      address: '89-G, Jalan Bandar Senawang 5',
      phone: '019-276 2890',
      email: 'kedai@example.com',
      facebook: 'Cuci Cuci Senawang',
      payment_details: 'Maybank 1234|Rizqiman Gemilang Legacy',
      terms: 'Barang yang tidak dituntut dalam 3 bulan akan dilupuskan.',
      duitnow_qr: '',
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
  it('shows staff the book of open orders and the work tabs', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [order()] }),
    })
    renderSignedIn()

    const row = await screen.findByRole('row', { name: /Pesanan 412, Ali/ })
    expect(row).toHaveTextContent('412-1: Karpet Biasa (8 x 10 kaki)RM144.00')
    expect(row).toHaveTextContent('Belum cuci')
    expect(row).toHaveTextContent('Progress: 0 / 1 barang')
    expect(row).toHaveTextContent('Baki RM94.00')
    expect(screen.getByText('Dobi Karpet Xpress')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Buku Utama', 'Buku Kerja Luar', 'Borang Cuci', 'Borang Packing', 'Rekod harian', 'Resit & WhatsApp', 'Pelanggan'])
    expect(calls.find((c) => c.path === '/api/orders')?.query.getAll('status')).toEqual(['received', 'washed', 'ready'])
  })

  it("shows today's numbers in the cards and on the tabs", async () => {
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [] }),
      'GET /api/work/summary': () => ({
        body: { to_wash: 4, to_pack: 2, drying: 3, ready_orders: 1, unpaid: '350.00', unpaid_orders: 2 },
      }),
    })
    renderSignedIn()

    const toPack = await screen.findByRole('link', { name: /5–7 hari kering/ })
    expect(toPack).toHaveTextContent('2 karpet')
    expect(toPack).toHaveTextContent('3 lagi masih kering')
    expect(screen.getByRole('link', { name: /Baki belum bayar/ })).toHaveTextContent('RM350.00')
    expect(screen.getByRole('link', { name: /Baki belum bayar/ })).toHaveAttribute('href', '#/orders?tapis=unpaid')
    expect(screen.getByRole('link', { name: /Borang Cuci/ })).toHaveTextContent('Borang Cuci4')
  })

  it('filters the book to customers who still owe money', async () => {
    const owing = order({ id: 8, number: 413, code: '413', balance: '94.00' })
    const paid = order({ id: 9, number: 414, code: '414', balance: '0.00', paid: '144.00', status: 'completed' })
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [owing, paid] }),
    })
    renderSignedIn('#/orders?tapis=unpaid')

    expect(await screen.findByRole('row', { name: /Pesanan 413/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /Pesanan 414/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Belum bayar' })).toHaveAttribute('aria-pressed', 'true')
    expect(calls.find((c) => c.path === '/api/orders')?.query.getAll('status')).toEqual(['received', 'washed', 'ready', 'completed'])
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
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual([...['Buku Utama', 'Buku Kerja Luar', 'Borang Cuci', 'Borang Packing', 'Rekod harian', 'Resit & WhatsApp', 'Pelanggan'], 'Analytics'])
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

    expect(screen.getByText('80 kaki persegi · RM144.00')).toBeInTheDocument()
    expect(screen.queryByLabelText('Diskaun (RM)')).toBeNull() // owner only
    expect(screen.queryByLabelText('Deposit (RM)')).toBeNull() // money is recorded by the owner
    await user.click(screen.getByRole('button', { name: 'Simpan pesanan' }))

    await waitFor(() => expect(window.location.hash).toBe('#/orders/7'))
    const posted = calls.find((c) => c.method === 'POST')?.body as Record<string, unknown>
    expect(posted.items).toEqual([{ service_id: 1, length_ft: '8', width_ft: '10' }])
    expect(posted.deposit).toBe('0')
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
    expect(screen.getByRole('button', { name: 'Tanda siap (sudah dipack)' })).toBeInTheDocument()
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

    const row = await screen.findByRole('row', { name: /Pesanan 412/ })
    expect(row).toHaveTextContent('Selesai 20/10/26')
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
      'GET /api/auth/me': me('owner'),
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
    expect(text).toContain('1. Karpet Biasa (412-1, 8 x 10 kaki) - RM144.00')
    expect(text).toContain('TELAH DIBAYAR (PAID)')
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

  it('shows the receipt like the paper one, with the WhatsApp message', async () => {
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [order()] }),
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
    })
    renderSignedIn('#/orders/7/resit')

    const sheet = await screen.findByRole('article', { name: 'Resit 412' })
    expect(sheet).toHaveTextContent('Dobi Karpet Xpress')
    expect(sheet).toHaveTextContent('No. SSM: 201903262495 (NS0229212-P)')
    expect(sheet).toHaveTextContent('Page FB: Cuci Cuci Senawang • Tel: 019-276 2890')
    expect(sheet).toHaveTextContent('M/S : Ali — 5, Jalan A, Seremban 2')
    expect(sheet).toHaveTextContent('1Karpet Biasa (412-1, 8 x 10 kaki)80 kp²1.80144.00')
    expect(sheet).toHaveTextContent('Bayaran onlineMaybank 1234Rizqiman Gemilang Legacy')
    expect(sheet).toHaveTextContent('Jumlah hargaRM144.00Deposit / dibayarRM50.00BakiRM94.00')
    expect(sheet).toHaveTextContent('dilupuskan')
    expect(within(sheet).queryByText('PAID')).toBeNull() // RM94 still owed
    const message = screen.getByText(/Berikut adalah resit/)
    expect(message).toHaveTextContent('*No. siri resit:* 412')
    expect(message).toHaveTextContent('*Baki:* RM94.00')
    expect(screen.getByRole('link', { name: 'Hantar resit melalui WhatsApp' })).toHaveAttribute(
      'href',
      expect.stringMatching(/^https:\/\/wa\.me\/60123456789\?text=/),
    )
    expect(screen.getByRole('button', { name: 'Cetak / simpan PDF' })).toBeInTheDocument()
  })

  it('stamps PAID once the payments cover the total', async () => {
    const paidUp = { paid: '144.00', balance: '0.00' }
    const payments = [
      ...order().payments,
      { id: 2, amount: '94.00', method: 'cash' as const, paid_on: '2026-10-16', note: null, received_by: 'Pekerja', voided: false, void_reason: null },
    ]
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [] }),
      'GET /api/orders/7/receipt': () => ({ body: receipt({ ...paidUp, payments }) }),
    })
    renderSignedIn('#/orders/7/resit')

    const sheet = await screen.findByRole('article', { name: 'Resit 412' })
    expect(within(sheet).getByLabelText('Dibayar 16/10/26')).toHaveTextContent('PAIDDate : 16/10/26')
    expect(screen.getByText(/Aktif: dibayar penuh 16\/10\/26/)).toBeInTheDocument()
  })

  it('moves each carpet on its own and shows its drying window', async () => {
    const second = {
      ...order().items[0],
      id: 2,
      position: 2,
      tag: '412-2',
      service: { id: 3, name: 'Karpet Shaggy', pricing_unit: 'per_sqft' as const, needs_fold: false, on_site: false },
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
    await user.click(within(lines[0]).getByRole('button', { name: 'Siap cuci' }))

    expect(calls.find((c) => c.method === 'PATCH')?.path).toBe('/api/orders/7/items/1')
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'washed' })
    expect(await screen.findByText('dicuci 10 Oct · kering 15 Oct–17 Oct')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Undur' })).toBeNull() // owner only
  })

  it('shows how many carpets of an order are packed in the book', async () => {
    const items = [order().items[0], { ...order().items[0], id: 2, position: 2, tag: '412-2' }, { ...order().items[0], id: 3, position: 3, tag: '412-3' }]
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [order({ items, items_washed: 2, items_ready: 1 })] }),
    })
    renderSignedIn()

    const row = await screen.findByRole('row', { name: /Pesanan 412/ })
    expect(row).toHaveTextContent('Progress: 1 / 3 barang')
    expect(row).toHaveTextContent('Belum selesai')
  })

  it('shows the business month by month and hides AI booking sections for an answers-only business', async () => {
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
      'GET /api/analytics/business': (call) => {
        const month = call.query.get('month') ?? '2026-10'
        const october = month === '2026-10'
        return {
          body: {
            month, start: `${month}-01`, end: `${month}-30`,
            revenue_total: '5200.00', unpaid: '256.00', unpaid_orders: 2,
            months: [
              { month: '2026-09', revenue: '3956.00', orders: 30, top_service: 'Cucian Sofa' },
              { month: '2026-10', revenue: '1244.00', orders: 9, top_service: 'Karpet Biasa' },
            ],
            revenue: october ? '1244.00' : '3956.00',
            revenue_by_method: { cash: '744.00', transfer: '500.00', duitnow: '0' },
            orders: october ? 9 : 30, order_value: '1500.00', cancelled: 1,
            services: [{ name: 'Karpet Biasa', items: 7, value: '980.00' }],
            busy_days: [{ weekday: 'Sat', orders: 5 }], average_days_to_ready: 6.4,
          },
        }
      },
    })
    const user = renderSignedIn('#/analytics')

    const business = await screen.findByRole('region', { name: 'Perniagaan' })
    expect(business).toHaveTextContent('Jumlah hasil keseluruhanRM5456.00') // 5200 received + 256 owed
    expect(business).toHaveTextContent('Jumlah hasil diterimaRM5200.00')
    expect(business).toHaveTextContent('Baki belum dibayarRM256.002 pesanan')
    const monthly = within(business).getByRole('region', { name: 'Setiap bulan' })
    const rows = within(monthly).getAllByRole('row').map((r) => r.textContent)
    expect(rows[1]).toBe('Oktober 2026RM1244.009Karpet Biasa') // newest first
    expect(rows[2]).toBe('September 2026RM3956.0030Cucian Sofa')
    expect(business).toHaveTextContent('Purata masa siap6.4 hari')
    expect(business).not.toHaveTextContent('Sedang kering')
    expect(business).not.toHaveTextContent('Belum dicuci')

    await user.selectOptions(within(business).getByLabelText('Lihat bulan'), '2026-09')
    expect(await within(business).findByRole('heading', { name: 'September 2026' })).toBeInTheDocument()
    expect(calls.findLast((c) => c.path === '/api/analytics/business')?.query.get('month')).toBe('2026-09')
    expect(await screen.findByText('Chats')).toBeInTheDocument()
    expect(screen.queryByText('Bookings made')).toBeNull()
    expect(screen.queryByText('Chat to booking, by channel')).toBeNull()
  })

  it('lists carpets to wash by order and records one as washed', async () => {
    let washed = false
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/items': () => ({ body: washed ? [] : [workItem()] }),
      'GET /api/work/log': (call) => ({
        body: { day: call.query.get('day'), washed: washed ? [workItem({ washed_on: '2026-10-10', washed_by: 'Amir' })] : [], packed: [] },
      }),
      'PATCH /api/orders/7/items/1': () => {
        washed = true
        return { body: order() }
      },
      'GET /api/work/untagged': () => ({ body: [] }),
    })
    const user = renderSignedIn('#/cuci')

    expect(await screen.findByText('Senarai karpet untuk dicuci (1)')).toBeInTheDocument()
    expect(screen.getByText('Staf bertugas:').nextSibling).toHaveTextContent('Pekerja')
    await user.type(screen.getByLabelText('Catatan cuci 412-1'), 'tompok tak hilang')
    await user.click(screen.getByRole('button', { name: 'Tandakan siap cuci' }))

    expect(await screen.findByRole('status')).toHaveTextContent('412-1 dicuci.')
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'washed', note: 'tompok tak hilang' })
    expect(await screen.findByText('Telah dicuci (10/10/26)')).toBeInTheDocument()
    expect(screen.getByText('Oleh: Amir')).toBeInTheDocument()
    expect(screen.getByText('Semua karpet sudah dicuci.')).toBeInTheDocument()
  })

  it('packs velvet rolled or folded and keeps drying carpets apart', async () => {
    const velvet = workItem({
      id: 1,
      service: { id: 4, name: 'Karpet Velvet', pricing_unit: 'per_sqft', needs_fold: true, on_site: false },
      status: 'washed',
      washed_on: '2020-01-01',
      ready_from: '2020-01-06',
      ready_by: '2020-01-08',
    })
    const drying = workItem({ id: 2, position: 2, tag: '412-2', status: 'washed', washed_on: '2099-01-01', ready_from: '2099-01-06', ready_by: '2099-01-08' })
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/items': () => ({ body: [velvet, drying] }),
      'GET /api/work/log': (call) => ({ body: { day: call.query.get('day'), washed: [], packed: [] } }),
      'PATCH /api/orders/7/items/1': () => ({ body: order() }),
    })
    const user = renderSignedIn('#/packing')

    expect(await screen.findByText('1 karpet sedia untuk pack')).toBeInTheDocument()
    const velvetRow = screen.getByRole('row', { name: 'Karpet 412-1' })
    expect(velvetRow).toHaveTextContent('(cukup 5–7 hari)')
    expect(screen.getByRole('row', { name: 'Karpet 412-2' })).toHaveTextContent('Tiada (bukan velvet)')

    await user.click(within(velvetRow).getByRole('button', { name: 'Tandakan siap pack' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Pilih Gulung atau Lipat untuk karpet velvet 412-1 dulu.')
    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)

    await user.click(within(velvetRow).getByRole('radio', { name: 'Gulung' }))
    await user.click(within(velvetRow).getByRole('button', { name: 'Tandakan siap pack' }))
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'ready', fold: 'rolled' })
    expect(await screen.findByRole('status')).toHaveTextContent('412-1 dipack (Gulung).')
  })

  it("prints the day's washing and packing forms with who did them", async () => {
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/log': (call) => ({
        body: {
          day: call.query.get('day'),
          washed: [workItem({ washed_by: 'Amir' }), workItem({ id: 2, tag: '412-2', washed_by: 'Ammar' })],
          packed: [workItem({ id: 3, tag: '410-1', packed_by: 'Razi', fold: 'folded' })],
          on_site: [],
        },
      }),
    })
    renderSignedIn('#/rekod')

    const washing = await screen.findByRole('region', { name: 'Rekod cuci karpet' })
    expect(washing).toHaveTextContent('Staf bertugas: Amir, Ammar')
    expect(washing).toHaveTextContent('1412-1Karpet Biasa8 x 10 kakitompok kopiAmir')
    const packing = screen.getByRole('region', { name: 'Rekod packing karpet' })
    expect(packing).toHaveTextContent('1410-1Karpet Biasa8 x 10 kakiLipatRazi')
    expect(screen.getByRole('button', { name: 'Cetak' })).toBeInTheDocument()
  })
})

function workItem(overrides: Partial<WorkItem> = {}): WorkItem {
  return { ...order().items[0], order_id: 7, order_number: 412, customer_name: 'Ali', received_on: '2026-10-10', ...overrides }
}

describe('untagged carpets', () => {
  it('logs a carpet without its tag and matches it later', async () => {
    let untagged = [{ id: 5, description: 'Biasa 7 x 5, biru', found_on: '2026-10-10', found_by: 'Amir', matched_tag: null }]
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/items': () => ({ body: [] }),
      'GET /api/work/log': (call) => ({ body: { day: call.query.get('day'), washed: [], packed: [] } }),
      'GET /api/work/untagged': () => ({ body: untagged }),
      'POST /api/work/untagged/5/match': () => {
        untagged = []
        return { body: {} }
      },
    })
    const user = renderSignedIn('#/cuci')

    const panel = await screen.findByRole('complementary', { name: 'Karpet hilang tag' })
    expect(await within(panel).findByText('Biasa 7 x 5, biru')).toBeInTheDocument()
    await user.type(within(panel).getByLabelText('No. siri sebenar'), '412-2')
    await user.click(within(panel).getByRole('button', { name: 'Padankan' }))

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ tag: '412-2' })
    expect(await within(panel).findByText('Dipadankan dengan 412-2.')).toBeInTheDocument()
    expect(within(panel).getByText('Tiada karpet tanpa tag.')).toBeInTheDocument()
  })
})


describe('measuring when washing', () => {
  it('asks for the size of an unmeasured carpet before it is marked washed', async () => {
    const unmeasured = workItem({ length_ft: null, width_ft: null, quantity: null, line_total: null })
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/items': () => ({ body: [unmeasured] }),
      'GET /api/work/log': (call) => ({ body: { day: call.query.get('day'), washed: [], packed: [] } }),
      'GET /api/work/untagged': () => ({ body: [] }),
      'PATCH /api/orders/7/items/1': () => ({ body: order() }),
    })
    const user = renderSignedIn('#/cuci')

    expect(await screen.findByText('Saiz: Belum diukur')).toBeInTheDocument()
    const wash = screen.getByRole('button', { name: 'Tandakan siap cuci' })
    expect(wash).toBeDisabled()

    await user.type(screen.getByLabelText('Panjang 412-1 (kaki)'), '8')
    await user.type(screen.getByLabelText('Lebar 412-1 (kaki)'), '10')
    await user.click(wash)

    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'washed', length_ft: '8', width_ft: '10' })
  })
})

describe("jobs at the customer's home", () => {
  const sofa = {
    ...order().items[0],
    id: 2,
    position: 1,
    tag: '412-1',
    service: { id: 3, name: 'Cucian Sofa', pricing_unit: 'per_item' as const, needs_fold: false, on_site: true },
    length_ft: null,
    width_ft: null,
    quantity: '3',
    unit_price: '60.00',
    line_total: '180.00',
    notes: null,
  }

  it('lists home jobs by visit and marks one done', async () => {
    const today = new Date().toISOString().slice(0, 10)
    const visits = [
      order({ id: 7, kind: 'on_site', code: 'L412', items: [sofa], visit_at: `${today}T02:00:00Z`, next_status: 'ready' }),
      order({ id: 8, kind: 'on_site', number: 413, code: 'L413', items: [{ ...sofa, id: 3, tag: 'L413-1' }], visit_at: null, next_status: 'ready' }),
    ]
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/visits': () => ({ body: visits }),
      'PATCH /api/orders/7/items/2': () => ({ body: order() }),
    })
    const user = renderSignedIn('#/kerja-luar')

    const todayGroup = await screen.findByRole('region', { name: 'Hari ini' })
    const card = within(todayGroup).getByRole('article', { name: 'Kerja luar L412, Ali' })
    expect(card).toHaveTextContent('Cucian Sofa × 3')
    expect(within(card).getByRole('link', { name: '5, Jalan A, Seremban 2' })).toHaveAttribute(
      'href',
      expect.stringContaining('google.com/maps'),
    )
    expect(screen.getByRole('region', { name: 'Belum dijadualkan' })).toHaveTextContent('L413')

    await user.click(within(card).getByRole('button', { name: 'Tandakan siap' }))
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'ready' })
    expect(await screen.findByRole('status')).toHaveTextContent('412-1 siap.')
  })

  it('finishes a home-only order with one button and keeps the visit time', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({
        body: { ...receipt(), order: order({ items: [sofa], next_status: 'ready', visit_at: '2026-10-21T02:00:00Z' }) },
      }),
      'PATCH /api/orders/7': () => ({ body: order({ items: [{ ...sofa, status: 'ready' }], status: 'ready' }) }),
    })
    const user = renderSignedIn('#/orders/7')

    expect(await screen.findByText('Belum dibuat (kerja luar)')).toBeInTheDocument()
    expect(screen.getByLabelText('Tarikh & masa lawatan')).toHaveValue('2026-10-21T10:00')
    await user.click(screen.getByRole('button', { name: 'Tandakan siap (kerja luar selesai)' }))

    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'ready' })
  })

  it('records kerja luar in its own book, with the visit time', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/services': () => ({ body: SERVICES }),
      'GET /api/customers': () => ({ body: [] }),
      'POST /api/orders': () => ({ status: 201, body: order() }),
    })
    const user = renderSignedIn('#/orders/new?jenis=luar')

    expect(await screen.findByRole('heading', { name: 'Kerja luar baru' })).toBeInTheDocument()
    await user.type(await screen.findByLabelText('No. telefon'), '012-345 6789')
    await user.type(screen.getByLabelText('Nama'), 'Ali')
    // Only house jobs are offered here; carpets go in Buku Utama.
    expect(within(screen.getByLabelText('Jenis')).queryByRole('option', { name: 'Karpet Biasa' })).toBeNull()
    expect(screen.queryByText('Cara pulang')).toBeNull()
    await user.selectOptions(screen.getByLabelText('Jenis'), 'Cucian Sofa')
    await user.type(screen.getByLabelText('Kuantiti'), '3')
    await user.type(screen.getByLabelText('Tarikh & masa lawatan (pilihan)'), '2026-10-21T10:00')
    await user.click(screen.getByRole('button', { name: 'Simpan pesanan' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const posted = calls.find((c) => c.method === 'POST')?.body as Record<string, unknown>
    expect(posted.visit_at).toBe('2026-10-21T10:00:00+08:00')
  })
})

describe('paying by DuitNow QR', () => {
  it('shows the shop QR with the amount and records the payment once received', async () => {
    const withQr = receipt()
    withQr.business.duitnow_qr = '00020101021126330014A0000006150001010600000102111234567890520400005303458580'
    const calls = mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({ body: withQr }),
      'POST /api/orders/7/payments': () => ({ status: 201, body: order({ paid: '144.00', balance: '0.00' }) }),
    })
    const user = renderSignedIn('#/orders/7')

    await user.click(await screen.findByRole('button', { name: 'Bayar dengan DuitNow QR' }))
    const dialog = screen.getByRole('dialog', { name: 'Bayar dengan DuitNow QR' })
    expect(dialog).toHaveTextContent('RM94.00')
    expect(dialog).toHaveTextContent('Rujukan: 412')
    await user.click(within(dialog).getByRole('button', { name: 'Sudah terima RM94.00' }))

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ amount: '94.00', method: 'duitnow', note: 'DuitNow QR' })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('lets staff show the QR but leaves recording the money to the owner', async () => {
    const withQr = receipt()
    withQr.business.duitnow_qr = '00020101021126330014A0000006150001010600000102111234567890520400005303458580'
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({ body: withQr }),
    })
    const user = renderSignedIn('#/orders/7')

    await user.click(await screen.findByRole('button', { name: 'Bayar dengan DuitNow QR' }))
    const dialog = screen.getByRole('dialog', { name: 'Bayar dengan DuitNow QR' })

    expect(dialog).toHaveTextContent('RM94.00')
    expect(within(dialog).queryByRole('button', { name: /Sudah terima/ })).toBeNull()
    expect(dialog).toHaveTextContent('Hanya pemilik boleh rekod bayaran')
    expect(screen.queryByRole('button', { name: 'Simpan bayaran' })).toBeNull()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('has no QR button when the shop has no QR set', async () => {
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
    })
    renderSignedIn('#/orders/7')

    expect(await screen.findByText('Rekod bayaran')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Bayar dengan DuitNow QR' })).toBeNull()
  })
})

describe('searching the washing list', () => {
  it('narrows the list to the matching carpets', async () => {
    const items = [
      workItem({ id: 1, tag: '412-1', customer_name: 'Ali' }),
      workItem({ id: 2, tag: '413-1', order_id: 8, order_number: 413, customer_name: 'Puan Aisyah' }),
    ]
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/items': () => ({ body: items }),
      'GET /api/work/log': (call) => ({ body: { day: call.query.get('day'), washed: [], packed: [] } }),
      'GET /api/work/untagged': () => ({ body: [] }),
    })
    const user = renderSignedIn('#/cuci')

    expect(await screen.findByText('#413-1')).toBeInTheDocument()
    const search = screen.getByLabelText('Cari karpet untuk dicuci')
    await user.type(search, 'aisyah')
    expect(screen.queryByText('#412-1')).toBeNull()
    expect(screen.getByText('#413-1')).toBeInTheDocument()

    await user.clear(search)
    await user.type(search, '412')
    expect(screen.getByText('#412-1')).toBeInTheDocument()
    expect(screen.queryByText('#413-1')).toBeNull()

    await user.type(search, '9')
    expect(screen.getByText('Tiada karpet sepadan dengan carian.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Kosongkan carian' }))
    expect(screen.getByText('#412-1')).toBeInTheDocument()
  })
})

describe('closing a ready order', () => {
  const ready = () => order({ status: 'ready', items: [{ ...order().items[0], status: 'ready' }], items_ready: 1, items_washed: 1 })

  it('asks first when money is still owed, then moves the order out of Siap', async () => {
    let closed = false
    const confirm = vi.fn(() => true)
    vi.stubGlobal('confirm', confirm)
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: closed ? [] : [ready()] }),
      'PATCH /api/orders/7': () => {
        closed = true
        return { body: order({ status: 'completed' }) }
      },
    })
    const user = renderSignedIn('#/orders?tapis=ready')

    await user.click(await screen.findByRole('button', { name: 'Sudah diambil / dihantar' }))

    expect(confirm).toHaveBeenCalledWith('Baki RM94.00 belum dibayar. Teruskan?')
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'completed' })
    expect(await screen.findByRole('status')).toHaveTextContent('412 Ali: selesai, baki RM94.00 masih di Belum bayar.')
    expect(await screen.findByText('Tiada pesanan di sini.')).toBeInTheDocument()
  })

  it('does nothing if the worker says no', async () => {
    vi.stubGlobal('confirm', vi.fn(() => false))
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [ready()] }),
    })
    const user = renderSignedIn('#/orders?tapis=ready')

    await user.click(await screen.findByRole('button', { name: 'Sudah diambil / dihantar' }))

    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
  })
})

describe('two books', () => {
  it('keeps Buku Utama to carpets and offers only carpets for a new order there', async () => {
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [] }),
      'GET /api/services': () => ({ body: SERVICES }),
    })
    const user = renderSignedIn()

    await screen.findByText('Tiada pesanan di sini.')
    expect(calls.find((c) => c.path === '/api/orders')?.query.get('kind')).toBe('shop')
    expect(screen.queryByRole('button', { name: 'Kerja luar' })).toBeNull() // no longer a Buku Utama filter

    await user.click(screen.getByRole('link', { name: /Daftar pesanan baru/ }))
    expect(await screen.findByRole('heading', { name: 'Pesanan karpet baru' })).toBeInTheDocument()
    expect(within(screen.getByLabelText('Jenis')).queryByRole('option', { name: 'Cucian Sofa' })).toBeNull()
  })

  it('shows the kerja luar book with its own orders and numbers', async () => {
    const sofaJob = order({
      kind: 'on_site',
      code: 'L3',
      number: 3,
      status: 'ready',
      items: [{ ...order().items[0], tag: 'L3-1', service: { id: 3, name: 'Cucian Sofa', pricing_unit: 'per_item', needs_fold: false, on_site: true }, length_ft: null, width_ft: null, quantity: '3', status: 'ready' }],
    })
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [sofaJob] }),
    })
    renderSignedIn('#/kerja-luar/buku')

    const row = await screen.findByRole('row', { name: /Pesanan L3, Ali/ })
    expect(row).toHaveTextContent('L3-1: Cucian Sofa')
    expect(calls.find((c) => c.path === '/api/orders')?.query.get('kind')).toBe('on_site')
    expect(screen.getByRole('link', { name: 'Buku kerja luar' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Selesai' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Daftar kerja luar baru/ })[0]).toHaveAttribute('href', '#/orders/new?jenis=luar')
  })
})


describe('summary cards', () => {
  it('show on Buku Utama only; the work pages keep their counts on the menu', async () => {
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/summary': () => ({
        body: { to_wash: 4, to_pack: 2, drying: 3, ready_orders: 1, unpaid: '350.00', unpaid_orders: 2, house_jobs: 1 },
      }),
      'GET /api/work/items': () => ({ body: [] }),
      'GET /api/work/log': (call) => ({ body: { day: call.query.get('day'), washed: [], packed: [] } }),
      'GET /api/work/untagged': () => ({ body: [] }),
    })
    renderSignedIn('#/cuci')

    expect(await screen.findByRole('link', { name: /Borang Cuci/ })).toHaveTextContent('Borang Cuci4')
    expect(screen.queryByRole('link', { name: /Baki belum bayar/ })).toBeNull()
    expect(screen.queryByRole('link', { name: /Menunggu cuci/ })).toBeNull()
  })
})

describe('saving a receipt', () => {
  const backend = () =>
    mockBackend({
      'GET /api/auth/me': me('owner'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': () => ({ body: [order()] }),
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
    })

  it('names the PDF "RESIT CUCI CUCI SENAWANG" while printing', async () => {
    backend()
    let titleWhilePrinting = ''
    vi.stubGlobal('print', vi.fn(() => (titleWhilePrinting = document.title)))
    const user = renderSignedIn('#/orders/7/resit')

    await user.click(await screen.findByRole('button', { name: 'Cetak / simpan PDF' }))

    expect(titleWhilePrinting).toBe('RESIT CUCI CUCI SENAWANG')
    window.dispatchEvent(new Event('afterprint'))
    expect(document.title).not.toBe('RESIT CUCI CUCI SENAWANG') // the page's own title again
  })

  it('saves the receipt as a JPEG with the same name', async () => {
    backend()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const user = renderSignedIn('#/orders/7/resit')

    await user.click(await screen.findByRole('button', { name: 'Simpan / kongsi gambar (JPEG)' }))

    await waitFor(() => expect(click).toHaveBeenCalled())
    const link = click.mock.contexts[0] as HTMLAnchorElement
    expect(link.download).toBe('RESIT CUCI CUCI SENAWANG.jpg')
    expect(link.href).toMatch(/^data:image\/jpeg/)
    click.mockRestore()
  })
})


describe('finding a receipt', () => {
  it('searches every order by name or phone and opens the one tapped', async () => {
    const other = order({ id: 9, number: 20, code: '20', customer: { ...order().customer, id: 4, name: 'Puan Aisyah', phone: '+60135550352' } })
    const calls = mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/orders': (call) => ({ body: call.query.get('q') ? [other] : [order()] }),
      'GET /api/orders/7/receipt': () => ({ body: receipt() }),
      'GET /api/orders/9/receipt': () => ({ body: { ...receipt(), order: other } }),
    })
    const user = renderSignedIn('#/orders/7/resit')

    await user.type(await screen.findByLabelText('Cari resit pelanggan'), 'aisyah')
    const results = await screen.findByRole('list', { name: 'Hasil carian' })
    expect(results).toHaveTextContent('#20 Puan Aisyah')
    expect(calls.find((c) => c.query.get('q'))?.query.get('q')).toBe('aisyah')

    await user.click(within(results).getByRole('link', { name: /Puan Aisyah/ }))
    expect(await screen.findByRole('article', { name: 'Resit 20' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Hasil carian' })).toBeNull()
  })
})

describe('waiting to be washed', () => {
  it('shows when each carpet arrived and how long it has waited', async () => {
    const daysAgo = (n: number) => {
      const d = new Date(`${todayInMalaysia()}T12:00:00+08:00`)
      d.setUTCDate(d.getUTCDate() - n)
      return d.toISOString().slice(0, 10)
    }
    const items = [
      workItem({ id: 1, tag: '412-1', received_on: daysAgo(8) }),
      workItem({ id: 2, tag: '413-1', order_id: 8, order_number: 413, received_on: daysAgo(4) }),
      workItem({ id: 3, tag: '414-1', order_id: 9, order_number: 414, received_on: daysAgo(0) }),
    ]
    mockBackend({
      'GET /api/auth/me': me('staff'),
      'GET /api/business': () => ({ body: REAL_BUSINESS }),
      'GET /api/work/items': () => ({ body: items }),
      'GET /api/work/log': (call) => ({ body: { day: call.query.get('day'), washed: [], packed: [] } }),
      'GET /api/work/untagged': () => ({ body: [] }),
    })
    renderSignedIn('#/cuci')

    expect(await screen.findByText(/8 hari lalu/)).toHaveClass('text-rose-800') // a week or more: red
    expect(screen.getByText(/4 hari lalu/)).toHaveClass('text-amber-900')
    expect(screen.getByText(/hari ini/)).toHaveTextContent(`Diterima ${formatShortDate(daysAgo(0))} · hari ini`)
  })
})
