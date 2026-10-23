import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { BarList, ChartCard, ColumnChart, ColumnLabels, DataTable, Meter, StatTile } from './charts'
import { useBusiness } from './business'
import { BusinessSection } from './BusinessSection'
import { formatDateTime } from './format'
import type { AnalyticsSummary, UnansweredQuestion, UnansweredReason } from './types'

const PERIODS = [7, 30, 90] as const

const CHANNEL_LABEL = { web: 'Web chat', whatsapp: 'WhatsApp' } as const

const WEEKDAY_NAME: Record<string, string> = {
  Mon: 'Monday',
  Tue: 'Tuesday',
  Wed: 'Wednesday',
  Thu: 'Thursday',
  Fri: 'Friday',
  Sat: 'Saturday',
  Sun: 'Sunday',
}

const REASON_LABEL: Record<UnansweredReason, string> = {
  no_answer: 'No answer',
  handed_off: 'Handed to you',
  gave_up: 'AI gave up',
}

function percent(rate: number | null): string {
  return rate === null ? '–' : `${Math.round(rate * 100)}%`
}

export function AnalyticsPage() {
  const { request } = useAuth()
  const business = useBusiness()
  // A real business whose assistant sends bookings to WhatsApp has no AI bookings to show.
  const bookings = business?.bookings !== false
  const [days, setDays] = useState<(typeof PERIODS)[number]>(30)
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let current = true
    request<AnalyticsSummary>(`/api/analytics?days=${days}`)
      .then((data) => {
        if (!current) return
        setSummary(data)
        setError(null)
      })
      .catch(() => current && setError("Couldn't load analytics. Please try again."))
      .finally(() => current && setLoading(false))
    return () => {
      current = false
    }
  }, [days, reload, request])

  const choosePeriod = (value: (typeof PERIODS)[number]) => {
    setLoading(true) // keep showing the old numbers, faded, until the new ones arrive
    setDays(value)
  }

  const openUnanswered = summary ? Object.values(summary.open_unanswered).reduce((a, b) => a + b, 0) : 0

  // The AI chat's period. The business numbers have their own year and month pickers.
  const periodPicker = (
    <div role="group" aria-label="Period" className="flex rounded-full bg-white p-1 ring-1 ring-line">
      {PERIODS.map((value) => (
        <button
          key={value}
          type="button"
          aria-pressed={days === value}
          onClick={() => choosePeriod(value)}
          className="rounded-full px-3 py-1.5 text-sm font-semibold text-ink-soft aria-pressed:bg-ink aria-pressed:text-white"
        >
          Last {value} days
        </button>
      ))}
    </div>
  )

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-2xl font-bold">Analytics</h1>
        {!business?.orders && periodPicker}
      </div>

      {error && (
        <p role="alert" className="rounded-2xl bg-red-50 p-4 text-danger ring-1 ring-red-200">
          {error}
        </p>
      )}
      {!summary && !error && <p className="text-ink-soft">Loading analytics…</p>}

      {business?.orders && <BusinessSection />}

      {summary && (
        <div className={`space-y-4 transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
          {business?.orders && (
            <div className="flex flex-wrap items-end justify-between gap-3 pt-4">
              <h2 className="font-display text-xl font-bold">Pembantu AI (chat)</h2>
              {periodPicker}
            </div>
          )}
          <div className={`grid grid-cols-2 gap-3 ${bookings ? 'md:grid-cols-5' : 'md:grid-cols-3'}`}>
            <StatTile label="Chats" value={String(summary.conversations)} />
            {bookings && <StatTile label="Bookings made" value={String(summary.bookings)} />}
            {bookings && <StatTile label="Chats that booked" value={percent(summary.conversion_rate)} />}
            <StatTile label="Handed to you" value={String(summary.handed_off)} />
            <StatTile label="Open questions" value={String(openUnanswered)} hint="Needing an answer" />
          </div>

          {bookings && (
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Chat to booking, by channel"
              subtitle="Share of chats in this period that led to a booking"
              chart={
                <div className="space-y-4">
                  {summary.conversion.map((c) => (
                    <Meter
                      key={c.channel}
                      label={CHANNEL_LABEL[c.channel]}
                      value={c.converted}
                      max={c.conversations}
                      detail={`${percent(c.rate)} · ${c.converted} of ${c.conversations} chats`}
                    />
                  ))}
                </div>
              }
              table={
                <DataTable
                  columns={['Channel', 'Chats', 'Booked', 'Rate']}
                  rows={summary.conversion.map((c) => [CHANNEL_LABEL[c.channel], c.conversations, c.converted, percent(c.rate)])}
                />
              }
            />

            <ChartCard
              title="Busy days"
              subtitle="Bookings made in this period, by visit day (cancelled ones excluded)"
              chart={
                <>
                  <ColumnChart
                    valueLabel="Bookings by visit day"
                    data={summary.busy_days.map((d) => ({
                      label: d.weekday,
                      value: d.bookings,
                      description: `${WEEKDAY_NAME[d.weekday] ?? d.weekday}: ${d.bookings} ${d.bookings === 1 ? 'booking' : 'bookings'}`,
                    }))}
                  />
                  <ColumnLabels labels={summary.busy_days.map((d) => d.weekday)} />
                </>
              }
              table={
                <DataTable
                  columns={['Day', 'Bookings']}
                  rows={summary.busy_days.map((d) => [WEEKDAY_NAME[d.weekday] ?? d.weekday, d.bookings])}
                />
              }
            />
          </div>
          )}

          <ChartCard
            title="What customers ask about"
            subtitle="Knowledge sections the assistant cited most in this period"
            chart={
              summary.top_topics.length ? (
                <BarList
                  data={summary.top_topics.map((t) => ({
                    label: t.heading,
                    sublabel: t.title,
                    value: t.count,
                    description: `${t.heading} (${t.title}): cited ${t.count === 1 ? 'once' : `${t.count} times`}`,
                  }))}
                />
              ) : (
                <p className="text-sm text-ink-soft">No cited answers in this period yet.</p>
              )
            }
            table={
              <DataTable
                columns={['Topic', 'Document', 'Times cited']}
                rows={summary.top_topics.map((t) => [t.heading, t.title, t.count])}
              />
            }
          />

          <UnansweredList onChange={() => setReload((n) => n + 1)} />
        </div>
      )}
    </section>
  )
}

function UnansweredList({ onChange }: { onChange: () => void }) {
  const { request } = useAuth()
  const [questions, setQuestions] = useState<UnansweredQuestion[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    request<UnansweredQuestion[]>('/api/unanswered-questions?resolved=false')
      .then((rows) => current && setQuestions(rows))
      .catch(() => current && setError("Couldn't load the questions."))
    return () => {
      current = false
    }
  }, [request])

  const resolve = async (id: number) => {
    try {
      await request(`/api/unanswered-questions/${id}`, { method: 'PATCH', body: { resolved: true } })
      setQuestions((rows) => rows?.filter((q) => q.id !== id) ?? null)
      onChange() // refresh the "Open questions" count
    } catch {
      setError("Couldn't mark that question as resolved.")
    }
  }

  return (
    <section aria-labelledby="unanswered-heading" className="rounded-2xl bg-white p-4 ring-1 ring-line">
      <h2 id="unanswered-heading" className="font-semibold">
        Questions the assistant couldn't answer
      </h2>
      <p className="mb-3 text-xs text-ink-soft">
        Add the missing information to the knowledge base or price list, then mark each one resolved.
      </p>
      {error && (
        <p role="alert" className="mb-2 text-sm text-danger">
          {error}
        </p>
      )}
      {questions?.length === 0 && <p className="text-sm text-ink-soft">Nothing waiting. Nice.</p>}
      <ul className="divide-y divide-line">
        {questions?.map((q) => (
          <li key={q.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
            <div className="min-w-0 space-y-1">
              <p>{q.question}</p>
              <p className="text-xs text-ink-soft">
                <span className="font-semibold">{REASON_LABEL[q.reason]}</span>
                {q.detail && ` · ${q.detail}`} · {formatDateTime(q.created_at)}
              </p>
            </div>
            <button
              type="button"
              onClick={() => resolve(q.id)}
              className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-line hover:bg-foam"
            >
              Mark resolved
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
