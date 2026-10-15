import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { ORDER_STATUS_LABEL, ORDER_STATUS_STYLE, formatDay, formatMoney, formatSize } from './format'
import type { Order, OrderStatus } from './types'
import { href } from './useHashRoute'

// Today's work first: what still needs washing, then what can be handed back.
const FILTERS: { value: OrderStatus | ''; label: string }[] = [
  { value: 'received', label: 'Belum dicuci' },
  { value: 'washed', label: 'Sedang kering' },
  { value: 'ready', label: 'Siap' },
  { value: '', label: 'Semua' },
]

export function OrdersPage() {
  const { request } = useAuth()
  const [status, setStatus] = useState<OrderStatus | ''>('received')
  const [query, setQuery] = useState('')
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    const params = new URLSearchParams()
    // A search looks through every status: a customer asking about a tag may be anywhere.
    if (query.trim()) params.set('q', query.trim())
    else if (status) params.set('status', status)
    const timer = setTimeout(() => {
      request<Order[]>(`/api/orders?${params}`)
        .then((data) => {
          if (current) {
            setOrders(data)
            setError(false)
          }
        })
        .catch(() => {
          if (current) setError(true)
        })
    }, 250) // wait for typing to pause
    return () => {
      current = false
      clearTimeout(timer)
    }
  }, [request, status, query])

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-bold">Pesanan</h1>
        <a href={href({ page: 'new-order' })} className="rounded-full bg-brand px-5 py-3 font-semibold hover:bg-brand-hover">
          + Pesanan baru
        </a>
      </div>

      <label className="block">
        <span className="sr-only">Cari pesanan</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Cari: no. pesanan, tag (412-2), telefon atau nama"
          className="w-full rounded-2xl bg-white px-4 py-3 ring-1 ring-line outline-none focus:ring-2 focus:ring-brand"
        />
      </label>

      {!query.trim() && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Tapis status">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              aria-pressed={status === f.value}
              onClick={() => setStatus(f.value)}
              className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-line aria-pressed:bg-ink aria-pressed:text-white"
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {error && <p role="alert" className="text-danger">Tak dapat muatkan pesanan. Cuba lagi.</p>}
      {orders === null && !error && <p className="text-ink-soft">Memuatkan…</p>}
      {orders?.length === 0 && <p className="text-ink-soft">Tiada pesanan di sini.</p>}

      <ul className="space-y-3">
        {orders?.map((order) => (
          <li key={order.id}>
            <OrderCard order={order} />
          </li>
        ))}
      </ul>
    </section>
  )
}

export function OrderCard({ order }: { order: Order }) {
  const items = order.items.map((i) => `${i.service.name} ${formatSize(i)}`).join(', ')
  return (
    <a
      href={href({ page: 'order', id: order.id })}
      aria-label={`Pesanan ${order.number}, ${order.customer.name}`}
      className="block rounded-2xl bg-white p-4 ring-1 ring-line hover:ring-ink/30"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">
            #{order.number} · {order.customer.name}
          </p>
          <p className="text-sm text-ink-soft">
            {order.customer.phone} · diterima {formatDay(order.received_on)}
          </p>
          <p className="mt-1 truncate text-sm">{items}</p>
        </div>
        <div className="shrink-0 text-right">
          <span className={`rounded-full px-3 py-1 text-xs font-bold ${ORDER_STATUS_STYLE[order.status]}`}>
            {ORDER_STATUS_LABEL[order.status]}
          </span>
          <p className="mt-2 font-semibold">{order.price_pending ? 'Harga belum lengkap' : formatMoney(order.total)}</p>
          {Number(order.balance) > 0 && !order.price_pending && (
            <p className="text-xs text-ink-soft">Baki {formatMoney(order.balance)}</p>
          )}
        </div>
      </div>
      {order.status === 'washed' && order.ready_from && order.ready_by && (
        <p className="mt-2 text-xs text-ink-soft">
          Jangka kering: {formatDay(order.ready_from)} – {formatDay(order.ready_by)}
        </p>
      )}
    </a>
  )
}
