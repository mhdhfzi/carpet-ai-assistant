/**
 * Entry point of the embeddable widget. A host site adds one tag:
 *
 *   <script src="https://…/widget.js" data-api="https://api.example.com" defer></script>
 *
 * The widget renders inside a shadow root, so the host page's CSS can't restyle it and the
 * widget's CSS can't leak into the page.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ChatWidget, type WidgetOptions } from './ChatWidget'
import { DEMO_BRAND } from './i18n'
import css from './widget.css?inline'

const HOST_ID = 'kilau-chat-widget'

export function mountChatWidget(options: WidgetOptions): () => void {
  document.getElementById(HOST_ID)?.remove() // never mount twice

  const host = document.createElement('div')
  host.id = HOST_ID
  document.body.appendChild(host)

  const shadow = host.attachShadow({ mode: 'open' })
  const style = document.createElement('style')
  style.textContent = css
  const container = document.createElement('div')
  shadow.append(style, container)

  const root = createRoot(container)
  root.render(
    <StrictMode>
      <ChatWidget {...options} />
    </StrictMode>,
  )
  return () => {
    root.unmount()
    host.remove()
  }
}

/**
 * Options from the script tag. Only data-api is required; the rest default to the demo:
 *   data-name="Cuci-Cuci Senawang"  data-short-name="Cuci-Cuci"
 *   data-whatsapp="012-345 6789"    data-bookings="false"   data-offset-bottom="92"
 */
export function optionsFromScript(script: HTMLScriptElement): WidgetOptions {
  const data = script.dataset
  const offset = Number(data.offsetBottom)
  const name = data.name?.trim() || DEMO_BRAND.name
  return {
    apiBase: (data.api ?? '').replace(/\/+$/, ''),
    bottomOffset: Number.isFinite(offset) && offset >= 0 ? offset : 16,
    brand: {
      name,
      shortName: data.shortName?.trim() || (data.name ? name : DEMO_BRAND.shortName),
      bookings: data.bookings !== 'false',
    },
    whatsapp: data.whatsapp?.trim() || undefined,
  }
}

// Auto-mount when loaded by a <script data-api=…> tag. currentScript is only available
// while the script first runs, so read it now.
const script = document.currentScript
if (script instanceof HTMLScriptElement && script.dataset.api !== undefined) {
  const start = () => mountChatWidget(optionsFromScript(script))
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true })
  } else {
    start()
  }
}
