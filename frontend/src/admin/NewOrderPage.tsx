import { type FormEvent, useEffect, useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import { ItemsEditor, NumberField } from './ItemsEditor'
import { type ItemRow, emptyRow, rowPrice, rowsToInput } from './itemRows'
import { PAYMENT_LABEL, RETURN_LABEL, formatMoney, fromVisitInput, todayInMalaysia } from './format'
import type { CustomerSummary, Order, OrderKind, PaymentMethod, ReturnMethod } from './types'
import { href } from './useHashRoute'
import { useServices } from './useServices'

/** A new order in one book: carpets (Buku Utama) or kerja luar. Each offers only its own
 * services, so the two are never mixed in one order (the server refuses that too). */
export function NewOrderPage({ kind }: { kind: OrderKind }) {
  const luar = kind === 'on_site'
  const { request, state } = useAuth()
  const isOwner = state.status === 'signed-in' && state.owner.role === 'owner'
  const services = useServices()

  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [area, setArea] = useState('')
  const [address, setAddress] = useState('')
  const [known, setKnown] = useState<CustomerSummary | null>(null)
  const [receivedOn, setReceivedOn] = useState(todayInMalaysia())
  const [visitAt, setVisitAt] = useState('')
  const [rows, setRows] = useState<ItemRow[]>(() => [emptyRow()])
  const [deposit, setDeposit] = useState('')
  const [depositMethod, setDepositMethod] = useState<PaymentMethod>('cash')
  const [discount, setDiscount] = useState('')
  const [returnMethod, setReturnMethod] = useState<ReturnMethod | ''>('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // A returning customer: once a phone number is typed, fill in what we know about them.
  useEffect(() => {
    const digits = phone.replace(/\D/g, '')
    if (digits.length < 9) return
    let current = true
    const timer = setTimeout(() => {
      request<CustomerSummary[]>(`/api/customers?q=${digits}`)
        .then((found) => {
          if (!current) return
          const match = found.find((c) => c.phone.replace(/\D/g, '').endsWith(digits.replace(/^0/, ''))) ?? null
          setKnown(match)
          if (match) {
            setName((v) => v || match.name)
            setArea((v) => v || (match.area ?? ''))
            setAddress((v) => v || (match.address ?? ''))
          }
        })
        .catch(() => {
          /* the lookup is a convenience; the form works without it */
        })
    }, 300)
    return () => {
      current = false
      clearTimeout(timer)
    }
  }, [phone, request])

  const byId = new Map((services ?? []).map((s) => [s.id, s]))
  const lines = rows.map((row) => rowPrice(row, row.serviceId === null ? undefined : byId.get(row.serviceId)))
  const pending = lines.some((l) => l.total === null)
  // Sofa, mattress and car seat jobs are done at the customer's home: when is the visit?
  const offered = (services ?? []).filter((s) => s.on_site === luar)
  const subtotal = lines.reduce((sum, l) => sum + (l.total ?? 0), 0)
  const total = Math.max(subtotal - Number(discount || 0), 0)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const order = await request<Order>('/api/orders', {
        method: 'POST',
        body: {
          customer: { name: name.trim(), phone, area: area.trim() || null, address: address.trim() || null },
          received_on: receivedOn,
          ...(luar && visitAt ? { visit_at: fromVisitInput(visitAt) } : {}),
          items: rowsToInput(rows),
          deposit: deposit || '0',
          deposit_method: depositMethod,
          ...(isOwner && discount ? { discount } : {}),
          return_method: returnMethod || null,
          notes: notes.trim() || null,
        },
      })
      window.location.hash = href({ page: 'order', id: order.id })
    } catch (err) {
      setError(errorMessage(err, 'Tak dapat simpan pesanan. Semak dan cuba lagi.'))
      setBusy(false)
    }
  }

  if (services === null) return <p className="text-ink-soft">Memuatkan…</p>

  return (
    <form onSubmit={submit} className="mx-auto max-w-xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-bold">{luar ? 'Kerja luar baru' : 'Pesanan karpet baru'}</h1>
        <a href={luar ? href({ page: 'visits', book: true }) : href({ page: 'orders' })} className="text-sm underline">
          Batal
        </a>
      </div>

      <section className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-line">
        <h2 className="font-semibold">Pelanggan</h2>
        <TextField label="No. telefon" value={phone} onChange={setPhone} type="tel" required placeholder="012-345 6789" />
        {known && (
          <p role="status" className="rounded-xl bg-brand/20 px-3 py-2 text-sm">
            Pelanggan lama: {known.name} ({known.orders} pesanan)
          </p>
        )}
        <TextField label="Nama" value={name} onChange={setName} required />
        <TextField label="Kawasan" value={area} onChange={setArea} placeholder="cth. Seremban 2" />
        <TextField label="Alamat" value={address} onChange={setAddress} />
        <TextField label="Tarikh diterima" value={receivedOn} onChange={setReceivedOn} type="date" required />
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">Barang</h2>
        <ItemsEditor services={offered} rows={rows} onChange={setRows} isOwner={isOwner} />
      </section>

      {luar && (
        <section className="space-y-2 rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-200">
          <h2 className="font-semibold">Lawatan ke rumah pelanggan</h2>
          <TextField label="Tarikh & masa lawatan (pilihan)" value={visitAt} onChange={setVisitAt} type="datetime-local" />
          <p className="text-xs text-ink-soft">Boleh diisi atau ditukar kemudian. Kerja ini akan muncul di Jadual Kerja Luar.</p>
        </section>
      )}

      <section className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-line">
        <h2 className="font-semibold">Bayaran & lain-lain</h2>
        {/* Staff may take the deposit when the order is made; later payments are the owner's. */}
        <NumberField label="Deposit (RM)" value={deposit} onChange={setDeposit} />
        {Number(deposit) > 0 && (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Cara bayaran deposit">
            {(Object.keys(PAYMENT_LABEL) as PaymentMethod[]).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={depositMethod === m}
                onClick={() => setDepositMethod(m)}
                className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-line aria-pressed:bg-ink aria-pressed:text-white"
              >
                {PAYMENT_LABEL[m]}
              </button>
            ))}
          </div>
        )}
        {isOwner && <NumberField label="Diskaun (RM)" value={discount} onChange={setDiscount} />}
        {!luar && (
          <fieldset className="space-y-1">
            <legend className="text-sm font-semibold">Cara pulang</legend>
            {(Object.keys(RETURN_LABEL) as ReturnMethod[]).map((method) => (
              <label key={method} className="flex items-center gap-2 py-1">
                <input
                  type="radio"
                  name="return"
                  checked={returnMethod === method}
                  onChange={() => setReturnMethod(method)}
                  className="size-5"
                />
                {RETURN_LABEL[method]}
              </label>
            ))}
          </fieldset>
        )}
        <label className="block space-y-1">
          <span className="text-sm font-semibold">Catatan</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="w-full rounded-xl bg-foam px-3 py-3" />
        </label>
      </section>

      <div className="sticky bottom-0 space-y-3 border-t border-line bg-mist py-4">
        <p className="flex justify-between text-lg font-semibold">
          <span>Jumlah{pending && ' (belum lengkap)'}</span>
          <span>{formatMoney(String(total))}</span>
        </p>
        {deposit && <p className="flex justify-between text-sm text-ink-soft"><span>Baki</span><span>{formatMoney(String(total - Number(deposit)))}</span></p>}
        {error && (
          <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-danger ring-1 ring-red-200">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className="w-full rounded-full bg-brand py-4 text-lg font-semibold hover:bg-brand-hover disabled:opacity-50">
          {busy ? 'Menyimpan…' : 'Simpan pesanan'}
        </button>
      </div>
    </form>
  )
}

export function TextField({
  label,
  value,
  onChange,
  type = 'text',
  required = false,
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  required?: boolean
  placeholder?: string
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-semibold">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl bg-foam px-3 py-3"
      />
    </label>
  )
}
