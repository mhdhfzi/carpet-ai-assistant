// Small, dependency-free chart pieces in plain HTML/CSS. Single-series charts use one
// validated hue (--color-chart); text always uses text colours, never the data colour.
import { type ReactNode, useId, useState } from 'react'

export function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-line">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-soft">{hint}</p>}
    </div>
  )
}

/** A card with a title and a "Show as table" switch, so values never depend on the chart. */
export function ChartCard({
  title,
  subtitle,
  chart,
  table,
}: {
  title: string
  subtitle?: string
  chart: ReactNode
  table: ReactNode
}) {
  const [asTable, setAsTable] = useState(false)
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="rounded-2xl bg-white p-4 ring-1 ring-line">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id={headingId} className="font-semibold">
            {title}
          </h2>
          {subtitle && <p className="text-xs text-ink-soft">{subtitle}</p>}
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
      {asTable ? table : chart}
    </section>
  )
}

/** A share of a whole: the fill and its track are steps of the same hue. */
export function Meter({ label, value, max, detail }: { label: string; value: number; max: number; detail: string }) {
  const percent = max ? Math.round((value / max) * 100) : 0
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-semibold">{label}</span>
        <span className="text-ink-soft">{detail}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={detail}
        className="h-3 overflow-hidden rounded-full bg-chart-track"
      >
        <div className="h-full rounded-full bg-chart" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

type Datum = { label: string; value: number; description: string }

/** Vertical columns from one baseline: thin bars, rounded data-end, value on the cap. */
export function ColumnChart({
  data,
  valueLabel,
  formatValue = String,
}: {
  data: Datum[]
  valueLabel: string
  formatValue?: (value: number) => string
}) {
  const max = Math.max(1, ...data.map((d) => d.value))
  return (
    <div className="flex h-48 items-end gap-2 border-b border-line" role="list" aria-label={valueLabel}>
      {data.map((d) => (
        <div key={d.label} role="listitem" className="flex h-full flex-1 flex-col items-center justify-end">
          {/* The column is the hover/focus target; its tooltip repeats the value in words. */}
          <div
            tabIndex={0}
            aria-label={d.description}
            className="group relative flex w-full flex-1 flex-col items-center justify-end outline-none"
          >
            <span className="pointer-events-none absolute -top-8 z-10 hidden rounded-lg bg-ink px-2 py-1 text-xs whitespace-nowrap text-white group-hover:block group-focus:block">
              {d.description}
            </span>
            <span className="mb-1 text-xs font-semibold">{formatValue(d.value)}</span>
            <div
              className="w-full max-w-6 rounded-t-[4px] bg-chart transition-opacity group-hover:opacity-80 group-focus:ring-2 group-focus:ring-ink"
              style={{ height: `${(d.value / max) * 100}%`, minHeight: d.value ? 2 : 0 }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ColumnLabels({ labels }: { labels: string[] }) {
  return (
    <div className="mt-2 flex gap-2" aria-hidden="true">
      {labels.map((label) => (
        <span key={label} className="flex-1 text-center text-xs text-ink-soft">
          {label}
        </span>
      ))}
    </div>
  )
}

/** Horizontal bars, longest first, value at the tip. */
export function BarList({
  data,
  formatValue = String,
}: {
  data: (Datum & { sublabel?: string })[]
  formatValue?: (value: number) => string
}) {
  const max = Math.max(1, ...data.map((d) => d.value))
  return (
    <ul className="space-y-3">
      {data.map((d) => (
        <li key={`${d.sublabel}-${d.label}`} aria-label={d.description} className="space-y-1">
          <p className="text-sm">
            {d.label}
            {d.sublabel && <span className="text-ink-soft"> · {d.sublabel}</span>}
          </p>
          <div className="flex items-center gap-2">
            <div className="h-3 rounded-r-[4px] bg-chart" style={{ width: `${(d.value / max) * 85}%` }} />
            <span className="text-xs font-semibold">{formatValue(d.value)}</span>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function DataTable({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-ink-soft">
          {columns.map((column) => (
            <th key={column} className="border-b border-line pb-2 font-semibold">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="tabular-nums">
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td key={j} className="border-b border-line py-2">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
