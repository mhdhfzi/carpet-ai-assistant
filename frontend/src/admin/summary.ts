import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import type { WorkSummary } from './types'

// Today's numbers: the cards at the top of the work pages and the counts on the tabs.
// Any screen that changes the work (a carpet washed, a payment recorded) calls
// notifyWorkChanged(), and every card and count refreshes.

const CHANGED = 'dashboard:work-changed'

export function notifyWorkChanged() {
  window.dispatchEvent(new Event(CHANGED))
}

/** Today's numbers, or null until loaded (or when `enabled` is false: no back office). */
export function useWorkSummary(enabled: boolean): WorkSummary | null {
  const { request } = useAuth()
  const [summary, setSummary] = useState<WorkSummary | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const onChange = () => setVersion((v) => v + 1)
    window.addEventListener(CHANGED, onChange)
    window.addEventListener('hashchange', onChange) // fresh numbers on every page
    return () => {
      window.removeEventListener(CHANGED, onChange)
      window.removeEventListener('hashchange', onChange)
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let current = true
    request<WorkSummary>('/api/work/summary')
      .then((data) => {
        if (current) setSummary(data)
      })
      .catch(() => {}) // the cards are a convenience: the page works without them
    return () => {
      current = false
    }
  }, [enabled, request, version])

  return enabled ? summary : null
}
