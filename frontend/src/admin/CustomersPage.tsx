import { useEffect, useState } from 'react'
import { useAuth } from './auth'
import { formatDay, formatMoney } from './format'
import type { CustomerSummary } from './types'
import { href } from './useHashRoute'

const PAGE_SIZE = 50

/** Every customer in one table, most recent first; tap a row for their order history. */
export function CustomersPage() {
  const { request } = useAuth()
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState<CustomerSummary[] | null>(null)
  const [more, setMore] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) })
    if (query.trim()) params.set('q', query.trim())
    const timer = setTimeout(() => {
      request<CustomerSummary[]>(`/api/customers?${params}`)
        .then((data) => {
          if (!current) return
          setRows(data)
          setMore(data.length === PAGE_SIZE)
          setError(false)
        })
        .catch(() => {
          if (current) setError(true)
        })
    }, 250)
    return () => {
      current = false
      clearTimeout(timer)
    }
  }, [request, query])

  const loadMore = async () => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(rows?.length ?? 0) })
    if (query.trim()) params.set('q', query.trim())
    try {
      const next = await request<CustomerSummary[]>(`/api/customers?${params}`)
      setRows((current) => [...(current ?? []), ...next])
      setMore(next.length === PAGE_SIZE)
    } catch {
      setError(true)
    }
  }

  return (
    <section className="space-y-4">
      <h1 className="font-display text-2xl font-bold">Pelanggan</h1>
      <label className="block">
        <span className="sr-only">Cari pelanggan</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Cari nama atau telefon"
          className="w-full rounded-2xl bg-white px-4 py-3 ring-1 ring-line outline-none focus:ring-2 focus:ring-brand"
        />
      </label>

      {error && <p role="alert" className="text-danger">Tak dapat muatkan pelanggan. Cuba lagi.</p>}
      {rows === null && !error && <p className="text-ink-soft">Memuatkan…</p>}
      {rows?.length === 0 && <p className="text-ink-soft">Tiada pelanggan dijumpai.</p>}

      {rows && rows.length > 0 && (
        // Wide on purpose: on a phone it scrolls sideways rather than squeezing the columns.
        <div className="overflow-x-auto rounded-2xl bg-white ring-1 ring-line">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-line bg-foam text-xs uppercase tracking-wide text-ink-soft">
              <tr>
                <th scope="col" className="px-4 py-3">Nama</th>
                <th scope="col" className="px-4 py-3">Telefon</th>
                <th scope="col" className="px-4 py-3">Kawasan</th>
                <th scope="col" className="px-4 py-3">Alamat</th>
                <th scope="col" className="px-4 py-3 text-right">Pesanan</th>
                <th scope="col" className="px-4 py-3">Terakhir</th>
                <th scope="col" className="px-4 py-3 text-right">Jumlah</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((c) => (
                <tr key={c.id} className="hover:bg-mist">
                  <td className="px-4 py-3 font-semibold">
                    <a href={href({ page: 'customer', id: c.id })} className="underline">
                      {c.name}
                    </a>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{c.phone}</td>
                  <td className="px-4 py-3">{c.area ?? '–'}</td>
                  <td className="px-4 py-3">{c.address ?? '–'}</td>
                  <td className="px-4 py-3 text-right">{c.orders}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{c.last_order_on ? formatDay(c.last_order_on) : '–'}</td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">{formatMoney(c.total_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {more && (
        <button type="button" onClick={loadMore} className="w-full rounded-full py-3 font-semibold ring-1 ring-line hover:bg-white">
          Tunjuk lagi
        </button>
      )}
    </section>
  )
}
