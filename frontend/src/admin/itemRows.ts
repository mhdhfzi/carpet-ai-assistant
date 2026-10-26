// The order form's item lines: what's typed, and turning it into what the API expects.

import type { ItemFold, OrderItem, OrderItemInput, Service } from './types'

/** One editable line of an order, as typed (strings, so half-typed numbers are fine). */
export type ItemRow = {
  key: number
  id?: number // an item already on the order: it keeps its tag number
  tag?: string
  serviceId: number | null
  length: string
  width: string
  quantity: string
  unitPrice: string // owner only ("Lain-lain": anyone); '' = the price list's price
  notes: string // "Lain-lain": what the job is
  fold?: ItemFold // velvet: gulung or lipat
}

let nextKey = 1

export function emptyRow(serviceId: number | null = null): ItemRow {
  return { key: nextKey++, serviceId, length: '', width: '', quantity: '', unitPrice: '', notes: '' }
}

export function rowsFromItems(items: OrderItem[]): ItemRow[] {
  return items.map((item) => ({
    key: nextKey++,
    id: item.id,
    tag: item.tag,
    serviceId: item.service.id,
    length: item.length_ft ? String(Number(item.length_ft)) : '',
    width: item.width_ft ? String(Number(item.width_ft)) : '',
    quantity: item.length_ft || item.quantity === null ? '' : String(Number(item.quantity)),
    unitPrice: '',
    notes: item.notes ?? '',
    fold: item.fold ?? undefined,
  }))
}

export function rowsToInput(rows: ItemRow[]): OrderItemInput[] {
  return rows
    .filter((row) => row.serviceId !== null)
    .map((row) => ({
      ...(row.id ? { id: row.id } : {}),
      service_id: row.serviceId as number,
      ...(row.length && row.width ? { length_ft: row.length, width_ft: row.width } : {}),
      ...(row.quantity ? { quantity: row.quantity } : {}),
      ...(row.unitPrice ? { unit_price: row.unitPrice } : {}),
      ...(row.notes.trim() ? { notes: row.notes.trim() } : {}),
      ...(row.fold ? { fold: row.fold } : {}),
    }))
}

/** What a row still needs before the order can be saved, or null: velvet says gulung or
 * lipat, and "Lain-lain" what the job is. */
export function rowProblem(row: ItemRow, service: Service | undefined, label: string): string | null {
  if (!service) return null
  if (service.needs_fold && !row.fold) return `${label}: pilih Gulung atau Lipat untuk ${service.name}.`
  if (service.custom && !row.notes.trim()) return `${label}: tulis kerja apa untuk ${service.name}.`
  return null
}

/** The quantity and price a row will get, for the live preview. The server decides for real. */
export function rowPrice(row: ItemRow, service: Service | undefined): { units: number; total: number | null } {
  if (!service) return { units: 0, total: null }
  const units =
    service.pricing_unit === 'per_sqft' && row.length && row.width
      ? Number(row.length) * Number(row.width)
      : Number(row.quantity || 0)
  const unit = row.unitPrice
    ? Number(row.unitPrice)
    : service.unit_price_max || service.custom
      ? null
      : Number(service.unit_price)
  // Whole ringgit per line, like the server (RM37.80 -> RM37).
  return { units, total: unit === null || !units ? null : Math.floor(Math.round(units * unit * 100) / 100) }
}
