// Finding a carpet or job on the work lists (Borang Cuci, Borang Packing, Kerja Luar). The
// lists only hold work still to do, so they're filtered right here as you type.

import type { Order, WorkItem } from './types'

/** "12" finds every item of order 12; "12-2" (or "#12-2") just that one. Null: not a number. */
function numberMatch(q: string, orderNumber: number, tags: string[]): boolean | null {
  const m = q.match(/^#?(\d+)(?:-(\d+))?$/)
  if (!m) return null
  if (m[2]) return tags.includes(`${Number(m[1])}-${Number(m[2])}`)
  return orderNumber === Number(m[1])
}

function includes(texts: (string | null | undefined)[], q: string): boolean {
  return texts.some((text) => text?.toLowerCase().includes(q))
}

/** One carpet on Borang Cuci or Borang Packing: by order or tag number, name, type or notes. */
export function carpetMatches(item: WorkItem, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const byNumber = numberMatch(q, item.order_number, [item.tag])
  if (byNumber !== null) return byNumber
  return includes([item.customer_name, item.service.name, item.notes, item.wash_note], q)
}

/** An order on Kerja Luar: by order or tag number, phone, name, address or job type. */
export function orderMatches(order: Order, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const digits = q.replace(/\D/g, '')
  // A long run of digits is part of a phone number, typed any way ("012-345 6789").
  if (digits.length >= 4 && order.customer.phone.replace(/\D/g, '').includes(digits.replace(/^0+/, ''))) return true
  const byNumber = numberMatch(q, order.number, order.items.map((i) => i.tag))
  if (byNumber !== null) return byNumber
  return includes(
    [order.customer.name, order.customer.address, order.customer.area, ...order.items.map((i) => i.service.name)],
    q,
  )
}
