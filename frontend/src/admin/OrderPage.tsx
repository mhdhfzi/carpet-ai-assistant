import { useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import {
  ORDER_ACTION_LABEL,
  ORDER_STATUS_LABEL,
  ALL_ITEMS_ACTION_LABEL,
  FOLD_LABEL,
  ITEM_ACTION_LABEL,
  ITEM_STATUS_LABEL,
  ITEM_STATUS_STYLE,
  ORDER_STATUS_STYLE,
  PAYMENT_LABEL,
  RETURN_LABEL,
  formatDateTime,
  formatDay,
  formatMoney,
  formatSize,
  formatVisit,
  isHomeJob,
  needsMeasuring,
  whatsAppUrl,
  roundingOf,
} from './format'
import { ItemsEditor, NumberField } from './ItemsEditor'
import { type ItemRow, rowProblem, rowsFromItems, rowsToInput } from './itemRows'
import {
  type ItemFold,
  type ItemStatus,
  NEXT_ITEM_STATUS,
  type Order,
  type OrderStatus,
  type PaymentMethod,
  type Receipt,
  type ReturnMethod,
} from './types'
import { OwnerRecordsNote, QrPayButton } from './QrPay'
import { ReceiptSentLine, useReceiptSent } from './ReceiptSent'
import { notifyWorkChanged } from './summary'
import { VisitEditor } from './VisitEditor'
import { readyMessage, receiptMessage } from './whatsappMessages'
import { href } from './useHashRoute'
import { useServices } from './useServices'

const ALL_STATUSES: OrderStatus[] = ['received', 'washed', 'ready', 'completed', 'cancelled']

export function OrderPage({ id, edit = false }: { id: number; edit?: boolean }) {
  const { request, state } = useAuth()
  const isOwner = state.status === 'signed-in' && state.owner.role === 'owner'
  const [order, setOrder] = useState<Order | null>(null)
  const [business, setBusiness] = useState<Receipt['business'] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(edit) // opened from the book's "Ubah barang"

  useEffect(() => {
    let current = true
    // The receipt view: the order plus the business details the WhatsApp messages need.
    request<Receipt>(`/api/orders/${id}/receipt`)
      .then((data) => {
        if (!current) return
        setOrder(data.order)
        setBusiness(data.business)
      })
      .catch(() => {
        if (current) setLoadError(true)
      })
    return () => {
      current = false
    }
  }, [id, request])

  const send = async (path: string, method: string, body: Record<string, unknown>) => {
    setBusy(true)
    setError(null)
    try {
      setOrder(await request<Order>(`/api/orders/${id}${path}`, { method, body }))
      notifyWorkChanged()
      setEditing(false)
    } catch (err) {
      setError(errorMessage(err, 'Tak dapat simpan perubahan. Cuba lagi.'))
    } finally {
      setBusy(false)
    }
  }
  const save = (changes: Record<string, unknown>) => send('', 'PATCH', changes)

  if (loadError) return <p role="alert" className="text-danger">Pesanan tak dijumpai.</p>
  if (!order) return <p className="text-ink-soft">Memuatkan…</p>

  const next = order.next_status ?? undefined
  const homeJobs = order.items.some(isHomeJob)
  const homeOnly = order.items.every(isHomeJob)
  const closed = order.status === 'completed' || order.status === 'cancelled'
  // Velvet is packed rolled or folded, so it can't be packed with the rest in one go.
  const velvetToPack = order.items.some((i) => i.status === 'washed' && i.service.needs_fold)
  // Unmeasured carpets get their size on Borang Cuci, as they're washed.
  const toMeasure = order.items.some((i) => i.status === 'received' && needsMeasuring(i))

  return (
    <article className="mx-auto max-w-xl space-y-5">
      {order.kind === 'on_site' ? (
        <a href={href({ page: 'visits', book: true })} className="text-sm underline">
          ← Buku kerja luar
        </a>
      ) : (
        <a href={href({ page: 'orders' })} className="text-sm underline">
          ← Semua pesanan
        </a>
      )}

      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">{order.kind === 'on_site' ? 'Kerja luar' : 'Pesanan'} {order.code}</h1>
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

      {next === 'ready' && velvetToPack ? (
        <p className="rounded-2xl bg-white p-4 text-center text-sm ring-1 ring-line">
          Ada karpet velvet: pack setiap karpet di bawah dan pilih Gulung atau Lipat.
        </p>
      ) : next === 'washed' && toMeasure ? (
        <p className="rounded-2xl bg-white p-4 text-center text-sm ring-1 ring-line">
          Ada karpet belum diukur: isi saiz dan tandakan siap cuci di{' '}
          <a href={href({ page: 'wash' })} className="font-semibold underline">
            Borang Cuci
          </a>
          .
        </p>
      ) : next && (
        <button
          type="button"
          disabled={busy}
          onClick={() => save({ status: next })}
          className="w-full rounded-full bg-brand py-4 text-lg font-semibold hover:bg-brand-hover disabled:opacity-50"
        >
          {homeOnly && next === 'ready'
            ? 'Tandakan siap (kerja luar selesai)'
            : (order.items.length > 1 && ALL_ITEMS_ACTION_LABEL[next]) || ORDER_ACTION_LABEL[next]}
        </button>
      )}
      {next === 'completed' && Number(order.balance) > 0 && (
        <p className="text-center text-sm font-semibold text-danger">
          Baki {formatMoney(order.balance)} belum dibayar: rekod bayaran di bawah dulu.
        </p>
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
        <EditItems
          order={order}
          isOwner={isOwner}
          busy={busy}
          onCancel={() => setEditing(false)}
          onSave={save}
          onCancelItem={(itemId, reason) => send(`/items/${itemId}/cancel`, 'POST', { reason })}
        />
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
              <li key={item.id} className="space-y-2 p-3">
                <div className="flex justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold">
                    <span className="mr-2 rounded bg-ink px-1.5 py-0.5 font-mono text-xs text-white">{item.tag}</span>
                    {item.service.name}
                    {item.fold && <span className="ml-1 text-sm font-normal text-purple-800">({FOLD_LABEL[item.fold]})</span>}
                  </p>
                  <p className="text-sm text-ink-soft">
                    {formatSize(item)}
                    {item.service.pricing_unit === 'per_sqft' && item.quantity !== null && ` (${Number(item.quantity)} kaki persegi)`}
                  </p>
                  {item.notes && <p className="text-sm">Catatan: {item.notes}</p>}
                </div>
                <p className="shrink-0 font-semibold">{item.line_total ? formatMoney(item.line_total) : needsMeasuring(item) ? 'Harga selepas diukur' : 'Harga belum ditetapkan'}</p>
                </div>
                <ItemProgress
                  item={item}
                  open={!closed}
                  isOwner={isOwner}
                  busy={busy}
                  onMove={(status, fold) => send(`/items/${item.id}`, 'PATCH', { status, fold })}
                />
              </li>
            ))}
            {order.cancelled_items.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-3 bg-slate-50 p-3 text-ink-soft">
                <div className="min-w-0">
                  <p className="font-semibold line-through">
                    <span className="mr-2 rounded bg-slate-300 px-1.5 py-0.5 font-mono text-xs text-slate-700">{item.tag}</span>
                    {item.service.name}
                  </p>
                  <p className="text-xs">
                    Dibatalkan{item.cancelled_on && ` ${formatDay(item.cancelled_on)}`}
                    {item.cancelled_by && ` (${item.cancelled_by})`}
                    {item.cancel_reason && ` · ${item.cancel_reason}`}
                  </p>
                </div>
                {isOwner && order.status !== 'cancelled' && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => send(`/items/${item.id}/restore`, 'POST', {})}
                    className="shrink-0 text-xs underline"
                  >
                    Pulihkan
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {homeJobs && order.status !== 'cancelled' && (
        <section className="space-y-2 rounded-2xl bg-white p-4 ring-1 ring-line">
          <h2 className="font-semibold">Lawatan ke rumah pelanggan</h2>
          <p className="text-sm text-ink-soft">
            {order.visit_at ? formatVisit(order.visit_at) : 'Masa lawatan belum ditetapkan.'}
          </p>
          {!closed && <VisitEditor key={order.visit_at ?? ''} order={order} busy={busy} onSave={(visitAt) => save({ visit_at: visitAt })} />}
        </section>
      )}

      <Payments
        order={order}
        isOwner={isOwner}
        busy={busy}
        business={business}
        onPay={(payment) => send('/payments', 'POST', payment)}
        onVoid={(paymentId, reason) => send(`/payments/${paymentId}/void`, 'POST', { reason })}
      />

      {business && <SendToCustomer order={order} business={business} onRecorded={setOrder} />}

      {/* Only carpets go back to the customer; a home job is finished at their house. */}
      {order.items.some((i) => !i.service.on_site) && (
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
      )}

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
              {event.item_tag && <span className="mr-1 rounded bg-ink px-1 font-mono text-xs text-white">{event.item_tag}</span>}
              <span className="font-semibold">
                {eventLabel(order, event)}
              </span>{' '}
              · {formatDateTime(event.at)}
              {event.by && ` · ${event.by}`}
              {event.note && <span className="text-ink-soft"> — {event.note}</span>}
            </li>
          ))}
        </ol>
      </section>
    </article>
  )
}

function Payments({
  order,
  isOwner,
  busy,
  onPay,
  onVoid,
  business,
}: {
  order: Order
  isOwner: boolean
  busy: boolean
  business: Receipt['business'] | null
  onPay: (payment: Record<string, unknown>) => Promise<void>
  onVoid: (paymentId: number, reason: string) => Promise<void>
}) {
  const owed = Number(order.balance)
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState<PaymentMethod>('cash')
  const canPay = order.status !== 'cancelled' && (owed > 0 || order.price_pending)

  return (
    <section className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-line">
      <h2 className="font-semibold">Bayaran</h2>
      <div className="space-y-1">
        <Row label="Jumlah barang" value={formatMoney(order.subtotal)} />
        {Number(order.discount) > 0 && <Row label="Diskaun" value={`− ${formatMoney(order.discount)}`} />}
        {roundingOf(order) > 0 && <Row label="Pembundaran (sen dibuang)" value={`− ${formatMoney(roundingOf(order).toFixed(2))}`} />}
        <Row label={order.price_pending ? 'Jumlah (belum lengkap)' : 'Jumlah'} value={formatMoney(order.total)} strong />
        <Row label="Sudah dibayar" value={formatMoney(order.paid)} />
        {owed < 0 ? (
          // e.g. an item cancelled after a big deposit: money to give back.
          <p className="flex justify-between rounded-lg bg-rose-50 px-2 py-1 font-semibold text-rose-800">
            <span>Lebihan bayar, perlu dipulangkan</span>
            <span>{formatMoney(String(-owed))}</span>
          </p>
        ) : (
          <Row label="Baki" value={formatMoney(order.balance)} strong />
        )}
      </div>

      {order.payments.length > 0 && (
        <ul className="divide-y divide-line border-t border-line text-sm" aria-label="Senarai bayaran">
          {order.payments.map((p) => (
            <li key={p.id} className={`flex items-start justify-between gap-3 py-2 ${p.voided ? 'text-ink-soft' : ''}`}>
              <div>
                <p className={p.voided ? 'line-through' : ''}>
                  {formatDay(p.paid_on)} · {PAYMENT_LABEL[p.method]}
                  {p.note && ` · ${p.note}`}
                </p>
                <p className="text-xs text-ink-soft">
                  {p.received_by && `Diterima oleh ${p.received_by}`}
                  {p.voided && ` · Dibatalkan: ${p.void_reason}`}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className={`font-semibold ${p.voided ? 'line-through' : ''}`}>{formatMoney(p.amount)}</p>
                {isOwner && !p.voided && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      const reason = window.prompt('Sebab batalkan bayaran ini?')
                      if (reason && reason.trim().length >= 3) void onVoid(p.id, reason.trim())
                    }}
                    className="text-xs text-danger underline"
                  >
                    Batalkan
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {canPay && business?.duitnow_qr && owed > 0 && !order.price_pending && (
        <QrPayButton
          qr={business.duitnow_qr}
          amount={order.balance}
          reference={order.code}
          payee={business.name}
          busy={busy}
          onReceived={isOwner ? () => onPay({ amount: owed.toFixed(2), method: 'duitnow', note: 'DuitNow QR' }) : undefined}
        />
      )}

      {canPay && !isOwner && <OwnerRecordsNote />}

      {canPay && isOwner && (
        <div className="space-y-3 border-t border-line pt-3">
          <p className="text-sm font-semibold">Rekod bayaran</p>
          <NumberField label="Jumlah dibayar (RM)" value={amount} onChange={setAmount} />
          {owed > 0 && (
            <button type="button" onClick={() => setAmount(owed.toFixed(2))} className="text-sm underline">
              Bayar penuh baki ({formatMoney(order.balance)})
            </button>
          )}
          <div className="flex flex-wrap gap-2" role="group" aria-label="Cara bayaran">
            {(Object.keys(PAYMENT_LABEL) as PaymentMethod[]).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={method === m}
                onClick={() => setMethod(m)}
                className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-line aria-pressed:bg-ink aria-pressed:text-white"
              >
                {PAYMENT_LABEL[m]}
              </button>
            ))}
          </div>
          <button
            type="button"
            disabled={busy || !(Number(amount) > 0)}
            onClick={async () => {
              await onPay({ amount, method })
              setAmount('')
            }}
            className="w-full rounded-full bg-ink py-3 font-semibold text-white disabled:opacity-40"
          >
            Simpan bayaran
          </button>
        </div>
      )}
    </section>
  )
}

/** "Siap dipack" for a carpet, "Siap (kerja luar)" for a job done at the customer's home. */
function eventLabel(order: Order, event: Order['events'][number]): string {
  if (!event.item_tag) return ORDER_STATUS_LABEL[event.status]
  const item = order.items.find((i) => i.tag === event.item_tag)
  if (item?.service.on_site) return event.status === 'ready' ? 'Siap (kerja luar)' : 'Belum dibuat (kerja luar)'
  return ITEM_STATUS_LABEL[event.status as ItemStatus] ?? ORDER_STATUS_LABEL[event.status]
}

function SendToCustomer({
  order,
  business,
  onRecorded,
}: {
  order: Order
  business: Receipt['business']
  onRecorded: (order: Order) => void
}) {
  // "Your carpets are ready to collect" is about carpets; a home job is done in front of them.
  const ready = (order.status === 'ready' || order.status === 'completed') && order.items.some((i) => !i.service.on_site)
  const { ask, prompt } = useReceiptSent(order, onRecorded)
  return (
    <section className="space-y-2 rounded-2xl bg-white p-4 ring-1 ring-line">
      <h2 className="font-semibold">Hantar kepada pelanggan</h2>
      <p className="text-sm text-ink-soft">WhatsApp dibuka dengan mesej siap ditulis. Semak, kemudian tekan Hantar.</p>
      <ReceiptSentLine order={order} />
      <div className="flex flex-wrap gap-2">
        {ready && (
          <a
            href={whatsAppUrl(order.customer.phone, readyMessage(order, business.name, business.payment_details))}
            target="_blank"
            rel="noreferrer"
            className="rounded-full bg-[#1f9e4f] px-4 py-2 text-sm font-semibold text-white"
          >
            WhatsApp: barang siap
          </a>
        )}
        <a
          href={whatsAppUrl(order.customer.phone, receiptMessage(order, business))}
          target="_blank"
          rel="noreferrer"
          onClick={() => ask('whatsapp')}
          className="rounded-full bg-[#1f9e4f] px-4 py-2 text-sm font-semibold text-white"
        >
          WhatsApp: resit
        </a>
        <a href={href({ page: 'receipt', id: order.id })} className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-line">
          Lihat / cetak resit
        </a>
      </div>
      {prompt}
    </section>
  )
}

/** One carpet's step, its drying window, and the button for its next step. */
function ItemProgress({
  item,
  open,
  isOwner,
  busy,
  onMove,
}: {
  item: Order['items'][number]
  open: boolean
  isOwner: boolean
  busy: boolean
  onMove: (status: ItemStatus, fold?: ItemFold) => Promise<void>
}) {
  const home = isHomeJob(item)
  // A home job is done in one visit: not done yet, then done.
  const next = home ? (item.status === 'ready' ? undefined : 'ready') : NEXT_ITEM_STATUS[item.status]
  // Packing velvet: one button per way of packing it.
  const choices: { label: string; fold?: ItemFold }[] =
    next === 'ready' && item.service.needs_fold
      ? (['rolled', 'folded'] as const).map((fold) => ({ label: `Pack: ${FOLD_LABEL[fold]}`, fold }))
      : next
        ? [{ label: home ? 'Tandakan siap' : ITEM_ACTION_LABEL[next] }]
        : []
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${ITEM_STATUS_STYLE[item.status]}`}>
        {home ? (item.status === 'ready' ? 'Siap (kerja luar)' : 'Belum dibuat (kerja luar)') : ITEM_STATUS_LABEL[item.status]}
      </span>
      <span className="text-xs text-ink-soft">{stepHistory(item)}</span>
      {open && next === 'washed' && needsMeasuring(item) ? (
        <a
          href={href({ page: 'wash' })}
          className="ml-auto rounded-full bg-brand px-3 py-1.5 text-xs font-semibold hover:bg-brand-hover"
        >
          Ukur & cuci
        </a>
      ) : (
        open &&
        next &&
        choices.map((choice, index) => (
          <button
            key={choice.label}
            type="button"
            disabled={busy}
            onClick={() => onMove(next, choice.fold)}
            className={`${index === 0 ? 'ml-auto ' : ''}rounded-full bg-brand px-3 py-1.5 text-xs font-semibold hover:bg-brand-hover disabled:opacity-50`}
          >
            {choice.label}
          </button>
        ))
      )}
      {open && isOwner && item.status !== 'received' && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onMove(item.status === 'ready' && !home ? 'washed' : 'received')}
          className={`${next ? '' : 'ml-auto '}text-xs text-ink-soft underline`}
        >
          Undur
        </button>
      )}
    </div>
  )
}

/** "dicuci 15 Oct (Amir) · kering 20–22 Oct" or "dipack 21 Oct (Razi), Gulung". */
function stepHistory(item: Order['items'][number]): string {
  const by = (name: string | null) => (name ? ` (${name})` : '')
  const parts: string[] = []
  if (item.washed_on) parts.push(`dicuci ${formatDay(item.washed_on)}${by(item.washed_by)}`)
  if (item.ready_from && item.ready_by) parts.push(`kering ${formatDay(item.ready_from)}–${formatDay(item.ready_by)}`)
  if (item.ready_on && isHomeJob(item)) {
    parts.push(`siap ${formatDay(item.ready_on)}${by(item.packed_by)}`)
  } else if (item.ready_on) {
    parts.push(`dipack ${formatDay(item.ready_on)}${by(item.packed_by)}${item.fold ? `, ${FOLD_LABEL[item.fold]}` : ''}`)
  }
  return parts.join(' · ')
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
  onCancelItem,
}: {
  order: Order
  isOwner: boolean
  busy: boolean
  onCancel: () => void
  onSave: (changes: Record<string, unknown>) => Promise<void>
  onCancelItem: (itemId: number, reason: string) => Promise<void>
}) {
  const all = useServices()
  const [rows, setRows] = useState<ItemRow[]>(() => rowsFromItems(order.items))
  const [discount, setDiscount] = useState(Number(order.discount) > 0 ? String(Number(order.discount)) : '')
  const [problem, setProblem] = useState<string | null>(null)
  if (all === null) return <p className="text-ink-soft">Memuatkan…</p>
  // Only this book's services: carpets in Buku Utama, kerja luar in Buku Kerja Luar.
  const services = all.filter((s) => s.on_site === (order.kind === 'on_site'))
  const saveItems = () => {
    const missing = rows
      .map((row) => rowProblem(row, services.find((s) => s.id === row.serviceId), row.tag ? `Barang ${row.tag}` : 'Barang baru'))
      .find(Boolean)
    setProblem(missing ?? null)
    if (missing) return
    void onSave({
      items: rowsToInput(rows),
      ...(isOwner && discount !== (Number(order.discount) > 0 ? String(Number(order.discount)) : '') ? { discount: discount || '0' } : {}),
    })
  }
  const cancelItem = (row: ItemRow) => {
    const name = services.find((s) => s.id === row.serviceId)?.name ?? ''
    const reason = window.prompt(`Batalkan ${row.tag} ${name}? Tulis sebab (cth. harga mahal):`)
    if (reason && reason.trim().length >= 3 && row.id) void onCancelItem(row.id, reason.trim())
  }
  return (
    <section className="space-y-3">
      <h2 className="font-semibold">Ubah barang</h2>
      <p className="text-sm text-ink-soft">Pelanggan tak mahu satu barang? Tekan "Batal barang": nombor tag yang lain kekal.</p>
      <ItemsEditor services={services} rows={rows} onChange={setRows} isOwner={isOwner} onCancelItem={cancelItem} />
      {isOwner && (
        <div className="rounded-2xl bg-white p-4 ring-1 ring-line">
          <NumberField label="Diskaun (RM)" value={discount} onChange={setDiscount} />
        </div>
      )}
      {problem && (
        <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-danger ring-1 ring-red-200">
          {problem}
        </p>
      )}
      <div className="flex gap-3">
        <button type="button" disabled={busy} onClick={saveItems} className="flex-1 rounded-full bg-brand py-3 font-semibold disabled:opacity-50">
          Simpan barang
        </button>
        <button type="button" onClick={onCancel} className="rounded-full px-5 py-3 font-semibold ring-1 ring-line">
          Batal
        </button>
      </div>
    </section>
  )
}
