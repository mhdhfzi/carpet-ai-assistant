// Widget labels. The assistant itself replies in whatever language the customer writes;
// these are only the widget's own buttons and notices.

export type Lang = 'ms' | 'en'

/** Which business the widget is for. The defaults are the portfolio demo. */
export type Brand = {
  name: string // e.g. "Kilau Carpet Care"
  shortName: string // in the title, e.g. "Kilau"
  bookings: boolean // false: the assistant answers and estimates; bookings go to WhatsApp
}

export const DEMO_BRAND: Brand = { name: 'Kilau Carpet Care', shortName: 'Kilau', bookings: true }

export function stringsFor(lang: Lang, brand: Brand) {
  const { name, shortName, bookings } = brand
  return lang === 'en'
    ? {
        open: 'Ask us',
        openLabel: `Open chat with the ${shortName} assistant`,
        close: 'Close chat',
        title: `${shortName} Assistant`,
        subtitle: 'Usually replies in seconds',
        greeting: bookings
          ? `Hi! I'm ${name}'s AI assistant. Ask about prices, services or make a booking.`
          : `Hi! I'm ${name}'s AI assistant. Ask about prices and services. To book, WhatsApp us.`,
        placeholder: 'Type a message…',
        send: 'Send',
        typing: 'Typing…',
        error: "Sorry, the assistant can't be reached right now. Please try again shortly.",
        retry: 'Try again',
        handedOff: 'The owner will reply to you here as soon as possible.',
        aiNotice: 'AI-generated. Prices are estimates; the owner will confirm.',
        whatsapp: 'WhatsApp us',
      }
    : {
        open: 'Tanya kami',
        openLabel: `Buka chat dengan pembantu ${shortName}`,
        close: 'Tutup chat',
        title: `Pembantu ${shortName}`,
        subtitle: 'Biasanya membalas dalam beberapa saat',
        greeting: bookings
          ? `Hai! Saya pembantu AI ${name}. Tanya tentang harga, servis atau buat tempahan.`
          : `Hai! Saya pembantu AI ${name}. Tanya tentang harga dan servis. Untuk tempahan, WhatsApp kami.`,
        placeholder: 'Taip mesej…',
        send: 'Hantar',
        typing: 'Sedang menaip…',
        error: 'Maaf, pembantu tidak dapat dihubungi sekarang. Cuba lagi sebentar.',
        retry: 'Cuba lagi',
        handedOff: 'Pemilik akan membalas anda di sini secepat mungkin.',
        aiNotice: 'Dijana AI. Harga ialah anggaran; pemilik akan mengesahkan.',
        whatsapp: 'WhatsApp kami',
      }
}

export type Strings = ReturnType<typeof stringsFor>

export function toLang(value: string | null | undefined): Lang {
  return value?.toLowerCase().startsWith('en') ? 'en' : 'ms'
}

/** A wa.me link for a Malaysian number written any common way ("012-345 6789", "+60 12…"). */
export function whatsAppLink(number: string): string {
  const digits = number.replace(/\D/g, '')
  return `https://wa.me/${digits.startsWith('0') ? `6${digits}` : digits}`
}
