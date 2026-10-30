// Small, dependency-free chart pieces in plain HTML/CSS. Single-series charts use one
// validated hue (--color-chart); text always uses text colours, never the data colour.
import { type ReactNode, useId, useState } from 'react'

export function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0 rounded-2xl bg-white p-4 ring-1 ring-line">
      <p className="text-sm text-ink-soft">{label}</p>
      {/* A bit smaller on a phone, and it wraps rather than run into the next tile. */}
      <p className="mt-1 text-2xl font-semibold break-words sm:text-3xl">{value}</p>
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

type Point = { label: string; value: number }

/** A round top for the y axis: 1, 2 or 5 times a power of ten (RM3,956 -> RM5,000). */
function niceMax(value: number): number {
  if (value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  return ([1, 2, 5, 10].find((step) => step * power >= value) ?? 10) * power
}

const WIDTH = 600
const HEIGHT = 200

/**
 * A line over time with a soft fill, and a thin grey line behind it to compare (last year).
 * Each slot is a hover/focus target that shows its numbers; `describe` says them in words.
 */
export function TrendChart({
  label,
  slots,
  current,
  compare,
  currentName,
  compareName,
  highlight = null,
  formatValue = String,
  describe,
}: {
  label: string
  slots: string[] // the x axis, e.g. Jan..Dis
  current: Point[] // up to slots.length points, from the first slot
  compare: Point[]
  currentName: string
  compareName: string
  highlight?: number | null // a slot to mark, e.g. the month shown in detail
  formatValue?: (value: number) => string
  describe: (slot: number) => string
}) {
  const [active, setActive] = useState<number | null>(null)
  const top = niceMax(Math.max(...current.map((p) => p.value), ...compare.map((p) => p.value)))
  const x = (i: number) => ((i + 0.5) / slots.length) * WIDTH
  const y = (value: number) => HEIGHT - (value / top) * HEIGHT
  const path = (points: Point[]) => points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.value)}`).join(' ')
  const area = current.length
    ? `${path(current)} L${x(current.length - 1)},${HEIGHT} L${x(0)},${HEIGHT} Z`
    : ''
  const hasCompare = compare.some((p) => p.value > 0)
  const shown = active

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4 text-xs text-ink-soft" aria-hidden="true">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded bg-chart" /> {currentName}
        </span>
        {hasCompare && (
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded bg-slate-300" /> {compareName}
          </span>
        )}
      </div>
      <div className="flex gap-2">
        {/* The y axis: three round values, so the lines can be read without hovering. */}
        <div className="relative w-12 shrink-0 text-right text-[11px] text-ink-soft" aria-hidden="true">
          {[1, 0.5, 0].map((f) => (
            <span key={f} className="absolute right-0 -translate-y-1/2" style={{ top: `${(1 - f) * 100}%` }}>
              {formatValue(top * f)}
            </span>
          ))}
        </div>
        <div className="relative h-48 min-w-0 flex-1">
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible" aria-hidden="true">
            {[0, 0.5, 1].map((f) => (
              <line key={f} x1={0} x2={WIDTH} y1={HEIGHT * f} y2={HEIGHT * f} className="stroke-line" strokeWidth={1} vectorEffect="non-scaling-stroke" />
            ))}
            {hasCompare && (
              <path d={path(compare)} fill="none" className="stroke-slate-300" strokeWidth={2} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            )}
            {area && <path d={area} className="fill-chart" fillOpacity={0.1} />}
            <path d={path(current)} fill="none" className="stroke-chart" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            {shown !== null && (
              <line x1={x(shown)} x2={x(shown)} y1={0} y2={HEIGHT} className="stroke-slate-400" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
            )}
          </svg>
          {/* Dots in HTML so they stay round however the chart is stretched. */}
          {current.map((p, i) => (
            <span
              key={p.label}
              aria-hidden="true"
              className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full bg-chart ring-2 ring-white ${
                i === highlight || i === shown ? 'size-3' : 'size-2'
              }`}
              style={{ left: `${(x(i) / WIDTH) * 100}%`, top: `${(y(p.value) / HEIGHT) * 100}%` }}
            />
          ))}
          {/* One hover/focus target per slot, wider than the line. */}
          <div role="list" aria-label={label} className="absolute inset-0 flex" onMouseLeave={() => setActive(null)}>
            {slots.map((slot, i) => (
              <div
                key={slot}
                role="listitem"
                tabIndex={0}
                aria-label={describe(i)}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                className="h-full flex-1 outline-none focus-visible:bg-slate-100/60"
              />
            ))}
          </div>
          {shown !== null && (
            <p
              className="pointer-events-none absolute top-0 z-10 rounded-lg bg-ink px-2.5 py-1.5 text-xs whitespace-nowrap text-white shadow"
              style={{
                left: `${(x(shown) / WIDTH) * 100}%`,
                transform: `translateX(${shown < 2 ? '-10%' : shown > slots.length - 3 ? '-90%' : '-50%'})`,
              }}
            >
              {describe(shown)}
            </p>
          )}
        </div>
      </div>
      <div className="mt-2 ml-14 flex" aria-hidden="true">
        {slots.map((slot) => (
          // Every other label on a phone: twelve don't fit side by side.
          <span key={slot} className="flex-1 text-center text-[11px] text-ink-soft max-sm:even:invisible">
            {slot}
          </span>
        ))}
      </div>
    </div>
  )
}

/** A plain table. Words never wrap or run into each other: on a narrow phone the table
 * slides sideways instead of squeezing its columns. */
export function DataTable({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-ink-soft">
            {columns.map((column) => (
              <th key={column} className="border-b border-line pr-5 pb-2 font-semibold whitespace-nowrap last:pr-0">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="border-b border-line py-2 pr-5 whitespace-nowrap last:pr-0">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
