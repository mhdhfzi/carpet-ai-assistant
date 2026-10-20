import { useState } from 'react'
import { fromVisitInput, toVisitInput } from './format'
import type { Order } from './types'

/** The date and time of the house visit, typed in Malaysia time and saved when changed. */
export function VisitEditor({
  order,
  busy,
  onSave,
  compact = false,
}: {
  order: Order
  busy: boolean
  onSave: (visitAt: string | null) => Promise<void>
  compact?: boolean
}) {
  const saved = toVisitInput(order.visit_at)
  const [value, setValue] = useState(saved)
  return (
    <div className={`flex flex-wrap items-end gap-2 ${compact ? 'text-xs' : 'text-sm'}`}>
      <label className="space-y-1">
        <span className="block font-semibold text-slate-600">{compact ? 'Tukar masa lawatan' : 'Tarikh & masa lawatan'}</span>
        <input
          type="datetime-local"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="rounded-lg border border-slate-300 px-2.5 py-1.5"
        />
      </label>
      {value !== saved && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onSave(fromVisitInput(value))}
          className="rounded-lg bg-slate-900 px-3 py-2 font-semibold text-white disabled:opacity-50"
        >
          Simpan masa
        </button>
      )}
    </div>
  )
}
