import { type CSSProperties, type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from 'react'
import { type Brand, DEMO_BRAND, type Strings, stringsFor, whatsAppLink } from './i18n'
import { ChatIcon, CloseIcon, SendIcon } from './icons'
import { fetchAvailable } from './api'
import { type ChatMessage, useChat } from './useChat'
import { useHostLang } from './useHostLang'

export type WidgetOptions = {
  /** Backend base URL, e.g. "https://api.example.com"; "" means same origin. */
  apiBase: string
  /** Distance from the bottom of the screen in px, e.g. to sit above a WhatsApp button. */
  bottomOffset: number
  /** Which business this is for; defaults to the portfolio demo. */
  brand?: Brand
  /** The business's WhatsApp number, for a `WhatsApp us` link in the chat. */
  whatsapp?: string
}

const MAX_LENGTH = 2000 // same limit as the backend

/**
 * The host page can open the chat from its own buttons, optionally with a question typed in:
 *   window.dispatchEvent(new CustomEvent('kilau-chat:open', { detail: { message: '...' } }))
 */
export const OPEN_EVENT = 'kilau-chat:open'

export function ChatWidget({ apiBase, bottomOffset, brand = DEMO_BRAND, whatsapp }: WidgetOptions) {
  const t = stringsFor(useHostLang(), brand)
  const [open, setOpen] = useState(false)
  const [available, setAvailable] = useState(false)
  const [prefill, setPrefill] = useState({ text: '', version: 0 })
  const chat = useChat(apiBase)
  const bottom = `max(${bottomOffset}px, env(safe-area-inset-bottom))`
  const { loadHistory } = chat

  const openChat = () => {
    setOpen(true)
    void loadHistory()
  }

  // Show nothing until the server says the chat can answer: when it's switched off or out
  // of AI credit, visitors just don't see a chat button.
  const availableRef = useRef(false)
  useEffect(() => {
    let current = true
    void fetchAvailable(apiBase).then((ok) => {
      if (!current) return
      availableRef.current = ok
      setAvailable(ok)
    })
    return () => {
      current = false
    }
  }, [apiBase])

  // Listening from the start (not only once the chat is known to be available) means an
  // open request is never lost in the moment between; while unavailable it's ignored.
  useEffect(() => {
    const onOpen = (event: Event) => {
      if (!availableRef.current) return
      const message = (event as CustomEvent<{ message?: unknown } | null>).detail?.message
      // A new version remounts the panel, so its draft starts as this message.
      setPrefill((p) => ({ text: typeof message === 'string' ? message.slice(0, MAX_LENGTH) : '', version: p.version + 1 }))
      setOpen(true)
      void loadHistory()
    }
    window.addEventListener(OPEN_EVENT, onOpen)
    return () => {
      window.removeEventListener(OPEN_EVENT, onOpen)
    }
  }, [loadHistory])

  if (!available) return null

  return (
    <div className="font-sans text-[15px] leading-normal text-ink antialiased">
      {open ? (
        <ChatPanel
          key={prefill.version}
          t={t}
          chat={chat}
          bottom={bottom}
          initialDraft={prefill.text}
          whatsapp={whatsapp}
          onClose={() => setOpen(false)}
        />
      ) : (
        <button
          type="button"
          onClick={openChat}
          aria-label={t.openLabel}
          className="fixed right-4 z-[2147483000] flex h-14 items-center gap-2 rounded-full bg-brand pr-5 pl-4 font-semibold text-ink shadow-lift transition-transform hover:scale-105 hover:bg-brand-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink active:scale-95 sm:right-6"
          style={{ bottom }}
        >
          <ChatIcon className="size-6" />
          {t.open}
        </button>
      )}
    </div>
  )
}

type PanelProps = {
  t: Strings
  chat: ReturnType<typeof useChat>
  bottom: string
  initialDraft: string
  whatsapp?: string
  onClose: () => void
}

function ChatPanel({ t, chat, bottom, initialDraft, whatsapp, onClose }: PanelProps) {
  const [draft, setDraft] = useState(initialDraft)
  const input = useRef<HTMLTextAreaElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const busy = chat.status === 'sending' || chat.status === 'loading'

  // Block bodies on purpose: an effect must return nothing or a cleanup function, and
  // scrollIntoView() returns a Promise in current browsers.
  useEffect(() => {
    input.current?.focus()
  }, [])
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [chat.messages, chat.status])

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (busy || !draft.trim()) return
    void chat.send(draft)
    setDraft('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter adds a new line.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <section
      role="dialog"
      aria-label={t.title}
      onKeyDown={(event) => event.key === 'Escape' && onClose()}
      // Phones: docked to the bottom edge. Larger screens: above the host's buttons.
      className="fixed inset-x-2 bottom-2 z-[2147483000] flex h-[min(85dvh,640px)] flex-col overflow-hidden rounded-3xl bg-white shadow-lift ring-1 ring-line sm:inset-x-auto sm:right-6 sm:bottom-(--cc-bottom) sm:w-96"
      style={{ '--cc-bottom': bottom } as CSSProperties}
    >
      <header className="flex items-center gap-3 bg-ink px-4 py-3 text-white">
        <span className="grid size-10 place-items-center rounded-full bg-brand text-ink">
          <ChatIcon className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-base font-bold">{t.title}</h2>
          <p className="text-xs text-white/70">{t.subtitle}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={t.close}
          className="grid size-10 place-items-center rounded-full hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-brand"
        >
          <CloseIcon className="size-5" />
        </button>
      </header>

      {/* New messages are announced to screen readers. */}
      <div className="flex-1 space-y-3 overflow-y-auto bg-mist p-4" aria-live="polite" aria-relevant="additions">
        <Bubble role="assistant" text={t.greeting} />
        {chat.messages.map((message) => (
          <Bubble key={message.id} role={message.role} text={message.text} />
        ))}
        {chat.status === 'sending' && (
          <p className="w-fit rounded-2xl rounded-bl-sm bg-white px-4 py-2.5 text-ink-soft ring-1 ring-line">
            {t.typing}
          </p>
        )}
        {chat.status === 'error' && (
          <div role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-danger ring-1 ring-red-200">
            <p>{t.error}</p>
            <button type="button" onClick={chat.retry} className="mt-2 font-semibold underline underline-offset-2">
              {t.retry}
            </button>
          </div>
        )}
        {chat.handedOff && (
          <p className="rounded-2xl bg-brand/20 px-4 py-3 text-sm text-ink">{t.handedOff}</p>
        )}
        <div ref={end} />
      </div>

      <form className="border-t border-line bg-white p-3" onSubmit={submit}>
        <div className="flex items-end gap-2">
          <label className="sr-only" htmlFor="kilau-chat-input">
            {t.placeholder}
          </label>
          <textarea
            id="kilau-chat-input"
            ref={input}
            rows={1}
            value={draft}
            maxLength={MAX_LENGTH}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t.placeholder}
            className="max-h-32 min-h-11 flex-1 resize-none rounded-2xl bg-foam px-4 py-2.5 outline-none focus:ring-2 focus:ring-brand"
          />
          <button
            type="submit"
            aria-label={t.send}
            disabled={busy || !draft.trim()}
            className="grid size-11 shrink-0 place-items-center rounded-full bg-brand text-ink hover:bg-brand-hover disabled:opacity-40"
          >
            <SendIcon className="size-5" />
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-ink-soft">
          {t.aiNotice}
          {whatsapp && (
            <>
              {' · '}
              <a
                href={whatsAppLink(whatsapp)}
                target="_blank"
                rel="noreferrer"
                className="font-semibold text-ink underline underline-offset-2"
              >
                {t.whatsapp}
              </a>
            </>
          )}
        </p>
      </form>
    </section>
  )
}

function Bubble({ role, text }: { role: ChatMessage['role']; text: string }) {
  const mine = role === 'customer'
  return (
    <p
      className={`w-fit max-w-[85%] rounded-2xl px-4 py-2.5 break-words whitespace-pre-wrap ${
        mine ? 'ml-auto rounded-br-sm bg-ink text-white' : 'rounded-bl-sm bg-white ring-1 ring-line'
      }`}
    >
      {plainText(text)}
    </p>
  )
}

/** Replies are plain text, but drop Markdown bold markers if the model adds them anyway. */
function plainText(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/gs, '$1').replace(/__(.+?)__/gs, '$1')
}
