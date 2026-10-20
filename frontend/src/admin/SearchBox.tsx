import { SearchIcon } from './icons'

/** The search box above a work list: filters as you type; ✕ clears it. */
export function SearchBox({
  value,
  onChange,
  label,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  label: string
  placeholder: string
}) {
  return (
    <div className="relative">
      <label>
        <span className="sr-only">{label}</span>
        <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pr-10 pl-9 text-sm focus:ring-2 focus:ring-amber-500 focus:outline-none [&::-webkit-search-cancel-button]:hidden"
        />
      </label>
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Kosongkan carian"
          className="absolute top-1/2 right-2 grid size-7 -translate-y-1/2 place-items-center rounded-full text-slate-500 hover:bg-slate-100"
        >
          ✕
        </button>
      )}
    </div>
  )
}
