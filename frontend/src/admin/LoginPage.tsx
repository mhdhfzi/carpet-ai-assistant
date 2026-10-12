import { type FormEvent, useState } from 'react'
import { ApiError } from './api'
import { useAuth } from './auth'

// The public, read-only demo login (created by python -m app.seed_demo). Published on
// purpose: the server refuses every change from this account.
export const DEMO_EMAIL = 'demo@example.com'
export const DEMO_PASSWORD = 'kilau-demo-2026'

export function LoginPage({ notice }: { notice?: string }) {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await attempt(email, password)
  }

  const attempt = async (email: string, password: string) => {
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
        <div className="space-y-2 border-t border-line pt-5 text-center">
          <p className="text-sm text-ink-soft">Just looking? The demo account can see everything but change nothing.</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => attempt(DEMO_EMAIL, DEMO_PASSWORD)}
            className="w-full rounded-full py-3 font-semibold ring-1 ring-line hover:bg-foam disabled:opacity-50"
          >
            Try the demo account
          </button>
        </div>
      </form>
    </main>
  )
}
