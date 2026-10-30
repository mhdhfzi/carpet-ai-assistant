import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import {
  BarList,
  Change,
  ChartCard,
  ColumnChart,
  ColumnLabels,
  DataTable,
  LineChart,
  type LineSeries,
  Meter,
  StatTile,
} from './charts'
import { PAYMENT_LABEL, formatMoney, todayInMalaysia } from './format'
import type { BusinessAnalytics, MonthStat, PaymentMethod } from './types'

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

// Month names alone ("Oktober"): the year is picked once, at the top.
const monthLong = new Intl.DateTimeFormat('ms-MY', { month: 'long', timeZone: 'Asia/Kuala_Lumpur' })
const MONTHS = Array.from({ length: 12 }, (_, i) => monthLong.format(new Date(Date.UTC(2026, i, 15))))
const monthShort = new Intl.DateTimeFormat('ms-MY', { month: 'short', timeZone: 'Asia/Kuala_Lumpur' })
const MONTHS_SHORT = Array.from({ length: 12 }, (_, i) => monthShort.format(new Date(Date.UTC(2026, i, 15))))

/** "Oktober" from "2026-10". */
function monthName(month: string): string {
  return MONTHS[Number(month.slice(5, 7)) - 1]
}

/** "Okt" from "2026-10", under the line charts. */
function monthLabel(month: string): string {
  return MONTHS_SHORT[Number(month.slice(5, 7)) - 1]
}

// What the monthly line can show, one at a time: money and counts don't share a scale.
const MEASURES = {
  revenue: { label: 'Hasil', of: (m: MonthStat) => Number(m.revenue), format: (v: number) => formatMoney(v.toFixed(2)) },
  orders: { label: 'Pesanan', of: (m: MonthStat) => m.orders, format: (v: number) => `${v} pesanan` },
  customers: { label: 'Pelanggan', of: (m: MonthStat) => m.customers, format: (v: number) => `${v} pelanggan` },
}
type Measure = keyof typeof MEASURES

// The year's most popular services get a line each (validated categorical hues, in fixed
// order); the rest are added up as one grey "Lain-lain" line.
const SERVICE_COLOURS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']
const OTHERS_COLOUR = '#8a8a8a'

/** The business side for one year: its totals, its months side by side, and the whole year or
 * one month in detail. */
export function BusinessSection() {
  const { request } = useAuth()
  const [year, setYear] = useState<number | null>(null) // null: this year (the server decides)
  const [month, setMonth] = useState<number | null>(null) // null: the whole year
  const [data, setData] = useState<BusinessAnalytics | null>(null)
  const [error, setError] = useState(false)
  const [measure, setMeasure] = useState<Measure>('revenue')

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
  // What the shop should collect in all: received so far plus what's still owed (in sen, so
  // the sum has no rounding error).
  const expected = ((Math.round(Number(data.revenue_total) * 100) + Math.round(Number(data.unpaid) * 100)) / 100).toFixed(2)
  const period = data.month ? 'bulan ini' : 'tahun ini'

  // Each month is compared with the one before it (January with the December before).
  const before = (index: number) => (index > 0 ? data.months[index - 1] : data.month_before)
  const versus = (index: number) => monthName(before(index).month)
  const change = (index: number, of: (m: MonthStat) => number) => (
    <Change now={of(data.months[index])} before={of(before(index))} versus={versus(index)} />
  )
  // The year's tiles: the latest month against the one before. This month isn't over yet.
  const latest = data.months.length - 1
  const latestNote =
    latest >= 0 && (before(latest).orders || Number(before(latest).revenue))
      ? `${monthName(data.months[latest].month)} berbanding ${versus(latest)}${
          data.months[latest].month === todayInMalaysia().slice(0, 7) ? ' (bulan belum habis)' : ''
        }`
      : ''
  const latestChange = (of: (m: MonthStat) => number) => (latest >= 0 ? change(latest, of) : undefined)
  // One month in detail: that month against the one before.
  const chosen = data.month ? data.months.findIndex((m) => Number(m.month.slice(5, 7)) === data.month) : -1
  const chosenChange = (of: (m: MonthStat) => number) => (chosen >= 0 ? change(chosen, of) : undefined)
  const shown = MEASURES[measure]
  const services = serviceLines(data)
  const labels = data.months.map((m) => monthLabel(m.month))

  return (
    <section aria-labelledby="business-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="business-heading" className="font-display text-xl font-bold">
          Perniagaan
        </h2>
        {/* Everything below belongs to the chosen year. */}
        <div role="group" aria-label="Tahun" className="flex flex-wrap rounded-full bg-white p-1 ring-1 ring-line">
          {data.years.map((y) => (
            <button
              key={y}
              type="button"
              aria-pressed={data.year === y}
              onClick={() => {
                setYear(y)
                setMonth(null)
              }}
              className="rounded-full px-4 py-1.5 text-sm font-bold text-ink-soft aria-pressed:bg-ink aria-pressed:text-white"
            >
              {y}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Jumlah hasil keseluruhan"
          value={formatMoney(expected)}
          change={latestChange((m) => Number(m.order_value))}
          hint={`Diterima + baki belum dibayar${latestNote && ` · nilai pesanan ${latestNote}`}`}
        />
        <StatTile
          label="Jumlah hasil diterima"
          value={formatMoney(data.revenue_total)}
          change={latestChange((m) => Number(m.revenue))}
          hint={`Semua bayaran sepanjang tahun${latestNote && ` · ${latestNote}`}`}
        />
        <StatTile
          label="Baki belum dibayar"
          value={formatMoney(data.unpaid)}
          hint={data.unpaid_orders ? `${data.unpaid_orders} pesanan tahun ini` : 'Semua sudah dibayar'}
        />
        <StatTile
          label="Jumlah pelanggan"
          value={String(data.customers_total)}
          change={latestChange((m) => m.customers)}
          hint={`Pelanggan berlainan tahun ini${latestNote && ` · ${latestNote}`}`}
        />
      </div>

      <section aria-labelledby="monthly-heading" className="space-y-4 rounded-2xl bg-white p-4 ring-1 ring-line">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 id="monthly-heading" className="font-semibold">
              Setiap bulan
            </h3>
            <p className="text-xs text-ink-soft">Januari hingga bulan terkini; % berbanding bulan sebelumnya</p>
          </div>
          <div role="group" aria-label="Tunjuk" className="flex rounded-full bg-foam p-1">
            {(Object.keys(MEASURES) as Measure[]).map((key) => (
              <button
                key={key}
                type="button"
                aria-pressed={measure === key}
                onClick={() => setMeasure(key)}
                className="rounded-full px-3 py-1 text-xs font-bold text-ink-soft aria-pressed:bg-ink aria-pressed:text-white"
              >
                {MEASURES[key].label}
              </button>
            ))}
          </div>
        </div>
        <LineChart
          valueLabel={`${shown.label} setiap bulan`}
          labels={labels}
          series={[{ name: shown.label, colour: 'var(--color-chart)', values: data.months.map(shown.of) }]}
          formatValue={shown.format}
          tooltip={(i) => (
            <span className="flex items-baseline gap-2">
              {monthName(data.months[i].month)}: {shown.format(shown.of(data.months[i]))}
              <span className="rounded bg-white px-1">{change(i, shown.of)}</span>
            </span>
          )}
        />
        <DataTable
          columns={['Bulan', 'Hasil diterima', 'Pesanan', 'Pelanggan', 'Servis paling popular']}
          rows={newestFirst.map((m) => {
            const i = data.months.indexOf(m)
            const withChange = (text: string, of: (s: MonthStat) => number) => (
              <span className="flex items-baseline gap-1.5">
                {text}
                {change(i, of)}
              </span>
            )
            return [
              monthName(m.month),
              withChange(formatMoney(m.revenue), MEASURES.revenue.of),
              withChange(String(m.orders), MEASURES.orders.of),
              withChange(String(m.customers), MEASURES.customers.of),
              m.top_service ?? '–',
            ]
          })}
        />
      </section>

      <div className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <h3 className="text-lg font-bold">{data.month ? MONTHS[data.month - 1] : 'Sepanjang tahun'}</h3>
        <label className="text-sm">
          <span className="mb-1 block text-xs font-bold text-slate-600">Lihat</span>
          <select
            value={data.month ?? ''}
            onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : null)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-semibold"
          >
            <option value="">Sepanjang tahun</option>
            {data.months.map((m) => (
              <option key={m.month} value={Number(m.month.slice(5, 7))}>
                {monthName(m.month)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          label="Hasil diterima"
          value={formatMoney(data.revenue)}
          change={chosenChange(MEASURES.revenue.of)}
          hint={`Bayaran ${period}`}
        />
        <StatTile
          label="Pesanan"
          value={String(data.orders)}
          change={chosenChange(MEASURES.orders.of)}
          hint={`Nilai ${formatMoney(data.order_value)}${data.cancelled ? ` · ${data.cancelled} dibatalkan` : ''}`}
        />
        <StatTile
          label="Jumlah pelanggan"
          value={String(data.customers)}
          change={chosenChange(MEASURES.customers.of)}
          hint={chosen >= 0 ? `Pelanggan berlainan · berbanding ${versus(chosen)}` : 'Pelanggan berlainan tahun ini'}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Servis paling popular"
          subtitle={`Barang dalam pesanan ${data.month ? 'bulan ini' : 'setiap bulan'} (sofa dikira ikut tempat duduk)`}
          chart={
            !data.services.length ? (
              <p className="text-sm text-ink-soft">Tiada pesanan {period}.</p>
            ) : data.month ? (
              <BarList
                data={data.services.map((s) => ({
                  label: s.name,
                  sublabel: formatMoney(s.value),
                  value: s.items,
                  description: `${s.name}: ${s.items} barang, ${formatMoney(s.value)}`,
                }))}
              />
            ) : (
              // The whole year: how each service did, month by month.
              <LineChart
                valueLabel="Barang setiap bulan, ikut servis"
                labels={labels}
                series={services}
                formatValue={(v) => `${v} barang`}
                tooltip={(i) => (
                  <span className="block space-y-0.5">
                    <span className="block font-bold">{monthName(data.months[i].month)}</span>
                    {services.map((s) => (
                      <span key={s.name} className="flex items-center gap-1.5">
                        <span className="inline-block size-2 rounded-full" style={{ background: s.colour }} />
                        {s.name}: {s.values[i]}
                      </span>
                    ))}
                  </span>
                )}
              />
            )
          }
          table={
            <DataTable
              columns={['Servis', 'Barang', 'Nilai']}
              rows={data.services.map((s) => [s.name, s.items, formatMoney(s.value)])}
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
                />
              ))}
            </div>
          }
          table={
            <DataTable
              columns={['Cara', 'Jumlah']}
              rows={methods.map((m) => [PAYMENT_LABEL[m], formatMoney(data.revenue_by_method[m])])}
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

/** A line per popular service (the year's top four), month by month, and the rest as one. */
function serviceLines(data: BusinessAnalytics): LineSeries[] {
  const top = data.services.slice(0, SERVICE_COLOURS.length).map((s) => s.name)
  const lines: LineSeries[] = top.map((name, i) => ({
    name,
    colour: SERVICE_COLOURS[i],
    values: data.months.map((m) => m.items_by_service[name] ?? 0),
  }))
  if (data.services.length > top.length) {
    lines.push({
      name: 'Lain-lain',
      colour: OTHERS_COLOUR,
      values: data.months.map((m) =>
        Object.entries(m.items_by_service).reduce((sum, [name, items]) => (top.includes(name) ? sum : sum + items), 0),
      ),
    })
  }
  return lines
}
