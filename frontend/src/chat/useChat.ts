import { useCallback, useRef, useState } from 'react'
import { fetchHistory, type Role, sendMessage } from './api'

export type ChatMessage = { id: number; role: Role; text: string }

export type ChatStatus = 'idle' | 'loading' | 'sending' | 'error'

// The session token is the only link between this browser and its conversation. It lives
// in localStorage so a page reload keeps the conversation; the messages themselves are
// fetched from the server, which stays the source of truth.
const SESSION_KEY = 'kilau-chat-session'

function readSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY)
  } catch {
    return null // storage blocked (private mode, strict settings): chat still works
  }
}

function writeSession(value: string | null) {
  try {
    if (value) localStorage.setItem(SESSION_KEY, value)
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    /* storage unavailable */
  }
}

let nextId = 1

export function useChat(apiBase: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [handedOff, setHandedOff] = useState(false)
  const [failedText, setFailedText] = useState<string | null>(null)
  const session = useRef<string | null>(readSession())
  const loaded = useRef(false)

  const add = (role: Role, text: string) =>
    setMessages((current) => [...current, { id: nextId++, role, text }])

  /** Load an earlier conversation, once, when the chat is first opened. */
  const loadHistory = useCallback(async () => {
    if (loaded.current || !session.current) return
    loaded.current = true
    setStatus('loading')
    try {
      const history = await fetchHistory(apiBase, session.current)
      if (history === null) {
        session.current = null // the server forgot it: start fresh
        writeSession(null)
      } else {
        setMessages(history.messages.map((m) => ({ id: nextId++, role: m.role, text: m.content })))
        setHandedOff(history.handed_off)
      }
      setStatus('idle')
    } catch {
      setStatus('idle') // history is a nicety; the chat still works without it
    }
  }, [apiBase])

  const send = useCallback(
    async (raw: string, { retry = false } = {}) => {
      const text = raw.trim()
      if (!text) return
      if (!retry) add('customer', text)
      setFailedText(null)
      setStatus('sending')
      try {
        const response = await sendMessage(apiBase, session.current, text)
        session.current = response.session_id
        writeSession(response.session_id)
        setHandedOff(response.handed_off)
        if (response.reply) add('assistant', response.reply)
        setStatus('idle')
      } catch {
        setFailedText(text)
        setStatus('error')
      }
    },
    [apiBase],
  )

  const retry = useCallback(() => {
    if (failedText) void send(failedText, { retry: true })
  }, [failedText, send])

  return { messages, status, handedOff, loadHistory, send, retry }
}
