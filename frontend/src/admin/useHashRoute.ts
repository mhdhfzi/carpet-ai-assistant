import { useEffect, useState } from 'react'

// Two pages don't justify a router library: the page lives in the URL hash (#/bookings),
// so links, the back button and reloads all work.
export const ROUTES = ['bookings', 'analytics'] as const
export type Route = (typeof ROUTES)[number]

function parse(hash: string): Route {
  const name = hash.replace(/^#\/?/, '')
  return (ROUTES as readonly string[]).includes(name) ? (name as Route) : 'bookings'
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash))

  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return route
}
