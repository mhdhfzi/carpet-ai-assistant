import { useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import { formatDateTime, formatMoney, formatShortDate } from './format'
import { notifyWorkChanged } from './summary'
import type { Order } from './types'
import { href } from './useHashRoute'

// Owner only: orders deleted by mistake or as duplicates. They're hidden everywhere else;
// here the owner sees who deleted each one, when and why, and can bring one back.

export function DeletedOrdersPage() {
  const { request } = useAuth()
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<number | null>(null)

  useEffect(() => {
    let current = true
    request<Order[]>('/api/orders/deleted')
      .then((data) => current && setOrders(data))
      .catch(() => current && setError('Tak dapat muatkan senarai.'))
    return () => {
      current = false
    }
  }, [request])

  const restore = async (order: Order) => {
    if (!window.confirm(`Pulihkan pesanan ${order.code}?`)) return
    setBusy(order.id)
    setError(null)
    try {
      const back = await request<Order>(`/api/orders/${order.id}/restore`, { method: 'POST' })
      notifyWorkChanged()
      window.location.assign(href({ page: 'order', id: back.id }))
    } catch (err) {
      setError(errorMessage(err, 'Tak dapat pulihkan. Cuba lagi.'))
      setBusy(null)
    }
  }

  return (
    <section className="mx-auto max-w-2xl space-y-4">
      <div>
        <a href={href({ page: 'orders' })} className="text-sm underline">
          ← Buku Utama
        </a>
        <h1 className="mt-1 font-display text-2xl font-bold">Pesanan dipadam</h1>
        <p className="text-sm text-ink-soft">Pesanan yang dipadam kerana silap atau berulang. Hanya pemilik nampak senarai ini.</p>
      </div>
      {error && (
        <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-danger ring-1 ring-red-200">
          {error}
        </p>
      )}
      {orders === null && !error && <p className="text-ink-soft">Memuatkan…</p>}
      {orders?.length === 0 && <p className="rounded-xl bg-white p-6 text-center text-ink-soft ring-1 ring-line">Tiada pesanan dipadam.</p>}
      <ul className="space-y-3">
        {orders?.map((order) => (
          <li key={order.id} aria-label={`Pesanan dipadam ${order.code}`} className="space-y-2 rounded-2xl bg-white p-4 ring-1 ring-line">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-bold">
                  {order.kind === 'on_site' ? `Kerja luar ${order.code}` : `Pesanan #${order.code}`} · {order.customer.name}
                </p>
                <p className="text-xs text-ink-soft">
                  Masuk {formatShortDate(order.received_on)} · {order.items.map((i) => i.name).join(', ')} · {formatMoney(order.total)}
                </p>
              </div>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => restore(order)}
                className="shrink-0 rounded-full px-3 py-1.5 text-sm font-semibold ring-1 ring-line hover:bg-foam disabled:opacity-50"
              >
                Pulihkan
              </button>
            </div>
            <p className="text-sm text-rose-800">
              Dipadam {order.deleted_at && formatDateTime(order.deleted_at)}
              {order.deleted_by && ` oleh ${order.deleted_by}`}
              {order.delete_reason && ` · ${order.delete_reason}`}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}
