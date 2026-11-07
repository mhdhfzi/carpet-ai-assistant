import { useEffect, useState } from 'react'
import type { OrderKind } from './types'

// A handful of pages doesn't justify a router library: the page lives in the URL hash
// (#/orders/12), so links, the back button and reloads all work.
export type Route =
  | { page: 'bookings' }
  | { page: 'analytics' }
  | { page: 'orders'; filter?: string; month?: string } // month: "2026-10", from analytics
  | { page: 'receipts' }
  | { page: 'customers' }
  | { page: 'wash' }
  | { page: 'pack' }
  | { page: 'visits'; book?: boolean; filter?: string; month?: string } // Kerja Luar: the visit schedule, or its book
  | { page: 'log' }
  | { page: 'deleted' } // the owner's "Pesanan dipadam" list
  | { page: 'new-order'; kind?: OrderKind }
  | { page: 'order'; id: number; edit?: boolean } // edit: open with "Ubah barang" showing
  | { page: 'receipt'; id: number }
  | { page: 'customer'; id: number }

/** The route in a hash, or null for an empty or unknown one (the app picks a default). */
export function parseRoute(hash: string): Route | null {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?')
  const [name, id, rest] = path.split('/')
  const number = Number(id)
  switch (name) {
    case 'bookings':
    case 'analytics':
      return { page: name }
    case 'orders':
      if (id === 'new') return { page: 'new-order', kind: new URLSearchParams(query).get('jenis') === 'luar' ? 'on_site' : 'shop' }
      if (rest === 'resit' && Number.isInteger(number) && number > 0) return { page: 'receipt', id: number }
      if (id && Number.isInteger(number) && number > 0)
        return { page: 'order', id: number, edit: new URLSearchParams(query).has('ubah') }
      return {
        page: 'orders',
        filter: new URLSearchParams(query).get('tapis') ?? undefined,
        month: new URLSearchParams(query).get('bulan') ?? undefined,
      }
    case 'resit':
      return { page: 'receipts' }
    case 'cuci':
      return { page: 'wash' }
    case 'packing':
      return { page: 'pack' }
    case 'kerja-luar':
    case 'kerja-rumah': // the page's old address, kept for bookmarks
      return id === 'buku'
        ? {
            page: 'visits',
            book: true,
            filter: new URLSearchParams(query).get('tapis') ?? undefined,
            month: new URLSearchParams(query).get('bulan') ?? undefined,
          }
        : { page: 'visits' }
    case 'rekod':
      return { page: 'log' }
    case 'dipadam':
      return { page: 'deleted' }
    case 'customers':
      return id && Number.isInteger(number) && number > 0 ? { page: 'customer', id: number } : { page: 'customers' }
    default:
      return null
  }
}

/** A book's tab and month in its address: "?tapis=unpaid&bulan=2026-10". */
function bookQuery({ filter, month }: { filter?: string; month?: string }): string {
  const query = new URLSearchParams({ ...(filter ? { tapis: filter } : {}), ...(month ? { bulan: month } : {}) }).toString()
  return query ? `?${query}` : ''
}

export function href(route: Route): string {
  switch (route.page) {
    case 'orders':
      return `#/orders${bookQuery(route)}`
    case 'receipts':
      return '#/resit'
    case 'new-order':
      return route.kind === 'on_site' ? '#/orders/new?jenis=luar' : '#/orders/new'
    case 'order':
      return `#/orders/${route.id}${route.edit ? '?ubah' : ''}`
    case 'receipt':
      return `#/orders/${route.id}/resit`
    case 'customer':
      return `#/customers/${route.id}`
    case 'wash':
      return '#/cuci'
    case 'pack':
      return '#/packing'
    case 'visits':
      if (!route.book) return '#/kerja-luar'
      return `#/kerja-luar/buku${bookQuery(route)}`
    case 'log':
      return '#/rekod'
    case 'deleted':
      return '#/dipadam'
    default:
      return `#/${route.page}`
  }
}

export function useHashRoute(): Route | null {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))

  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return route
}
