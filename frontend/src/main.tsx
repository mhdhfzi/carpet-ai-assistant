// Development demo page: mounts the widget the same way widget.js does on a real site.
// API calls go to /api on this origin and Vite proxies them to the backend.
import { mountChatWidget } from './chat/embed'

// 16px margin + 64px WhatsApp button + 12px gap, matching cucicucisenawang.com.
mountChatWidget({ apiBase: '', bottomOffset: 92 })
