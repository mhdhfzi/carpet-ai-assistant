// Whether a customer has had their receipt. The dashboard can't see inside WhatsApp (or the
// share menu, or the print dialog), so after a receipt is opened for sending it asks
// "Sudah hantar?" and records the answer, with who and when.

import { useState } from 'react'
import { errorMessage } from './api'
import { useAuth } from './auth'
import { formatDateTime } from './format'
import { CheckIcon } from './icons'
import type { Order, ReceiptChannel, ReceiptSend } from './types'

// The helpers and hook live with the components they serve.
// oxlint-disable-next-line react/only-export-components
export function lastSend(order: Order): ReceiptSend | undefined {
  return order.receipt_sends.at(-1)
}

/** Ask once a receipt has been opened for sending; record it on "Ya, sudah". The question
 * belongs to the order it was asked about, so switching to another customer drops it. */
// oxlint-disable-next-line react/only-export-components
export function useReceiptSent(order: Order | null, onRecorded: (order: Order) => void) {
  const { request } = useAuth()
  const [asking, setAsking] = useState<{ orderId: number; channel: ReceiptChannel } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const open = order !== null && asking?.orderId === order.id

  const ask = (channel: ReceiptChannel) => {
    if (order) setAsking({ orderId: order.id, channel })
    setError(null)
  }

  const confirm = async () => {
    if (!open || !asking) return
    setBusy(true)
    setError(null)
    try {
      onRecorded(
        await request<Order>(`/api/orders/${asking.orderId}/receipt-sent`, { method: 'POST', body: { channel: asking.channel } }),
      )
      setAsking(null)
    } catch (err) {
      setError(errorMessage(err, 'Tak dapat simpan. Cuba lagi.'))
    } finally {
      setBusy(false)
    }
  }

  const prompt = open && (
    <div role="group" aria-label="Sudah hantar resit?" className="space-y-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3">
      <p className="text-sm font-semibold text-emerald-900">Sudah hantar resit kepada {order.customer.name}?</p>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={confirm}
          className="flex items-center gap-1.5 rounded-full bg-emerald-600 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          <CheckIcon className="size-4" /> Ya, sudah
        </button>
        <button type="button" onClick={() => setAsking(null)} className="rounded-full bg-white px-4 py-2 text-sm font-semibold ring-1 ring-emerald-300">
          Belum
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  )
  return { ask, prompt }
}

/** "Resit dihantar Sat 24 Oct, 10:15 (Amir)", or that it hasn't been sent yet. */
export function ReceiptSentLine({ order }: { order: Order }) {
  const last = lastSend(order)
  if (order.status === 'cancelled') return null
  return last ? (
    <p className="flex items-center gap-1 text-xs font-semibold text-emerald-800">
      <CheckIcon className="size-3.5" /> Resit dihantar {formatDateTime(last.sent_at)}
      {last.sent_by && ` (${last.sent_by})`}
    </p>
  ) : (
    <p className="text-xs text-slate-500">Resit belum dihantar</p>
  )
}
