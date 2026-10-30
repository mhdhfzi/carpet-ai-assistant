// Small, dependency-free chart pieces in plain HTML/CSS. Single-series charts use one
// validated hue (--color-chart); text always uses text colours, never the data colour.
import { type ReactNode, useId, useState } from 'react'

export function StatTile({
  label,
  value,
  hint,
  change,
}: {
  label: string
  value: string
  hint?: string
  change?: ReactNode
}) {
  return (
    <div className="min-w-0 rounded-2xl bg-white p-4 ring-1 ring-line">
      <p className="text-sm text-ink-soft">{label}</p>
      {/* A bit smaller on a phone, and it wraps rather than run into the next tile. */}
      <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
        <span className="text-2xl font-semibold break-words sm:text-3xl">{value}</span>
        {change}
      </p>
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

/** A plain table. Words never wrap or run into each other: on a narrow phone the table
 * slides sideways instead of squeezing its columns. */
export function DataTable({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
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

/** The change from the period before, as a whole percentage: "▲ 12%" (better) or "▼ 8%"
 * (worse). Nothing when there's nothing to compare with: a "+100%" against an empty month
 * says nothing. */
export function Change({ now, before, versus }: { now: number; before: number | undefined; versus: string }) {
  if (!before) return null
  const percent = Math.round(((now - before) / before) * 100)
  const [mark, colour] = percent > 0 ? ['▲', 'text-emerald-700'] : percent < 0 ? ['▼', 'text-danger'] : ['=', 'text-ink-soft']
  return (
    <span className={`text-xs font-bold whitespace-nowrap ${colour}`}>
      {mark} {Math.abs(percent)}%<span className="sr-only"> berbanding {versus}</span>
    </span>
  )
}

export type LineSeries = { name: string; colour: string; values: number[] }

const WIDTH = 640
const HEIGHT = 200
const PAD = 8 // room for the markers at the top and bottom

/** Lines over time on one axis, from zero. Hovering (or tabbing to) a point shows a guide line
 * and `tooltip(index)`; with more than one line, a legend names them. */
export function LineChart({
  series,
  labels,
  valueLabel,
  formatValue = String,
  tooltip,
}: {
  series: LineSeries[]
  labels: string[]
  valueLabel: string
  formatValue?: (value: number) => string
  tooltip: (index: number) => ReactNode
}) {
  const [active, setActive] = useState<number | null>(null)
  const max = Math.max(1, ...series.flatMap((s) => s.values))
  const n = labels.length
  // Each month in the middle of its own slot, so it sits right above its label.
  const x = (i: number) => ((i + 0.5) * WIDTH) / n
  const y = (v: number) => PAD + (1 - v / max) * (HEIGHT - 2 * PAD)
  const left = (i: number) => `${(x(i) / WIDTH) * 100}%`
  return (
    <div className="space-y-2">
      {series.length > 1 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Petunjuk">
          {series.map((s) => (
            <li key={s.name} className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-4 rounded" style={{ background: s.colour }} />
              {s.name}
            </li>
          ))}
        </ul>
      )}
      {/* The scale's top, above its dashed line; the solid line is zero. */}
      <p className="text-[10px] text-ink-soft tabular-nums" aria-hidden="true">
        {formatValue(max)}
      </p>
      <div>
        <div className="relative" onMouseLeave={() => setActive(null)}>
          {/* Stretched to a fixed height whatever the width; the lines keep their 2px and the
              dots, drawn on top in HTML, stay round. */}
          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            preserveAspectRatio="none"
            className="block h-44 w-full overflow-visible"
            role="img"
            aria-label={valueLabel}
          >
            <line x1={0} x2={WIDTH} y1={y(0)} y2={y(0)} className="stroke-line" strokeWidth={1} vectorEffect="non-scaling-stroke" />
            <line x1={0} x2={WIDTH} y1={y(max)} y2={y(max)} className="stroke-line" strokeWidth={1} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
            {active !== null && (
              <line x1={x(active)} x2={x(active)} y1={0} y2={HEIGHT} className="stroke-ink-soft" strokeWidth={1} vectorEffect="non-scaling-stroke" />
            )}
            {series.map((s) => (
              <g key={s.name}>
                <polyline
                  points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')}
                  fill="none"
                  stroke={s.colour}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                />
              </g>
            ))}
          </svg>
          {series.map((s) =>
            s.values.map((v, i) => (
              <span
                key={`${s.name}-${i}`}
                aria-hidden="true"
                className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-white ${active === i ? 'size-3' : 'size-2'}`}
                style={{ left: left(i), top: `${(y(v) / HEIGHT) * 100}%`, background: s.colour }}
              />
            )),
          )}
          {/* One wide target per month: easier to hit than a dot, by mouse, finger or keyboard. */}
          <div className="absolute inset-0 flex">
            {labels.map((label, i) => (
              <button
                key={label}
                type="button"
                aria-label={label}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                onClick={() => setActive(i)}
                className="h-full flex-1 cursor-default outline-none focus-visible:bg-ink/5"
              />
            ))}
          </div>
          {active !== null && (
            <div
              role="status"
              className="pointer-events-none absolute top-0 z-10 rounded-lg bg-ink px-2.5 py-1.5 text-xs whitespace-nowrap text-white shadow-lift"
              style={{
                left: left(active),
                transform: `translateX(${active > n / 2 ? 'calc(-100% - 8px)' : '8px'})`,
              }}
            >
              {tooltip(active)}
            </div>
          )}
        </div>
      </div>
      <div className="flex text-[10px] text-ink-soft" aria-hidden="true">
        {labels.map((label) => (
          <span key={label} className="flex-1 text-center">
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}
