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

/** "RM150", "RM1.2k": short enough to sit on top of a column. */
function shortMoney(value: number): string {
  return value >= 1000 ? `RM${(value / 1000).toFixed(1)}k` : `RM${Math.round(value)}`
}

/** Money, orders and work in progress from the back office. */
export function BusinessSection({ days }: { days: number }) {
  const { request } = useAuth()
  const [data, setData] = useState<BusinessAnalytics | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    request<BusinessAnalytics>(`/api/analytics/business?days=${days}`)
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
  }, [days, request])

  if (error) return <p role="alert" className="text-danger">Tak dapat muatkan data perniagaan.</p>
  if (!data) return <p className="text-ink-soft">Memuatkan data perniagaan…</p>

  const revenue = Number(data.revenue)
  const methods = Object.keys(PAYMENT_LABEL) as PaymentMethod[]
  const weekly = data.revenue_over_time.length > 7 || data.days > 7

  return (
    <section aria-labelledby="business-heading" className="space-y-4">
      <h2 id="business-heading" className="font-display text-xl font-bold">
        Perniagaan
      </h2>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Hasil diterima" value={formatMoney(data.revenue)} hint="Bayaran dalam tempoh ini" />
        <StatTile
          label="Pesanan"
          value={String(data.orders)}
          hint={`Nilai ${formatMoney(data.order_value)}${data.cancelled ? ` · ${data.cancelled} dibatalkan` : ''}`}
        />
        <StatTile
          label="Baki belum dibayar"
          value={formatMoney(data.unpaid)}
          hint={data.unpaid_orders ? `${data.unpaid_orders} pesanan (semua masa)` : 'Semua sudah dibayar'}
        />
        <StatTile
          label="Purata masa siap"
          value={data.average_days_to_ready === null ? '–' : `${data.average_days_to_ready} hari`}
          hint="Karpet: diterima hingga kering"
        />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatTile label="Belum dicuci" value={String(data.in_progress.received)} hint="Sekarang" />
        <StatTile label="Sedang kering" value={String(data.in_progress.washed)} hint="Sekarang" />
        <StatTile label="Siap, tunggu diambil" value={String(data.in_progress.ready)} hint="Sekarang" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Hasil diterima"
          subtitle={weekly ? 'Bayaran diterima setiap minggu (bermula Isnin)' : 'Bayaran diterima setiap hari'}
          chart={
            <>
              <ColumnChart
                valueLabel="Hasil diterima"
                formatValue={shortMoney}
                data={data.revenue_over_time.map((b) => ({
                  label: b.start,
                  value: Number(b.amount),
                  description: `${weekly ? 'Minggu ' : ''}${b.label}: ${formatMoney(b.amount)}`,
                }))}
              />
              <ColumnLabels labels={data.revenue_over_time.map((b) => b.label)} />
            </>
          }
          table={
            <DataTable
              columns={[weekly ? 'Minggu bermula' : 'Hari', 'Jumlah']}
              rows={data.revenue_over_time.map((b) => [b.label, formatMoney(b.amount)])}
            />
          }
        />

        <ChartCard
          title="Cara bayaran"
          subtitle="Bahagian hasil dalam tempoh ini"
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
          title="Servis paling popular"
          subtitle="Barang dalam pesanan tempoh ini (sofa dikira ikut tempat duduk)"
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
              <p className="text-sm text-ink-soft">Tiada pesanan dalam tempoh ini.</p>
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
          title="Hari sibuk"
          subtitle="Pesanan diterima mengikut hari"
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
