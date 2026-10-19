import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { formatMoney, formatShortDate, formatSize, whatsAppUrl } from './format'
import { ChatIcon, CheckIcon, PrintIcon } from './icons'
import type { Order, Receipt } from './types'
import { href } from './useHashRoute'
import { paymentLines, readyMessage, receiptMessage } from './whatsappMessages'

// "Resit & WhatsApp": pick an order, check the message, send it on WhatsApp, or print the
// receipt (a phone can save it as a PDF from the print dialog). The receipt copies the
// business's paper one. Its number is the order number. The PAID stamp isn't a switch: it
// appears once the payments recorded cover the total, so a receipt can't say paid when
// it isn't.

export function ReceiptPage({ id }: { id?: number }) {
  const { request } = useAuth()
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState(false)
  const selected = id ?? orders?.[0]?.id

  useEffect(() => {
    let current = true
    const params = new URLSearchParams()
    for (const s of ['received', 'washed', 'ready', 'completed']) params.append('status', s)
    request<Order[]>(`/api/orders?${params}`)
      .then((data) => {
        if (current) setOrders(data)
      })
      .catch(() => {
        if (current) setOrders([])
      })
    return () => {
      current = false
    }
  }, [request])

  useEffect(() => {
    if (selected === undefined) return
    let current = true
    request<Receipt>(`/api/orders/${selected}/receipt`)
      .then((data) => {
        if (current) {
          setReceipt(data)
          setError(false)
        }
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [selected, request])

  if (error) return <p role="alert" className="text-danger">Resit tak dijumpai.</p>
  if (orders?.length === 0 && id === undefined) {
    return <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-ink-soft shadow-sm">Belum ada pesanan.</p>
  }
  if (!receipt || receipt.order.id !== selected) return <p className="text-ink-soft">Memuatkan…</p>

  const { business, order } = receipt
  const choices = orders && !orders.some((o) => o.id === order.id) ? [order, ...orders] : (orders ?? [order])
  const message = receiptMessage(order, business)
  const ready = order.status === 'ready' || order.status === 'completed'
  const paid = paidOn(order)

  return (
    <div className="grid items-start gap-6 lg:grid-cols-12">
      <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-5 print:hidden">
        <h1 className="text-base font-bold text-slate-900">Pilih pelanggan & resit</h1>

        <label className="block">
          <span className="mb-1 block text-xs font-bold text-slate-600">No. siri resit pelanggan</span>
          <select
            value={order.id}
            onChange={(e) => {
              window.location.hash = href({ page: 'receipt', id: Number(e.target.value) })
            }}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold"
          >
            {choices.map((o) => (
              <option key={o.id} value={o.id}>
                #{o.number} — {o.customer.name} ({o.items.length} barang)
              </option>
            ))}
          </select>
        </label>

        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3.5">
          <span className="text-xs font-bold text-slate-700">Setem "PAID":</span>
          {paid ? (
            <span className="flex items-center gap-1 rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-bold text-white">
              <CheckIcon className="size-3.5" /> Aktif: dibayar penuh {formatShortDate(paid)}
            </span>
          ) : (
            <span className="text-right text-xs text-slate-600">
              {order.price_pending ? 'Harga belum lengkap. ' : `Baki ${formatMoney(order.balance)}. `}
              <a href={href({ page: 'order', id: order.id })} className="font-semibold text-slate-900 underline">
                Rekod bayaran
              </a>
            </span>
          )}
        </div>

        <div className="space-y-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs font-extrabold text-emerald-900 uppercase">
              <ChatIcon /> Pratonton mesej WhatsApp
            </span>
            <span className="font-mono text-[11px] text-emerald-800">{order.customer.phone}</span>
          </p>
          <pre className="max-h-80 overflow-y-auto rounded-lg border border-emerald-200 bg-white p-3 font-sans text-xs leading-relaxed whitespace-pre-wrap text-slate-700">
            {message}
          </pre>
          <a
            href={whatsAppUrl(order.customer.phone, message)}
            target="_blank"
            rel="noreferrer"
            className="block w-full rounded-xl bg-emerald-600 py-3 text-center text-sm font-bold text-white shadow transition hover:bg-emerald-700"
          >
            Hantar resit melalui WhatsApp
          </a>
          {ready && (
            <a
              href={whatsAppUrl(order.customer.phone, readyMessage(order, business.name, business.payment_details))}
              target="_blank"
              rel="noreferrer"
              className="block w-full rounded-xl border border-emerald-600 bg-white py-2.5 text-center text-sm font-bold text-emerald-700 hover:bg-emerald-100"
            >
              Hantar mesej "barang siap"
            </a>
          )}
        </div>

        <button
          type="button"
          onClick={() => window.print()}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 py-3 text-sm font-bold text-white hover:bg-slate-800"
        >
          <PrintIcon /> Cetak / simpan PDF
        </button>
      </div>

      <div className="lg:col-span-7">
        <ReceiptSheet receipt={receipt} />
      </div>
    </div>
  )
}

/** The day the payments recorded covered the total (the PAID stamp), or null. */
function paidOn(order: Order): string | null {
  if (order.price_pending || Number(order.total) <= 0 || Number(order.balance) > 0) return null
  return order.payments.filter((p) => !p.voided).at(-1)?.paid_on ?? null
}

/** The printed receipt, laid out like the business's paper one. */
export function ReceiptSheet({ receipt }: { receipt: Receipt }) {
  const { business, order } = receipt
  const paid = paidOn(order)
  const address = [order.customer.address, order.customer.area].filter(Boolean).join(', ')

  return (
    <article
      aria-label={`Resit ${order.number}`}
      className="relative overflow-hidden rounded-xl border-2 border-slate-800 bg-white p-4 shadow-xl sm:p-6 print:rounded-none print:shadow-none"
    >
      <header className="flex flex-wrap items-start justify-between gap-4 border-b-2 border-slate-800 pb-4 sm:flex-nowrap">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="grid size-16 shrink-0 place-items-center rounded-full border-4 border-amber-500 bg-slate-900 text-lg font-black text-amber-400">
            {business.logo}
          </span>
          <div className="min-w-0 text-xs text-slate-700">
            <h2 className="text-xl font-black tracking-tight text-slate-900 uppercase">{business.name}</h2>
            {business.reg_no && <p>No. SSM: {business.reg_no}</p>}
            {business.address && <p>{business.address}</p>}
            {business.email && <p>E-mail: {business.email}</p>}
            {(business.facebook || business.phone) && (
              <p className="font-bold text-slate-900">
                {[business.facebook && `Page FB: ${business.facebook}`, business.phone && `Tel: ${business.phone}`]
                  .filter(Boolean)
                  .join(' • ')}
              </p>
            )}
          </div>
        </div>
        <div className="shrink-0 border-2 border-slate-900 bg-slate-50 px-4 py-1.5 font-mono text-2xl font-black tracking-widest text-slate-900">
          {order.number}
        </div>
      </header>

      <div className="grid gap-3 border-b-2 border-slate-800 py-3 text-sm md:grid-cols-3">
        <p className="md:col-span-2">
          <span className="font-bold text-slate-600">M/S : </span>
          <span className="font-bold text-slate-900 underline decoration-dotted">
            {order.customer.name}
            {address && ` — ${address}`}
          </span>
        </p>
        <div>
          <p>
            <span className="font-bold text-slate-600">DATE : </span>
            <span className="font-mono font-bold">{formatShortDate(order.received_on)}</span>
          </p>
          <p>
            <span className="font-bold text-slate-600">TEL : </span>
            <span className="font-mono font-bold">{order.customer.phone}</span>
          </p>
        </div>
      </div>

      <div className="relative my-4 overflow-x-auto">
        {paid && (
          <div
            aria-label={`Dibayar ${formatShortDate(paid)}`}
            className="pointer-events-none absolute top-8 right-6 z-10 -rotate-8 rounded border-4 border-red-600 bg-white/85 px-6 py-2 text-center text-red-600 shadow-[inset_0_0_0_2px_#dc2626] sm:right-12"
          >
            <p className="text-3xl font-black tracking-widest">PAID</p>
            <p className="border-t border-red-600 pt-0.5 text-xs font-bold">Date : {formatShortDate(paid)}</p>
          </div>
        )}
        <table className="w-full border-2 border-slate-800 text-sm">
          <thead>
            <tr className="bg-slate-900 text-xs text-white uppercase">
              <th scope="col" className="w-12 border-r border-slate-600 px-3 py-2">No.</th>
              <th scope="col" className="border-r border-slate-600 px-3 py-2 text-left">Jenis perniagaan</th>
              <th scope="col" className="w-24 border-r border-slate-600 px-3 py-2 text-center">Kuantiti</th>
              <th scope="col" className="w-24 border-r border-slate-600 px-3 py-2 text-right">Harga</th>
              <th scope="col" className="w-24 px-3 py-2 text-right">Jumlah</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-300">
            {order.items.map((item, index) => (
              <tr key={item.id} className="h-12">
                <td className="border-r border-slate-800 px-3 text-center font-bold">{index + 1}</td>
                <td className="border-r border-slate-800 px-3 py-1.5 font-bold text-slate-900">
                  {item.service.name}{' '}
                  <span className="font-mono font-normal text-slate-600">
                    ({item.tag}
                    {item.length_ft && item.width_ft ? `, ${formatSize(item)}` : ''})
                  </span>
                </td>
                <td className="border-r border-slate-800 px-3 text-center font-bold whitespace-nowrap">
                  {item.service.pricing_unit === 'per_sqft' ? `${Number(item.quantity)} kp²` : Number(item.quantity)}
                </td>
                <td className="border-r border-slate-800 px-3 text-right font-mono whitespace-nowrap">
                  {item.unit_price ? Number(item.unit_price).toFixed(2) : '—'}
                </td>
                <td className="px-3 text-right font-mono font-bold whitespace-nowrap text-slate-900">
                  {item.line_total ? Number(item.line_total).toFixed(2) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid items-center gap-4 pt-2 md:grid-cols-2">
        {business.payment_details ? (
          <div className="rounded border-2 border-slate-800 bg-slate-50 p-3 text-center">
            <p className="text-xs font-bold text-slate-700">Bayaran online</p>
            {paymentLines(business.payment_details).map((line) => (
              <p key={line} className="text-sm font-black text-slate-900">
                {line}
              </p>
            ))}
          </div>
        ) : (
          <div />
        )}
        <div className="space-y-1 text-sm">
          <Total label="Jumlah harga" value={order.subtotal} strong />
          <Total label="Deposit / dibayar" value={order.paid} />
          {Number(order.discount) > 0 && <Total label="Diskaun" value={order.discount} />}
          <Total label="Baki" value={Number(order.balance) > 0 ? order.balance : '0'} strong />
          {order.price_pending && <p className="text-xs text-slate-500">Sebahagian harga belum ditetapkan.</p>}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-6 text-xs text-slate-600">
        <p className="border-t border-slate-400 pt-1">Terima oleh</p>
        <p className="border-t border-slate-400 pt-1">Tandatangan</p>
      </div>

      {business.terms && (
        <p className="mt-4 rounded bg-slate-900 p-2.5 text-center text-[10px] leading-snug font-medium text-white uppercase">
          {business.terms}
        </p>
      )}
    </article>
  )
}

function Total({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <p
      className={`flex justify-between px-3 ${
        strong ? 'border-2 border-slate-800 bg-slate-100 py-1.5 font-black' : 'border border-slate-800 py-1 text-xs font-bold'
      }`}
    >
      <span>{label}</span>
      <span>{formatMoney(value)}</span>
    </p>
  )
}
