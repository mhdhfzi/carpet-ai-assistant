import type { ReactNode } from 'react'
import { AnalyticsPage } from './AnalyticsPage'
import { useAuth } from './auth'
import { BookingsPage } from './BookingsPage'
import { type Business, useBusiness } from './business'
import { CustomerPage } from './CustomerPage'
import { CustomersPage } from './CustomersPage'
import { LoginPage } from './LoginPage'
import { NewOrderPage } from './NewOrderPage'
import { OrderPage } from './OrderPage'
import { OrdersPage } from './OrdersPage'
import { ReceiptPage } from './ReceiptPage'
import { LogPage, PackPage, WashPage } from './WorkPages'
import { HouseJobsPage } from './HouseJobsPage'
import {
  BookIcon,
  BoxIcon,
  CalendarIcon,
  ChartIcon,
  ClipboardIcon,
  DropIcon,
  HomeIcon,
  ReceiptIcon,
  UsersIcon,
} from './icons'
import { SummaryCards } from './SummaryCards'
import { useWorkSummary } from './summary'
import type { WorkSummary } from './types'
import { type Route, href, useHashRoute } from './useHashRoute'

type NavItem = {
  route: Route
  label: string
  icon: (props: { className?: string }) => ReactNode
  active?: string // the selected tab's colours, as in the reference design
  count?: number
}

/** The menu depends on the business (does it use orders? bookings?) and on the role:
 * staff only work with orders; the server refuses them everything else anyway. */
function navFor(business: Business | null | undefined, staff: boolean, summary: WorkSummary | null): NavItem[] {
  // In the order the work happens, like the paper: the book, washing, packing, the receipt.
  const backOffice: NavItem[] = [
    { route: { page: 'orders' }, label: 'Buku Utama', icon: BookIcon },
    { route: { page: 'wash' }, label: 'Borang Cuci', icon: DropIcon, active: 'bg-sky-500 text-white', count: summary?.to_wash },
    { route: { page: 'pack' }, label: 'Borang Packing', icon: BoxIcon, count: summary?.to_pack },
    { route: { page: 'visits' }, label: 'Kerja Rumah', icon: HomeIcon, active: 'bg-emerald-500 text-white', count: summary?.house_jobs },
    { route: { page: 'receipts' }, label: 'Resit & WhatsApp', icon: ReceiptIcon, active: 'bg-emerald-500 text-white' },
    { route: { page: 'log' }, label: 'Rekod harian', icon: ClipboardIcon },
    { route: { page: 'customers' }, label: 'Pelanggan', icon: UsersIcon },
  ]
  if (staff) return backOffice
  const items: NavItem[] = business?.orders ? [...backOffice] : []
  if (business?.bookings !== false) items.push({ route: { page: 'bookings' }, label: 'Bookings', icon: CalendarIcon })
  items.push({ route: { page: 'analytics' }, label: 'Analytics', icon: ChartIcon })
  return items
}

const STAFF_PAGES = new Set<Route['page']>([
  'orders',
  'customers',
  'new-order',
  'order',
  'receipt',
  'receipts',
  'customer',
  'wash',
  'pack',
  'visits',
  'log',
])

export function App() {
  const { state } = useAuth()
  const business = useBusiness()
  const route = useHashRoute()

  if (state.status === 'checking') {
    return <p className="grid min-h-dvh place-items-center text-ink-soft">Loading…</p>
  }
  if (state.status === 'signed-out') return <LoginPage notice={state.notice} business={business} />

  const staff = state.owner.role === 'staff'
  return <SignedIn business={business} route={route} staff={staff} />
}

function SignedIn({
  business,
  route,
  staff,
}: {
  business: Business | null | undefined
  route: Route | null
  staff: boolean
}) {
  const summary = useWorkSummary(Boolean(business?.orders) || staff)
  const nav = navFor(business, staff, summary)
  // Wait for the business before picking a default page, so nobody lands on the wrong one.
  if (!route && business === undefined && !staff) {
    return <p className="grid min-h-dvh place-items-center text-ink-soft">Loading…</p>
  }
  const current = route && (!staff || STAFF_PAGES.has(route.page)) ? route : nav[0].route

  return (
    <Layout nav={nav} current={current} business={business}>
      {summary && WORK_PAGES.has(current.page) && <SummaryCards summary={summary} />}
      <Page route={current} />
    </Layout>
  )
}

/** The pages that open with today's numbers, as in the reference design. */
const WORK_PAGES = new Set<Route['page']>(['orders', 'wash', 'pack', 'visits', 'receipts', 'receipt'])

function Page({ route }: { route: Route }) {
  switch (route.page) {
    case 'analytics':
      return <AnalyticsPage />
    case 'orders':
      return <OrdersPage key={route.filter ?? ''} filter={route.filter} />
    case 'customers':
      return <CustomersPage />
    case 'wash':
      return <WashPage />
    case 'pack':
      return <PackPage />
    case 'visits':
      return <HouseJobsPage />
    case 'log':
      return <LogPage />
    case 'receipt':
      return <ReceiptPage key={route.id} id={route.id} />
    case 'receipts':
      return <ReceiptPage />
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
  if (route.page === 'receipt') return 'receipts'
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
  const brand = business?.brand ?? business?.name

  return (
    <div className="flex min-h-dvh flex-col bg-mist print:bg-white">
      <header className="z-30 bg-slate-900 md:sticky md:top-0 text-white shadow-lg print:hidden">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 pt-3 pb-2">
          <div className="flex min-w-0 items-center gap-3">
            {business && (
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-amber-500 text-sm font-extrabold text-slate-900 shadow">
                {business.logo}
              </span>
            )}
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-base leading-tight font-bold uppercase sm:text-lg">
                {brand ?? 'Dashboard'}
                {business && business.brand !== business.name && (
                  <span className="rounded-full border border-amber-400/30 bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300 normal-case">
                    {business.name}
                  </span>
                )}
              </p>
              {business?.address && <p className="truncate text-xs text-slate-400">{business.address}</p>}
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {readOnly && (
              <span className="rounded-full bg-amber-500 px-3 py-1 text-xs font-bold text-slate-900" title="You can look around, but changes are turned off">
                Demo · read-only
              </span>
            )}
            <span className="hidden text-slate-300 sm:inline">{owner?.name}</span>
            <button
              type="button"
              onClick={() => signOut()}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ring-white/25 hover:bg-white/10"
            >
              Sign out
            </button>
          </div>
        </div>
        <div className="mx-auto max-w-7xl px-4 pb-3">
          <nav aria-label="Main" className="flex gap-1.5 overflow-x-auto rounded-xl bg-slate-800 p-1.5">
            {nav.map((item) => {
              const selected = section(current) === item.route.page
              return (
                <a
                  key={item.route.page}
                  href={href(item.route)}
                  aria-current={selected ? 'page' : undefined}
                  className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold transition ${
                    selected ? `${item.active ?? 'bg-amber-500 text-slate-950'} shadow` : 'text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  <item.icon className="size-4" />
                  <span>{item.label}</span>
                  {item.count !== undefined && item.count > 0 && (
                    <span
                      className={`rounded-full px-1.5 text-[10px] font-bold ${selected ? 'bg-slate-900/20' : 'bg-slate-700 text-white'}`}
                    >
                      {item.count}
                    </span>
                  )}
                </a>
              )
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6 print:p-0">{children}</main>
    </div>
  )
}
