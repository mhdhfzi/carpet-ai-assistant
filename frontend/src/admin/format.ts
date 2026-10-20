import type { BookingLocation, BookingStatus, ItemFold, ItemStatus, OrderStatus, PaymentMethod, ReturnMethod } from './types'

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

/** wa.me wants the number without "+" or spaces; `text` pre-fills the message. */
export function whatsAppUrl(phone: string, text?: string): string {
  const url = `https://wa.me/${phone.replace(/\D/g, '')}`
  return text ? `${url}?text=${encodeURIComponent(text)}` : url
}

// --- Back office (orders): labels in Malay, as the business writes them ---------------------

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  received: 'Diterima',
  washed: 'Dicuci',
  ready: 'Siap',
  completed: 'Selesai',
  cancelled: 'Dibatalkan',
}

export const ORDER_STATUS_STYLE: Record<OrderStatus, string> = {
  received: 'bg-brand/25 text-ink',
  washed: 'bg-sky-100 text-sky-900',
  ready: 'bg-emerald-100 text-emerald-900',
  completed: 'bg-foam text-ink-soft',
  cancelled: 'bg-red-50 text-danger',
}

/** The button that moves an order to this status. */
export const ORDER_ACTION_LABEL: Record<OrderStatus, string> = {
  received: 'Tanda diterima',
  washed: 'Tanda sudah dicuci',
  ready: 'Tanda siap (sudah dipack)',
  completed: 'Tanda selesai (diambil / dihantar)',
  cancelled: 'Batalkan pesanan',
}

/** The big button when an order has several items: it moves all of them. */
export const ALL_ITEMS_ACTION_LABEL: Partial<Record<OrderStatus, string>> = {
  washed: 'Tanda semua sudah dicuci',
  ready: 'Tanda semua siap (sudah dipack)',
}

/** One carpet's step. */
export const ITEM_STATUS_LABEL: Record<ItemStatus, string> = {
  received: 'Belum dicuci',
  washed: 'Sedang kering',
  ready: 'Siap dipack',
}

export const ITEM_STATUS_STYLE: Record<ItemStatus, string> = {
  received: 'bg-brand/25 text-ink',
  washed: 'bg-sky-100 text-sky-900',
  ready: 'bg-emerald-100 text-emerald-900',
}

/** The button that moves one carpet to this step. */
export const ITEM_ACTION_LABEL: Record<ItemStatus, string> = {
  received: 'Belum dicuci',
  washed: 'Siap cuci',
  ready: 'Siap pack',
}

/** Velvet is packed one of two ways; the packing form asks which. */
export const FOLD_LABEL: Record<ItemFold, string> = {
  rolled: 'Gulung',
  folded: 'Lipat',
}

export const RETURN_LABEL: Record<ReturnMethod, string> = {
  pickup: 'Pelanggan ambil di kedai',
  delivery: 'Kami hantar',
}

const dateFormat = new Intl.DateTimeFormat('en-MY', { timeZone: TIME_ZONE, day: 'numeric', month: 'short' })

/** "15 Oct" from "2026-10-15" (a calendar date, not a moment in time). */
export function formatDay(isoDate: string): string {
  return dateFormat.format(new Date(`${isoDate}T12:00:00+08:00`))
}

/** "8 x 10 kaki" for a measured carpet, "3" for counted items, "Belum diukur" until measured. */
export function formatSize(item: { length_ft: string | null; width_ft: string | null; quantity: string | null }): string {
  if (item.length_ft && item.width_ft) return `${Number(item.length_ft)} x ${Number(item.width_ft)} kaki`
  return item.quantity === null ? 'Belum diukur' : String(Number(item.quantity))
}

/** A carpet that came in without its size: it's measured when it's washed. */
export function needsMeasuring(item: { service: { pricing_unit: string }; quantity: string | null }): boolean {
  return item.service.pricing_unit === 'per_sqft' && item.quantity === null
}

export const PAYMENT_LABEL: Record<PaymentMethod, string> = {
  cash: 'Tunai',
  transfer: 'Pindahan bank',
  duitnow: 'DuitNow / e-wallet',
}

/** Whole days from one calendar date to another (both "YYYY-MM-DD"). */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000)
}

/** "10/10/26", as the book and the receipt write dates. */
export function formatShortDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${day}/${month}/${year.slice(2)}`
}

/** A washed carpet can be packed from 5 days after washing; anything else straight away. */
export function readyToPack(item: { status: ItemStatus; ready_from: string | null }, today: string): boolean {
  return item.status === 'washed' && (!item.ready_from || item.ready_from <= today)
}

/** Done at the customer's home in one visit (sofa, mattress, car seats). */
export function isHomeJob(item: { service: { on_site: boolean } }): boolean {
  return item.service.on_site
}

const visitFormat = new Intl.DateTimeFormat('ms-MY', {
  timeZone: TIME_ZONE,
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
})

/** "Sel, 21 Okt, 10:00 PG": a house visit, in Malaysia time. */
export function formatVisit(iso: string): string {
  return visitFormat.format(new Date(iso))
}

/** The Malaysia calendar day of a moment, "YYYY-MM-DD". */
export function visitDay(iso: string): string {
  return todayInMalaysia(new Date(iso))
}

/** A moment as a datetime-local input's value, in Malaysia time ("2026-10-21T10:00"). */
export function toVisitInput(iso: string | null): string {
  if (!iso) return ''
  return new Date(new Date(iso).getTime() + 8 * 3_600_000).toISOString().slice(0, 16)
}

/** A datetime-local value (Malaysia time) as the API wants it, or null when cleared. */
export function fromVisitInput(value: string): string | null {
  return value ? `${value}:00+08:00` : null
}

