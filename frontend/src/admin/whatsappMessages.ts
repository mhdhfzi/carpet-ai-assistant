// Ready-written WhatsApp messages to customers. The dashboard opens WhatsApp with one of
// these filled in, and the owner reads it and presses Send: nothing is sent automatically.
// The wording is in one place so it's easy to change. *Bold* is WhatsApp's own formatting.

import { formatShortDate, formatSize } from './format'
import type { Order, Receipt } from './types'

const rm = (value: string | number) => `RM${Number(value).toFixed(2)}`

/** The payment details, one item per line (written with new lines or "|" in the settings). */
export function paymentLines(details: string): string[] {
  return details
    .split(/\n|\|/)
    .map((line) => line.trim())
    .filter(Boolean)
}

function itemLines(order: Order): string[] {
  return order.items.map(
    (item, index) =>
      `${index + 1}. ${item.service.name} (${item.tag}, ${formatSize(item)}) - ${item.line_total ? rm(item.line_total) : 'harga akan dimaklumkan'}`,
  )
}

function moneyLines(order: Order): string[] {
  const lines = [`*Jumlah harga:* ${rm(order.total)}${order.price_pending ? ' (belum lengkap)' : ''}`]
  if (Number(order.paid) > 0) lines.push(`*Deposit / dibayar:* ${rm(order.paid)}`)
  lines.push(
    Number(order.balance) > 0 || order.price_pending
      ? `*Baki:* ${rm(order.balance)}`
      : '*Status bayaran:* TELAH DIBAYAR (PAID). Terima kasih!',
  )
  return lines
}

function paymentBlock(order: Order, details: string): string[] {
  if (!details || (Number(order.balance) <= 0 && !order.price_pending)) return []
  return ['', '*Bayaran online:*', ...paymentLines(details)]
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
    `Barang anda (no. siri *${order.number}*) sudah siap dicuci dan dibungkus.`,
    '',
    ...itemLines(order),
    '',
    ...moneyLines(order),
    ...paymentBlock(order, paymentDetails),
    '',
    handBack,
    '',
    `Terima kasih, ${business}`,
  ].join('\n')
}

/** The receipt as a message: everything on the printed receipt, in text. */
export function receiptMessage(order: Order, business: Receipt['business']): string {
  return [
    `Assalamualaikum / Salam sejahtera ${order.customer.name},`,
    `Berikut adalah resit daripada *${business.name}*:`,
    '',
    `*No. siri resit:* ${order.number}`,
    `*Tarikh masuk:* ${formatShortDate(order.received_on)}`,
    '*Senarai barang:*',
    ...itemLines(order),
    ...(Number(order.discount) > 0 ? [`*Diskaun:* -${rm(order.discount)}`] : []),
    '',
    ...moneyLines(order),
    ...paymentBlock(order, business.payment_details),
    '',
    `Terima kasih kerana menggunakan perkhidmatan ${business.name}!`,
  ].join('\n')
}
