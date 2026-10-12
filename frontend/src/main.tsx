// The demo landing page: mounts the widget the same way widget.js does on a real site.
// API calls go to /api on this origin (Vite proxies them to the backend in development).
import { OPEN_EVENT } from './chat/ChatWidget'
import { mountChatWidget } from './chat/embed'
import './landing.css'

mountChatWidget({ apiBase: '', bottomOffset: 16 })

// "Try asking" buttons open the chat with their question typed in.
for (const button of document.querySelectorAll<HTMLElement>('[data-ask]')) {
  button.addEventListener('click', () => {
    window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { message: button.dataset.ask } }))
  })
}

// The widget follows the page's language, so switching it here shows both translations.
const langButtons = document.querySelectorAll<HTMLButtonElement>('[data-lang]')
const showLang = () => {
  for (const b of langButtons) b.setAttribute('aria-pressed', String(b.dataset.lang === document.documentElement.lang))
}
for (const button of langButtons) {
  button.addEventListener('click', () => {
    document.documentElement.lang = button.dataset.lang ?? 'en'
    showLang()
  })
}
showLang()
