import { act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mountChatWidget, optionsFromScript } from './embed'
import { DEMO_BRAND, whatsAppLink } from './i18n'

function shadow(): ShadowRoot {
  const host = document.getElementById('kilau-chat-widget')
  if (!host?.shadowRoot) throw new Error('widget not mounted')
  return host.shadowRoot
}

describe('mountChatWidget', () => {
  it('renders inside a shadow root with its own styles', () => {
    act(() => {
      mountChatWidget({ apiBase: '', bottomOffset: 16 })
    })

    // Vitest doesn't compile CSS, so only check the stylesheet is attached to the shadow
    // root; the real CSS is checked in the built widget.js.
    expect(shadow().querySelector('style')).not.toBeNull()
    expect(shadow().querySelector('button')).toHaveTextContent('Tanya kami')
  })

  it('mounts only once and can be removed', () => {
    let unmount = () => {}
    act(() => {
      mountChatWidget({ apiBase: '', bottomOffset: 16 })
      unmount = mountChatWidget({ apiBase: '', bottomOffset: 16 })
    })
    expect(document.querySelectorAll('#kilau-chat-widget')).toHaveLength(1)

    act(() => unmount())

    expect(document.getElementById('kilau-chat-widget')).toBeNull()
  })
})

describe('optionsFromScript', () => {
  function script(data: Record<string, string>): HTMLScriptElement {
    const el = document.createElement('script')
    Object.assign(el.dataset, data)
    return el
  }

  it('reads the API URL and offset, defaulting to the demo business', () => {
    expect(optionsFromScript(script({ api: 'https://api.example.com/', offsetBottom: '92' }))).toEqual({
      apiBase: 'https://api.example.com',
      bottomOffset: 92,
      brand: DEMO_BRAND,
      whatsapp: undefined,
    })
  })

  it('reads a real business, its WhatsApp number and answers-only mode', () => {
    const options = optionsFromScript(
      script({ api: '', name: 'Cuci-Cuci Senawang', shortName: 'Cuci-Cuci', whatsapp: ' 012-345 6789 ', bookings: 'false' }),
    )

    expect(options.brand).toEqual({ name: 'Cuci-Cuci Senawang', shortName: 'Cuci-Cuci', bookings: false })
    expect(options.whatsapp).toBe('012-345 6789')
    expect(optionsFromScript(script({ api: '', name: 'Cuci-Cuci Senawang' })).brand?.shortName).toBe('Cuci-Cuci Senawang')
  })

  it('falls back to a 16px offset when missing or invalid', () => {
    expect(optionsFromScript(script({ api: '' })).bottomOffset).toBe(16)
    expect(optionsFromScript(script({ api: '', offsetBottom: 'abc' })).bottomOffset).toBe(16)
  })
})

describe('whatsAppLink', () => {
  it('turns local and international Malaysian numbers into wa.me links', () => {
    expect(whatsAppLink('012-345 6789')).toBe('https://wa.me/60123456789')
    expect(whatsAppLink('+60 12-345 6789')).toBe('https://wa.me/60123456789')
  })
})
