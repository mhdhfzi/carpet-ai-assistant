// Finding a carpet or job on the work lists (Borang Cuci, Borang Packing, Kerja Luar). The
// lists only hold work still to do, so they're filtered right here as you type.

import type { Order, WorkItem } from './types'

/** "12" finds order 12 (412 or L12 alike: the book's page already picks one book); "L12" only
 * the kerja luar order; "12-2" or "L12-2" just that item. Null: the search isn't a number. */
function numberMatch(q: string, code: string, tags: string[]): boolean | null {
  const m = q.match(/^#?(l?)(\d+)(?:-(\d+))?$/i)
  if (!m) return null
  const wanted = Number(m[2])
  const same = (written: string) => {
    const w = written.match(/^(L?)(\d+)$/i)
    return w !== null && Number(w[2]) === wanted && (!m[1] || w[1] !== '')
  }
  if (m[3]) return tags.some((t) => same(t.split('-')[0]) && Number(t.split('-')[1]) === Number(m[3]))
  return same(code)
}

function includes(texts: (string | null | undefined)[], q: string): boolean {
  return texts.some((text) => text?.toLowerCase().includes(q))
}

/** One carpet on Borang Cuci or Borang Packing: by order or tag number, name, type or notes. */
export function carpetMatches(item: WorkItem, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const byNumber = numberMatch(q, String(item.order_number), [item.tag])
  if (byNumber !== null) return byNumber
  return includes([item.customer_name, item.service.name, item.name, item.notes, item.wash_note], q)
}

/** An order on Kerja Luar: by order or tag number, phone, name, address or job type. */
export function orderMatches(order: Order, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const digits = q.replace(/\D/g, '')
  // A long run of digits is part of a phone number, typed any way ("012-345 6789").
  if (digits.length >= 4 && order.customer.phone.replace(/\D/g, '').includes(digits.replace(/^0+/, ''))) return true
  const byNumber = numberMatch(q, order.code, order.items.map((i) => i.tag))
  if (byNumber !== null) return byNumber
  return includes(
    [order.customer.name, order.customer.address, order.customer.area, ...order.items.flatMap((i) => [i.name, i.service.name])],
    q,
  )
}
