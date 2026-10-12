import { useEffect, useRef, useState } from 'react'
import { useAuth } from './auth'
import { LOCATION_LABEL, STATUS_LABEL, formatDateTime, formatMoney, formatWhen, whatsAppUrl } from './format'
import type { Booking, Conversation } from './types'

export function BookingDetail({ booking, onClose }: { booking: Booking; onClose: () => void }) {
  const { request } = useAuth()
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [chatError, setChatError] = useState(false)
  const closeButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeButton.current?.focus()
  }, [])

  useEffect(() => {
    if (!booking.conversation_id) return
    let cancelled = false
    request<Conversation>(`/api/conversations/${booking.conversation_id}`)
      .then((data) => !cancelled && setConversation(data))
      .catch(() => !cancelled && setChatError(true))
    return () => {
      cancelled = true
    }
  }, [booking.conversation_id, request])

  const { customer } = booking
  return (
    <div className="fixed inset-0 z-10 flex justify-end bg-ink/30" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Booking ${booking.id} details`}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.key === 'Escape' && onClose()}
        className="h-full w-full max-w-lg space-y-6 overflow-y-auto bg-white p-6 shadow-lift"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-ink-soft">
              Booking #{booking.id} · {STATUS_LABEL[booking.status]}
            </p>
            <h2 className="font-display text-xl font-bold">{formatWhen(booking.scheduled_start, booking.scheduled_end)}</h2>
            <p className="text-sm text-ink-soft">{LOCATION_LABEL[booking.location]}</p>
          </div>
          <button ref={closeButton} type="button" onClick={onClose} className="rounded-full px-3 py-1.5 text-sm font-semibold ring-1 ring-line hover:bg-foam">
            Close
          </button>
        </div>

        <section className="space-y-1">
          <h3 className="font-semibold">Customer</h3>
          <p>{customer.name}</p>
          <p className="text-sm">
            <a className="underline" href={`tel:${customer.phone}`}>
              {customer.phone}
            </a>
            {' · '}
            <a className="underline" href={whatsAppUrl(customer.phone)} target="_blank" rel="noreferrer">
              WhatsApp
            </a>
          </p>
          {customer.address && <p className="text-sm text-ink-soft">{customer.address}</p>}
          {customer.area && !customer.address && <p className="text-sm text-ink-soft">{customer.area}</p>}
        </section>

        <section className="space-y-2">
          <h3 className="font-semibold">Services</h3>
          <ul className="divide-y divide-line rounded-2xl ring-1 ring-line">
            {booking.items.map((item) => (
              <li key={item.id} className="flex justify-between gap-3 p-3 text-sm">
                <span>
                  {item.service.name} × {Number(item.quantity)}
                </span>
                <span>{formatMoney(item.line_total, item.line_total_max)}</span>
              </li>
            ))}
            <li className="flex justify-between gap-3 p-3 font-semibold">
              <span>Estimated total</span>
              <span>{formatMoney(booking.estimated_price, booking.estimated_price_max)}</span>
            </li>
          </ul>
          {booking.notes && <p className="text-sm">Notes: {booking.notes}</p>}
        </section>

        <section className="space-y-3">
          <h3 className="font-semibold">Chat that led to this booking</h3>
          {!booking.conversation_id && <p className="text-sm text-ink-soft">Booked directly, not through the chat.</p>}
          {chatError && <p className="text-sm text-danger">Couldn't load the conversation.</p>}
          {booking.conversation_id && !conversation && !chatError && <p className="text-sm text-ink-soft">Loading chat…</p>}
          {conversation && (
            <ol className="space-y-3">
              <li className="text-xs text-ink-soft">
                {conversation.channel === 'whatsapp' ? 'WhatsApp' : 'Web chat'} · started {formatDateTime(conversation.created_at)}
              </li>
              {conversation.messages.map((message) => (
                <li key={message.id} className={message.role === 'customer' ? 'ml-8' : 'mr-8'}>
                  <p
                    className={`rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${
                      message.role === 'customer' ? 'bg-ink text-white' : 'bg-foam'
                    }`}
                  >
                    <span className="sr-only">{message.role === 'customer' ? 'Customer: ' : 'Assistant: '}</span>
                    {message.content}
                  </p>
                  {message.sources && message.sources.length > 0 && (
                    <p className="mt-1 text-xs text-ink-soft">
                      Sources: {message.sources.map((s) => `${s.title} › ${s.heading}`).join('; ')}
                    </p>
                  )}
                  {message.role === 'assistant' && message.grounded === false && (
                    <p className="mt-1 text-xs text-brand-ink">Not grounded in the knowledge base</p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
      </aside>
    </div>
  )
}
