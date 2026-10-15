import type { ReactNode } from 'react'
import { AnalyticsPage } from './AnalyticsPage'
import { useAuth } from './auth'
import { BookingsPage } from './BookingsPage'
import { type Business, shortName, useBusiness } from './business'
import { CustomerPage } from './CustomerPage'
import { CustomersPage } from './CustomersPage'
import { LoginPage } from './LoginPage'
import { NewOrderPage } from './NewOrderPage'
import { OrderPage } from './OrderPage'
import { OrdersPage } from './OrdersPage'
import { type Route, href, useHashRoute } from './useHashRoute'

type NavItem = { route: Route; label: string }

/** The menu depends on the business (does it use orders? bookings?) and on the role:
 * staff only work with orders; the server refuses them everything else anyway. */
function navFor(business: Business | null | undefined, staff: boolean): NavItem[] {
  const backOffice: NavItem[] = [
    { route: { page: 'orders' }, label: 'Pesanan' },
    { route: { page: 'customers' }, label: 'Pelanggan' },
  ]
  if (staff) return backOffice
  const items: NavItem[] = business?.orders ? [...backOffice] : []
  if (business?.bookings !== false) items.push({ route: { page: 'bookings' }, label: 'Bookings' })
  items.push({ route: { page: 'analytics' }, label: 'Analytics' })
  return items
}

const STAFF_PAGES = new Set<Route['page']>(['orders', 'customers', 'new-order', 'order', 'customer'])

export function App() {
  const { state } = useAuth()
  const business = useBusiness()
  const route = useHashRoute()

  if (state.status === 'checking') {
    return <p className="grid min-h-dvh place-items-center text-ink-soft">Loading…</p>
  }
  if (state.status === 'signed-out') return <LoginPage notice={state.notice} business={business} />

  const staff = state.owner.role === 'staff'
  const nav = navFor(business, staff)
  // Wait for the business before picking a default page, so nobody lands on the wrong one.
  if (!route && business === undefined && !staff) {
    return <p className="grid min-h-dvh place-items-center text-ink-soft">Loading…</p>
  }
  const current = route && (!staff || STAFF_PAGES.has(route.page)) ? route : nav[0].route

  return (
    <Layout nav={nav} current={current} business={business}>
      <Page route={current} />
    </Layout>
  )
}

function Page({ route }: { route: Route }) {
  switch (route.page) {
    case 'analytics':
      return <AnalyticsPage />
    case 'orders':
      return <OrdersPage />
    case 'customers':
      return <CustomersPage />
    case 'new-order':
      return <NewOrderPage />
    case 'order':
      return <OrderPage key={route.id} id={route.id} />
    case 'customer':
      return <CustomerPage key={route.id} id={route.id} />
    default:
      return <BookingsPage />
  }
}

/** Which menu item a page belongs to: a single order under Pesanan, a customer under Pelanggan. */
function section(route: Route): Route['page'] {
  if (route.page === 'order' || route.page === 'new-order') return 'orders'
  if (route.page === 'customer') return 'customers'
  return route.page
}

function Layout({
  nav,
  current,
  business,
  children,
}: {
  nav: NavItem[]
  current: Route
  business: Business | null | undefined
  children: ReactNode
}) {
  const { state, signOut, readOnly } = useAuth()
  const owner = state.status === 'signed-in' ? state.owner : null

  return (
    <div className="min-h-dvh bg-mist">
      <header className="bg-ink text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <p className="font-display text-lg font-bold">
            {business && `${shortName(business.name)} `}
            <span className="text-brand">Dashboard</span>
          </p>
          <nav aria-label="Main" className="flex gap-1">
            {nav.map((item) => (
              <a
                key={item.route.page}
                href={href(item.route)}
                aria-current={section(current) === item.route.page ? 'page' : undefined}
                className="rounded-full px-4 py-2 text-sm font-semibold text-white/70 hover:text-white aria-[current=page]:bg-white/10 aria-[current=page]:text-white"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {readOnly && (
              <span className="rounded-full bg-brand px-3 py-1 text-xs font-bold text-ink" title="You can look around, but changes are turned off">
                Demo · read-only
              </span>
            )}
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
