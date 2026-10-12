import { type CSSProperties, useState } from 'react'
import { strings } from './i18n'
import { ChatIcon, CloseIcon, SendIcon } from './icons'
import { useHostLang } from './useHostLang'

export type WidgetOptions = {
  /** Backend base URL, e.g. "https://api.cucicucisenawang.com"; "" means same origin. */
  apiBase: string
  /** Distance from the bottom of the screen in px, e.g. to sit above a WhatsApp button. */
  bottomOffset: number
}

export function ChatWidget({ bottomOffset }: WidgetOptions) {
  const t = strings[useHostLang()]
  const [open, setOpen] = useState(false)
  const bottom = `max(${bottomOffset}px, env(safe-area-inset-bottom))`

  return (
    <div className="font-sans text-[15px] leading-normal text-ink antialiased">
      {open ? (
        <section
          role="dialog"
          aria-label={t.title}
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
              onClick={() => setOpen(false)}
              aria-label={t.close}
              className="grid size-10 place-items-center rounded-full hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-brand"
            >
              <CloseIcon className="size-5" />
            </button>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto bg-mist p-4">
            <p className="max-w-[85%] rounded-2xl rounded-bl-sm bg-white px-4 py-2.5 ring-1 ring-line">
              {t.greeting}
            </p>
          </div>

          <form className="flex items-end gap-2 border-t border-line bg-white p-3" onSubmit={(e) => e.preventDefault()}>
            <label className="sr-only" htmlFor="cuci-chat-input">
              {t.placeholder}
            </label>
            <textarea
              id="cuci-chat-input"
              rows={1}
              placeholder={t.placeholder}
              className="max-h-32 min-h-11 flex-1 resize-none rounded-2xl bg-foam px-4 py-2.5 outline-none focus:ring-2 focus:ring-brand"
            />
            <button
              type="submit"
              aria-label={t.send}
              className="grid size-11 shrink-0 place-items-center rounded-full bg-brand text-ink hover:bg-brand-hover"
            >
              <SendIcon className="size-5" />
            </button>
          </form>
        </section>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={t.openLabel}
          className="fixed right-4 z-[2147483000] flex h-14 items-center gap-2 rounded-full bg-brand pr-5 pl-4 font-semibold text-ink shadow-lift transition-transform hover:scale-105 hover:bg-brand-hover active:scale-95 sm:right-6"
          style={{ bottom }}
        >
          <ChatIcon className="size-6" />
          {t.open}
        </button>
      )}
    </div>
  )
}
