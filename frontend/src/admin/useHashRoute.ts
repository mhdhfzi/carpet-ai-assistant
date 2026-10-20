import { useEffect, useState } from 'react'

// A handful of pages doesn't justify a router library: the page lives in the URL hash
// (#/orders/12), so links, the back button and reloads all work.
export type Route =
  | { page: 'bookings' }
  | { page: 'analytics' }
  | { page: 'orders'; filter?: string }
  | { page: 'receipts' }
  | { page: 'customers' }
  | { page: 'wash' }
  | { page: 'pack' }
  | { page: 'visits' }
  | { page: 'log' }
  | { page: 'new-order' }
  | { page: 'order'; id: number }
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
      if (id === 'new') return { page: 'new-order' }
      if (rest === 'resit' && Number.isInteger(number) && number > 0) return { page: 'receipt', id: number }
      if (id && Number.isInteger(number) && number > 0) return { page: 'order', id: number }
      return { page: 'orders', filter: new URLSearchParams(query).get('tapis') ?? undefined }
    case 'resit':
      return { page: 'receipts' }
    case 'cuci':
      return { page: 'wash' }
    case 'packing':
      return { page: 'pack' }
    case 'kerja-rumah':
      return { page: 'visits' }
    case 'rekod':
      return { page: 'log' }
    case 'customers':
      return id && Number.isInteger(number) && number > 0 ? { page: 'customer', id: number } : { page: 'customers' }
    default:
      return null
  }
}

export function href(route: Route): string {
  switch (route.page) {
    case 'orders':
      return route.filter ? `#/orders?tapis=${route.filter}` : '#/orders'
    case 'receipts':
      return '#/resit'
    case 'new-order':
      return '#/orders/new'
    case 'order':
      return `#/orders/${route.id}`
    case 'receipt':
      return `#/orders/${route.id}/resit`
    case 'customer':
      return `#/customers/${route.id}`
    case 'wash':
      return '#/cuci'
    case 'pack':
      return '#/packing'
    case 'visits':
      return '#/kerja-rumah'
    case 'log':
      return '#/rekod'
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
