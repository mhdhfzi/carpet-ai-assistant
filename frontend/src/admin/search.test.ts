import { describe, expect, it } from 'vitest'
import { carpetMatches, orderMatches } from './search'
import type { Order, WorkItem } from './types'

const carpet = (overrides: Partial<WorkItem>): WorkItem =>
  ({
    tag: '12-2',
    order_number: 12,
    customer_name: 'Puan Aisyah',
    service: { name: 'Karpet Velvet' },
    notes: 'tompok kopi',
    wash_note: null,
    ...overrides,
  }) as WorkItem

describe('finding a carpet on the work lists', () => {
  it.each([
    ['12', true],
    ['#12', true],
    ['12-2', true],
    ['12-1', false],
    ['1', false],
    ['aisyah', true],
    ['VELVET', true],
    ['kopi', true],
    ['shaggy', false],
    ['  ', true],
  ])('"%s" matches: %s', (query, expected) => {
    expect(carpetMatches(carpet({}), query)).toBe(expected)
  })
})

describe('finding a house job', () => {
  const order = {
    kind: 'on_site',
    number: 18,
    code: 'L18',
    customer: { name: 'Encik Lim', phone: '+60123456789', address: '11, Jalan BBN', area: 'Nilai' },
    items: [{ tag: 'L18-1', service: { name: 'Cucian Sofa' } }],
  } as unknown as Order

  it.each([
    ['18', true],
    ['L18', true],
    ['l18-1', true],
    ['18-1', true],
    ['L19', false],
    ['012-345 6789', true],
    ['3456789', true],
    ['lim', true],
    ['nilai', true],
    ['sofa', true],
    ['tilam', false],
  ])('"%s" matches: %s', (query, expected) => {
    expect(orderMatches(order, query)).toBe(expected)
  })
})
