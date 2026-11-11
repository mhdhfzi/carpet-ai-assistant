// Extra charges being typed on the order form and the order page (see ChargesEditor).

import type { Charge } from './types'

/** One extra charge being typed: its amount and why. */
export type ChargeRow = { key: number; amount: string; reason: string }

let nextKey = 0

export function chargeRows(charges: Charge[] = []): ChargeRow[] {
  return charges.map((c) => ({ key: nextKey++, amount: String(Number(c.amount)), reason: c.reason }))
}

export function emptyCharge(): ChargeRow {
  return { key: nextKey++, amount: '', reason: '' }
}

/** The charges to save: rows left empty are dropped. */
export function chargesToInput(rows: ChargeRow[]): Charge[] {
  return rows
    .filter((row) => row.amount.trim() || row.reason.trim())
    .map((row) => ({ amount: row.amount.trim(), reason: row.reason.trim() }))
}

/** What's missing before the charges can be saved, or null. */
export function chargeProblem(rows: ChargeRow[]): string | null {
  for (const [index, charge] of chargesToInput(rows).entries()) {
    if (!(Number(charge.amount) > 0)) return `Caj ${index + 1}: isi amaun (RM).`
    if (charge.reason.length < 2) return `Caj ${index + 1}: tulis sebab caj (cth. Ambil lebih 15km).`
  }
  return null
}

export function chargeRowsTotal(rows: ChargeRow[]): number {
  return rows.reduce((sum, row) => sum + (Number(row.amount) > 0 ? Number(row.amount) : 0), 0)
}
