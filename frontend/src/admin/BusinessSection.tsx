import { type ReactNode, useEffect, useId, useState } from 'react'
import { useAuth } from './auth'
import { BarList, ChartCard, ColumnChart, ColumnLabels, DataTable, Meter, TrendChart } from './charts'
import { PAYMENT_LABEL, formatMoney, todayInMalaysia } from './format'
import type { BusinessAnalytics, PaymentMethod, WorkSummary } from './types'
import { href } from './useHashRoute'

const WEEKDAY: Record<string, string> = {
  Mon: 'Isnin',
  Tue: 'Selasa',
  Wed: 'Rabu',
  Thu: 'Khamis',
  Fri: 'Jumaat',
  Sat: 'Sabtu',
  Sun: 'Ahad',
}
const WEEKDAY_SHORT: Record<string, string> = {
  Mon: 'Isn',
  Tue: 'Sel',
  Wed: 'Rab',
  Thu: 'Kha',
  Fri: 'Jum',
  Sat: 'Sab',
  Sun: 'Aha',
}

// Month names alone ("Oktober"): the year is said once, with the period.
const monthLong = new Intl.DateTimeFormat('ms-MY', { month: 'long', timeZone: 'Asia/Kuala_Lumpur' })
const monthShort = new Intl.DateTimeFormat('ms-MY', { month: 'short', timeZone: 'Asia/Kuala_Lumpur' })
const MONTHS = Array.from({ length: 12 }, (_, i) => monthLong.format(new Date(Date.UTC(2026, i, 15))))
const MONTHS_SHORT = Array.from({ length: 12 }, (_, i) => monthShort.format(new Date(Date.UTC(2026, i, 15))))

/** "Oktober" from "2026-10". */
function monthName(month: string): string {
  return MONTHS[Number(month.slice(5, 7)) - 1]
}

/** RM in whole ringgit for the chart's axis and tooltips ("RM1,244"). */
function ringgit(value: number): string {
  return `RM${Math.round(value).toLocaleString('en-MY')}`
}

/** "+12%" in green, "-7%" in red (or the other way round when lower is better), "baru" when
 * the period before had none. Nothing when both are zero. */
function Change({ now, before, lowerIsBetter = false, unit }: { now: number; before: number; lowerIsBetter?: boolean; unit?: string }) {
  if (!now && !before) return null
  let text: string
  let diff: number
  if (unit) {
    diff = Math.round((now - before) * 10) / 10
    text = `${diff > 0 ? '+' : ''}${diff} ${unit}`
  } else if (!before) {
    return <span className="text-sm font-bold text-emerald-700">baru</span>
  } else {
    diff = Math.round(((now - before) / before) * 100)
    text = `${diff > 0 ? '+' : ''}${diff}%`
  }
  const good = lowerIsBetter ? diff < 0 : diff > 0
  const colour = diff === 0 ? 'text-ink-soft' : good ? 'text-emerald-700' : 'text-red-700'
  return <span className={`text-sm font-bold ${colour}`}>{text}</span>
}

function Kpi({ label, value, change, hint }: { label: string; value: string; change?: ReactNode; hint?: string }) {
  return (
    <div className="min-w-0 xl:px-5 xl:first:pl-0">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-2xl font-bold break-words">{value}</span>
        {change}
      </p>
      <p className="text-sm text-ink-soft">{label}</p>
      {hint && <p className="text-xs text-ink-soft">{hint}</p>}
    </div>
  )
}

/** The business side for one year, or one of its months: the headline numbers against the
 * period before, money month by month against last year, what's in the shop right now, and
 * the period's services, payments and busy days. */
export function BusinessSection() {
  const { request } = useAuth()
  const [year, setYear] = useState<number | null>(null) // null: this year (the server decides)
  const [month, setMonth] = useState<number | null>(null) // null: the whole year
  const [data, setData] = useState<BusinessAnalytics | null>(null)
  const [error, setError] = useState(false)
  const [asTable, setAsTable] = useState(false)
  const pickerId = useId()

  useEffect(() => {
    let current = true
    const query = new URLSearchParams()
    if (year) query.set('year', String(year))
    if (month) query.set('month', String(month))
    const search = query.toString() // not query.size: older phone browsers lack it
    request<BusinessAnalytics>(`/api/analytics/business${search ? `?${search}` : ''}`)
      .then((body) => {
        if (!current) return
        setData(body)
        setError(false)
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [year, month, request])

  if (error) return <p role="alert" className="text-danger">Tak dapat muatkan data perniagaan.</p>
  if (!data) return <p className="text-ink-soft">Memuatkan data perniagaan…</p>

  const revenue = Number(data.revenue)
  const methods = Object.keys(PAYMENT_LABEL) as PaymentMethod[]
  const newestFirst = [...data.months].reverse()
  // By month number (1-12), so a missing month is a gap of zero, never a shift.
  const thisYear = new Map(data.months.map((m) => [Number(m.month.slice(5, 7)), m]))
  const lastYear = new Map(data.last_year_months.map((m) => [Number(m.month.slice(5, 7)), m]))
  const shownMonths = Math.max(0, ...thisYear.keys())
  // Before the shop used the system, last year is all zeros: nothing to compare with.
  const hasLastYear = data.last_year_months.some((m) => Number(m.revenue) > 0)
  const points = (byMonth: typeof thisYear, count: number) =>
    Array.from({ length: count }, (_, i) => ({ label: MONTHS_SHORT[i], value: Number(byMonth.get(i + 1)?.revenue ?? 0) }))
  // What the shop should collect in all: received so far plus what's still owed (in sen, so
  // the sum has no rounding error).
  const expected = ((Math.round(Number(data.revenue_total) * 100) + Math.round(Number(data.unpaid) * 100)) / 100).toFixed(2)
  const period = data.month ? 'bulan ini' : 'tahun ini'
  const title = data.month ? `${MONTHS[data.month - 1]} ${data.year}` : `Sepanjang ${data.year}`
  const before = data.previous
  const beforeYear = Number(before.start.slice(0, 4))
  const beforeName = data.month
    ? `${monthName(before.start)}${beforeYear !== data.year ? ` ${beforeYear}` : ''}`
    : String(beforeYear)

  // Every period that can be picked: each year, then its months newest first.
  const today = todayInMalaysia()
  const monthsOf = (y: number) => {
    const last = y === Number(today.slice(0, 4)) ? Number(today.slice(5, 7)) : 12
    return Array.from({ length: last }, (_, i) => last - i)
  }
  const choose = (value: string) => {
    const [y, m] = value.split('-').map(Number)
    setYear(y)
    setMonth(m || null)
  }

  const describe = (i: number) => {
    const m = thisYear.get(i + 1)
    const old = hasLastYear ? lastYear.get(i + 1) : undefined
    const now = m ? `${ringgit(Number(m.revenue))}, ${m.orders} pesanan` : 'belum ada'
    return `${MONTHS[i]} ${data.year}: ${now}${old ? ` · ${data.year - 1}: ${ringgit(Number(old.revenue))}` : ''}`
  }

  return (
    <section aria-labelledby="business-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="business-heading" className="font-display text-xl font-bold">
          Perniagaan
        </h2>
        {/* Everything below belongs to the chosen period. */}
        <label htmlFor={pickerId} className="flex items-center gap-2 rounded-xl bg-white py-1 pr-1 pl-3 text-sm ring-1 ring-line">
          <span className="font-semibold text-ink-soft">Tempoh</span>
          <select
            id={pickerId}
            value={data.month ? `${data.year}-${data.month}` : String(data.year)}
            onChange={(e) => choose(e.target.value)}
            className="rounded-lg bg-foam px-2 py-1.5 font-semibold"
          >
            {data.years.map((y) => (
              <optgroup key={y} label={String(y)}>
                <option value={String(y)}>Sepanjang {y}</option>
                {monthsOf(y).map((m) => (
                  <option key={m} value={`${y}-${m}`}>
                    {MONTHS[m - 1]} {y}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-labelledby="performance-heading" className="min-w-0 space-y-5 rounded-2xl bg-white p-4 ring-1 ring-line sm:p-5 lg:col-span-2">
          <div>
            <h3 id="performance-heading" className="font-semibold">
              Prestasi
            </h3>
            <p className="text-lg font-bold">{title}</p>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-5 xl:grid-cols-4 xl:gap-0 xl:divide-x xl:divide-line">
            <Kpi
              label="Hasil diterima"
              value={formatMoney(data.revenue)}
              change={<Change now={revenue} before={Number(before.revenue)} />}
            />
            <Kpi
              label="Pesanan"
              value={String(data.orders)}
              change={<Change now={data.orders} before={before.orders} />}
              hint={data.cancelled ? `${data.cancelled} dibatalkan` : undefined}
            />
            <Kpi
              label="Baki belum dibayar"
              value={formatMoney(data.unpaid)}
              hint={data.unpaid_orders ? `${data.unpaid_orders} pesanan ${data.year}` : 'Semua sudah dibayar'}
            />
            <Kpi
              label="Purata masa siap"
              value={data.average_days_to_ready === null ? '–' : `${data.average_days_to_ready} hari`}
              change={
                data.average_days_to_ready !== null &&
                before.average_days_to_ready !== null && (
                  <Change now={data.average_days_to_ready} before={before.average_days_to_ready} unit="hari" lowerIsBetter />
                )
              }
            />
          </div>
          <p className="text-xs text-ink-soft">Perubahan berbanding {beforeName}.</p>

          <div className="space-y-3 border-t border-line pt-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h3 className="font-semibold">Setiap bulan</h3>
                <p className="text-xs text-ink-soft">
                  Hasil diterima {data.year}
                  {hasLastYear && `, dengan ${data.year - 1} untuk perbandingan`}
                </p>
              </div>
              <button
                type="button"
                aria-pressed={asTable}
                onClick={() => setAsTable((v) => !v)}
                className="rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-line hover:bg-foam aria-pressed:bg-ink aria-pressed:text-white"
              >
                Show as table
              </button>
            </div>
            {asTable ? (
              <DataTable
                columns={['Bulan', 'Hasil diterima', 'Pesanan', 'Servis paling popular', String(data.year - 1)]}
                rows={newestFirst.map((m) => {
                  const old = lastYear.get(Number(m.month.slice(5, 7)))
                  return [monthName(m.month), formatMoney(m.revenue), m.orders, m.top_service ?? '–', old ? formatMoney(old.revenue) : '–']
                })}
              />
            ) : (
              <TrendChart
                label="Hasil setiap bulan"
                slots={MONTHS_SHORT}
                current={points(thisYear, shownMonths)}
                compare={hasLastYear ? points(lastYear, 12) : []}
                currentName={String(data.year)}
                compareName={String(data.year - 1)}
                highlight={data.month ? data.month - 1 : null}
                formatValue={ringgit}
                describe={describe}
              />
            )}
            <p className="text-xs text-ink-soft">
              Diterima sepanjang {data.year}: <span className="font-semibold text-ink">{formatMoney(data.revenue_total)}</span>
              {' · '}Jumlah keseluruhan (termasuk baki): <span className="font-semibold text-ink">{formatMoney(expected)}</span>
            </p>
          </div>
        </section>

        <ShopNow />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          title="Servis paling popular"
          subtitle={`Barang dalam pesanan ${period} (sofa dikira ikut tempat duduk)`}
          chart={
            data.services.length ? (
              <BarList
                data={data.services.map((s) => ({
                  label: s.name,
                  sublabel: formatMoney(s.value),
                  value: s.items,
                  change: <Change now={s.items} before={before.items_by_service[s.name] ?? 0} />,
                  description: `${s.name}: ${s.items} barang, ${formatMoney(s.value)} · ${beforeName}: ${before.items_by_service[s.name] ?? 0}`,
                }))}
              />
            ) : (
              <p className="text-sm text-ink-soft">Tiada pesanan {period}.</p>
            )
          }
          table={
            <DataTable
              columns={['Servis', 'Barang', beforeName, 'Nilai']}
              rows={data.services.map((s) => [s.name, s.items, before.items_by_service[s.name] ?? 0, formatMoney(s.value)])}
            />
          }
        />

        <ChartCard
          title="Cara bayaran"
          subtitle={`Bahagian hasil ${period}`}
          chart={
            <div className="space-y-4">
              {methods.map((m) => (
                <Meter
                  key={m}
                  label={PAYMENT_LABEL[m]}
                  value={Number(data.revenue_by_method[m])}
                  max={revenue}
                  detail={`${formatMoney(data.revenue_by_method[m])}${revenue ? ` · ${Math.round((Number(data.revenue_by_method[m]) / revenue) * 100)}%` : ''}`}
                  change={<Change now={Number(data.revenue_by_method[m])} before={Number(before.revenue_by_method[m])} />}
                />
              ))}
            </div>
          }
          table={
            <DataTable
              columns={['Cara', 'Jumlah', beforeName]}
              rows={methods.map((m) => [PAYMENT_LABEL[m], formatMoney(data.revenue_by_method[m]), formatMoney(before.revenue_by_method[m])])}
            />
          }
        />

        <ChartCard
          title="Hari sibuk"
          subtitle={`Pesanan diterima mengikut hari, ${period}`}
          chart={
            <>
              <ColumnChart
                valueLabel="Pesanan mengikut hari"
                data={data.busy_days.map((d) => ({
                  label: d.weekday,
                  value: d.orders,
                  description: `${WEEKDAY[d.weekday]}: ${d.orders} pesanan`,
                }))}
              />
              <ColumnLabels labels={data.busy_days.map((d) => WEEKDAY_SHORT[d.weekday] ?? d.weekday)} />
            </>
          }
          table={
            <DataTable
              columns={['Hari', 'Pesanan']}
              rows={data.busy_days.map((d) => [WEEKDAY[d.weekday] ?? d.weekday, d.orders])}
            />
          }
        />
      </div>
    </section>
  )
}

/** What's in the shop right now, whatever period is picked: like a "live" card. */
function ShopNow() {
  const { request } = useAuth()
  const [summary, setSummary] = useState<WorkSummary | null>(null)

  useEffect(() => {
    let current = true
    request<WorkSummary>('/api/work/summary')
      .then((body) => {
        if (current) setSummary(body)
      })
      .catch(() => {}) // the card just stays empty; the rest of the page still works
    return () => {
      current = false
    }
  }, [request])

  const rows: { label: string; value: string; link?: string }[] = summary
    ? [
        { label: 'Belum cuci', value: String(summary.to_wash), link: href({ page: 'wash' }) },
        { label: 'Sedang kering', value: String(summary.drying) },
        { label: 'Sedia pack', value: String(summary.to_pack), link: href({ page: 'pack' }) },
        { label: 'Siap, tunggu diambil', value: `${summary.ready_orders} tempahan`, link: href({ page: 'orders', filter: 'ready' }) },
        { label: 'Kerja luar belum siap', value: String(summary.house_jobs), link: href({ page: 'visits' }) },
      ]
    : []

  return (
    <section aria-labelledby="shop-now-heading" className="flex min-w-0 flex-col rounded-2xl bg-white p-4 ring-1 ring-line sm:p-5">
      <h3 id="shop-now-heading" className="font-semibold">
        Di kedai sekarang
      </h3>
      {summary ? (
        <>
          <p className="mt-3 flex items-center gap-3">
            <span className="relative flex size-2.5" aria-hidden="true">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-brand opacity-60 motion-reduce:hidden" />
              <span className="relative inline-flex size-2.5 rounded-full bg-brand" />
            </span>
            <span className="text-3xl font-bold">{summary.to_wash + summary.drying + summary.to_pack}</span>
          </p>
          <p className="text-sm text-ink-soft">karpet belum dipack</p>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] tracking-wide text-ink-soft uppercase">
                <th className="pb-2 font-semibold">Peringkat</th>
                <th className="pb-2 text-right font-semibold">Jumlah</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {rows.map((row) => (
                <tr key={row.label} className="border-t border-line">
                  <td className="py-2.5">
                    {row.link ? (
                      <a href={row.link} className="hover:underline">
                        {row.label}
                      </a>
                    ) : (
                      row.label
                    )}
                  </td>
                  <td className="py-2.5 text-right font-semibold">{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <a href={href({ page: 'wash' })} className="mt-auto pt-4 text-right text-sm font-semibold text-brand-ink hover:underline">
            Buka Borang Cuci →
          </a>
        </>
      ) : (
        <p className="mt-3 text-sm text-ink-soft">Memuatkan…</p>
      )}
    </section>
  )
}

