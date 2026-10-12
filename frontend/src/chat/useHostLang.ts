import { useEffect, useState } from 'react'
import { type Lang, toLang } from './i18n'

/** Follows the host page's <html lang>, so the widget switches language with the site. */
export function useHostLang(): Lang {
  const [lang, setLang] = useState(() => toLang(document.documentElement.lang))

  useEffect(() => {
    const html = document.documentElement
    const observer = new MutationObserver(() => setLang(toLang(html.lang)))
    observer.observe(html, { attributes: true, attributeFilter: ['lang'] })
    return () => observer.disconnect()
  }, [])

  return lang
}
