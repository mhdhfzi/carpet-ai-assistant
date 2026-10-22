import { formatMoney } from './format'
import { type ItemRow, emptyRow, rowPrice } from './itemRows'
import type { Service } from './types'

type Props = {
  services: Service[]
  rows: ItemRow[]
  onChange: (rows: ItemRow[]) => void
  isOwner: boolean
}

export function ItemsEditor({ services, rows, onChange, isOwner }: Props) {
  const byId = new Map(services.map((s) => [s.id, s]))
  const carpets = services.filter((s) => s.pricing_unit === 'per_sqft')
  const others = services.filter((s) => s.pricing_unit !== 'per_sqft')
  const update = (key: number, patch: Partial<ItemRow>) =>
    onChange(rows.map((row) => (row.key === key ? { ...row, ...patch } : row)))

  return (
    <div className="space-y-3">
      {rows.map((row, index) => {
        const service = row.serviceId === null ? undefined : byId.get(row.serviceId)
        const isCarpet = service?.pricing_unit === 'per_sqft'
        const { units, total } = rowPrice(row, service)
        const label = `Barang ${index + 1}`
        return (
          <fieldset key={row.key} className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-line">
            <legend className="sr-only">{label}</legend>
            <div className="flex items-center justify-between gap-2">
              <p className="font-semibold">{label}</p>
              {rows.length > 1 && (
                <button
                  type="button"
                  onClick={() => onChange(rows.filter((r) => r.key !== row.key))}
                  className="text-sm text-danger underline"
                >
                  Buang
                </button>
              )}
            </div>
            <label className="block space-y-1">
              <span className="text-sm font-semibold">Jenis</span>
              <select
                value={row.serviceId ?? ''}
                onChange={(e) => update(row.key, { serviceId: e.target.value ? Number(e.target.value) : null })}
                className="w-full rounded-xl bg-foam px-3 py-3"
              >
                <option value="">Pilih jenis…</option>
                {carpets.length > 0 && (
                  <optgroup label="Karpet (ikut kaki persegi)">
                    {carpets.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </optgroup>
                )}
                {others.length > 0 && (
                  <optgroup label="Kerja luar (di rumah pelanggan)">
                    {others.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </label>

            {isCarpet ? (
              <div className="grid grid-cols-2 gap-3">
                <NumberField label="Panjang (kaki)" value={row.length} onChange={(v) => update(row.key, { length: v })} />
                <NumberField label="Lebar (kaki)" value={row.width} onChange={(v) => update(row.key, { width: v })} />
              </div>
            ) : (
              service && (
                <NumberField
                  label="Kuantiti"
                  value={row.quantity}
                  step="1"
                  onChange={(v) => update(row.key, { quantity: v })}
                />
              )
            )}

            {isOwner && service && (
              <NumberField
                label={
                  service.unit_price_max
                    ? `Harga seunit (RM${service.unit_price}–RM${service.unit_price_max})`
                    : `Harga seunit (biasa RM${service.unit_price})`
                }
                value={row.unitPrice}
                onChange={(v) => update(row.key, { unitPrice: v })}
              />
            )}

            <label className="block space-y-1">
              <span className="text-sm font-semibold">Catatan (pilihan)</span>
              <input
                value={row.notes}
                onChange={(e) => update(row.key, { notes: e.target.value })}
                placeholder="cth. tompok kopi di tepi"
                className="w-full rounded-xl bg-foam px-3 py-3"
              />
            </label>

            {service && (
              <p className="text-sm text-ink-soft" aria-live="polite">
                {isCarpet && units > 0 && `${Math.round(units * 100) / 100} kaki persegi · `}
                {total === null
                  ? service.unit_price_max
                    ? 'Harga ditetapkan oleh pemilik selepas diperiksa'
                    : isCarpet
                      ? 'Saiz boleh diisi semasa cuci; harga dikira selepas itu'
                      : 'Masukkan kuantiti'
                  : formatMoney(String(total))}
              </p>
            )}
          </fieldset>
        )
      })}
      <button
        type="button"
        onClick={() => onChange([...rows, emptyRow()])}
        className="w-full rounded-2xl border-2 border-dashed border-line py-3 font-semibold hover:bg-white"
      >
        + Tambah barang
      </button>
    </div>
  )
}

export function NumberField({
  label,
  value,
  onChange,
  step = '0.01',
}: {
  label: string
  value: string
  onChange: (value: string) => void
  step?: string
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-semibold">{label}</span>
      <input
        type="number"
        inputMode="decimal"
        min="0"
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl bg-foam px-3 py-3"
      />
    </label>
  )
}
