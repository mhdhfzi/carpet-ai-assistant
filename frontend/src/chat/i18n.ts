// Widget labels. The assistant itself replies in whatever language the customer writes;
// these are only the widget's own buttons and notices.

export type Lang = 'ms' | 'en'

export const strings = {
  ms: {
    open: 'Tanya kami',
    openLabel: 'Buka chat dengan pembantu Cuci-Cuci',
    close: 'Tutup chat',
    title: 'Pembantu Cuci-Cuci',
    subtitle: 'Biasanya membalas dalam beberapa saat',
    greeting:
      'Hai! Saya pembantu AI Cuci-Cuci Senawang. Tanya tentang harga, servis atau buat tempahan.',
    placeholder: 'Taip mesej…',
    send: 'Hantar',
    typing: 'Sedang menaip…',
    error: 'Maaf, pembantu tidak dapat dihubungi sekarang. Cuba lagi sebentar.',
    retry: 'Cuba lagi',
    handedOff: 'Pemilik akan membalas anda di sini secepat mungkin.',
    aiNotice: 'Dijana AI. Harga ialah anggaran; pemilik akan mengesahkan.',
  },
  en: {
    open: 'Ask us',
    openLabel: 'Open chat with the Cuci-Cuci assistant',
    close: 'Close chat',
    title: 'Cuci-Cuci Assistant',
    subtitle: 'Usually replies in seconds',
    greeting:
      "Hi! I'm Cuci-Cuci Senawang's AI assistant. Ask about prices, services or make a booking.",
    placeholder: 'Type a message…',
    send: 'Send',
    typing: 'Typing…',
    error: "Sorry, the assistant can't be reached right now. Please try again shortly.",
    retry: 'Try again',
    handedOff: 'The owner will reply to you here as soon as possible.',
    aiNotice: 'AI-generated. Prices are estimates; the owner will confirm.',
  },
} satisfies Record<Lang, Record<string, string>>

export type Strings = (typeof strings)['ms']

export function toLang(value: string | null | undefined): Lang {
  return value?.toLowerCase().startsWith('en') ? 'en' : 'ms'
}
