// One bill for a customer's carpets and kerja luar: the two orders keep their own books and
// numbers, but the customer gets one receipt, one total and one balance. This merges them
// for showing; payments still go to the real order (the server splits them, oldest first).

import type { Order } from './types'

export function combinedBill(order: Order, linked: Order | null | undefined): Order {
  if (!linked) return order
  const [first, second] = order.kind === 'shop' ? [order, linked] : [linked, order]
  const sum = (key: 'subtotal' | 'discount' | 'total' | 'paid' | 'balance') =>
    (Number(first[key]) + Number(second[key])).toFixed(2)
  return {
    ...order,
    code: `${first.code} / ${second.code}`,
    received_on: first.received_on < second.received_on ? first.received_on : second.received_on,
    items: [...first.items, ...second.items],
    cancelled_items: [...first.cancelled_items, ...second.cancelled_items],
    subtotal: sum('subtotal'),
    discount: sum('discount'),
    total: sum('total'),
    paid: sum('paid'),
    balance: sum('balance'),
    price_pending: first.price_pending || second.price_pending,
    payments: [...first.payments, ...second.payments].sort((a, b) => a.paid_on.localeCompare(b.paid_on) || a.id - b.id),
  }
}
