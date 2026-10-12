import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { BookingDetail } from './BookingDetail'
import { ACTION_LABEL, LOCATION_LABEL, STATUS_LABEL, STATUS_STYLE, formatMoney, formatWhen, todayInMalaysia } from './format'
import { type Booking, type BookingStatus, NEXT_STATUSES } from './types'

type Range = 'upcoming' | 'past' | 'all'

const RANGES: { value: Range; label: string }[] = [
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'past', label: 'Past' },
  { value: 'all', label: 'All' },
]

export function BookingsPage() {
  const { request } = useAuth()
  const [range, setRange] = useState<Range>('upcoming')
  const [status, setStatus] = useState<BookingStatus | ''>('')
  const [bookings, setBookings] = useState<Booking[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Booking | null>(null)

  useEffect(() => {
    const params = new URLSearchParams({ limit: '100' })
    // Malaysia midnight today, so "upcoming" means from today onwards in the shop's time.
    const today = `${todayInMalaysia()}T00:00:00+08:00`
    if (range === 'upcoming') params.set('start_from', today)
    if (range === 'past') params.set('start_to', today)
    if (status) params.set('status', status)

    // Ignore a response that arrives after the filters changed again (out-of-order replies).
    let current = true
    request<Booking[]>(`/api/bookings?${params}`)
      .then((rows) => {
        if (!current) return
        // The API returns oldest first; past bookings read better newest first.
        setBookings(range === 'past' ? [...rows].reverse() : rows)
        setError(null)
      })
      .catch(() => current && setError("Couldn't load bookings. Please try again."))
    return () => {
      current = false
    }
  }, [range, status, request])
  const updated = (booking: Booking) => {
    setBookings((rows) => rows?.map((row) => (row.id === booking.id ? booking : row)) ?? null)
    setSelected((current) => (current?.id === booking.id ? booking : current))
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-2xl font-bold">Bookings</h1>
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Date range" className="flex rounded-full bg-white p-1 ring-1 ring-line">
            {RANGES.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={range === option.value}
                onClick={() => setRange(option.value)}
                className="rounded-full px-3 py-1.5 text-sm font-semibold text-ink-soft aria-pressed:bg-ink aria-pressed:text-white"
              >
                {option.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span className="font-semibold">Status</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as BookingStatus | '')}
              className="rounded-full bg-white px-3 py-2 ring-1 ring-line"
            >
              <option value="">All</option>
              {(Object.keys(STATUS_LABEL) as BookingStatus[]).map((value) => (
                <option key={value} value={value}>
                  {STATUS_LABEL[value]}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-2xl bg-red-50 p-4 text-danger ring-1 ring-red-200">
          {error}
        </p>
      )}
      {bookings === null && !error && <p className="text-ink-soft">Loading bookings…</p>}
      {bookings?.length === 0 && <p className="rounded-2xl bg-white p-6 text-ink-soft ring-1 ring-line">No bookings here.</p>}

      <ul className="space-y-3">
        {bookings?.map((booking) => (
          <BookingCard key={booking.id} booking={booking} onUpdated={updated} onOpen={() => setSelected(booking)} />
        ))}
      </ul>

      {selected && <BookingDetail booking={selected} onClose={() => setSelected(null)} />}
    </section>
  )
}

function BookingCard({
  booking,
  onUpdated,
  onOpen,
}: {
  booking: Booking
  onUpdated: (booking: Booking) => void
  onOpen: () => void
}) {
  const { request } = useAuth()
  const [busy, setBusy] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const change = async (status: BookingStatus) => {
    if (status === 'cancelled' && !confirmCancel) {
      setConfirmCancel(true) // cancelling can't be undone: ask once more
      return
    }
    setBusy(true)
    setError(null)
    try {
      onUpdated(await request<Booking>(`/api/bookings/${booking.id}`, { method: 'PATCH', body: { status } }))
      setConfirmCancel(false)
    } catch {
      setError("Couldn't update this booking.")
    } finally {
      setBusy(false)
    }
  }

  const services = booking.items.map((item) => `${item.service.name} × ${Number(item.quantity)}`).join(', ')

  return (
    <li className="rounded-2xl bg-white p-4 ring-1 ring-line" aria-label={`Booking ${booking.id}, ${booking.customer.name}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="font-semibold">{formatWhen(booking.scheduled_start, booking.scheduled_end)}</p>
          <p>
            {booking.customer.name}
            {booking.customer.area && <span className="text-ink-soft"> · {booking.customer.area}</span>}
          </p>
          <p className="text-sm text-ink-soft">{services}</p>
        </div>
        <div className="flex flex-col items-end gap-2 text-right">
          <span className={`rounded-full px-3 py-1 text-xs font-bold ${STATUS_STYLE[booking.status]}`}>
            {STATUS_LABEL[booking.status]}
          </span>
          <p className="font-semibold">{formatMoney(booking.estimated_price, booking.estimated_price_max)}</p>
          <p className="text-xs text-ink-soft">{LOCATION_LABEL[booking.location]}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
        <button type="button" onClick={onOpen} className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-line hover:bg-foam">
          View details
        </button>
        {NEXT_STATUSES[booking.status].map((next) => (
          <button
            key={next}
            type="button"
            disabled={busy}
            onClick={() => change(next)}
            className={
              next === 'cancelled'
                ? 'rounded-full px-4 py-2 text-sm font-semibold text-danger ring-1 ring-red-200 hover:bg-red-50 disabled:opacity-50'
                : 'rounded-full bg-brand px-4 py-2 text-sm font-semibold hover:bg-brand-hover disabled:opacity-50'
            }
          >
            {next === 'cancelled' && confirmCancel ? 'Yes, cancel it' : ACTION_LABEL[next]}
          </button>
        ))}
        {confirmCancel && (
          <button type="button" onClick={() => setConfirmCancel(false)} className="text-sm text-ink-soft underline">
            Keep booking
          </button>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </li>
  )
}
