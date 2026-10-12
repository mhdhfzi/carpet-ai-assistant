import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatWidget } from './ChatWidget'

type Reply = { status?: number; body?: unknown }

/** A fake backend: replies in order and records every request. */
function mockApi(...replies: Reply[]) {
  const calls: { url: string; body: unknown }[] = []
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const reply = replies.shift() ?? { status: 500 }
    return new Response(JSON.stringify(reply.body ?? {}), { status: reply.status ?? 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

const answer = (reply: string | null, extra: object = {}) => ({
  body: { session_id: 'session-abc', reply, handed_off: false, ...extra },
})

async function openChat() {
  const user = userEvent.setup()
  render(<ChatWidget apiBase="https://api.test" bottomOffset={16} />)
  await user.click(screen.getByRole('button', { name: /buka chat/i }))
  return user
}

beforeEach(() => {
  document.documentElement.lang = 'ms'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ChatWidget', () => {
  it('opens with a greeting and focuses the input', async () => {
    mockApi()
    await openChat()

    expect(screen.getByRole('dialog', { name: 'Pembantu Cuci-Cuci' })).toBeInTheDocument()
    expect(screen.getByText(/pembantu AI Cuci-Cuci Senawang/)).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveFocus()
  })

  it('sends a message and shows the reply', async () => {
    const calls = mockApi(answer('Kami tutup pada hari Jumaat.'))
    const user = await openChat()

    await user.type(screen.getByRole('textbox'), 'Buka hari Jumaat?{Enter}')

    expect(await screen.findByText('Kami tutup pada hari Jumaat.')).toBeInTheDocument()
    expect(screen.getByText('Buka hari Jumaat?')).toBeInTheDocument()
    expect(calls[0]).toEqual({
      url: 'https://api.test/api/chat',
      body: { session_id: null, message: 'Buka hari Jumaat?' },
    })
    expect(screen.getByRole('textbox')).toHaveValue('')
  })

  it('keeps the session for follow-up messages and page reloads', async () => {
    const calls = mockApi(answer('Hello!'), answer('RM60 per seat.'))
    const user = await openChat()

    await user.type(screen.getByRole('textbox'), 'Hi{Enter}')
    await screen.findByText('Hello!')
    await user.type(screen.getByRole('textbox'), 'Sofa price?{Enter}')
    await screen.findByText('RM60 per seat.')

    expect(calls[1].body).toEqual({ session_id: 'session-abc', message: 'Sofa price?' })
    expect(localStorage.getItem('cuci-chat-session')).toBe('session-abc')
  })

  it('restores the conversation from the server when reopened later', async () => {
    localStorage.setItem('cuci-chat-session', 'session-abc')
    const calls = mockApi({
      body: {
        session_id: 'session-abc',
        handed_off: false,
        messages: [
          { role: 'customer', content: 'Earlier question', created_at: '2026-10-12T01:00:00Z' },
          { role: 'assistant', content: 'Earlier answer', created_at: '2026-10-12T01:00:05Z' },
        ],
      },
    })

    await openChat()

    expect(await screen.findByText('Earlier answer')).toBeInTheDocument()
    expect(calls[0].url).toBe('https://api.test/api/chat/session-abc')
  })

  it('starts fresh if the server no longer knows the session', async () => {
    localStorage.setItem('cuci-chat-session', 'expired')
    mockApi({ status: 404 })

    await openChat()

    await waitFor(() => expect(localStorage.getItem('cuci-chat-session')).toBeNull())
  })

  it('does not call the API until the chat is opened', () => {
    localStorage.setItem('cuci-chat-session', 'session-abc')
    mockApi()

    render(<ChatWidget apiBase="" bottomOffset={16} />)

    expect(fetch).not.toHaveBeenCalled()
  })

  it('shows an error with a retry that resends the message', async () => {
    const calls = mockApi({ status: 503 }, answer('Back online!'))
    const user = await openChat()

    await user.type(screen.getByRole('textbox'), 'Hello?{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent(/tidak dapat dihubungi/)

    await user.click(screen.getByRole('button', { name: 'Cuba lagi' }))

    expect(await screen.findByText('Back online!')).toBeInTheDocument()
    expect(calls[1].body).toEqual({ session_id: null, message: 'Hello?' })
    expect(screen.getAllByText('Hello?')).toHaveLength(1) // not shown twice
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('tells the customer when the owner has taken over', async () => {
    mockApi(answer(null, { handed_off: true }))
    const user = await openChat()

    await user.type(screen.getByRole('textbox'), 'Saya nak cakap dengan orang{Enter}')

    expect(await screen.findByText(/Pemilik akan membalas/)).toBeInTheDocument()
  })

  it('does not send blank messages; Shift+Enter adds a new line', async () => {
    mockApi()
    const user = await openChat()

    await user.type(screen.getByRole('textbox'), '   {Enter}')
    await user.type(screen.getByRole('textbox'), 'line one{Shift>}{Enter}{/Shift}line two')

    expect(fetch).not.toHaveBeenCalled()
    expect(screen.getByRole('textbox')).toHaveValue('   line one\nline two')
  })

  it('closes with the close button or Escape', async () => {
    mockApi()
    const user = await openChat()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /buka chat/i }))
    await user.click(screen.getByRole('button', { name: 'Tutup chat' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it("switches language when the host page's language changes", async () => {
    mockApi()
    await openChat()

    act(() => {
      document.documentElement.lang = 'en'
    })

    expect(await screen.findByRole('dialog', { name: 'Cuci-Cuci Assistant' })).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveAttribute('placeholder', 'Type a message…')
  })
})
