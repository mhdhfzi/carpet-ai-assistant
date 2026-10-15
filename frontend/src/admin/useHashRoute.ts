import { useEffect, useState } from 'react'

// A handful of pages doesn't justify a router library: the page lives in the URL hash
// (#/orders/12), so links, the back button and reloads all work.
export type Route =
  | { page: 'bookings' }
  | { page: 'analytics' }
  | { page: 'orders' }
  | { page: 'customers' }
  | { page: 'new-order' }
  | { page: 'order'; id: number }
  | { page: 'customer'; id: number }

/** The route in a hash, or null for an empty or unknown one (the app picks a default). */
export function parseRoute(hash: string): Route | null {
  const [name, id] = hash.replace(/^#\/?/, '').split('/')
  const number = Number(id)
  switch (name) {
    case 'bookings':
    case 'analytics':
      return { page: name }
    case 'orders':
      if (id === 'new') return { page: 'new-order' }
      return id && Number.isInteger(number) && number > 0 ? { page: 'order', id: number } : { page: 'orders' }
    case 'customers':
      return id && Number.isInteger(number) && number > 0 ? { page: 'customer', id: number } : { page: 'customers' }
    default:
      return null
  }
}

export function href(route: Route): string {
  switch (route.page) {
    case 'new-order':
      return '#/orders/new'
    case 'order':
      return `#/orders/${route.id}`
    case 'customer':
      return `#/customers/${route.id}`
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
