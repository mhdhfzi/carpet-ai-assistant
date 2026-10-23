// Shapes returned by the backend (see backend/app/schemas). Money arrives as strings
// ("180.00") so no precision is lost.

export type BookingStatus = 'pending' | 'confirmed' | 'done' | 'cancelled'
export type BookingLocation = 'customer_home' | 'shop'

export type Booking = {
  id: number
  customer: { id: number; name: string; phone: string; area: string | null; address: string | null }
  conversation_id: number | null
  scheduled_start: string
  scheduled_end: string
  location: BookingLocation
  status: BookingStatus
  estimated_price: string
  estimated_price_max: string
  notes: string | null
  items: {
    id: number
    service: { id: number; name: string }
    quantity: string
    unit_price: string
    unit_price_max: string
    line_total: string
    line_total_max: string
  }[]
  created_at: string
}

export type Source = { source: string; title: string; heading: string; cited_text: string }

export type Conversation = {
  id: number
  channel: 'web' | 'whatsapp'
  handed_off: boolean
  handoff_reason: string | null
  customer: { id: number; name: string; phone: string } | null
  created_at: string
  messages: {
    id: number
    role: 'customer' | 'assistant' | 'staff'
    content: string
    sources: Source[] | null
    grounded: boolean | null
    created_at: string
  }[]
}

// Mirrors the backend's allowed status changes (app/services/bookings.py).
export const NEXT_STATUSES: Record<BookingStatus, BookingStatus[]> = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['done', 'cancelled'],
  done: [],
  cancelled: [],
}

export type UnansweredReason = 'no_answer' | 'handed_off' | 'gave_up'

export type AnalyticsSummary = {
  days: number
  start: string
  end: string
  conversations: number
  handed_off: number
  bookings: number
  conversion_rate: number | null
  conversion: { channel: 'web' | 'whatsapp'; conversations: number; converted: number; rate: number | null }[]
  busy_days: { weekday: string; bookings: number }[]
  top_topics: { title: string; heading: string; count: number }[]
  open_unanswered: Record<UnansweredReason, number>
}

export type UnansweredQuestion = {
  id: number
  conversation_id: number
  message_id: number
  reason: UnansweredReason
  question: string
  detail: string | null
  top_score: number | null
  resolved: boolean
  created_at: string
}

// --- Back office (orders) -------------------------------------------------------------------

export type OrderStatus = 'received' | 'washed' | 'ready' | 'completed' | 'cancelled'
export type ItemStatus = 'received' | 'washed' | 'ready'
/** How a velvet carpet was packed: gulung or lipat. */
export type ItemFold = 'rolled' | 'folded'
export type ReturnMethod = 'pickup' | 'delivery'
export type PaymentMethod = 'cash' | 'transfer' | 'duitnow'

export type Payment = {
  id: number
  amount: string
  method: PaymentMethod
  paid_on: string
  note: string | null
  received_by: string | null
  voided: boolean
  void_reason: string | null
}
export type PricingUnit = 'per_sqft' | 'per_item' | 'flat'

export type Service = {
  id: number
  name: string
  pricing_unit: PricingUnit
  unit_price: string
  unit_price_max: string | null
  on_site: boolean // done at the customer's home: no washing or packing forms
  is_active: boolean
}

export type OrderCustomer = { id: number; name: string; phone: string; area: string | null; address: string | null }

export type OrderItem = {
  id: number
  position: number
  tag: string
  service: { id: number; name: string; pricing_unit: PricingUnit; needs_fold: boolean; on_site: boolean }
  length_ft: string | null
  width_ft: string | null
  quantity: string | null // null: a carpet not measured yet (measured when washed)
  unit_price: string | null
  line_total: string | null
  notes: string | null
  status: ItemStatus
  washed_on: string | null
  washed_by: string | null
  wash_note: string | null
  ready_on: string | null // the day it was packed
  packed_by: string | null
  fold: ItemFold | null
  ready_from: string | null
  ready_by: string | null
}

/** An item on the washing or packing list, with its order. */
export type WorkItem = OrderItem & {
  order_id: number
  order_number: number
  customer_name: string
  received_on: string
}

/** One day's washing and packing forms. */
export type WorkLog = { day: string; washed: WorkItem[]; packed: WorkItem[]; on_site: WorkItem[] }

/** Which book an order is in: carpets (shop) or kerja luar (on_site), each numbered on its own. */
export type OrderKind = 'shop' | 'on_site'

export type Order = {
  id: number
  kind: OrderKind
  number: number
  code: string // the number as written: '412', or 'L12' in the kerja luar book
  customer: OrderCustomer
  received_on: string
  visit_at: string | null // the house visit, for sofa / mattress / car jobs
  status: OrderStatus
  next_status: OrderStatus | null // what the order's big button moves it to
  return_method: ReturnMethod | null
  discount: string
  notes: string | null
  washed_on: string | null
  ready_on: string | null
  completed_on: string | null
  ready_from: string | null
  ready_by: string | null
  items_washed: number
  items_ready: number
  price_pending: boolean
  subtotal: string
  total: string
  paid: string
  balance: string
  items: OrderItem[]
  payments: Payment[]
  events: { status: OrderStatus; item_tag: string | null; note: string | null; by: string | null; at: string }[]
  created_at: string
}

export type CustomerSummary = OrderCustomer & {
  orders: number
  last_order_on: string | null
  total_value: string
  unpaid: string
}

export type Receipt = {
  business: {
    name: string // as printed on the receipt
    logo: string
    logo_image: string // a picture for the badge instead of the letters; '' = none
    reg_no: string
    address: string
    phone: string
    email: string
    facebook: string
    payment_details: string // one item per line
    terms: string
    duitnow_qr: string // the shop's DuitNow QR (its text); '' = none
  }
  order: Order
  issued_on: string
}
export type CustomerDetail = CustomerSummary & { order_history: Order[] }

/** What the order form sends for each item. */
export type OrderItemInput = {
  service_id: number
  length_ft?: string
  width_ft?: string
  quantity?: string
  unit_price?: string
  notes?: string
}

export const NEXT_ITEM_STATUS: Partial<Record<ItemStatus, ItemStatus>> = {
  received: 'washed',
  washed: 'ready',
}

export const NEXT_ORDER_STATUS: Partial<Record<OrderStatus, OrderStatus>> = {
  received: 'washed',
  washed: 'ready',
  ready: 'completed',
}

/** GET /api/analytics/business: one year's totals, its months, and the whole year or one month
 * in detail. */
export type BusinessAnalytics = {
  year: number
  years: number[] // the years that can be picked, newest first
  month: number | null // the month in detail (1-12), or null for the whole year
  start: string
  end: string
  revenue_total: string // received in the year
  unpaid: string // owed now on the year's orders
  unpaid_orders: number
  months: { month: string; revenue: string; orders: number; top_service: string | null }[] // January first
  revenue: string // the detail period's
  revenue_by_method: Record<PaymentMethod, string>
  orders: number
  order_value: string
  cancelled: number
  services: { name: string; items: number; value: string }[]
  busy_days: { weekday: string; orders: number }[]
  average_days_to_ready: number | null
}

/** The cards at the top of the work pages (GET /api/work/summary). */
export type WorkSummary = {
  to_wash: number
  to_pack: number
  drying: number
  ready_orders: number
  unpaid: string
  unpaid_orders: number
  house_jobs: number // sofa / mattress / car jobs not done yet
}

/** A carpet found without its tag ("XXX" on the washing form). */
export type UntaggedItem = {
  id: number
  description: string
  found_on: string
  found_by: string | null
  matched_tag: string | null
}
