import { type ReactNode, useCallback, useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import { formatSize, formatVisit, isHomeJob, todayInMalaysia, visitDay, whatsAppUrl } from './format'
import { AlertIcon, CheckIcon, HomeIcon, PhoneIcon, PlusIcon } from './icons'
import { notifyWorkChanged } from './summary'
import type { Order } from './types'
import { href } from './useHashRoute'
import { VisitEditor } from './VisitEditor'
import { SearchBox } from './SearchBox'
import { orderMatches } from './search'

// "Kerja Luar": sofa, mattress and car seat jobs, done at the customer's home in one visit.
// They skip the washing and packing forms: the team goes, does the job, and marks it done.
// Listed by visit time, so the day's route is in one place.

/** Kerja Luar: the visit schedule, or the kerja luar book (its own orders and numbers). */
export function HouseJobsPage({ view, children }: { view: 'schedule' | 'book'; children?: ReactNode }) {
  const tabs = [
    { key: 'book', label: 'Buku kerja luar', route: href({ page: 'visits', book: true }) },
    { key: 'schedule', label: 'Jadual lawatan', route: href({ page: 'visits' }) },
  ] as const
  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-emerald-900 p-5 text-white shadow">
        <div className="max-w-2xl">
          <span className="rounded bg-emerald-700 px-2.5 py-1 text-xs font-bold tracking-wider uppercase">Kerja luar</span>
          <h1 className="mt-2 flex items-center gap-2 text-xl font-extrabold uppercase">
            <HomeIcon className="size-5" /> {view === 'book' ? 'Buku kerja luar' : 'Jadual kerja luar'}
          </h1>
          <p className="mt-0.5 text-xs text-white/80">
            Sofa, tilam dan seat kereta dibuat di rumah pelanggan dalam satu lawatan: tiada borang cuci atau packing.
            Pesanan kerja luar ada buku dan nombor sendiri (L1, L2…).
          </p>
        </div>
        {view === 'schedule' && (
          // The book has the same button in its search bar.
          <a
            href={href({ page: 'new-order', kind: 'on_site' })}
            className="flex items-center gap-1.5 rounded-lg bg-white px-4 py-2.5 text-xs font-bold text-emerald-900 shadow hover:bg-emerald-50"
          >
            <PlusIcon /> Daftar kerja luar baru
          </a>
        )}
      </div>
      <nav aria-label="Kerja luar" className="flex gap-1.5">
        {tabs.map((tab) => (
          <a
            key={tab.key}
            href={tab.route}
            aria-current={view === tab.key ? 'page' : undefined}
            className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 aria-[current=page]:bg-emerald-700 aria-[current=page]:text-white aria-[current=page]:ring-emerald-700"
          >
            {tab.label}
          </a>
        ))}
      </nav>
      {view === 'book' ? children : <VisitSchedule />}
    </section>
  )
}

function VisitSchedule() {
  const { request } = useAuth()
  const today = todayInMalaysia()
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState(false)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null)
  const reload = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    let current = true
    request<Order[]>('/api/work/visits')
      .then((data) => {
        if (current) {
          setOrders(data)
          setError(false)
        }
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [request, version])

  const save = async (order: Order, path: string, body: Record<string, unknown>, done: string) => {
    setBusy(true)
    setNotice(null)
    try {
      await request<Order>(`/api/orders/${order.id}${path}`, { method: 'PATCH', body })
      setNotice({ ok: true, text: done })
      reload()
      notifyWorkChanged()
    } catch (err) {
      setNotice({ ok: false, text: errorMessage(err, 'Tak dapat simpan. Cuba lagi.') })
    } finally {
      setBusy(false)
    }
  }

  const groups: { title: string; tone: string; orders: Order[] }[] = [
    { title: 'Terlepas (tarikh sudah lepas)', tone: 'text-rose-700', orders: [] },
    { title: 'Hari ini', tone: 'text-emerald-700', orders: [] },
    { title: 'Akan datang', tone: 'text-slate-800', orders: [] },
    { title: 'Belum dijadualkan', tone: 'text-amber-800', orders: [] },
  ]
  for (const order of (orders ?? []).filter((o) => orderMatches(o, query))) {
    const day = order.visit_at ? visitDay(order.visit_at) : null
    groups[day === null ? 3 : day < today ? 0 : day === today ? 1 : 2].orders.push(order)
  }

  return (
    <section className="space-y-6">
      {notice && (
        <p
          role={notice.ok ? 'status' : 'alert'}
          className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
            notice.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-rose-200 bg-rose-50 text-rose-800'
          }`}
        >
          {notice.ok ? <CheckIcon /> : <AlertIcon />} {notice.text}
        </p>
      )}
      {(orders?.length ?? 0) > 0 && (
        <SearchBox
          value={query}
          onChange={setQuery}
          label="Cari kerja luar"
          placeholder="Cari no. siri, nama, no. HP atau alamat"
        />
      )}
      {query.trim() !== '' && (orders?.length ?? 0) > 0 && groups.every((g) => g.orders.length === 0) && (
        <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-ink-soft shadow-sm">
          Tiada kerja luar sepadan dengan carian.
        </p>
      )}
      {error && <p role="alert" className="text-danger">Tak dapat muatkan jadual. Cuba lagi.</p>}
      {orders === null && !error && <p className="text-ink-soft">Memuatkan…</p>}
      {orders?.length === 0 && (
        <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-ink-soft shadow-sm">
          Tiada kerja luar yang belum siap.
        </p>
      )}

      {groups
        .filter((g) => g.orders.length > 0)
        .map((group) => (
          <section key={group.title} aria-label={group.title} className="space-y-3">
            <h2 className={`text-sm font-bold uppercase ${group.tone}`}>
              {group.title} ({group.orders.length})
            </h2>
            <ul className="grid gap-3 lg:grid-cols-2">
              {group.orders.map((order) => (
                <li key={order.id}>
                  <VisitCard
                    order={order}
                    busy={busy}
                    onDone={(itemId, tag) => save(order, `/items/${itemId}`, { status: 'ready' }, `${tag} siap.`)}
                    onReschedule={(visitAt) => save(order, '', { visit_at: visitAt }, `Masa lawatan ${order.code} disimpan.`)}
                  />
                </li>
              ))}
            </ul>
          </section>
        ))}
    </section>
  )
}

function VisitCard({
  order,
  busy,
  onDone,
  onReschedule,
}: {
  order: Order
  busy: boolean
  onDone: (itemId: number, tag: string) => Promise<void>
  onReschedule: (visitAt: string | null) => Promise<void>
}) {
  const jobs = order.items.filter((i) => isHomeJob(i) && i.status !== 'ready')
  const address = [order.customer.address, order.customer.area].filter(Boolean).join(', ')
  return (
    <article
      aria-label={`Kerja luar ${order.code}, ${order.customer.name}`}
      className="h-full space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-base font-extrabold text-slate-900">
            {order.visit_at ? formatVisit(order.visit_at) : 'Masa belum ditetapkan'}
          </p>
          <a href={href({ page: 'order', id: order.id })} className="text-sm font-semibold text-slate-700 hover:underline">
            {order.code} · {order.customer.name}
          </a>
        </div>
        <div className="flex gap-2 text-xs font-semibold">
          <a href={`tel:${order.customer.phone}`} className="flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1.5 hover:bg-slate-200">
            <PhoneIcon className="size-3.5" /> Telefon
          </a>
          <a
            href={whatsAppUrl(order.customer.phone)}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-emerald-50 px-2.5 py-1.5 text-emerald-800 hover:bg-emerald-100"
          >
            WhatsApp
          </a>
        </div>
      </header>

      {address ? (
        <a
          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`}
          target="_blank"
          rel="noreferrer"
          className="block text-sm text-slate-600 underline decoration-dotted"
        >
          {address}
        </a>
      ) : (
        <p className="text-sm text-slate-500">Alamat belum diisi</p>
      )}

      <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200">
        {jobs.map((item) => (
          <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
            <p className="text-sm">
              <span className="mr-2 rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs font-semibold text-white">{item.tag}</span>
              <span className="font-semibold">{item.service.name}</span>
              <span className="text-slate-500"> × {formatSize(item)}</span>
              {item.notes && <span className="block text-xs text-rose-700">Catatan: {item.notes}</span>}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => onDone(item.id, item.tag)}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50"
            >
              <CheckIcon className="size-3.5" /> Tandakan siap
            </button>
          </li>
        ))}
      </ul>

      <VisitEditor order={order} busy={busy} onSave={onReschedule} compact />
    </article>
  )
}
