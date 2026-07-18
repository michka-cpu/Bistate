import { useEffect, useState } from 'react'

type HealthState = 'checking' | 'online' | 'offline'

function App() {
  const [health, setHealth] = useState<HealthState>('checking')

  useEffect(() => {
    async function checkHealth() {
      try {
        const response = await fetch('/api/health')
        const body: { status?: string } = await response.json()
        setHealth(response.ok && body.status === 'ok' ? 'online' : 'offline')
      } catch {
        setHealth('offline')
      }
    }

    void checkHealth()
  }, [])

  const statusStyles = {
    checking: 'bg-amber-400',
    online: 'bg-emerald-400',
    offline: 'bg-rose-400',
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-slate-100 sm:px-12">
      <div className="mx-auto max-w-5xl">
        <header className="flex items-center justify-between border-b border-slate-800 pb-8">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-emerald-400">Bistate</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Property workspace</h1>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-300" aria-live="polite">
            <span className={`h-2.5 w-2.5 rounded-full ${statusStyles[health]}`} />
            API {health}
          </div>
        </header>

        <section className="mt-12 rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-2xl shadow-black/20">
          <p className="text-sm font-medium text-emerald-400">FIRST MILESTONE</p>
          <h2 className="mt-3 text-2xl font-semibold">Your real-estate decisions, in one place.</h2>
          <p className="mt-4 max-w-2xl leading-7 text-slate-400">
            Bistate is ready to track properties. Underwriting tools will arrive in a future milestone.
          </p>
        </section>

        <section className="mt-6 grid gap-6 md:grid-cols-3">
          {['Properties', 'Analysis', 'Portfolio'].map((label) => (
            <article key={label} className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="font-medium">{label}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">Coming soon</p>
            </article>
          ))}
        </section>
      </div>
    </main>
  )
}

export default App
