import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { formatDay, whatsAppUrl } from './format'
import { OrderCard } from './OrdersPage'
import type { CustomerDetail } from './types'
import { href } from './useHashRoute'

export function CustomerPage({ id }: { id: number }) {
  const { request } = useAuth()
  const [customer, setCustomer] = useState<CustomerDetail | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    request<CustomerDetail>(`/api/customers/${id}`)
      .then((data) => {
        if (current) setCustomer(data)
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [id, request])

  if (error) return <p role="alert" className="text-danger">Pelanggan tak dijumpai.</p>
  if (!customer) return <p className="text-ink-soft">Memuatkan…</p>

  return (
    <article className="mx-auto max-w-xl space-y-5">
      <a href={href({ page: 'customers' })} className="text-sm underline">
        ← Semua pelanggan
      </a>
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">{customer.name}</h1>
        <p className="text-sm">
          <a className="underline" href={`tel:${customer.phone}`}>
            {customer.phone}
          </a>
          {' · '}
          <a className="underline" href={whatsAppUrl(customer.phone)} target="_blank" rel="noreferrer">
            WhatsApp
          </a>
        </p>
        {(customer.address || customer.area) && (
          <p className="text-sm text-ink-soft">{[customer.address, customer.area].filter(Boolean).join(', ')}</p>
        )}
        <p className="text-sm text-ink-soft">
          {customer.orders} pesanan
          {customer.last_order_on && ` · terakhir ${formatDay(customer.last_order_on)}`}
        </p>
      </header>
      <ul className="space-y-3">
        {customer.order_history.map((order) => (
          <li key={order.id}>
            <OrderCard order={order} />
          </li>
        ))}
      </ul>
    </article>
  )
}
