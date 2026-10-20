import { formatMoney } from './format'
import { ClockIcon } from './icons'
import type { WorkSummary } from './types'
import { href } from './useHashRoute'

/** The four cards at the top of the work pages, as in the reference design. */
export function SummaryCards({ summary }: { summary: WorkSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4 print:hidden">
      <a
        href={href({ page: 'wash' })}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-sky-400"
      >
        <p className="text-xs font-semibold text-slate-500 uppercase">Menunggu cuci</p>
        <p className="mt-1 text-xl font-extrabold sm:text-2xl text-sky-700">{summary.to_wash} karpet</p>
        <p className="mt-1 text-xs text-slate-500">Buka senarai cucian</p>
      </a>

      <a
        href={href({ page: 'pack' })}
        className="rounded-xl border-2 border-amber-400 bg-amber-50 p-4 shadow-sm transition hover:bg-amber-100/60"
      >
        <p className="flex items-center justify-between gap-2 text-xs font-bold text-amber-900 uppercase">
          <span className="flex items-center gap-1.5">
            <ClockIcon className="size-3.5" /> 5–7 hari kering
          </span>
          {summary.to_pack > 0 && (
            <span className="rounded bg-amber-600 px-2 py-0.5 text-[10px] text-white">Wajib pack</span>
          )}
        </p>
        <p className="mt-1 text-xl font-extrabold sm:text-2xl text-amber-800">{summary.to_pack} karpet</p>
        <p className="mt-1 text-xs text-amber-900/80">
          {summary.drying > 0 ? `${summary.drying} lagi masih kering` : 'Sedia untuk dibungkus'}
        </p>
      </a>

      <a
        href={href({ page: 'orders', filter: 'ready' })}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-emerald-400"
      >
        <p className="text-xs font-semibold text-slate-500 uppercase">Siap (tunggu ambil / bayar)</p>
        <p className="mt-1 text-xl font-extrabold sm:text-2xl text-emerald-700">{summary.ready_orders} tempahan</p>
        <p className="mt-1 text-xs text-slate-500">Karpet sudah dipack, kerja rumah sudah selesai</p>
      </a>

      <a
        href={href({ page: 'orders', filter: 'unpaid' })}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-rose-400"
      >
        <p className="text-xs font-semibold text-slate-500 uppercase">Baki belum bayar</p>
        <p className="mt-1 text-xl font-extrabold sm:text-2xl text-rose-700">{formatMoney(summary.unpaid)}</p>
        <p className="mt-1 text-xs text-slate-500">{summary.unpaid_orders} tempahan belum dibayar penuh</p>
      </a>
    </div>
  )
}
