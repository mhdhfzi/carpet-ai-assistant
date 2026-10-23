import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { BarList, ChartCard, ColumnChart, ColumnLabels, DataTable, Meter, StatTile } from './charts'
import { PAYMENT_LABEL, formatMoney } from './format'
import type { BusinessAnalytics, PaymentMethod } from './types'

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

/** "Oktober" from "2026-10". */
function monthName(month: string): string {
  return MONTHS[Number(month.slice(5, 7)) - 1]
}

/** The business side for one year: its totals, its months side by side, and the whole year or
 * one month in detail. */
export function BusinessSection() {
  const { request } = useAuth()
  const [year, setYear] = useState<number | null>(null) // null: this year (the server decides)
  const [month, setMonth] = useState<number | null>(null) // null: the whole year
  const [data, setData] = useState<BusinessAnalytics | null>(null)
  const [error, setError] = useState(false)

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

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile label="Jumlah hasil keseluruhan" value={formatMoney(expected)} hint="Diterima + baki belum dibayar" />
        <StatTile label="Jumlah hasil diterima" value={formatMoney(data.revenue_total)} hint="Semua bayaran sepanjang tahun" />
        <StatTile
          label="Baki belum dibayar"
          value={formatMoney(data.unpaid)}
          hint={data.unpaid_orders ? `${data.unpaid_orders} pesanan tahun ini` : 'Semua sudah dibayar'}
        />
      </div>

      <section aria-labelledby="monthly-heading" className="space-y-4 rounded-2xl bg-white p-4 ring-1 ring-line">
        <div>
          <h3 id="monthly-heading" className="font-semibold">
            Setiap bulan
          </h3>
          <p className="text-xs text-ink-soft">Hasil diterima, pesanan dan servis paling popular, bulan terkini dahulu</p>
        </div>
        {/* Sideways bars, newest month first: twelve standing columns don't fit a phone. */}
        <BarList
          formatValue={(value) => formatMoney(String(value))}
          data={newestFirst.map((m) => ({
            label: monthName(m.month),
            sublabel: `${m.orders} pesanan`,
            value: Number(m.revenue),
            description: `${monthName(m.month)}: ${formatMoney(m.revenue)}, ${m.orders} pesanan`,
          }))}
        />
        <DataTable
          columns={['Bulan', 'Hasil diterima', 'Pesanan', 'Servis paling popular']}
          rows={newestFirst.map((m) => [monthName(m.month), formatMoney(m.revenue), m.orders, m.top_service ?? '–'])}
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
        <StatTile label="Hasil diterima" value={formatMoney(data.revenue)} hint={`Bayaran ${period}`} />
        <StatTile
          label="Pesanan"
          value={String(data.orders)}
          hint={`Nilai ${formatMoney(data.order_value)}${data.cancelled ? ` · ${data.cancelled} dibatalkan` : ''}`}
        />
        <StatTile
          label="Purata masa siap"
          value={data.average_days_to_ready === null ? '–' : `${data.average_days_to_ready} hari`}
          hint="Karpet: diterima hingga dipack"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
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
                  description: `${s.name}: ${s.items} barang, ${formatMoney(s.value)}`,
                }))}
              />
            ) : (
              <p className="text-sm text-ink-soft">Tiada pesanan {period}.</p>
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
