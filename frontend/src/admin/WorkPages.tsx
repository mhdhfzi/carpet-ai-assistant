import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import { FOLD_LABEL, daysBetween, formatShortDate, formatSize, needsMeasuring, readyToPack, todayInMalaysia } from './format'
import { AlertIcon, BoxIcon, CheckIcon, ClockIcon, DropIcon, PrintIcon, TagIcon } from './icons'
import { SearchBox } from './SearchBox'
import { carpetMatches } from './search'
import { notifyWorkChanged } from './summary'
import type { ItemFold, ItemStatus, Order, UntaggedItem, WorkItem, WorkLog } from './types'
import { href } from './useHashRoute'

// The workers' screens, one per paper form: the washing form, the packing form (carpets
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

type Notice = { ok: boolean; text: string } | null

/** Moves one item a step along; reports what happened in a single line. */
function useMove(onDone: () => void) {
  const { request } = useAuth()
  const [busy, setBusy] = useState<number | null>(null)
  const [notice, setNotice] = useState<Notice>(null)

  const move = async (
    item: WorkItem,
    status: ItemStatus,
    extra: { fold?: ItemFold; note?: string; length_ft?: string; width_ft?: string } = {},
  ) => {
    setBusy(item.id)
    setNotice(null)
    try {
      await request<Order>(`/api/orders/${item.order_id}/items/${item.id}`, {
        method: 'PATCH',
        body: { status, ...extra },
      })
      const done = status === 'washed' ? 'dicuci' : `dipack${extra.fold ? ` (${FOLD_LABEL[extra.fold]})` : ''}`
      setNotice({ ok: true, text: `${item.tag} ${done}.` })
      onDone()
      notifyWorkChanged()
    } catch (err) {
      setNotice({ ok: false, text: errorMessage(err, `Tak dapat simpan ${item.tag}. Cuba lagi.`) })
    } finally {
      setBusy(null)
    }
  }
  return { move, busy, notice, setNotice }
}

/** The logged-in worker: the "staf bertugas" on today's forms. */
function useStaffName(): string {
  const { state } = useAuth()
  return state.status === 'signed-in' ? state.owner.name : ''
}

// --- Borang Cuci -----------------------------------------------------------------------------

export function WashPage() {
  const today = todayInMalaysia()
  const staff = useStaffName()
  const work = useWorkItems('received')
  const [version, setVersion] = useState(0)
  const { log } = useWorkLog(today, version)
  const [notes, setNotes] = useState<Record<number, string>>({})
  // Carpets that came in without their size are measured now, before they're marked washed.
  const [sizes, setSizes] = useState<Record<number, { length: string; width: string }>>({})
  const sizeOf = (id: number) => sizes[id] ?? { length: '', width: '' }
  const measured = (id: number) => Number(sizeOf(id).length) > 0 && Number(sizeOf(id).width) > 0
  const { move, busy, notice } = useMove(() => {
    work.reload()
    setVersion((v) => v + 1)
  })
  const [query, setQuery] = useState('')
  const toWash = (work.items ?? []).filter((item) => carpetMatches(item, query))
  const washedToday = (log?.washed ?? []).filter((item) => carpetMatches(item, query))
  const noMatch = query.trim() !== '' && (work.items?.length ?? 0) > 0 && toWash.length === 0 && washedToday.length === 0

  return (
    <section className="space-y-6">
      <Banner
        tone="bg-sky-900"
        badge="bg-sky-700"
        boxTone="border-sky-600 bg-sky-800"
        icon={<DropIcon className="size-5" />}
        kicker="Borang cuci"
        title="Rekod cuci karpet"
        staffLabel="Staf bertugas"
        staff={staff}
      >
        Bila staf tekan <strong>Tandakan siap cuci</strong>, tarikh cucian terus ditulis dalam Buku Utama dan kiraan{' '}
        <strong>5–7 hari kering</strong> bermula sendiri.
      </Banner>
      <NoticeLine notice={notice} />

      <div className="grid gap-6 md:grid-cols-3">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm md:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-100 px-4 py-3">
            <h2 className="text-sm font-bold text-slate-800">
              Senarai karpet untuk dicuci
              {work.items && work.items.length > 0 && ` (${work.items.length})`}
            </h2>
            <span className="text-xs text-slate-500">
              Staf aktif: <strong>{staff}</strong>
            </span>
          </div>
          <div className="border-b border-slate-200 p-3">
            <SearchBox
              value={query}
              onChange={setQuery}
              label="Cari karpet untuk dicuci"
              placeholder="Cari no. siri (12 / 12-2), nama atau jenis karpet"
            />
          </div>
          <Loading work={work} empty="Semua karpet sudah dicuci." />
          {noMatch && <p className="p-6 text-center text-sm text-ink-soft">Tiada karpet sepadan dengan carian.</p>}
          <ul className="divide-y divide-slate-200">
            {toWash.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-4 p-4 hover:bg-slate-50">
                <CarpetSummary item={item} />
                <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                  {needsMeasuring(item) && (
                    <div className="flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-900">
                      <span>Saiz:</span>
                      {(['length', 'width'] as const).map((side, i) => (
                        <span key={side} className="flex items-center gap-1.5">
                          {i === 1 && <span aria-hidden="true">×</span>}
                          <label>
                            <span className="sr-only">{`${side === 'length' ? 'Panjang' : 'Lebar'} ${item.tag} (kaki)`}</span>
                            <input
                              type="number"
                              inputMode="decimal"
                              min="0"
                              step="0.1"
                              value={sizeOf(item.id)[side]}
                              onChange={(e) => setSizes({ ...sizes, [item.id]: { ...sizeOf(item.id), [side]: e.target.value } })}
                              placeholder={side === 'length' ? 'P' : 'L'}
                              className="w-14 rounded-md border border-amber-300 bg-white px-1.5 py-1 text-center font-normal"
                            />
                          </label>
                        </span>
                      ))}
                      <span>kaki</span>
                    </div>
                  )}
                  <label className="min-w-0 flex-1 sm:flex-none">
                    <span className="sr-only">Catatan cuci {item.tag}</span>
                    <input
                      type="text"
                      maxLength={300}
                      value={notes[item.id] ?? ''}
                      onChange={(e) => setNotes({ ...notes, [item.id]: e.target.value })}
                      placeholder="Catatan (cth: tompok tak hilang)"
                      className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs sm:w-52"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy !== null || (needsMeasuring(item) && !measured(item.id))}
                    title={needsMeasuring(item) && !measured(item.id) ? 'Isi saiz karpet dulu' : undefined}
                    onClick={() =>
                      move(item, 'washed', {
                        ...(notes[item.id]?.trim() ? { note: notes[item.id].trim() } : {}),
                        ...(needsMeasuring(item) ? { length_ft: sizeOf(item.id).length, width_ft: sizeOf(item.id).width } : {}),
                      })
                    }
                    className="flex items-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-xs font-bold text-white shadow transition hover:bg-sky-700 disabled:opacity-50"
                  >
                    <CheckIcon className="size-3.5" /> Tandakan siap cuci
                  </button>
                </div>
              </li>
            ))}
            {washedToday.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-4 bg-emerald-50/40 p-4">
                <CarpetSummary item={item} />
                <div className="text-right">
                  <span className="inline-flex items-center gap-1 rounded-lg border border-emerald-300 bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                    <CheckIcon className="size-3.5" /> Telah dicuci ({formatShortDate(item.washed_on as string)})
                  </span>
                  <p className="mt-0.5 text-[11px] text-slate-500">Oleh: {item.washed_by ?? 'Staf'}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <UntaggedPanel />
      </div>
    </section>
  )
}

/** "#412-1  Karpet Biasa  Saiz: 8 x 10 kaki", the customer, and any notes. */
function CarpetSummary({ item }: { item: WorkItem }) {
  return (
    <div className="min-w-0 space-y-1">
      <p className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-slate-900 px-2.5 py-0.5 text-sm font-extrabold text-white">#{item.tag}</span>
        <span className={`text-sm font-bold ${item.service.needs_fold ? 'text-purple-800' : 'text-slate-800'}`}>{item.service.name}</span>
        <span
          className={`rounded px-2 py-0.5 font-mono text-xs ${needsMeasuring(item) ? 'bg-amber-100 text-amber-900' : 'bg-slate-200 text-slate-800'}`}
        >
          Saiz: {formatSize(item)}
        </span>
      </p>
      <p className="text-xs text-slate-500">
        Pelanggan:{' '}
        <a href={href({ page: 'order', id: item.order_id })} className="font-semibold text-slate-700 hover:underline">
          {item.customer_name}
        </a>{' '}
        (#{item.order_number})
      </p>
      {item.notes && <p className="text-xs font-semibold text-rose-700">Catatan pesanan: {item.notes}</p>}
      {item.wash_note && <p className="text-xs font-semibold text-rose-700">Catatan cuci: {item.wash_note}</p>}
    </div>
  )
}

/** Carpets whose tag came off ("XXX" on the paper form), until someone matches them. */
function UntaggedPanel() {
  const { request } = useAuth()
  const [items, setItems] = useState<UntaggedItem[] | null>(null)
  const [version, setVersion] = useState(0)
  const [adding, setAdding] = useState(false)
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState<Record<number, string>>({})
  const [notice, setNotice] = useState<Notice>(null)

  useEffect(() => {
    let current = true
    request<UntaggedItem[]>('/api/work/untagged')
      .then((data) => {
        if (current) setItems(data)
      })
      .catch(() => {
        if (current) setItems([])
      })
    return () => {
      current = false
    }
  }, [request, version])

  const save = async (path: string, body: unknown, done: string) => {
    setNotice(null)
    try {
      await request(path, { method: 'POST', body })
      setNotice({ ok: true, text: done })
      setVersion((v) => v + 1)
      return true
    } catch (err) {
      setNotice({ ok: false, text: errorMessage(err, 'Tak dapat simpan. Cuba lagi.') })
      return false
    }
  }

  const log = async (event: FormEvent) => {
    event.preventDefault()
    if (!description.trim()) return
    if (await save('/api/work/untagged', { description: description.trim() }, 'Karpet tiada tag direkod.')) {
      setDescription('')
      setAdding(false)
    }
  }

  return (
    <aside aria-label="Karpet hilang tag" className="h-fit space-y-4 rounded-xl border border-rose-200 bg-white p-4 shadow-sm">
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
        <h2 className="flex items-center gap-1.5 text-sm font-bold text-rose-900">
          <TagIcon /> Karpet hilang tag (XXX)
        </h2>
        <p className="mt-1 text-xs text-rose-800">
          Tag tertanggal semasa cucian? Rekod jenis dan saiz di sini supaya kaunter boleh padankan semula dengan
          no. siri yang betul.
        </p>
      </div>
      <NoticeLine notice={notice} />

      {items?.length === 0 && <p className="text-center text-xs text-slate-500">Tiada karpet tanpa tag.</p>}
      <ul className="space-y-2">
        {items?.map((item) => (
          <li key={item.id} className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
            <p className="flex justify-between gap-2 font-bold text-rose-700">
              <span>No. siri: XXX</span>
              <span>{formatShortDate(item.found_on)}</span>
            </p>
            <p>
              <strong>{item.description}</strong>
            </p>
            <p className="text-slate-500">Direkod oleh: {item.found_by ?? 'Staf'}</p>
            <form
              className="flex gap-1.5"
              onSubmit={(e) => {
                e.preventDefault()
                const tag = tags[item.id]?.trim()
                if (tag) void save(`/api/work/untagged/${item.id}/match`, { tag }, `Dipadankan dengan ${tag}.`)
              }}
            >
              <label className="min-w-0 flex-1">
                <span className="sr-only">No. siri sebenar</span>
                <input
                  value={tags[item.id] ?? ''}
                  onChange={(e) => setTags({ ...tags, [item.id]: e.target.value })}
                  placeholder="No. siri, cth 412-2"
                  className="w-full rounded-md border border-slate-300 bg-white px-2 py-1"
                />
              </label>
              <button type="submit" className="rounded-md bg-slate-900 px-2.5 py-1 font-semibold text-white">
                Padankan
              </button>
            </form>
          </li>
        ))}
      </ul>

      {adding ? (
        <form onSubmit={log} className="space-y-2">
          <label className="block text-xs font-semibold text-slate-700">
            Jenis & saiz karpet tiada tag
            <input
              autoFocus
              value={description}
              maxLength={200}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="cth: Biasa 6.7 x 9.7, warna biru"
              className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-2 text-sm font-normal"
            />
          </label>
          <div className="flex gap-2">
            <button type="submit" className="flex-1 rounded-lg bg-rose-600 py-2 text-xs font-bold text-white hover:bg-rose-700">
              Simpan
            </button>
            <button type="button" onClick={() => setAdding(false)} className="rounded-lg bg-slate-100 px-3 text-xs font-bold text-slate-600">
              Batal
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="w-full rounded-lg bg-rose-600 py-2.5 text-xs font-bold text-white shadow hover:bg-rose-700"
        >
          + Log karpet tiada tag (XXX)
        </button>
      )}
    </aside>
  )
}

// --- Borang Packing --------------------------------------------------------------------------

export function PackPage() {
  const today = todayInMalaysia()
  const staff = useStaffName()
  const work = useWorkItems('washed')
  const [version, setVersion] = useState(0)
  const { log } = useWorkLog(today, version)
  const [folds, setFolds] = useState<Record<number, ItemFold>>({})
  const { move, busy, notice, setNotice } = useMove(() => {
    work.reload()
    setVersion((v) => v + 1)
  })

  const pack = (item: WorkItem) => {
    const fold = folds[item.id]
    if (item.service.needs_fold && !fold) {
      setNotice({ ok: false, text: `Pilih Gulung atau Lipat untuk karpet velvet ${item.tag} dulu.` })
      return
    }
    void move(item, 'ready', fold ? { fold } : {})
  }

  const due = (work.items ?? []).filter((i) => readyToPack(i, today)).length
  const [query, setQuery] = useState('')
  const toPack = (work.items ?? []).filter((item) => carpetMatches(item, query))
  const packedToday = (log?.packed ?? []).filter((item) => carpetMatches(item, query))
  const noMatch = query.trim() !== '' && (work.items?.length ?? 0) + (log?.packed.length ?? 0) > 0 && toPack.length + packedToday.length === 0

  return (
    <section className="space-y-6">
      <Banner
        tone="bg-amber-900"
        badge="bg-amber-700"
        boxTone="border-amber-600 bg-amber-800"
        icon={<BoxIcon className="size-5" />}
        kicker="Borang packing"
        title="Rekod packing karpet (selepas 5–7 hari kering)"
        staffLabel="Staf packing"
        staff={staff}
      >
        Sistem menapis sendiri karpet yang dicuci <strong>5 hingga 7 hari lepas</strong>. Untuk karpet{' '}
        <strong>velvet</strong>, staf wajib tanda sama ada <strong>Gulung</strong> atau <strong>Lipat</strong>.
      </Banner>
      <NoticeLine notice={notice} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-100 px-4 py-3">
          <h2 className="text-sm font-bold text-slate-800">
            {due > 0 ? `${due} karpet sedia untuk pack` : 'Karpet yang sedang kering'}
          </h2>
          <span className="text-xs text-slate-500">
            Staf aktif: <strong>{staff}</strong>
          </span>
        </div>
        <div className="border-b border-slate-200 p-3">
          <SearchBox
            value={query}
            onChange={setQuery}
            label="Cari karpet untuk dipack"
            placeholder="Cari no. siri (12 / 12-2), nama atau jenis karpet"
          />
        </div>
        <Loading work={work} empty="Tiada karpet untuk dipack." />
        {noMatch && <p className="p-6 text-center text-sm text-ink-soft">Tiada karpet sepadan dengan carian.</p>}
        {(toPack.length > 0 || packedToday.length > 0) && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm max-md:block">
              <thead className="max-md:hidden">
                <tr className="bg-slate-800 text-xs text-white uppercase">
                  <th scope="col" className="px-4 py-3">No. siri karpet</th>
                  <th scope="col" className="px-4 py-3">Jenis karpet</th>
                  <th scope="col" className="px-4 py-3">Saiz (kaki)</th>
                  <th scope="col" className="px-4 py-3">Tarikh cuci & tempoh kering</th>
                  <th scope="col" className="px-4 py-3">Catatan (velvet: gulung @ lipat)</th>
                  <th scope="col" className="px-4 py-3 text-right">Status / sahkan packing</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 max-md:block">
                {toPack.map((item) => {
                  const days = item.washed_on ? daysBetween(item.washed_on, today) : 0
                  const ready = readyToPack(item, today)
                  return (
                    <PackRow key={item.id} item={item} label={`Karpet ${item.tag}`} className="hover:bg-amber-50/40">
                      <td className={packCell}>
                        <p className="text-xs font-semibold text-slate-700">Dicuci: {item.washed_on && formatShortDate(item.washed_on)}</p>
                        <span
                          className={`mt-1 inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-bold ${
                            ready ? 'border border-amber-400 bg-amber-100 text-amber-900' : 'bg-sky-100 text-sky-800'
                          }`}
                        >
                          <ClockIcon className="size-3" /> {days} hari kering {ready ? '(cukup 5–7 hari)' : ''}
                        </span>
                      </td>
                      <td className={packCell}>
                        {item.service.needs_fold ? (
                          <div className="flex items-center gap-2" role="radiogroup" aria-label={`Cara pack ${item.tag}`}>
                            {(['rolled', 'folded'] as const).map((fold) => (
                              <button
                                key={fold}
                                type="button"
                                role="radio"
                                aria-checked={folds[item.id] === fold}
                                onClick={() => setFolds({ ...folds, [item.id]: fold })}
                                className="rounded border border-purple-300 bg-white px-3 py-1 text-xs font-bold text-purple-800 uppercase transition hover:bg-purple-50 aria-checked:border-purple-700 aria-checked:bg-purple-700 aria-checked:text-white"
                              >
                                {FOLD_LABEL[fold]}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Tiada (bukan velvet)</span>
                        )}
                      </td>
                      <td className={`${packCell} md:text-right`}>
                        <button
                          type="button"
                          disabled={busy !== null}
                          onClick={() => pack(item)}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-extrabold text-slate-950 shadow transition hover:bg-amber-600 disabled:opacity-50"
                        >
                          <CheckIcon className="size-3.5" /> Tandakan siap pack
                        </button>
                      </td>
                    </PackRow>
                  )
                })}
                {packedToday.map((item) => (
                  <PackRow key={item.id} item={item} label={`Karpet ${item.tag}, sudah dipack`} className="bg-emerald-50/40">
                    <td className={packCell}>
                      <p className="text-xs font-semibold text-slate-700">Dicuci: {item.washed_on && formatShortDate(item.washed_on)}</p>
                    </td>
                    <td className={packCell}>
                      {item.fold ? (
                        <span className="rounded bg-purple-100 px-2.5 py-1 text-xs font-bold text-purple-800 uppercase">
                          Velvet: {FOLD_LABEL[item.fold]}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 italic">{item.service.needs_fold ? '—' : 'Tiada (bukan velvet)'}</span>
                      )}
                    </td>
                    <td className={`${packCell} md:text-right`}>
                      <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1 text-xs font-bold text-white">
                        <CheckIcon className="size-3.5" /> Siap pack ({formatShortDate(item.ready_on as string)})
                      </span>
                      <p className="mt-0.5 text-[11px] text-slate-500">Oleh: {item.packed_by ?? 'Staf'}</p>
                    </td>
                  </PackRow>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

const packCell = 'px-4 py-3.5 max-md:block max-md:px-0 max-md:py-1.5'

/** The first three columns of a packing row (tag, type, size); the rest are passed in. */
function PackRow({ item, label, className, children }: { item: WorkItem; label: string; className: string; children: ReactNode }) {
  return (
    <tr aria-label={label} className={`${className} align-top max-md:block max-md:px-4 max-md:py-3`}>
      <td className={packCell}>
        <span className="rounded border border-slate-300 bg-slate-100 px-2.5 py-1 font-extrabold text-slate-900">#{item.tag}</span>
        <p className="mt-1 text-xs text-slate-500">{item.customer_name}</p>
      </td>
      <td className={packCell}>
        <span
          className={`rounded px-2.5 py-1 text-xs font-bold ${
            item.service.needs_fold ? 'border border-purple-300 bg-purple-100 text-purple-900' : 'bg-slate-100 text-slate-800'
          }`}
        >
          {item.service.name}
        </span>
      </td>
      <td className={`${packCell} font-mono font-bold text-slate-700`}>{formatSize(item)}</td>
      {children}
    </tr>
  )
}

// --- Rekod harian ----------------------------------------------------------------------------

export function LogPage() {
  const [day, setDay] = useState(todayInMalaysia())
  const { log, error } = useWorkLog(day)

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm print:hidden">
        <div>
          <h1 className="text-xl font-extrabold">Rekod harian</h1>
          <p className="text-sm text-ink-soft">Borang cuci dan borang packing untuk satu hari, sedia untuk dicetak.</p>
        </div>
        <div className="flex items-end gap-2">
          <label className="text-sm">
            <span className="block text-xs font-bold text-slate-600">Tarikh</span>
            <input
              type="date"
              value={day}
              max={todayInMalaysia()}
              onChange={(e) => e.target.value && setDay(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-amber-500 focus:outline-none"
            />
          </label>
          <button
            type="button"
            onClick={() => window.print()}
            className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-4 py-2.5 text-xs font-bold text-white"
          >
            <PrintIcon /> Cetak
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
            last={(i) => [i.notes, i.wash_note].filter(Boolean).join('; ')}
          />
          <FormTable
            title="Rekod packing karpet"
            day={log.day}
            items={log.packed}
            staff={(i) => i.packed_by}
            lastHeading="Gulung / Lipat"
            last={(i) => (i.fold ? FOLD_LABEL[i.fold] : '')}
          />
          <FormTable
            title="Kerja luar"
            day={log.day}
            items={log.on_site}
            staff={(i) => i.packed_by}
            sizeHeading="Kuantiti"
            lastHeading="Catatan"
            last={(i) => i.notes ?? ''}
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
  sizeHeading = 'Saiz',
  lastHeading,
  last,
}: {
  title: string
  day: string
  items: WorkItem[]
  staff: (item: WorkItem) => string | null
  sizeHeading?: string
  lastHeading: string
  last: (item: WorkItem) => string
}) {
  const names = [...new Set(items.map(staff).filter((n): n is string => Boolean(n)))]
  return (
    <section
      aria-label={title}
      className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm print:break-inside-avoid print:rounded-none print:border-slate-800 print:shadow-none"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <h2 className="font-bold uppercase">{title}</h2>
        <p className="text-sm text-ink-soft">
          {formatLongDay(day)} · Staf bertugas: {names.length ? names.join(', ') : '-'}
        </p>
      </header>
      {items.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-ink-soft">Tiada rekod pada hari ini.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800 text-xs text-white uppercase">
              <tr>
                <th className="px-4 py-2 font-semibold">Bil</th>
                <th className="px-4 py-2 font-semibold">No. siri</th>
                <th className="px-4 py-2 font-semibold">Jenis</th>
                <th className="px-4 py-2 font-semibold">{sizeHeading}</th>
                <th className="px-4 py-2 font-semibold">{lastHeading}</th>
                <th className="px-4 py-2 font-semibold">Staf</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
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

/** The coloured strip at the top of a form page, with the worker on duty. */
function Banner({
  tone,
  badge,
  boxTone,
  icon,
  kicker,
  title,
  staffLabel,
  staff,
  children,
}: {
  tone: string
  badge: string
  boxTone: string
  icon: ReactNode
  kicker: string
  title: string
  staffLabel: string
  staff: string
  children: ReactNode
}) {
  return (
    <div className={`flex flex-wrap items-center justify-between gap-4 rounded-xl p-5 text-white shadow ${tone}`}>
      <div className="max-w-2xl">
        <span className={`rounded px-2.5 py-1 text-xs font-bold tracking-wider uppercase ${badge}`}>{kicker}</span>
        <h1 className="mt-2 flex items-center gap-2 text-xl font-extrabold uppercase">
          {icon} {title}
        </h1>
        <p className="mt-0.5 text-xs text-white/80">{children}</p>
      </div>
      <div className={`flex items-center gap-3 rounded-lg border p-3 ${boxTone}`}>
        <span className="text-xs font-bold text-white/75 uppercase">{staffLabel}:</span>
        <span className="rounded bg-white px-3 py-1.5 text-xs font-bold text-slate-900">{staff}</span>
      </div>
    </div>
  )
}

function NoticeLine({ notice }: { notice: Notice }) {
  if (!notice) return null
  return (
    <p
      role={notice.ok ? 'status' : 'alert'}
      className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
        notice.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-rose-200 bg-rose-50 text-rose-800'
      }`}
    >
      {notice.ok ? <CheckIcon /> : <AlertIcon />} {notice.text}
    </p>
  )
}

function Loading({ work, empty }: { work: { items: WorkItem[] | null; error: boolean }; empty: string }) {
  if (work.error) return <p role="alert" className="p-4 text-danger">Tak dapat muatkan senarai. Cuba lagi.</p>
  if (work.items === null) return <p className="p-4 text-ink-soft">Memuatkan…</p>
  if (work.items.length === 0) return <p className="p-6 text-center text-sm text-ink-soft">{empty}</p>
  return null
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
