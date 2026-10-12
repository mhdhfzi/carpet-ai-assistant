import type { ReactNode } from 'react'
import { AnalyticsPage } from './AnalyticsPage'
import { useAuth } from './auth'
import { BookingsPage } from './BookingsPage'
import { LoginPage } from './LoginPage'
import { type Route, useHashRoute } from './useHashRoute'

const NAV: { route: Route; label: string }[] = [
  { route: 'bookings', label: 'Bookings' },
  { route: 'analytics', label: 'Analytics' },
]

export function App() {
  const { state } = useAuth()
  const route = useHashRoute()

  if (state.status === 'checking') {
    return <p className="grid min-h-dvh place-items-center text-ink-soft">Loading…</p>
  }
  if (state.status === 'signed-out') return <LoginPage notice={state.notice} />

  return (
    <Layout route={route}>
      {route === 'analytics' ? <AnalyticsPage /> : <BookingsPage />}
    </Layout>
  )
}

function Layout({ route, children }: { route: Route; children: ReactNode }) {
  const { state, signOut } = useAuth()
  const owner = state.status === 'signed-in' ? state.owner : null

  return (
    <div className="min-h-dvh bg-mist">
      <header className="bg-ink text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <p className="font-display text-lg font-bold">
            Kilau <span className="text-brand">Dashboard</span>
          </p>
          <nav aria-label="Main" className="flex gap-1">
            {NAV.map((item) => (
              <a
                key={item.route}
                href={`#/${item.route}`}
                aria-current={route === item.route ? 'page' : undefined}
                className="rounded-full px-4 py-2 text-sm font-semibold text-white/70 hover:text-white aria-[current=page]:bg-white/10 aria-[current=page]:text-white"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-white/70">{owner?.name}</span>
            <button
              type="button"
              onClick={() => signOut()}
              className="rounded-full px-4 py-2 font-semibold ring-1 ring-white/25 hover:bg-white/10"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl p-4 sm:p-6">{children}</main>
    </div>
  )
}
