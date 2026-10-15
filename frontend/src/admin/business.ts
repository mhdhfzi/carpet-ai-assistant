import { useEffect, useState } from 'react'
import { api } from './api'

/** Which business this deployment serves (GET /api/business, public). */
export type Business = { name: string; demo: boolean; bookings: boolean }

/**
 * The business, or null while loading or if the request fails. Callers treat null as "not
 * the demo", so the demo login is never offered unless the server says this is the demo.
 */
export function useBusiness(): Business | null {
  const [business, setBusiness] = useState<Business | null>(null)

  useEffect(() => {
    let current = true
    api<Business>('/api/business')
      .then((data) => {
        if (!current) return
        setBusiness(data)
        document.title = `${shortName(data.name)} Dashboard`
      })
      .catch(() => {
        /* keep null: the page still works, just without the name */
      })
    return () => {
      current = false
    }
  }, [])

  return business
}

/** "Cuci-Cuci Senawang" -> "Cuci-Cuci", for the compact header. */
export function shortName(name: string): string {
  return name.split(' ')[0]
}
