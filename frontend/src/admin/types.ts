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
  is_active: boolean
}

export type OrderCustomer = { id: number; name: string; phone: string; area: string | null; address: string | null }

export type OrderItem = {
  id: number
  position: number
  tag: string
  service: { id: number; name: string; pricing_unit: PricingUnit; needs_fold: boolean }
  length_ft: string | null
  width_ft: string | null
  quantity: string
  unit_price: string | null
  line_total: string | null
  notes: string | null
  status: ItemStatus
  washed_on: string | null
  washed_by: string | null
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
export type WorkLog = { day: string; washed: WorkItem[]; packed: WorkItem[] }

export type Order = {
  id: number
  number: number
  customer: OrderCustomer
  received_on: string
  status: OrderStatus
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
  business: { name: string; reg_no: string; address: string; phone: string; payment_details: string }
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

export type BusinessAnalytics = {
  days: number
  start: string
  end: string
  revenue: string
  revenue_by_method: Record<PaymentMethod, string>
  revenue_over_time: { label: string; start: string; amount: string }[]
  orders: number
  order_value: string
  cancelled: number
  unpaid: string
  unpaid_orders: number
  in_progress: Record<'received' | 'washed' | 'ready', number>
  services: { name: string; items: number; value: string }[]
  busy_days: { weekday: string; orders: number }[]
  average_days_to_ready: number | null
}
