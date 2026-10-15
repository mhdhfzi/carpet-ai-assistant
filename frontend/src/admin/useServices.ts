import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import type { Service } from './types'

/** The active price list, for the order form; null while loading. */
export function useServices(): Service[] | null {
  const { request } = useAuth()
  const [services, setServices] = useState<Service[] | null>(null)

  useEffect(() => {
    let current = true
    request<Service[]>('/api/services')
      .then((data) => {
        if (current) setServices(data.filter((s) => s.is_active))
      })
      .catch(() => {
        if (current) setServices([])
      })
    return () => {
      current = false
    }
  }, [request])

  return services
}
