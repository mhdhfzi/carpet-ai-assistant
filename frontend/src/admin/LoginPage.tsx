import { type FormEvent, useState } from 'react'
import { ApiError } from './api'
import { useAuth } from './auth'

export function LoginPage({ notice }: { notice?: string }) {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(email, password)
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? 'Incorrect email or password.'
          : 'Sign-in is unavailable right now. Please try again later.',
      )
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-mist p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-3xl bg-white p-8 shadow-lift ring-1 ring-line">
        <div>
          <p className="text-sm font-semibold text-ink-soft">Kilau Carpet Care</p>
          <h1 className="font-display text-2xl font-bold">Owner dashboard</h1>
        </div>

        {notice && !error && (
          <p role="status" className="rounded-xl bg-brand/20 px-3 py-2 text-sm">
            {notice}
          </p>
        )}
        {error && (
          <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-danger ring-1 ring-red-200">
            {error}
          </p>
        )}

        <label className="block space-y-1">
          <span className="text-sm font-semibold">Email</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl bg-foam px-3 py-2.5 outline-none focus:ring-2 focus:ring-brand"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm font-semibold">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl bg-foam px-3 py-2.5 outline-none focus:ring-2 focus:ring-brand"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-full bg-brand py-3 font-semibold text-ink hover:bg-brand-hover disabled:opacity-50"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
