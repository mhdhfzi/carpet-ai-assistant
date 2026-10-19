// The order form's item lines: what's typed, and turning it into what the API expects.

import type { OrderItem, OrderItemInput, Service } from './types'

/** One editable line of an order, as typed (strings, so half-typed numbers are fine). */
export type ItemRow = {
  key: number
  serviceId: number | null
  length: string
  width: string
  quantity: string
  unitPrice: string // owner only; '' = the price list's price
  notes: string
}

let nextKey = 1

export function emptyRow(serviceId: number | null = null): ItemRow {
  return { key: nextKey++, serviceId, length: '', width: '', quantity: '', unitPrice: '', notes: '' }
}

export function rowsFromItems(items: OrderItem[]): ItemRow[] {
  return items.map((item) => ({
    key: nextKey++,
    serviceId: item.service.id,
    length: item.length_ft ? String(Number(item.length_ft)) : '',
    width: item.width_ft ? String(Number(item.width_ft)) : '',
    quantity: item.length_ft ? '' : String(Number(item.quantity)),
    unitPrice: '',
    notes: item.notes ?? '',
  }))
}

export function rowsToInput(rows: ItemRow[]): OrderItemInput[] {
  return rows
    .filter((row) => row.serviceId !== null)
    .map((row) => ({
      service_id: row.serviceId as number,
      ...(row.length && row.width ? { length_ft: row.length, width_ft: row.width } : {}),
      ...(row.quantity ? { quantity: row.quantity } : {}),
      ...(row.unitPrice ? { unit_price: row.unitPrice } : {}),
      ...(row.notes.trim() ? { notes: row.notes.trim() } : {}),
    }))
}

/** The quantity and price a row will get, for the live preview. The server decides for real. */
export function rowPrice(row: ItemRow, service: Service | undefined): { units: number; total: number | null } {
  if (!service) return { units: 0, total: null }
  const units =
    service.pricing_unit === 'per_sqft' && row.length && row.width
      ? Number(row.length) * Number(row.width)
      : Number(row.quantity || 0)
  const unit = row.unitPrice ? Number(row.unitPrice) : service.unit_price_max ? null : Number(service.unit_price)
  return { units, total: unit === null || !units ? null : Math.round(units * unit * 100) / 100 }
}
