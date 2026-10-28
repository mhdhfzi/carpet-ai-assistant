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
  unitPrice: string // owner only; '' = the price list's price (or the price it already has)
  notes: string // "Lain-lain": what the job is
  fold?: ItemFold // velvet: gulung or lipat
  // An item already on the order: the service and price it has, for the preview.
  saved?: { serviceId: number; price: string | null }
  suggested?: boolean // unitPrice is this agent's last price, filled in for the owner to check
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
    saved: { serviceId: item.service.id, price: item.unit_price },
  }))
}

export function rowsToInput(rows: ItemRow[]): OrderItemInput[] {
  return rows
    .filter((row) => row.serviceId !== null)
    .map((row) => ({
      ...(row.id ? { id: row.id } : {}),
      service_id: row.serviceId as number,
      ...(row.length && row.width ? { length_ft: row.length, width_ft: row.width } : {}),
      ...(row.quantity && !(row.length && row.width) ? { quantity: row.quantity } : {}),
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

/** Measured in feet: carpets, and "Lain-lain" brought to the shop (a shaggy rug; curtains
 * are counted instead, so for those the size is optional). */
export function measurable(service: Service | undefined): boolean {
  return !!service && (service.pricing_unit === 'per_sqft' || (service.custom && !service.on_site))
}

/** Priced from the price list (not a range, not "Lain-lain"). */
export function fixedPrice(service: Service): boolean {
  return !service.custom && !service.unit_price_max
}

/** The price a row gets when nobody types one, as the server does: the price list's, or
 * null when the owner prices it (a range, "Lain-lain", or an agent's carpet). */
export function listPrice(service: Service, agent: boolean): number | null {
  if (!fixedPrice(service) || (agent && !service.on_site)) return null
  return Number(service.unit_price)
}

/** The quantity and price a row will get, for the live preview. The server decides for real. */
export function rowPrice(row: ItemRow, service: Service | undefined, agent = false): { units: number; total: number | null } {
  if (!service) return { units: 0, total: null }
  const units = measurable(service) && row.length && row.width ? Number(row.length) * Number(row.width) : Number(row.quantity || 0)
  const kept = row.saved && row.saved.serviceId === service.id // an item keeps its price when edited
  const unit = row.unitPrice
    ? Number(row.unitPrice)
    : kept
      ? row.saved!.price === null
        ? null
        : Number(row.saved!.price)
      : listPrice(service, agent)
  // Whole ringgit per line, like the server (RM37.80 -> RM37).
  return { units, total: unit === null || !units ? null : Math.floor(Math.round(units * unit * 100) / 100) }
}

/** Agent prices the owner gave this agent last time, by service id. */
export type AgentPrices = Map<number, string>

type Request = <T>(path: string) => Promise<T>

/** Owner only: this agent's last prices, so the price boxes start from them. */
export async function loadAgentPrices(request: Request, customerId: number): Promise<AgentPrices> {
  const found = await request<{ service_id: number; unit_price: string }[]>(`/api/customers/${customerId}/agent-prices`)
  return new Map(found.map((p) => [p.service_id, p.unit_price]))
}

/** Fill empty price boxes with this agent's last prices, for the rows `fill` allows; with no
 * prices (back to a normal customer), take the filled-in ones out again. */
export function suggestPrices(rows: ItemRow[], prices: AgentPrices | null, fill: (row: ItemRow) => boolean = () => true): ItemRow[] {
  return rows.map((row) => {
    if (!prices) return row.suggested ? { ...row, unitPrice: '', suggested: false } : row
    const price = row.serviceId === null ? undefined : prices.get(row.serviceId)
    return price && row.unitPrice === '' && fill(row) ? { ...row, unitPrice: String(Number(price)), suggested: true } : row
  })
}
