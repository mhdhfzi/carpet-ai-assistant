import { FOLD_LABEL, formatMoney } from './format'
import { type AgentPrices, type ItemRow, emptyRow, fixedPrice, measurable, rowPrice } from './itemRows'
import type { Service } from './types'

type Props = {
  services: Service[]
  rows: ItemRow[]
  onChange: (rows: ItemRow[]) => void
  isOwner: boolean
  /** Editing an order: an item already on it is cancelled (it keeps its tag), not removed. */
  onCancelItem?: (row: ItemRow) => void
  /** An agent's order: carpets are priced by the owner, starting from the agent's last prices. */
  agent?: boolean
  prices?: AgentPrices | null
}

export function ItemsEditor({ services, rows, onChange, isOwner, onCancelItem, agent = false, prices = null }: Props) {
  const byId = new Map(services.map((s) => [s.id, s]))
  const carpets = services.filter((s) => s.pricing_unit === 'per_sqft')
  const others = services.filter((s) => s.pricing_unit !== 'per_sqft')
  // Buku Utama only offers shop services, so its "Lain-lain (kedai)" isn't a home job.
  const othersLabel = others.every((s) => s.on_site) ? 'Kerja luar (di rumah pelanggan)' : 'Lain-lain (di kedai)'
  const update = (key: number, patch: Partial<ItemRow>) =>
    onChange(rows.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  // A new type: an agent's price box starts from their last price for it.
  const choose = (row: ItemRow, serviceId: number | null) => {
    const last = agent && serviceId !== null ? prices?.get(serviceId) : undefined
    if (last) update(row.key, { serviceId, unitPrice: String(Number(last)), suggested: true })
    else update(row.key, { serviceId, ...(row.suggested ? { unitPrice: '', suggested: false } : {}) })
  }

  return (
    <div className="space-y-3">
      {rows.map((row, index) => {
        const service = row.serviceId === null ? undefined : byId.get(row.serviceId)
        const isCarpet = service?.pricing_unit === 'per_sqft'
        // "Lain-lain" at the shop: a size if it has one (shaggy), else a count (curtains).
        const optionalSize = measurable(service) && !isCarpet
        const sized = !!(row.length && row.width)
        const agentPrice = agent && !!service && fixedPrice(service) && !service.on_site
        const { units, total } = rowPrice(row, service, agent)
        const label = row.tag ? `Barang ${row.tag}` : `Barang ${index + 1}`
        return (
          <fieldset key={row.key} className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-line">
            <legend className="sr-only">{label}</legend>
            <div className="flex items-center justify-between gap-2">
              <p className="font-semibold">{label}</p>
              {row.id && onCancelItem ? (
                rows.some((r) => r.id && r.key !== row.key) && (
                  <button type="button" onClick={() => onCancelItem(row)} className="text-sm text-danger underline">
                    Batal barang
                  </button>
                )
              ) : (
                rows.length > 1 && (
                <button
                  type="button"
                  onClick={() => onChange(rows.filter((r) => r.key !== row.key))}
                  className="text-sm text-danger underline"
                >
                  Buang
                </button>
                )
              )}
            </div>
            <label className="block space-y-1">
              <span className="text-sm font-semibold">Jenis</span>
              <select
                value={row.serviceId ?? ''}
                onChange={(e) => choose(row, e.target.value ? Number(e.target.value) : null)}
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
                  <optgroup label={othersLabel}>
                    {others.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </label>

            {measurable(service) && (
              <div className="grid grid-cols-2 gap-3">
                <NumberField
                  label={optionalSize ? 'Panjang kaki (pilihan)' : 'Panjang (kaki)'}
                  value={row.length}
                  onChange={(v) => update(row.key, { length: v })}
                />
                <NumberField
                  label={optionalSize ? 'Lebar kaki (pilihan)' : 'Lebar (kaki)'}
                  value={row.width}
                  onChange={(v) => update(row.key, { width: v })}
                />
              </div>
            )}
            {optionalSize && !sized && (
              <p className="-mt-1 text-xs text-ink-soft">Ada saiz (cth. shaggy)? Isi panjang & lebar. Tiada saiz (toto, langsir)? Isi kuantiti.</p>
            )}
            {service && !isCarpet && !sized && (
              <NumberField label="Kuantiti" value={row.quantity} step="1" onChange={(v) => update(row.key, { quantity: v })} />
            )}

            {service?.needs_fold && (
              <div role="radiogroup" aria-label={`Gulung atau lipat ${label}`} className="space-y-1">
                <p className="text-sm font-semibold">
                  Cara pack <span className="font-normal text-ink-soft">(wajib)</span>
                </p>
                <div className="flex gap-2">
                  {(['rolled', 'folded'] as const).map((fold) => (
                    <button
                      key={fold}
                      type="button"
                      role="radio"
                      aria-checked={row.fold === fold}
                      onClick={() => update(row.key, { fold })}
                      className="flex-1 rounded-xl border border-purple-300 py-2.5 text-sm font-bold text-purple-800 aria-checked:border-purple-700 aria-checked:bg-purple-700 aria-checked:text-white"
                    >
                      {FOLD_LABEL[fold]}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {isOwner && service && (
              <div className="space-y-1">
                <NumberField
                  label={
                    agentPrice
                      ? `Harga ejen sekaki persegi (biasa RM${service.unit_price})`
                      : service.custom
                        ? sized
                          ? 'Harga sekaki persegi (RM)'
                          : 'Harga seunit (RM)'
                        : service.unit_price_max
                          ? `Harga seunit (RM${service.unit_price}–RM${service.unit_price_max})`
                          : `Harga seunit (biasa RM${service.unit_price})`
                  }
                  value={row.unitPrice}
                  onChange={(v) => update(row.key, { unitPrice: v, suggested: false })}
                />
                {row.suggested && <p className="text-xs text-amber-800">Harga terakhir ejen ini. Semak sebelum simpan.</p>}
              </div>
            )}

            <label className="block space-y-1">
              <span className="text-sm font-semibold">
                {service?.custom ? 'Kerja apa (wajib)' : 'Catatan (pilihan)'}
              </span>
              <input
                value={row.notes}
                onChange={(e) => update(row.key, { notes: e.target.value })}
                placeholder={service?.custom ? 'cth. Cuci langsir 3 helai' : 'cth. tompok kopi di tepi'}
                className="w-full rounded-xl bg-foam px-3 py-3"
              />
            </label>

            {service && (
              <p className="text-sm text-ink-soft" aria-live="polite">
                {(isCarpet || sized) && units > 0 && `${Math.round(units * 100) / 100} kaki persegi · `}
                {total === null
                  ? service.custom
                    ? 'Harga ditetapkan oleh pemilik'
                    : agentPrice
                    ? 'Harga ejen ditetapkan oleh pemilik'
                    : service.unit_price_max
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

/** Marks an agent's order (or an agent) in the books. */
export function AgentTag({ className = '' }: { className?: string }) {
  return <span className={`rounded bg-amber-100 px-1.5 py-0.5 text-xs font-bold text-amber-900 ${className}`}>Ejen</span>
}

/** Buku Utama: a normal customer or an agent (ejen), whose carpet prices the owner types. */
export function AgentChoice({ agent, onChange }: { agent: boolean; onChange: (agent: boolean) => void }) {
  return (
    <div role="radiogroup" aria-label="Jenis pelanggan" className="flex gap-2">
      {[
        { value: false, label: 'Pelanggan biasa' },
        { value: true, label: 'Ejen' },
      ].map((choice) => (
        <button
          key={choice.label}
          type="button"
          role="radio"
          aria-checked={agent === choice.value}
          onClick={() => onChange(choice.value)}
          className="flex-1 rounded-xl py-2.5 text-sm font-bold ring-1 ring-line aria-checked:bg-ink aria-checked:text-white aria-checked:ring-ink"
        >
          {choice.label}
        </button>
      ))}
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
      {/* Text with a number keypad: no up/down arrows, and scrolling the page can't change it. */}
      <input
        type="text"
        inputMode={step === '1' ? 'numeric' : 'decimal'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl bg-foam px-3 py-3"
      />
    </label>
  )
}
