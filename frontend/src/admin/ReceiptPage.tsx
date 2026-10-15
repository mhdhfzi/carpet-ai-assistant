import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { PAYMENT_LABEL, formatDay, formatMoney, formatSize } from './format'
import type { Receipt } from './types'
import { href } from './useHashRoute'

/** A printable receipt. "Cetak / simpan PDF" opens the browser's print dialog, where a
 * phone can also save it as a PDF to send. Its number is the order number. */
export function ReceiptPage({ id }: { id: number }) {
  const { request } = useAuth()
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    request<Receipt>(`/api/orders/${id}/receipt`)
      .then((data) => {
        if (current) setReceipt(data)
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [id, request])

  if (error) return <p role="alert" className="text-danger">Resit tak dijumpai.</p>
  if (!receipt) return <p className="text-ink-soft">Memuatkan…</p>

  const { business, order } = receipt
  const payments = order.payments.filter((p) => !p.voided)

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div className="flex items-center justify-between gap-3 print:hidden">
        <a href={href({ page: 'order', id: order.id })} className="text-sm underline">
          ← Pesanan #{order.number}
        </a>
        <button type="button" onClick={() => window.print()} className="rounded-full bg-brand px-5 py-2 font-semibold">
          Cetak / simpan PDF
        </button>
      </div>

      <article className="space-y-5 rounded-2xl bg-white p-6 ring-1 ring-line print:rounded-none print:p-0 print:ring-0">
        <header className="space-y-0.5 text-center">
          <h1 className="font-display text-xl font-bold">{business.name}</h1>
          {business.reg_no && <p className="text-xs">No. SSM: {business.reg_no}</p>}
          {business.address && <p className="text-xs">{business.address}</p>}
          {business.phone && <p className="text-xs">Tel / WhatsApp: {business.phone}</p>}
        </header>

        <div className="flex justify-between border-y border-line py-2 text-sm">
          <div>
            <p className="font-bold">RESIT</p>
            <p>No. {order.number}</p>
          </div>
          <div className="text-right">
            <p>Tarikh: {formatDay(receipt.issued_on)}</p>
            <p>Diterima: {formatDay(order.received_on)}</p>
          </div>
        </div>

        <div className="text-sm">
          <p className="font-semibold">{order.customer.name}</p>
          <p>{order.customer.phone}</p>
          {(order.customer.address || order.customer.area) && (
            <p>{[order.customer.address, order.customer.area].filter(Boolean).join(', ')}</p>
          )}
        </div>

        <table className="w-full text-sm">
          <thead className="border-b border-line text-left text-xs text-ink-soft">
            <tr>
              <th scope="col" className="py-1">Tag</th>
              <th scope="col" className="py-1">Barang</th>
              <th scope="col" className="py-1 text-right">Harga</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.id} className="align-top">
                <td className="py-1 pr-2 font-mono">{item.tag}</td>
                <td className="py-1">
                  {item.service.name}
                  <span className="block text-xs text-ink-soft">
                    {formatSize(item)}
                    {item.service.pricing_unit === 'per_sqft' && ` (${Number(item.quantity)} kaki persegi)`}
                    {item.unit_price && ` × ${formatMoney(item.unit_price)}`}
                  </span>
                </td>
                <td className="py-1 text-right whitespace-nowrap">{item.line_total ? formatMoney(item.line_total) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="space-y-1 border-t border-line pt-2 text-sm">
          <Line label="Jumlah barang" value={formatMoney(order.subtotal)} />
          {Number(order.discount) > 0 && <Line label="Diskaun" value={`− ${formatMoney(order.discount)}`} />}
          <Line label="Jumlah" value={formatMoney(order.total)} strong />
          {payments.map((p) => (
            <Line
              key={p.id}
              label={`Dibayar ${formatDay(p.paid_on)} (${PAYMENT_LABEL[p.method]}${p.note ? `, ${p.note}` : ''})`}
              value={`− ${formatMoney(p.amount)}`}
            />
          ))}
          <Line label="Baki" value={formatMoney(order.balance)} strong />
          {order.price_pending && <p className="text-xs text-ink-soft">Sebahagian harga belum ditetapkan.</p>}
        </div>

        {Number(order.balance) > 0 && business.payment_details && (
          <p className="rounded-xl bg-foam p-3 text-sm">Bayaran: {business.payment_details}</p>
        )}
        <p className="text-center text-sm">{Number(order.balance) > 0 ? 'Terima kasih.' : 'Telah dibayar sepenuhnya. Terima kasih!'}</p>
      </article>
    </div>
  )
}

function Line({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <p className={`flex justify-between gap-3 ${strong ? 'font-semibold' : ''}`}>
      <span>{label}</span>
      <span className="whitespace-nowrap">{value}</span>
    </p>
  )
}
