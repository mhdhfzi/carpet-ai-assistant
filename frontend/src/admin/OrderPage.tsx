import { useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import {
  ORDER_ACTION_LABEL,
  ORDER_STATUS_LABEL,
  ORDER_STATUS_STYLE,
  RETURN_LABEL,
  formatDateTime,
  formatDay,
  formatMoney,
  formatSize,
  whatsAppUrl,
} from './format'
import { ItemsEditor, NumberField } from './ItemsEditor'
import { type ItemRow, rowsFromItems, rowsToInput } from './itemRows'
import { NEXT_ORDER_STATUS, type Order, type OrderStatus, type ReturnMethod } from './types'
import { href } from './useHashRoute'
import { useServices } from './useServices'

const ALL_STATUSES: OrderStatus[] = ['received', 'washed', 'ready', 'completed', 'cancelled']

export function OrderPage({ id }: { id: number }) {
  const { request, state } = useAuth()
  const isOwner = state.status === 'signed-in' && state.owner.role === 'owner'
  const [order, setOrder] = useState<Order | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    let current = true
    request<Order>(`/api/orders/${id}`)
      .then((data) => {
        if (current) setOrder(data)
      })
      .catch(() => {
        if (current) setLoadError(true)
      })
    return () => {
      current = false
    }
  }, [id, request])

  const save = async (changes: Record<string, unknown>) => {
    setBusy(true)
    setError(null)
    try {
      setOrder(await request<Order>(`/api/orders/${id}`, { method: 'PATCH', body: changes }))
      setEditing(false)
    } catch (err) {
      setError(errorMessage(err, 'Tak dapat simpan perubahan. Cuba lagi.'))
    } finally {
      setBusy(false)
    }
  }

  if (loadError) return <p role="alert" className="text-danger">Pesanan tak dijumpai.</p>
  if (!order) return <p className="text-ink-soft">Memuatkan…</p>

  const next = NEXT_ORDER_STATUS[order.status]
  const closed = order.status === 'completed' || order.status === 'cancelled'

  return (
    <article className="mx-auto max-w-xl space-y-5">
      <a href={href({ page: 'orders' })} className="text-sm underline">
        ← Semua pesanan
      </a>

      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">Pesanan #{order.number}</h1>
          <p className="text-sm text-ink-soft">Diterima {formatDay(order.received_on)}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-bold ${ORDER_STATUS_STYLE[order.status]}`}>
          {ORDER_STATUS_LABEL[order.status]}
        </span>
      </header>

      {error && (
        <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-danger ring-1 ring-red-200">
          {error}
        </p>
      )}

      {next && (
        <button
          type="button"
          disabled={busy}
          onClick={() => save({ status: next })}
          className="w-full rounded-full bg-brand py-4 text-lg font-semibold hover:bg-brand-hover disabled:opacity-50"
        >
          {ORDER_ACTION_LABEL[next]}
        </button>
      )}
      {order.status === 'washed' && order.ready_from && order.ready_by && (
        <p className="text-center text-sm text-ink-soft">
          Jangka kering: {formatDay(order.ready_from)} – {formatDay(order.ready_by)}
        </p>
      )}

      <section className="space-y-1 rounded-2xl bg-white p-4 ring-1 ring-line">
        <h2 className="font-semibold">Pelanggan</h2>
        <p>
          <a href={href({ page: 'customer', id: order.customer.id })} className="underline">
            {order.customer.name}
          </a>
        </p>
        <p className="text-sm">
          <a className="underline" href={`tel:${order.customer.phone}`}>
            {order.customer.phone}
          </a>
          {' · '}
          <a className="underline" href={whatsAppUrl(order.customer.phone)} target="_blank" rel="noreferrer">
            WhatsApp
          </a>
        </p>
        {(order.customer.address || order.customer.area) && (
          <p className="text-sm text-ink-soft">{[order.customer.address, order.customer.area].filter(Boolean).join(', ')}</p>
        )}
      </section>

      {editing ? (
        <EditItems order={order} isOwner={isOwner} busy={busy} onCancel={() => setEditing(false)} onSave={save} />
      ) : (
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Barang</h2>
            {(!closed || isOwner) && order.status !== 'cancelled' && (
              <button type="button" onClick={() => setEditing(true)} className="text-sm underline">
                Ubah barang
              </button>
            )}
          </div>
          <ul className="divide-y divide-line rounded-2xl bg-white ring-1 ring-line">
            {order.items.map((item) => (
              <li key={item.id} className="flex justify-between gap-3 p-3">
                <div className="min-w-0">
                  <p className="font-semibold">
                    <span className="mr-2 rounded bg-ink px-1.5 py-0.5 font-mono text-xs text-white">{item.tag}</span>
                    {item.service.name}
                  </p>
                  <p className="text-sm text-ink-soft">
                    {formatSize(item)}
                    {item.service.pricing_unit === 'per_sqft' && ` (${Number(item.quantity)} kaki persegi)`}
                  </p>
                  {item.notes && <p className="text-sm">Catatan: {item.notes}</p>}
                </div>
                <p className="shrink-0 font-semibold">{item.line_total ? formatMoney(item.line_total) : 'Harga belum ditetapkan'}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Money order={order} isOwner={isOwner} busy={busy} onSave={save} />

      <section className="space-y-2 rounded-2xl bg-white p-4 ring-1 ring-line">
        <h2 className="font-semibold">Cara pulang</h2>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(RETURN_LABEL) as ReturnMethod[]).map((method) => (
            <button
              key={method}
              type="button"
              disabled={busy || order.status === 'cancelled'}
              aria-pressed={order.return_method === method}
              onClick={() => save({ return_method: method })}
              className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-line aria-pressed:bg-ink aria-pressed:text-white"
            >
              {RETURN_LABEL[method]}
            </button>
          ))}
        </div>
        <Notes order={order} busy={busy} onSave={save} />
      </section>

      {isOwner && (
        <section className="space-y-2 rounded-2xl bg-white p-4 ring-1 ring-line">
          <h2 className="font-semibold">Pemilik sahaja</h2>
          <label className="block space-y-1">
            <span className="text-sm">Betulkan status</span>
            <select
              value={order.status}
              disabled={busy}
              onChange={(e) => {
                const status = e.target.value as OrderStatus
                if (status !== 'cancelled' || window.confirm('Batalkan pesanan ini?')) void save({ status })
              }}
              className="w-full rounded-xl bg-foam px-3 py-3"
            >
              {ALL_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {ORDER_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
        </section>
      )}

      <section className="space-y-2">
        <h2 className="font-semibold">Sejarah</h2>
        <ol className="space-y-1 text-sm">
          {order.events.map((event, i) => (
            <li key={i}>
              <span className="font-semibold">{ORDER_STATUS_LABEL[event.status]}</span> · {formatDateTime(event.at)}
              {event.by && ` · ${event.by}`}
              {event.note && <span className="text-ink-soft"> — {event.note}</span>}
            </li>
          ))}
        </ol>
      </section>
    </article>
  )
}

function Money({
  order,
  isOwner,
  busy,
  onSave,
}: {
  order: Order
  isOwner: boolean
  busy: boolean
  onSave: (changes: Record<string, unknown>) => Promise<void>
}) {
  const [deposit, setDeposit] = useState(String(Number(order.deposit)))
  const [discount, setDiscount] = useState(String(Number(order.discount)))
  const changed = Number(deposit) !== Number(order.deposit) || Number(discount) !== Number(order.discount)

  return (
    <section className="space-y-2 rounded-2xl bg-white p-4 ring-1 ring-line">
      <Row label="Jumlah barang" value={formatMoney(order.subtotal)} />
      {Number(order.discount) > 0 && <Row label="Diskaun" value={`− ${formatMoney(order.discount)}`} />}
      <Row label={order.price_pending ? 'Jumlah (belum lengkap)' : 'Jumlah'} value={formatMoney(order.total)} strong />
      <Row label="Deposit" value={formatMoney(order.deposit)} />
      <Row label="Baki" value={formatMoney(order.balance)} strong />
      {order.status !== 'cancelled' && (
        <div className="grid grid-cols-2 gap-3 border-t border-line pt-3">
          <NumberField label="Deposit (RM)" value={deposit} onChange={setDeposit} />
          {isOwner && <NumberField label="Diskaun (RM)" value={discount} onChange={setDiscount} />}
          {changed && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onSave({ deposit: deposit || '0', ...(isOwner ? { discount: discount || '0' } : {}) })}
              className="col-span-2 rounded-full bg-ink py-3 font-semibold text-white disabled:opacity-50"
            >
              Simpan bayaran
            </button>
          )}
        </div>
      )}
    </section>
  )
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <p className={`flex justify-between ${strong ? 'font-semibold' : 'text-sm'}`}>
      <span>{label}</span>
      <span>{value}</span>
    </p>
  )
}

function Notes({ order, busy, onSave }: { order: Order; busy: boolean; onSave: (c: Record<string, unknown>) => Promise<void> }) {
  const [notes, setNotes] = useState(order.notes ?? '')
  return (
    <div className="space-y-2">
      <label className="block space-y-1">
        <span className="text-sm font-semibold">Catatan</span>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="w-full rounded-xl bg-foam px-3 py-3" />
      </label>
      {notes !== (order.notes ?? '') && (
        <button type="button" disabled={busy} onClick={() => onSave({ notes: notes.trim() || null })} className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white">
          Simpan catatan
        </button>
      )}
    </div>
  )
}

function EditItems({
  order,
  isOwner,
  busy,
  onCancel,
  onSave,
}: {
  order: Order
  isOwner: boolean
  busy: boolean
  onCancel: () => void
  onSave: (changes: Record<string, unknown>) => Promise<void>
}) {
  const services = useServices()
  const [rows, setRows] = useState<ItemRow[]>(() => rowsFromItems(order.items))
  if (services === null) return <p className="text-ink-soft">Memuatkan…</p>
  return (
    <section className="space-y-3">
      <h2 className="font-semibold">Ubah barang</h2>
      <ItemsEditor services={services} rows={rows} onChange={setRows} isOwner={isOwner} />
      <div className="flex gap-3">
        <button type="button" disabled={busy} onClick={() => onSave({ items: rowsToInput(rows) })} className="flex-1 rounded-full bg-brand py-3 font-semibold disabled:opacity-50">
          Simpan barang
        </button>
        <button type="button" onClick={onCancel} className="rounded-full px-5 py-3 font-semibold ring-1 ring-line">
          Batal
        </button>
      </div>
    </section>
  )
}
