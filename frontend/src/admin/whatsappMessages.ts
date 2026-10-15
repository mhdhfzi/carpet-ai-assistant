// Ready-written WhatsApp messages to customers. The dashboard opens WhatsApp with one of
// these filled in, and the owner reads it and presses Send: nothing is sent automatically.
// The wording is in one place so it's easy to change.

import { formatSize } from './format'
import type { Order } from './types'

const rm = (value: string | number) => `RM${Number(value).toFixed(2)}`

function itemLines(order: Order): string[] {
  return order.items.map(
    (item) =>
      `• ${item.tag} ${item.service.name} ${formatSize(item)}: ${item.line_total ? rm(item.line_total) : 'harga akan dimaklumkan'}`,
  )
}

function moneyLines(order: Order): string[] {
  const lines = [`Jumlah: ${rm(order.total)}${order.price_pending ? ' (belum lengkap)' : ''}`]
  if (Number(order.paid) > 0) lines.push(`Sudah dibayar: ${rm(order.paid)}`)
  lines.push(Number(order.balance) > 0 ? `Baki: ${rm(order.balance)}` : 'Telah dibayar sepenuhnya. Terima kasih!')
  return lines
}

/** "Your carpets are ready": items, what's left to pay, and pickup or delivery. */
export function readyMessage(order: Order, business: string, paymentDetails = ''): string {
  const handBack =
    order.return_method === 'delivery'
      ? 'Kami akan hubungi anda untuk atur masa penghantaran.'
      : 'Boleh datang ambil di kedai kami pada waktu operasi (tutup hari Jumaat).'
  return [
    `Assalamualaikum ${order.customer.name},`,
    '',
    `Barang anda (pesanan #${order.number}) sudah siap dicuci ✅`,
    '',
    ...itemLines(order),
    '',
    ...moneyLines(order),
    ...(Number(order.balance) > 0 && paymentDetails ? [`Bayaran: ${paymentDetails}`] : []),
    '',
    handBack,
    '',
    `Terima kasih, ${business}`,
  ].join('\n')
}

/** The receipt as a message: everything on the printed receipt, in text. */
export function receiptMessage(order: Order, business: string): string {
  const payments = order.payments
    .filter((p) => !p.voided)
    .map((p) => `• ${p.paid_on.split('-').reverse().join('/')}: ${rm(p.amount)}${p.note ? ` (${p.note})` : ''}`)
  return [
    `Resit ${business}`,
    `No. resit: ${order.number}`,
    `Pelanggan: ${order.customer.name}`,
    '',
    ...itemLines(order),
    ...(Number(order.discount) > 0 ? [`Diskaun: -${rm(order.discount)}`] : []),
    '',
    ...(payments.length ? ['Bayaran:', ...payments, ''] : []),
    ...moneyLines(order),
  ].join('\n')
}
