import { type ReactNode, useCallback, useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import { FOLD_LABEL, formatDay, formatSize, todayInMalaysia } from './format'
import type { ItemFold, ItemStatus, Order, WorkItem, WorkLog } from './types'
import { href } from './useHashRoute'

// The workers' screens, one per paper form: the washing list, the packing list (carpets
// washed 5-7 days ago), and the day's record of both. Each "done" button records the day
// and the worker's name (from their own login), as the forms do.

/** Items at one step across open orders, plus a way to reload after a change. */
function useWorkItems(status: ItemStatus) {
  const { request } = useAuth()
  const [items, setItems] = useState<WorkItem[] | null>(null)
  const [error, setError] = useState(false)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let current = true
    request<WorkItem[]>(`/api/work/items?status=${status}`)
      .then((data) => {
        if (current) {
          setItems(data)
          setError(false)
        }
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [request, status, version])

  return { items, error, reload: useCallback(() => setVersion((v) => v + 1), []) }
}

function useWorkLog(day: string, version = 0) {
  const { request } = useAuth()
  const [log, setLog] = useState<WorkLog | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    request<WorkLog>(`/api/work/log?day=${day}`)
      .then((data) => {
        if (current) {
          setLog(data)
          setError(false)
        }
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [request, day, version])

  // Another day's record isn't shown while the chosen day loads.
  return { log: log?.day === day ? log : null, error }
}

/** Moves one item a step along; reports what happened in a single line. */
function useMove(onDone: () => void) {
  const { request } = useAuth()
  const [busy, setBusy] = useState<number | null>(null)
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null)

  const move = async (item: WorkItem, status: ItemStatus, fold?: ItemFold) => {
    setBusy(item.id)
    setNotice(null)
    try {
      await request<Order>(`/api/orders/${item.order_id}/items/${item.id}`, {
        method: 'PATCH',
        body: { status, fold },
      })
      const done = status === 'washed' ? 'dicuci' : `dipack${fold ? ` (${FOLD_LABEL[fold]})` : ''}`
      setNotice({ ok: true, text: `${item.tag} ${done}.` })
      onDone()
    } catch (err) {
      setNotice({ ok: false, text: errorMessage(err, `Tak dapat simpan ${item.tag}. Cuba lagi.`) })
    } finally {
      setBusy(null)
    }
  }
  return { move, busy, notice }
}

// --- Cuci ------------------------------------------------------------------------------------

export function WashPage() {
  const today = todayInMalaysia()
  const work = useWorkItems('received')
  const [version, setVersion] = useState(0)
  const { log } = useWorkLog(today, version)
  const { move, busy, notice } = useMove(() => {
    work.reload()
    setVersion((v) => v + 1)
  })

  return (
    <section className="space-y-5">
      <PageHeader
        title="Cuci"
        lead="Karpet yang belum dicuci. Tekan Siap cuci bila selesai: tarikh dan nama anda direkod."
        count={work.items?.length}
      />
      <Notice notice={notice} />
      <Loading work={work} empty="Semua karpet sudah dicuci." />

      <div className="space-y-3">
        {groupByOrder(work.items ?? []).map((group) => (
          <OrderGroup key={group[0].order_id} items={group}>
            {(item) => (
              <ActionButton disabled={busy !== null} onClick={() => move(item, 'washed')}>
                Siap cuci
              </ActionButton>
            )}
          </OrderGroup>
        ))}
      </div>

      <DoneToday title="Dicuci hari ini" items={log?.washed} by={(i) => i.washed_by} />
    </section>
  )
}

// --- Packing ---------------------------------------------------------------------------------

export function PackPage() {
  const today = todayInMalaysia()
  const work = useWorkItems('washed')
  const [version, setVersion] = useState(0)
  const { log } = useWorkLog(today, version)
  const { move, busy, notice } = useMove(() => {
    work.reload()
    setVersion((v) => v + 1)
  })
  // Carpets dry for 5-7 days; anything that isn't a carpet can be packed straight away.
  const due = (work.items ?? []).filter((i) => !i.ready_from || i.ready_from <= today)
  const drying = (work.items ?? []).filter((i) => i.ready_from && i.ready_from > today)

  const actions = (item: WorkItem, early: boolean) => {
    const style = early ? 'secondary' : 'primary'
    if (item.service.needs_fold) {
      return (['rolled', 'folded'] as const).map((fold) => (
        <ActionButton key={fold} variant={style} disabled={busy !== null} onClick={() => move(item, 'ready', fold)}>
          {FOLD_LABEL[fold]}
        </ActionButton>
      ))
    }
    return (
      <ActionButton variant={style} disabled={busy !== null} onClick={() => move(item, 'ready')}>
        Siap pack
      </ActionButton>
    )
  }

  return (
    <section className="space-y-5">
      <PageHeader
        title="Packing"
        lead="Karpet yang sudah 5 hari dicuci boleh dipack. Karpet velvet: pilih Gulung atau Lipat."
        count={due.length}
      />
      <Notice notice={notice} />
      <Loading work={work} empty="Tiada karpet untuk dipack." />

      {due.length === 0 && drying.length > 0 && (
        <p className="rounded-2xl bg-white p-4 text-center text-sm text-ink-soft ring-1 ring-line">
          Tiada karpet cukup 5 hari lagi. Yang masih kering boleh dipack awal jika sudah kering.
        </p>
      )}
      {due.length > 0 && (
        <ItemList title={`Sedia untuk pack (${due.length})`}>
          {due.map((item) => (
            <ItemRow key={item.id} item={item} detail={item.washed_on ? `dicuci ${formatDay(item.washed_on)}` : undefined}>
              {actions(item, false)}
            </ItemRow>
          ))}
        </ItemList>
      )}
      {drying.length > 0 && (
        <ItemList title={`Masih kering (${drying.length})`}>
          {drying.map((item) => (
            <ItemRow
              key={item.id}
              item={item}
              detail={`dicuci ${formatDay(item.washed_on as string)} · boleh pack ${formatDay(item.ready_from as string)}`}
            >
              {actions(item, true)}
            </ItemRow>
          ))}
        </ItemList>
      )}

      <DoneToday
        title="Dipack hari ini"
        items={log?.packed}
        by={(i) => [i.packed_by, i.fold && FOLD_LABEL[i.fold]].filter(Boolean).join(' · ')}
      />
    </section>
  )
}

// --- Rekod harian ----------------------------------------------------------------------------

export function LogPage() {
  const [day, setDay] = useState(todayInMalaysia())
  const { log, error } = useWorkLog(day)

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3 print:hidden">
        <div>
          <h1 className="font-display text-2xl font-bold">Rekod harian</h1>
          <p className="text-sm text-ink-soft">Borang cuci dan borang packing untuk satu hari, sedia untuk dicetak.</p>
        </div>
        <div className="flex items-end gap-2">
          <label className="text-sm">
            <span className="block font-semibold">Tarikh</span>
            <input
              type="date"
              value={day}
              max={todayInMalaysia()}
              onChange={(e) => e.target.value && setDay(e.target.value)}
              className="rounded-xl bg-white px-3 py-2 ring-1 ring-line outline-none focus:ring-2 focus:ring-brand"
            />
          </label>
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white"
          >
            Cetak
          </button>
        </div>
      </div>

      {error && <p role="alert" className="text-danger">Tak dapat muatkan rekod. Cuba lagi.</p>}
      {!log && !error && <p className="text-ink-soft">Memuatkan…</p>}
      {log && (
        <>
          <FormTable
            title="Rekod cuci karpet"
            day={log.day}
            items={log.washed}
            staff={(i) => i.washed_by}
            lastHeading="Catatan"
            last={(i) => i.notes ?? ''}
          />
          <FormTable
            title="Rekod packing karpet"
            day={log.day}
            items={log.packed}
            staff={(i) => i.packed_by}
            lastHeading="Gulung / Lipat"
            last={(i) => (i.fold ? FOLD_LABEL[i.fold] : '')}
          />
        </>
      )}
    </section>
  )
}

function FormTable({
  title,
  day,
  items,
  staff,
  lastHeading,
  last,
}: {
  title: string
  day: string
  items: WorkItem[]
  staff: (item: WorkItem) => string | null
  lastHeading: string
  last: (item: WorkItem) => string
}) {
  const names = [...new Set(items.map(staff).filter((n): n is string => Boolean(n)))]
  return (
    <section aria-label={title} className="rounded-2xl bg-white ring-1 ring-line print:break-inside-avoid print:rounded-none print:ring-0">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-3">
        <h2 className="font-semibold">{title}</h2>
        <p className="text-sm text-ink-soft">
          {formatLongDay(day)} · Staf bertugas: {names.length ? names.join(', ') : '-'}
        </p>
      </header>
      {items.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-ink-soft">Tiada rekod pada hari ini.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs tracking-wide text-ink-soft uppercase">
              <tr>
                <th className="px-4 py-2 font-semibold">Bil</th>
                <th className="px-4 py-2 font-semibold">No. siri</th>
                <th className="px-4 py-2 font-semibold">Jenis</th>
                <th className="px-4 py-2 font-semibold">Saiz</th>
                <th className="px-4 py-2 font-semibold">{lastHeading}</th>
                <th className="px-4 py-2 font-semibold">Staf</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((item, index) => (
                <tr key={item.id}>
                  <td className="px-4 py-2 tabular-nums">{index + 1}</td>
                  <td className="px-4 py-2 font-mono font-semibold">{item.tag}</td>
                  <td className="px-4 py-2">{item.service.name}</td>
                  <td className="px-4 py-2 whitespace-nowrap">{formatSize(item)}</td>
                  <td className="px-4 py-2">{last(item)}</td>
                  <td className="px-4 py-2">{staff(item) ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// --- Shared pieces ---------------------------------------------------------------------------

function PageHeader({ title, lead, count }: { title: string; lead: string; count?: number }) {
  return (
    <header>
      <h1 className="font-display text-2xl font-bold">
        {title}
        {count !== undefined && count > 0 && (
          <span className="ml-2 rounded-full bg-ink px-2.5 py-0.5 align-middle text-sm text-white">{count}</span>
        )}
      </h1>
      <p className="text-sm text-ink-soft">{lead}</p>
    </header>
  )
}

function Notice({ notice }: { notice: { ok: boolean; text: string } | null }) {
  if (!notice) return null
  return (
    <p
      role={notice.ok ? 'status' : 'alert'}
      className={`rounded-xl px-3 py-2 text-sm ring-1 ${notice.ok ? 'bg-emerald-50 text-emerald-900 ring-emerald-200' : 'bg-red-50 text-danger ring-red-200'}`}
    >
      {notice.text}
    </p>
  )
}

function Loading({ work, empty }: { work: { items: WorkItem[] | null; error: boolean }; empty: string }) {
  if (work.error) return <p role="alert" className="text-danger">Tak dapat muatkan senarai. Cuba lagi.</p>
  if (work.items === null) return <p className="text-ink-soft">Memuatkan…</p>
  if (work.items.length === 0) return <p className="rounded-2xl bg-white p-6 text-center text-ink-soft ring-1 ring-line">{empty}</p>
  return null
}

/** One order's carpets together, as the tags are written: 12-1, 12-2, ... */
function OrderGroup({ items, children }: { items: WorkItem[]; children: (item: WorkItem) => ReactNode }) {
  const first = items[0]
  return (
    <ItemList
      title={
        <a href={href({ page: 'order', id: first.order_id })} className="hover:underline">
          #{first.order_number} · {first.customer_name}
        </a>
      }
      aside={`diterima ${formatDay(first.received_on)}`}
    >
      {items.map((item) => (
        <ItemRow key={item.id} item={item}>
          {children(item)}
        </ItemRow>
      ))}
    </ItemList>
  )
}

function ItemList({ title, aside, children }: { title: ReactNode; aside?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl bg-white ring-1 ring-line">
      <header className="flex items-baseline justify-between gap-2 border-b border-line px-4 py-2.5">
        <h2 className="font-semibold">{title}</h2>
        {aside && <p className="text-xs text-ink-soft">{aside}</p>}
      </header>
      <ul className="divide-y divide-line">{children}</ul>
    </section>
  )
}

function ItemRow({ item, detail, children }: { item: WorkItem; detail?: string; children: ReactNode }) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
      <span className="rounded bg-ink px-1.5 py-0.5 font-mono text-xs font-semibold text-white">{item.tag}</span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">
          {item.service.name} <span className="font-normal text-ink-soft">· {formatSize(item)}</span>
        </p>
        {(detail || item.notes) && (
          <p className="text-xs text-ink-soft">{[detail, item.notes && `Catatan: ${item.notes}`].filter(Boolean).join(' · ')}</p>
        )}
      </div>
      <div className="flex gap-2">{children}</div>
    </li>
  )
}

function ActionButton({
  children,
  onClick,
  disabled,
  variant = 'primary',
}: {
  children: ReactNode
  onClick: () => void
  disabled: boolean
  variant?: 'primary' | 'secondary'
}) {
  const style =
    variant === 'primary' ? 'bg-brand hover:bg-brand-hover' : 'bg-white ring-1 ring-line hover:ring-ink/30'
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`min-h-10 rounded-full px-4 text-sm font-semibold disabled:opacity-50 ${style}`}
    >
      {children}
    </button>
  )
}

function DoneToday({
  title,
  items,
  by,
}: {
  title: string
  items: WorkItem[] | undefined
  by: (item: WorkItem) => string | null
}) {
  if (!items?.length) return null
  return (
    <ItemList title={`${title} (${items.length})`} aside="Lihat Rekod harian untuk cetak">
      {items.map((item) => (
        <li key={item.id} className="flex items-center gap-3 px-4 py-2 text-sm">
          <span className="font-mono font-semibold">{item.tag}</span>
          <span className="min-w-0 flex-1 truncate">{item.service.name}</span>
          <span className="text-ink-soft">{by(item)}</span>
        </li>
      ))}
    </ItemList>
  )
}

function groupByOrder(items: WorkItem[]): WorkItem[][] {
  const groups = new Map<number, WorkItem[]>()
  for (const item of items) groups.set(item.order_id, [...(groups.get(item.order_id) ?? []), item])
  return [...groups.values()]
}

const longDay = new Intl.DateTimeFormat('ms-MY', {
  timeZone: 'Asia/Kuala_Lumpur',
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

/** "Sabtu, 10 Oktober 2026": the forms write the day as well as the date. */
function formatLongDay(isoDate: string): string {
  return longDay.format(new Date(`${isoDate}T12:00:00+08:00`))
}
