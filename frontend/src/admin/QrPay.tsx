import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { formatMoney } from './format'
import { CheckIcon } from './icons'

// Paying by the shop's DuitNow QR: the dashboard shows the QR full screen with the amount
// and the order number; the customer scans it with any bank or e-wallet app and types the
// amount (it's a static QR, accepted by every app). Nothing tells the system the money
// arrived, so a worker taps "Sudah terima" once it shows in the bank, which records it.

type Props = {
  qr: string // the text inside the shop's DuitNow QR
  amount: string // what's owed
  reference: number // the order number, for matching in the bank app
  payee: string // shown under the QR
  busy: boolean
  onReceived: () => Promise<void>
}

export function QrPayButton(props: Props) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-center gap-2 rounded-full bg-[#ed2e67] py-3 font-semibold text-white hover:bg-[#d4245a]"
      >
        <QrIcon /> Bayar dengan DuitNow QR
      </button>
      {open && <QrPayDialog {...props} onClose={() => setOpen(false)} />}
    </>
  )
}

function QrPayDialog({ qr, amount, reference, payee, busy, onReceived, onClose }: Props & { onClose: () => void }) {
  const [image, setImage] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    // Drawn from the code itself (not a photo), so it scans cleanly from a phone screen.
    QRCode.toDataURL(qr, { errorCorrectionLevel: 'M', margin: 2, width: 640, color: { dark: '#0f172a', light: '#ffffff' } })
      .then((url) => {
        if (current) setImage(url)
      })
      .catch(() => {
        if (current) setImage(null)
      })
    return () => {
      current = false
    }
  }, [qr])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/70 p-4 print:hidden" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Bayar dengan DuitNow QR"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-5 text-center shadow-2xl"
      >
        <p className="text-xs font-bold tracking-wider text-[#ed2e67] uppercase">DuitNow QR</p>
        {image ? (
          <img src={image} alt="Kod QR DuitNow kedai" className="mx-auto w-full max-w-72 rounded-lg ring-1 ring-slate-200" />
        ) : (
          <p className="py-24 text-sm text-ink-soft">Menyediakan QR…</p>
        )}
        <div>
          <p className="text-xs text-slate-500">Jumlah untuk dibayar</p>
          <p className="text-4xl font-black tracking-tight text-slate-900">{formatMoney(amount)}</p>
          <p className="mt-1 text-sm font-semibold text-slate-700">Rujukan: {reference}</p>
          <p className="text-xs text-slate-500">{payee}</p>
        </div>
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Imbas dengan app bank atau e-wallet, masukkan <strong>{formatMoney(amount)}</strong> dan rujukan{' '}
          <strong>{reference}</strong>.
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            await onReceived()
            onClose()
          }}
          className="flex w-full items-center justify-center gap-2 rounded-full bg-emerald-600 py-3 font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          <CheckIcon /> Sudah terima {formatMoney(amount)}
        </button>
        <p className="text-xs text-slate-500">Tekan hanya selepas wang masuk dalam akaun bank.</p>
        <button type="button" onClick={onClose} className="text-sm font-semibold text-slate-600 underline">
          Tutup
        </button>
      </div>
    </div>
  )
}

function QrIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true" className="size-4">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3" />
    </svg>
  )
}
