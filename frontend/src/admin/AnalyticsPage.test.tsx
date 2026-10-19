import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { AuthProvider } from './auth'
import type { AnalyticsSummary, UnansweredQuestion } from './types'

type Call = { method: string; path: string; query: URLSearchParams; body: unknown }
type Handler = (call: Call) => { status?: number; body?: unknown }

function mockBackend(routes: Record<string, Handler>) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const parsed = new URL(url, 'http://test')
      const call = {
        method: init?.method ?? 'GET',
        path: parsed.pathname,
        query: parsed.searchParams,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      }
      calls.push(call)
      const handler = routes[`${call.method} ${call.path}`]
      const { status = 200, body } = handler ? handler(call) : { status: 404 }
      return new Response(body === undefined ? null : JSON.stringify(body), { status })
    }),
  )
  return calls
}

function summary(overrides: Partial<AnalyticsSummary> = {}): AnalyticsSummary {
  return {
    days: 30,
    start: '2026-09-13T00:00:00+08:00',
    end: '2026-10-12T10:00:00Z',
    conversations: 15,
    handed_off: 3,
    bookings: 8,
    conversion_rate: 0.5333,
    conversion: [
      { channel: 'web', conversations: 9, converted: 3, rate: 0.3333 },
      { channel: 'whatsapp', conversations: 6, converted: 5, rate: 0.8333 },
    ],
    busy_days: [
      { weekday: 'Mon', bookings: 0 },
      { weekday: 'Tue', bookings: 1 },
      { weekday: 'Wed', bookings: 2 },
      { weekday: 'Thu', bookings: 1 },
      { weekday: 'Fri', bookings: 0 },
      { weekday: 'Sat', bookings: 2 },
      { weekday: 'Sun', bookings: 1 },
    ],
    top_topics: [
      { title: 'Price list', heading: 'Cucian Sofa', count: 2 },
      { title: 'Frequently asked questions', heading: 'Are you open on Friday?', count: 1 },
    ],
    open_unanswered: { no_answer: 2, handed_off: 3, gave_up: 0 },
    ...overrides,
  }
}

const QUESTIONS: UnansweredQuestion[] = [
  {
    id: 4,
    conversation_id: 7,
    message_id: 21,
    reason: 'no_answer',
    question: 'Do you clean curtains?',
    detail: null,
    top_score: 0.41,
    resolved: false,
    created_at: '2026-10-06T03:00:00Z',
  },
  {
    id: 5,
    conversation_id: 6,
    message_id: 18,
    reason: 'handed_off',
    question: 'Harga cuci karpet surau?',
    detail: 'Quote request: surau carpet',
    top_score: 0.58,
    resolved: false,
    created_at: '2026-10-10T03:00:00Z',
  },
]

const base: Record<string, Handler> = {
  'GET /api/auth/me': () => ({ body: { id: 1, email: 'o@example.com', name: 'Owner' } }),
  'GET /api/analytics': () => ({ body: summary() }),
  'GET /api/unanswered-questions': () => ({ body: QUESTIONS }),
}

function renderAnalytics() {
  sessionStorage.setItem('kilau-admin-token', JSON.stringify({ token: 't', expiresAt: Date.now() + 60_000 }))
  render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
  return userEvent.setup()
}

beforeEach(() => {
  sessionStorage.clear()
  window.location.hash = '#/analytics'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('analytics page', () => {
  it('shows the headline numbers', async () => {
    mockBackend(base)
    renderAnalytics()

    // The tiles come first; the questions list below may use the same words as a label.
    const tile = (label: string) => screen.getAllByText(label)[0].parentElement as HTMLElement
    await screen.findByText('Chats')
    expect(tile('Chats')).toHaveTextContent('15')
    expect(tile('Bookings made')).toHaveTextContent('8')
    expect(tile('Chats that booked')).toHaveTextContent('53%')
    expect(tile('Handed to you')).toHaveTextContent('3')
    expect(tile('Open questions')).toHaveTextContent('5')
  })

  it('shows conversion per channel as meters', async () => {
    mockBackend(base)
    renderAnalytics()

    const whatsapp = await screen.findByRole('meter', { name: 'WhatsApp' })
    expect(whatsapp).toHaveAttribute('aria-valuetext', '83% · 5 of 6 chats')
    expect(screen.getByRole('meter', { name: 'Web chat' })).toHaveAttribute('aria-valuenow', '3')
  })

  it('shows busy days as a chart and as a table', async () => {
    mockBackend(base)
    const user = renderAnalytics()

    const chart = await screen.findByRole('list', { name: 'Bookings by visit day' })
    expect(within(chart).getByLabelText('Wednesday: 2 bookings')).toBeInTheDocument()
    expect(within(chart).getByLabelText('Tuesday: 1 booking')).toBeInTheDocument()

    const card = screen.getByRole('region', { name: 'Busy days' })
    await user.click(within(card).getByRole('button', { name: 'Show as table' }))

    const rows = within(card).getAllByRole('row').map((r) => r.textContent)
    expect(rows).toContain('Saturday2')
    expect(rows).toContain('Friday0')
  })

  it('lists the most cited topics', async () => {
    mockBackend(base)
    renderAnalytics()

    const card = await screen.findByRole('region', { name: 'What customers ask about' })
    const items = within(card).getAllByRole('listitem').map((li) => li.getAttribute('aria-label'))
    expect(items).toEqual([
      'Cucian Sofa (Price list): cited 2 times',
      'Are you open on Friday? (Frequently asked questions): cited once',
    ])
  })

  it('reloads everything for a different period', async () => {
    const calls = mockBackend({ ...base, 'GET /api/analytics': (c) => ({ body: summary({ days: Number(c.query.get('days')), conversations: 4 }) }) })
    const user = renderAnalytics()
    await screen.findByText('Chats')

    await user.click(screen.getByRole('button', { name: 'Last 7 days' }))

    await waitFor(() => expect(calls.at(-1)?.query.get('days')).toBe('7'))
    expect(screen.getByRole('button', { name: 'Last 7 days' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('resolves an unanswered question and refreshes the count', async () => {
    let open = 5
    const calls = mockBackend({
      ...base,
      'GET /api/analytics': () => ({ body: summary({ open_unanswered: { no_answer: open - 3, handed_off: 3, gave_up: 0 } }) }),
      'PATCH /api/unanswered-questions/4': () => {
        open -= 1
        return { body: { ...QUESTIONS[0], resolved: true } }
      },
    })
    const user = renderAnalytics()
    const list = await screen.findByRole('region', { name: "Questions the assistant couldn't answer" })
    expect(await within(list).findByText('Do you clean curtains?')).toBeInTheDocument()
    expect(within(list).getByText(/Quote request: surau carpet/)).toBeInTheDocument()

    const curtains = within(list).getByText('Do you clean curtains?').closest('li') as HTMLElement
    await user.click(within(curtains).getByRole('button', { name: 'Mark resolved' }))

    await waitFor(() => expect(within(list).queryByText('Do you clean curtains?')).not.toBeInTheDocument())
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ resolved: true })
    await waitFor(() =>
      expect(screen.getByText('Open questions').parentElement).toHaveTextContent('4'),
    )
  })

  it('shows dashes instead of a rate when there were no chats', async () => {
    mockBackend({
      ...base,
      'GET /api/analytics': () => ({
        body: summary({
          conversations: 0,
          conversion_rate: null,
          conversion: [
            { channel: 'web', conversations: 0, converted: 0, rate: null },
            { channel: 'whatsapp', conversations: 0, converted: 0, rate: null },
          ],
          top_topics: [],
        }),
      }),
      'GET /api/unanswered-questions': () => ({ body: [] }),
    })
    renderAnalytics()

    await screen.findByText('Chats')
    expect(screen.getByText('Chats that booked').parentElement).toHaveTextContent('–')
    expect(screen.getByText('No cited answers in this period yet.')).toBeInTheDocument()
    expect(await screen.findByText('Nothing waiting. Nice.')).toBeInTheDocument()
  })

  it('shows an error when analytics cannot load', async () => {
    mockBackend({ ...base, 'GET /api/analytics': () => ({ status: 500 }) })
    renderAnalytics()

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load analytics")
  })
})
