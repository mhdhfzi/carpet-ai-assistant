import { useEffect, useState } from 'react'
import { api } from './api'

/** Which business this deployment serves (GET /api/business, public). */
export type Business = {
  name: string
  demo: boolean
  bookings: boolean
  orders: boolean
  brand: string // the name on receipts and in the header, e.g. a trading name
  logo: string // the short mark in the round badge
  logo_image: string // the badge's picture instead of the letters; '' = none
  address: string
}

/**
 * The business: undefined while loading, null if the request failed. Callers treat a missing
 * value as "not the demo", so the demo login is never offered unless the server says so.
 */
export function useBusiness(): Business | null | undefined {
  const [business, setBusiness] = useState<Business | null | undefined>(undefined)

  useEffect(() => {
    let current = true
    api<Business>('/api/business')
      .then((data) => {
        if (!current) return
        setBusiness(data)
        document.title = `${shortName(data.name)} Dashboard`
      })
      .catch(() => {
        if (current) setBusiness(null) // the page still works, just without the name
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
