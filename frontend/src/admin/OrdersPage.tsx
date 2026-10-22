import { useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import {
  ORDER_STATUS_LABEL,
  ORDER_STATUS_STYLE,
  daysBetween,
  formatDay,
  formatMoney,
  formatShortDate,
  formatSize,
  formatVisit,
  isHomeJob,
  readyToPack,
  todayInMalaysia,
} from './format'
import { ArrowIcon, BellIcon, CheckIcon, PhoneIcon, PlusIcon, ReceiptIcon, SearchIcon } from './icons'
import { notifyWorkChanged } from './summary'
import type { Order, OrderItem, OrderKind, OrderStatus } from './types'
import { href } from './useHashRoute'

// The books: Buku Utama for carpets, and the Kerja Luar book for sofa, mattress and car seat
// jobs done at customers' homes. Each lists its orders, where each item is, and what's owed.
// The filters match the questions asked of the book: what's not washed, what can be packed,
// what's ready to go back, who hasn't paid. Finished jobs move to the history.
const OPEN: OrderStatus[] = ['received', 'washed', 'ready']
type Filter = { key: string; label: string; statuses: OrderStatus[]; keep?: (o: Order, today: string) => boolean }
const COMMON: Filter[] = [
  { key: 'ready', label: 'Siap', statuses: ['ready'] },
  { key: 'unpaid', label: 'Belum bayar', statuses: [...OPEN, 'completed'], keep: (o) => owes(o) },
  { key: 'history', label: 'Sejarah', statuses: ['completed', 'cancelled'] },
]
const FILTERS: Record<OrderKind, Filter[]> = {
  shop: [
    { key: 'open', label: 'Semua', statuses: OPEN },
    { key: 'unwashed', label: 'Belum cuci', statuses: ['received'] },
    { key: 'to-pack', label: 'Kering 5–7 hari', statuses: ['received', 'washed'], keep: (o, today) => o.items.some((i) => readyToPack(i, today)) },
    ...COMMON,
  ],
  on_site: [
    { key: 'open', label: 'Semua', statuses: OPEN },
    { key: 'pending', label: 'Belum siap', statuses: ['received'] },
    ...COMMON,
  ],
}

export function OrdersPage({ kind, filter: initial }: { kind: OrderKind; filter?: string }) {
  const { request } = useAuth()
  const today = todayInMalaysia()
  const filters = FILTERS[kind]
  const luar = kind === 'on_site'
  const [filter, setFilter] = useState(filters.find((f) => f.key === initial) ?? filters[0])
  const [query, setQuery] = useState('')
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [error, setError] = useState(false)
  const [version, setVersion] = useState(0)
  const [closing, setClosing] = useState<number | null>(null)
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null)

  /** Picked up or delivered (or a house job finished): the order leaves Siap for Sejarah. */
  const close = async (order: Order) => {
    if (owes(order) && !window.confirm(`Baki ${formatMoney(order.balance)} belum dibayar. Teruskan?`)) return
    setClosing(order.id)
    setNotice(null)
    try {
      await request<Order>(`/api/orders/${order.id}`, { method: 'PATCH', body: { status: 'completed' } })
      setNotice({
        ok: true,
        text: `${order.code} ${order.customer.name}: selesai${owes(order) ? `, baki ${formatMoney(order.balance)} masih di Belum bayar` : ''}.`,
      })
      setVersion((v) => v + 1)
      notifyWorkChanged()
    } catch (err) {
      setNotice({ ok: false, text: errorMessage(err, `Tak dapat tandakan ${order.code} selesai. Cuba lagi.`) })
    } finally {
      setClosing(null)
    }
  }

  useEffect(() => {
    let current = true
    const params = new URLSearchParams({ kind })
    // A search looks through every status: a customer asking about a tag may be anywhere.
    if (query.trim()) params.set('q', query.trim())
    else for (const s of filter.statuses) params.append('status', s)
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
  }, [request, kind, filter, query, version])

  const shown = orders && !query.trim() && filter.keep ? orders.filter((o) => filter.keep?.(o, today)) : orders
  const toPack = (orders ?? []).flatMap((o) => o.items).filter((i) => readyToPack(i, today)).length

  return (
    <section className="space-y-5">
      {!luar && filter.key === 'open' && !query.trim() && toPack > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-r-xl border-l-4 border-amber-500 bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-transparent p-4">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-bold text-amber-900">
              <BellIcon /> Peringatan automatik: 5–7 hari selepas tarikh cuci
            </h2>
            <p className="mt-0.5 text-xs text-amber-900">
              Tak perlu kira tarikh dalam buku. <strong>{toPack} karpet</strong> sudah cukup 5 hari kering dan sedia
              untuk dimasukkan ke Borang Packing.
            </p>
          </div>
          <a
            href={href({ page: 'pack' })}
            className="flex items-center gap-1.5 rounded-lg bg-amber-600 px-4 py-2.5 text-xs font-bold text-white shadow transition hover:bg-amber-700"
          >
            Buka senarai packing ({toPack} karpet) <ArrowIcon className="size-3.5" />
          </a>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex w-full flex-wrap items-center gap-2 md:w-auto md:flex-1">
          <label className="relative w-full md:w-80">
            <span className="sr-only">Cari pesanan</span>
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Cari no. siri, nama atau no. HP"
              className="w-full rounded-lg border border-slate-300 py-2 pr-3 pl-9 text-sm focus:ring-2 focus:ring-amber-500 focus:outline-none"
            />
          </label>
          {!query.trim() && (
            <div className="flex flex-wrap gap-1" role="group" aria-label="Tapis status">
              {filters.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  aria-pressed={filter.key === f.key}
                  onClick={() => {
                    setOrders(null) // show "loading", not the previous filter's orders
                    setFilter(f)
                  }}
                  className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-200 aria-pressed:bg-slate-900 aria-pressed:text-white"
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <a
          href={href({ page: 'new-order', kind })}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white shadow hover:bg-emerald-700 md:w-auto"
        >
          <PlusIcon /> {luar ? 'Daftar kerja luar baru' : 'Daftar pesanan baru'}
        </a>
      </div>

      {notice && (
        <p
          role={notice.ok ? 'status' : 'alert'}
          className={`rounded-lg border px-3 py-2 text-sm ${notice.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-rose-200 bg-rose-50 text-rose-800'}`}
        >
          {notice.text}
        </p>
      )}
      {error && <p role="alert" className="text-danger">Tak dapat muatkan pesanan. Cuba lagi.</p>}
      {shown === null && !error && <p className="text-ink-soft">Memuatkan…</p>}
      {shown?.length === 0 && (
        <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-ink-soft shadow-sm">Tiada pesanan di sini.</p>
      )}

      {shown && shown.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm max-md:block">
              <thead className="max-md:hidden">
                <tr className="bg-slate-800 text-xs text-slate-200 uppercase">
                  <th scope="col" className="px-4 py-3">No. siri / tarikh</th>
                  <th scope="col" className="px-4 py-3">Pelanggan & alamat</th>
                  <th scope="col" className="px-4 py-3">{luar ? 'Senarai kerja' : 'Senarai karpet (jenis & saiz)'}</th>
                  <th scope="col" className="px-4 py-3">{luar ? 'Status kerja' : 'Tarikh cuci & tempoh kering'}</th>
                  <th scope="col" className="px-4 py-3">{luar ? 'Progress' : 'Status packing'}</th>
                  <th scope="col" className="px-4 py-3">Jumlah & bayaran</th>
                  <th scope="col" className="px-4 py-3 text-right">Tindakan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 max-md:block">
                {shown.map((order) => (
                  <BookRow key={order.id} order={order} today={today} closing={closing} onClose={close} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}

const cell = 'px-4 py-3.5 max-md:block max-md:px-0 max-md:py-1.5'

function BookRow({
  order,
  today,
  closing,
  onClose,
}: {
  order: Order
  today: string
  closing: number | null
  onClose: (order: Order) => void
}) {
  const packed = order.items_ready
  const count = order.items.length
  const unwashed = order.items.some((i) => !isHomeJob(i) && i.status === 'received')
  const homePending = order.items.some((i) => isHomeJob(i) && i.status !== 'ready')
  const carpetsLeft = order.items.some((i) => !isHomeJob(i) && i.status !== 'ready')
  const open = OPEN.includes(order.status)
  return (
    <tr aria-label={`Pesanan ${order.code}, ${order.customer.name}`} className="align-top hover:bg-slate-50/80 max-md:block max-md:px-4 max-md:py-3">
      <td className={cell}>
        <a
          href={href({ page: 'order', id: order.id })}
          className="rounded border border-slate-300 bg-slate-100 px-2.5 py-1 text-base font-extrabold text-slate-900 hover:border-slate-500"
        >
          {order.kind === 'on_site' ? order.code : `#${order.code}`}
        </a>
        <p className="mt-1.5 text-xs text-slate-500">
          Masuk: <strong>{formatShortDate(order.received_on)}</strong>
        </p>
        {order.visit_at && homePending && (
          <p className="mt-1 text-xs font-semibold text-emerald-800">Lawatan: {formatVisit(order.visit_at)}</p>
        )}
      </td>

      <td className={`${cell} max-w-xs`}>
        <p className="font-bold text-slate-900">{order.customer.name}</p>
        <p className="mt-0.5 flex items-center gap-1 font-mono text-xs text-slate-600">
          <PhoneIcon className="size-3" /> {order.customer.phone}
        </p>
        {(order.customer.address || order.customer.area) && (
          <p className="mt-1 text-xs leading-snug text-slate-500">
            {[order.customer.address, order.customer.area].filter(Boolean).join(', ')}
          </p>
        )}
      </td>

      <td className={cell}>
        <ul className="space-y-1.5">
          {order.items.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-2 rounded border border-slate-200 bg-slate-50 p-1.5 text-xs">
              <span>
                <span className="font-mono font-bold text-slate-700">{item.tag}:</span>{' '}
                <span className={`font-semibold ${item.service.needs_fold ? 'text-purple-700' : 'text-slate-800'}`}>
                  {item.service.name}
                </span>{' '}
                <span className="text-slate-500">({formatSize(item)})</span>
                {item.wash_note && (
                  <span className="ml-1.5 rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-semibold text-rose-700">
                    {item.wash_note}
                  </span>
                )}
              </span>
              <span className="font-semibold whitespace-nowrap text-slate-700">
                {item.line_total ? formatMoney(item.line_total) : '—'}
              </span>
            </li>
          ))}
        </ul>
      </td>

      <td className={cell}>
        <ul className="space-y-1.5">
          {order.items.map((item) => (
            <li key={item.id} className="text-xs">
              <WashState item={item} today={today} />
            </li>
          ))}
        </ul>
      </td>

      <td className={cell}>
        {order.status === 'cancelled' ? (
          <span className={`rounded px-2 py-0.5 text-[11px] font-bold ${ORDER_STATUS_STYLE.cancelled}`}>{ORDER_STATUS_LABEL.cancelled}</span>
        ) : (
          <>
            <p className="mb-1 text-xs font-bold">
              Progress: {packed} / {count} barang
            </p>
            <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
              <div
                className={`h-full ${packed === count ? 'bg-emerald-500' : 'bg-amber-500'}`}
                style={{ width: `${count ? (packed / count) * 100 : 0}%` }}
              />
            </div>
            <span
              className={`mt-1.5 inline-block rounded px-2 py-0.5 text-[11px] font-bold ${
                order.status === 'completed'
                  ? 'bg-slate-100 text-slate-600'
                  : packed === count
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-slate-100 text-slate-600'
              }`}
            >
              {order.status === 'completed'
                ? `Selesai ${order.completed_on ? formatShortDate(order.completed_on) : ''}`
                : packed === count
                  ? 'Siap'
                  : 'Belum selesai'}
            </span>
          </>
        )}
      </td>

      <td className={cell}>
        <p className="text-base font-extrabold text-slate-900">
          {order.price_pending ? 'Harga belum lengkap' : formatMoney(order.total)}
        </p>
        <PaidBadge order={order} />
      </td>

      <td className={`${cell} space-y-1.5 md:w-36 md:text-right`}>
        <a
          href={href({ page: 'receipt', id: order.id })}
          className="flex items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-slate-800"
        >
          <ReceiptIcon className="size-3.5" /> Resit & WA
        </a>
        {order.status === 'ready' && (
          <button
            type="button"
            disabled={closing !== null}
            onClick={() => onClose(order)}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
          >
            <CheckIcon className="size-3.5" />
            {order.items.some((i) => !isHomeJob(i)) ? 'Sudah diambil / dihantar' : 'Selesai'}
          </button>
        )}
        {open && carpetsLeft && (
          <a
            href={href({ page: unwashed ? 'wash' : 'pack' })}
            className="flex items-center justify-center gap-1 rounded-lg border border-amber-400/50 bg-amber-500/20 px-3 py-1.5 text-xs font-bold text-amber-900 hover:bg-amber-500/30"
          >
            {unwashed ? 'Ke Borang Cuci' : 'Ke Borang Packing'} <ArrowIcon className="size-3" />
          </a>
        )}
        {open && homePending && (
          <a
            href={href({ page: 'visits' })}
            className="flex items-center justify-center gap-1 rounded-lg border border-emerald-400/50 bg-emerald-500/15 px-3 py-1.5 text-xs font-bold text-emerald-900 hover:bg-emerald-500/25"
          >
            Ke Kerja Luar <ArrowIcon className="size-3" />
          </a>
        )}
        <a href={href({ page: 'order', id: order.id })} className="block text-center text-xs font-semibold text-slate-600 underline">
          Buka pesanan
        </a>
      </td>
    </tr>
  )
}

/** Where one carpet is: not washed, drying (day N), ready to pack, or packed. */
function WashState({ item, today }: { item: OrderItem; today: string }) {
  if (isHomeJob(item)) {
    return item.ready_on ? (
      <span className="font-semibold text-emerald-700">Kerja luar: siap {formatShortDate(item.ready_on)}</span>
    ) : (
      <span className="inline-block rounded border border-emerald-200 bg-emerald-50 px-2 py-1 font-medium text-emerald-800">
        Kerja luar: belum
      </span>
    )
  }
  if (!item.washed_on) {
    return <span className="inline-block rounded border border-sky-200 bg-sky-50 px-2 py-1 font-medium text-sky-800">Belum cuci</span>
  }
  const days = daysBetween(item.washed_on, today)
  return (
    <span>
      <span className="font-semibold text-slate-700">Cuci: {formatShortDate(item.washed_on)}</span>
      {item.status === 'ready' ? (
        <span className="ml-1.5 text-emerald-700">· Pack {item.ready_on && formatShortDate(item.ready_on)}</span>
      ) : readyToPack(item, today) ? (
        <span className="ml-1.5 inline-block rounded border border-amber-400 bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-900">
          Hari ke-{days} (sedia pack)
        </span>
      ) : (
        <span className="ml-1.5 text-slate-500">· hari ke-{days}</span>
      )}
    </span>
  )
}

function owes(order: Order): boolean {
  return order.status !== 'cancelled' && !order.price_pending && Number(order.balance) > 0
}

function PaidBadge({ order }: { order: Order }) {
  if (order.status === 'cancelled' || order.price_pending) return null
  if (owes(order)) {
    return (
      <span className="mt-1 inline-block rounded border border-rose-300 bg-rose-50 px-2.5 py-0.5 text-[11px] font-bold text-rose-700">
        Baki {formatMoney(order.balance)}
      </span>
    )
  }
  const last = order.payments.filter((p) => !p.voided).at(-1)
  return (
    <span className="mt-1 inline-block rounded border border-emerald-300 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700">
      PAID{last ? ` (${formatShortDate(last.paid_on)})` : ''}
    </span>
  )
}

/** One order as a card: used on a customer's page. */
export function OrderCard({ order }: { order: Order }) {
  const items = order.items.map((i) => `${i.service.name} ${formatSize(i)}`).join(', ')
  return (
    <a
      href={href({ page: 'order', id: order.id })}
      aria-label={`Pesanan ${order.code}, ${order.customer.name}`}
      className="block rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-400"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">
            {order.kind === 'on_site' ? order.code : `#${order.code}`} · {order.customer.name}
          </p>
          <p className="text-sm text-ink-soft">
            diterima {formatDay(order.received_on)}
            {order.completed_on && ` · selesai ${formatDay(order.completed_on)}`}
          </p>
          <p className="mt-1 truncate text-sm">{items}</p>
        </div>
        <div className="shrink-0 text-right">
          <span className={`rounded px-2.5 py-0.5 text-xs font-bold ${ORDER_STATUS_STYLE[order.status]}`}>
            {ORDER_STATUS_LABEL[order.status]}
          </span>
          <p className="mt-2 font-semibold">{order.price_pending ? 'Harga belum lengkap' : formatMoney(order.total)}</p>
          <PaidBadge order={order} />
        </div>
      </div>
    </a>
  )
}
