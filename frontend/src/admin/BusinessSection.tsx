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

const monthLong = new Intl.DateTimeFormat('ms-MY', { month: 'long', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur' })
const asDate = (month: string) => new Date(`${month}-15T12:00:00+08:00`)

/** "Oktober 2026" from "2026-10". */
function monthName(month: string): string {
  return monthLong.format(asDate(month))
}

/** The business side: totals to date, the last 12 months side by side, and one month in detail. */
export function BusinessSection() {
  const { request } = useAuth()
  const [month, setMonth] = useState<string | null>(null) // null: this month (the server decides)
  const [data, setData] = useState<BusinessAnalytics | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    request<BusinessAnalytics>(`/api/analytics/business${month ? `?month=${month}` : ''}`)
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
  }, [month, request])

  if (error) return <p role="alert" className="text-danger">Tak dapat muatkan data perniagaan.</p>
  if (!data) return <p className="text-ink-soft">Memuatkan data perniagaan…</p>

  const revenue = Number(data.revenue)
  const methods = Object.keys(PAYMENT_LABEL) as PaymentMethod[]
  const newestFirst = [...data.months].reverse()
  // What the shop should collect in all: received so far plus what's still owed (in sen, so
  // the sum has no rounding error).
  const expected = ((Math.round(Number(data.revenue_total) * 100) + Math.round(Number(data.unpaid) * 100)) / 100).toFixed(2)

  return (
    <section aria-labelledby="business-heading" className="space-y-4">
      <h2 id="business-heading" className="font-display text-xl font-bold">
        Perniagaan
      </h2>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile label="Jumlah hasil keseluruhan" value={formatMoney(expected)} hint="Diterima + baki belum dibayar" />
        <StatTile label="Jumlah hasil diterima" value={formatMoney(data.revenue_total)} hint="Semua bayaran setakat ini" />
        <StatTile
          label="Baki belum dibayar"
          value={formatMoney(data.unpaid)}
          hint={data.unpaid_orders ? `${data.unpaid_orders} pesanan (semua masa)` : 'Semua sudah dibayar'}
        />
      </div>

      <section aria-labelledby="monthly-heading" className="space-y-4 rounded-2xl bg-white p-4 ring-1 ring-line">
        <div>
          <h3 id="monthly-heading" className="font-semibold">
            Setiap bulan
          </h3>
          <p className="text-xs text-ink-soft">Hasil diterima, pesanan dan servis paling popular, 12 bulan terakhir</p>
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
        <h3 className="text-lg font-bold">{monthName(data.month)}</h3>
        <label className="text-sm">
          <span className="mb-1 block text-xs font-bold text-slate-600">Lihat bulan</span>
          <select
            value={data.month}
            onChange={(e) => setMonth(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-semibold"
          >
            {newestFirst.map((m) => (
              <option key={m.month} value={m.month}>
                {monthName(m.month)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile label="Hasil diterima" value={formatMoney(data.revenue)} hint="Bayaran bulan ini" />
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
          subtitle="Barang dalam pesanan bulan ini (sofa dikira ikut tempat duduk)"
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
              <p className="text-sm text-ink-soft">Tiada pesanan bulan ini.</p>
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
          subtitle="Bahagian hasil bulan ini"
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
          subtitle="Pesanan diterima mengikut hari, bulan ini"
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
