import { type ChargeRow, emptyCharge } from './chargeRows'
import { NumberField } from './ItemsEditor'

// Common reasons to pick from; anything else can be typed.
const REASONS = ['Ambil lebih 15km', 'Hantar lebih 15km', 'Bahan kimia khas']

/** Caj tambahan: a pickup over 15km, a special chemical for a kerja luar job. Each charge is
 * added to the total and printed on the bill with its reason. */
export function ChargesEditor({ rows, onChange }: { rows: ChargeRow[]; onChange: (rows: ChargeRow[]) => void }) {
  const update = (key: number, patch: Partial<ChargeRow>) =>
    onChange(rows.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold">Caj tambahan</p>
      {rows.map((row, index) => (
        <fieldset key={row.key} className="space-y-2 rounded-xl bg-amber-50 p-3 ring-1 ring-amber-200">
          <legend className="sr-only">{`Caj ${index + 1}`}</legend>
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">Caj {index + 1}</p>
            <button
              type="button"
              onClick={() => onChange(rows.filter((r) => r.key !== row.key))}
              className="text-sm text-danger underline"
            >
              Buang caj
            </button>
          </div>
          <NumberField label="Amaun (RM)" value={row.amount} onChange={(amount) => update(row.key, { amount })} />
          <label className="block space-y-1">
            <span className="text-sm font-semibold">Sebab</span>
            <input
              value={row.reason}
              list="charge-reasons"
              maxLength={200}
              placeholder="cth. Ambil lebih 15km"
              onChange={(e) => update(row.key, { reason: e.target.value })}
              className="w-full rounded-xl bg-white px-3 py-3"
            />
          </label>
        </fieldset>
      ))}
      <datalist id="charge-reasons">
        {REASONS.map((reason) => (
          <option key={reason} value={reason} />
        ))}
      </datalist>
      <button
        type="button"
        onClick={() => onChange([...rows, emptyCharge()])}
        className="w-full rounded-xl border-2 border-dashed border-amber-300 py-2.5 text-sm font-semibold hover:bg-amber-50"
      >
        + Tambah caj
      </button>
    </div>
  )
}
