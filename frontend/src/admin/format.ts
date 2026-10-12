import type { BookingLocation, BookingStatus } from './types'

// The business runs on Malaysia time, whatever timezone the owner's device is set to.
const TIME_ZONE = 'Asia/Kuala_Lumpur'

const dateTimeFormat = new Intl.DateTimeFormat('en-MY', {
  timeZone: TIME_ZONE,
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
})
const timeFormat = new Intl.DateTimeFormat('en-MY', { timeZone: TIME_ZONE, hour: 'numeric', minute: '2-digit' })

export function formatWhen(start: string, end: string): string {
  return `${dateTimeFormat.format(new Date(start))} – ${timeFormat.format(new Date(end))}`
}

export function formatDateTime(value: string): string {
  return dateTimeFormat.format(new Date(value))
}

/** "RM180.00", or "RM250.00 – RM400.00" for a price range. */
export function formatMoney(low: string, high: string = low): string {
  const rm = (value: string) => `RM${Number(value).toFixed(2)}`
  return Number(low) === Number(high) ? rm(low) : `${rm(low)} – ${rm(high)}`
}

/** Today's date (YYYY-MM-DD) in Malaysia, e.g. to filter upcoming bookings. */
export function todayInMalaysia(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE }).format(now)
}

export const STATUS_LABEL: Record<BookingStatus, string> = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  done: 'Done',
  cancelled: 'Cancelled',
}

export const STATUS_STYLE: Record<BookingStatus, string> = {
  pending: 'bg-brand/25 text-ink',
  confirmed: 'bg-emerald-100 text-emerald-900',
  done: 'bg-foam text-ink-soft',
  cancelled: 'bg-red-50 text-danger',
}

export const ACTION_LABEL: Record<BookingStatus, string> = {
  pending: 'Mark pending',
  confirmed: 'Confirm',
  done: 'Mark done',
  cancelled: 'Cancel booking',
}

export const LOCATION_LABEL: Record<BookingLocation, string> = {
  customer_home: 'Home visit',
  shop: 'At shop',
}

/** wa.me wants the number without "+" or spaces. */
export function whatsAppUrl(phone: string): string {
  return `https://wa.me/${phone.replace(/\D/g, '')}`
}
