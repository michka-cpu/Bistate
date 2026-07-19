import { FormEvent, ReactNode, useEffect, useState } from 'react'

type HealthState = 'checking' | 'online' | 'offline'
type Property = {
  id: number
  name: string
  address: string
  city: string
  state: string
  postal_code: string | null
  notes: string | null
}
type UnderwritingResult = {
  scenario: string
  dashboard: Record<string, number>
  renovation: { underwriting_renovation_budget: number, detailed_base_total: number, variance: number, low_total: number, high_total: number, inconsistency_note: string }
  zero_revenue_affordability: { status: string, monthly_owner_cash_requirement: number, zero_revenue_monthly_affordability_ceiling: number | null }
  projection: { years: Array<{ year: number, loan_balance: number, annual_cash_flow: number, sale_proceeds: number }>, levered_irr: number | null }
  sensitivity: { purchase_price: Record<string, number>, renovation_budget: Record<string, number> }
  comparables: { warning: string }
}
type PropertyForm = Omit<Property, 'id'>

const emptyProperty: PropertyForm = { name: '', address: '', city: '', state: '', postal_code: '', notes: '' }

function App() {
  const [health, setHealth] = useState<HealthState>('checking')
  const [properties, setProperties] = useState<Property[]>([])
  const [selected, setSelected] = useState<Property | null>(null)
  const [form, setForm] = useState<PropertyForm>(emptyProperty)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')
  const [underwriting, setUnderwriting] = useState<UnderwritingResult | null>(null)
  const [scenario, setScenario] = useState<'A' | 'B'>('A')

  async function loadProperties() {
    const response = await fetch('/api/properties')
    if (!response.ok) throw new Error('Unable to load properties')
    setProperties(await response.json() as Property[])
  }

  useEffect(() => {
    void fetch('/api/health')
      .then(async (response) => response.ok && (await response.json()).status === 'ok' ? setHealth('online') : setHealth('offline'))
      .catch(() => setHealth('offline'))
    void loadProperties().catch(() => setError('Properties could not be loaded.'))
    void loadUnderwriting().catch(() => setError('Underwriting could not be calculated.'))
  }, [])

  async function loadUnderwriting(selectedScenario = scenario) {
    const response = await fetch('/api/underwriting/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario: selectedScenario }) })
    if (!response.ok) throw new Error('Unable to calculate underwriting')
    setUnderwriting(await response.json() as UnderwritingResult)
  }

  function beginCreate() {
    setSelected(null)
    setForm(emptyProperty)
    setEditing(true)
    setError('')
  }

  function beginEdit(property: Property) {
    setSelected(property)
    setForm(property)
    setEditing(true)
    setError('')
  }

  async function saveProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const endpoint = selected ? `/api/properties/${selected.id}` : '/api/properties'
    const response = await fetch(endpoint, {
      method: selected ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (!response.ok) {
      setError('Property could not be saved. Check the required fields.')
      return
    }
    const saved = await response.json() as Property
    await loadProperties()
    setSelected(saved)
    setEditing(false)
  }

  async function deleteProperty(property: Property) {
    if (!window.confirm(`Delete ${property.name}?`)) return
    const response = await fetch(`/api/properties/${property.id}`, { method: 'DELETE' })
    if (!response.ok) {
      setError('Property could not be deleted.')
      return
    }
    await loadProperties()
    setSelected(null)
    setEditing(false)
  }

  const statusStyles = { checking: 'bg-amber-400', online: 'bg-emerald-400', offline: 'bg-rose-400' }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100 sm:px-12">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between border-b border-slate-800 pb-7">
          <div><p className="text-sm font-semibold uppercase tracking-[0.28em] text-emerald-400">Bistate</p><h1 className="mt-2 text-3xl font-semibold">Properties</h1></div>
          <div className="flex items-center gap-2 text-sm text-slate-300"><span className={`h-2.5 w-2.5 rounded-full ${statusStyles[health]}`} />API {health}</div>
        </header>

        {underwriting && <section className="mt-8 rounded-xl border border-emerald-900 bg-slate-900 p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-400">Underwriting · Scenario {underwriting.scenario}</p><h2 className="mt-1 text-xl font-semibold">Primary workbook results</h2></div><div className="flex gap-2"><select aria-label="Underwriting scenario" value={scenario} onChange={(event) => { const next = event.target.value as 'A' | 'B'; setScenario(next); void loadUnderwriting(next) }} className="rounded border border-slate-700 bg-slate-950 px-3 text-sm"><option value="A">Scenario A · Second Home</option><option value="B">Scenario B · Investment</option></select><button onClick={() => void loadUnderwriting()} className="rounded border border-emerald-700 px-3 py-2 text-sm text-emerald-300">Recalculate</button></div></div><div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{([['Total cash required', 'total_cash_required', '$'], ['NOI before debt', 'noi_before_debt', '$'], ['DSCR', 'dscr', '×'], ['Cash-on-cash return', 'cash_on_cash_return', '%']] as const).map(([label, key, suffix]) => <div key={key} className="rounded-lg bg-slate-950 p-4"><p className="text-sm text-slate-400">{label}</p><p className="mt-1 text-xl font-semibold">{suffix === '%' ? `${(underwriting.dashboard[key] * 100).toFixed(1)}%` : `${suffix}${underwriting.dashboard[key].toLocaleString(undefined, { maximumFractionDigits: 0 })}`}</p></div>)}</div><div className="mt-5 grid gap-4 lg:grid-cols-3"><Panel title="Renovation summary"><p>Underwriting budget: {money(underwriting.renovation.underwriting_renovation_budget)}</p><p>Category range: {money(underwriting.renovation.low_total)} – {money(underwriting.renovation.high_total)}</p><p>Detailed base: {money(underwriting.renovation.detailed_base_total)}</p><p className="mt-2 text-amber-300">Variance: {money(underwriting.renovation.variance)}. {underwriting.renovation.inconsistency_note}</p></Panel><Panel title="Zero-revenue affordability"><p className="font-semibold">{underwriting.zero_revenue_affordability.status}</p><p>Owner cash required: {money(underwriting.zero_revenue_affordability.monthly_owner_cash_requirement)} / month</p><p>Ceiling: {underwriting.zero_revenue_affordability.zero_revenue_monthly_affordability_ceiling === null ? 'Not provided — needs review' : money(underwriting.zero_revenue_affordability.zero_revenue_monthly_affordability_ceiling)}</p></Panel><Panel title="Sensitivity"><p>Purchase: {money(underwriting.sensitivity.purchase_price['-20%'])} to {money(underwriting.sensitivity.purchase_price['+20%'])}</p><p>Renovation: {money(underwriting.sensitivity.renovation_budget['-20%'])} to {money(underwriting.sensitivity.renovation_budget['+20%'])}</p><p className="mt-2 text-slate-400">Occupancy and ADR sensitivity is included in the API response.</p></Panel></div><div className="mt-5 overflow-x-auto"><h3 className="font-semibold">10-year projection</h3><table className="mt-2 w-full text-sm"><thead className="text-left text-slate-400"><tr><th>Year</th><th>Loan balance</th><th>Cash flow</th><th>Sale proceeds</th></tr></thead><tbody>{underwriting.projection.years.map((year) => <tr key={year.year} className="border-t border-slate-800"><td>{year.year}</td><td>{money(year.loan_balance)}</td><td>{money(year.annual_cash_flow)}</td><td>{money(year.sale_proceeds)}</td></tr>)}</tbody></table><p className="mt-2">Levered IRR: {underwriting.projection.levered_irr === null ? 'N/A' : `${(underwriting.projection.levered_irr * 100).toFixed(1)}%`}</p></div><p className="mt-5 rounded bg-amber-950 p-3 text-sm text-amber-200">Comparable data warning: {underwriting.comparables.warning}</p></section>}

        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Property list</h2><button onClick={beginCreate} className="rounded-md bg-emerald-500 px-3 py-2 text-sm font-medium text-slate-950">Add property</button></div>
            {properties.length === 0 ? <p className="mt-6 text-sm text-slate-400">No properties yet. Add your first property to begin.</p> : <ul className="mt-4 divide-y divide-slate-800">{properties.map((property) => <li key={property.id}><button onClick={() => { setSelected(property); setEditing(false) }} className="w-full py-4 text-left"><span className="block font-medium">{property.name}</span><span className="text-sm text-slate-400">{property.city}, {property.state}</span></button></li>)}</ul>}
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            {error && <p className="mb-4 rounded bg-rose-950 p-3 text-sm text-rose-200">{error}</p>}
            {editing ? <PropertyEditor form={form} setForm={setForm} onSave={saveProperty} onCancel={() => setEditing(false)} /> : selected ? <PropertyDetail property={selected} onEdit={() => beginEdit(selected)} onDelete={() => void deleteProperty(selected)} /> : <div className="py-16 text-center text-slate-400">Select a property to view its details.</div>}
          </section>
        </div>
      </div>
    </main>
  )
}

function money(value: number) { return value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }) }
function Panel({ title, children }: { title: string, children: ReactNode }) { return <div className="rounded-lg bg-slate-950 p-4 text-sm"><h3 className="mb-2 font-semibold">{title}</h3>{children}</div> }

function PropertyEditor({ form, setForm, onSave, onCancel }: { form: PropertyForm; setForm: (value: PropertyForm) => void; onSave: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void }) {
  const update = (key: keyof PropertyForm, value: string) => setForm({ ...form, [key]: value })
  return <form onSubmit={onSave}><h2 className="text-lg font-semibold">{form.name ? 'Edit property' : 'New property'}</h2><div className="mt-5 grid gap-4 sm:grid-cols-2">{(['name', 'address', 'city', 'state', 'postal_code'] as const).map((key) => <label key={key} className="text-sm capitalize text-slate-300">{key.replace('_', ' ')}<input required={key !== 'postal_code'} value={form[key] ?? ''} onChange={(event) => update(key, event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-slate-100" /></label>)}</div><label className="mt-4 block text-sm text-slate-300">Notes<textarea value={form.notes ?? ''} onChange={(event) => update('notes', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-slate-100" /></label><div className="mt-5 flex gap-3"><button className="rounded bg-emerald-500 px-4 py-2 font-medium text-slate-950">Save</button><button type="button" onClick={onCancel} className="rounded border border-slate-700 px-4 py-2">Cancel</button></div></form>
}

function PropertyDetail({ property, onEdit, onDelete }: { property: Property; onEdit: () => void; onDelete: () => void }) {
  return <div><div className="flex items-start justify-between"><div><h2 className="text-xl font-semibold">{property.name}</h2><p className="mt-1 text-slate-400">{property.address}<br />{property.city}, {property.state} {property.postal_code}</p></div><div className="flex gap-2"><button onClick={onEdit} className="rounded border border-slate-700 px-3 py-2 text-sm">Edit</button><button onClick={onDelete} className="rounded bg-rose-500 px-3 py-2 text-sm text-white">Delete</button></div></div>{property.notes && <p className="mt-6 whitespace-pre-wrap border-t border-slate-800 pt-5 text-slate-300">{property.notes}</p>}</div>
}

export default App
