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
