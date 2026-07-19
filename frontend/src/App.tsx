import { useEffect, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

type EnrichmentField = { value: unknown; source: string; last_updated: string; confidence: number; missing_reason?: string | null }
type Underwriting = {
  dashboard: Record<string, number>
  renovation: Record<string, unknown>
  sensitivity: Record<string, unknown>
  projection: { levered_irr: number | null; years: Array<Record<string, number>> }
  assumptions: Record<string, unknown>
  traceability: Record<string, unknown>
}
type Property = {
  id: number; name: string; address: string; city: string; state: string; postal_code: string | null
  status: string; listing_source: string | null; listing_url: string | null; mls_number: string | null
  county: string | null; acreage: number | null; bedrooms: number | null; bathrooms: number | null
  square_feet: number | null; asking_price: number | null; annual_taxes: number | null; images: string[]
  description: string | null; agent: Record<string, unknown> | null; latitude: number | null; longitude: number | null
  enrichment_data: Record<string, EnrichmentField>; underwriting_output: Underwriting | null
  overall_score: number | null; buy_score: number | null; airbnb_score: number | null; wedding_score: number | null
  personal_use_score: number | null; confidence_score: number | null; pipeline_state: Record<string, string>; provider_errors: Record<string, unknown>
}
type Note = { id: number; body: string; author: string | null; created_at: string }
type Task = { id: number; title: string; assignee: string | null; due_date: string | null; completed: boolean }
type Document = { id: number; filename: string; document_type: string; size_bytes: number }
type Memo = { executive_summary: string; strengths: string[]; weaknesses: string[]; risks: string[]; comparable_properties: Array<Record<string, unknown>>; missing_information: string[] }

const tabs = ['Overview', 'Financials', 'Underwriting', 'Renovation', 'Airbnb', 'Wedding', 'Maps', 'Comparable Sales', 'Documents', 'Notes'] as const
const statuses = ['New', 'Reviewing', 'Underwriting', 'Needs Info', 'Approved', 'Rejected', 'Under Contract', 'Closed']
type Tab = typeof tabs[number]

export default function App() {
  const [properties, setProperties] = useState<Property[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('Overview')
  const [importValue, setImportValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notes, setNotes] = useState<Note[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [memo, setMemo] = useState<Memo | null>(null)

  const selected = properties.find((property) => property.id === selectedId) ?? null

  async function loadProperties(preferredId?: number) {
    const response = await fetch('/api/properties')
    if (!response.ok) throw new Error('Unable to load the acquisition pipeline.')
    const data = await response.json() as Property[]
    setProperties(data)
    setSelectedId(preferredId ?? selectedId ?? data[0]?.id ?? null)
  }

  async function loadWorkspace(propertyId: number) {
    const [notesResponse, tasksResponse, documentsResponse, memoResponse] = await Promise.all([
      fetch(`/api/properties/${propertyId}/notes`), fetch(`/api/properties/${propertyId}/tasks`),
      fetch(`/api/properties/${propertyId}/documents`), fetch(`/api/properties/${propertyId}/report`),
    ])
    setNotes(notesResponse.ok ? await notesResponse.json() as Note[] : [])
    setTasks(tasksResponse.ok ? await tasksResponse.json() as Task[] : [])
    setDocuments(documentsResponse.ok ? await documentsResponse.json() as Document[] : [])
    setMemo(memoResponse.ok ? await memoResponse.json() as Memo : null)
  }

  // The initial pipeline load should run once; later mutations refresh it explicitly.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void loadProperties().catch((reason: Error) => setError(reason.message)) }, [])
  useEffect(() => { if (selectedId) void loadWorkspace(selectedId) }, [selectedId])

  async function importProperty(event: FormEvent) {
    event.preventDefault()
    if (!importValue.trim()) return
    setBusy(true); setError('')
    const value = importValue.trim()
    const body = value.startsWith('http') ? { listing_url: value } : (/^MLS[-\s#]/i.test(value) ? { mls_number: value } : { raw_address: value })
    try {
      const response = await fetch('/api/properties/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!response.ok) throw new Error('Import failed. Check the listing URL, address, or MLS number.')
      const property = await response.json() as Property
      setImportValue(''); await loadProperties(property.id); await loadWorkspace(property.id)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  async function updateStatus(status: string) {
    if (!selected) return
    const response = await fetch(`/api/properties/${selected.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) })
    if (response.ok) await loadProperties(selected.id)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">B</span><div><strong>Bistate</strong><small>Acquisition OS</small></div></div>
        <div className="pipeline-label"><span>Property pipeline</span><span>{properties.length}</span></div>
        <nav className="property-list" aria-label="Property pipeline">
          {properties.map((property) => <button key={property.id} className={`property-row ${property.id === selectedId ? 'active' : ''}`} onClick={() => { setSelectedId(property.id); setActiveTab('Overview') }}><span className="property-score">{Math.round(property.overall_score ?? 0)}</span><span><strong>{property.name}</strong><small>{property.city}, {property.state}</small></span><StatusDot status={property.status} /></button>)}
          {!properties.length && <div className="empty-sidebar">Import your first opportunity to start the pipeline.</div>}
        </nav>
        <div className="sidebar-footer"><span className="online-dot" /> Workbook engine ready</div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <form className="import-form" onSubmit={importProperty}>
            <span className="search-icon">＋</span>
            <input aria-label="Listing URL, address, or MLS number" value={importValue} onChange={(event) => setImportValue(event.target.value)} placeholder="Paste a Zillow, Realtor, Redfin, Airbnb, LoopNet URL, address, or MLS #" />
            <button disabled={busy}>{busy ? 'Analyzing…' : 'Import & analyze'}</button>
          </form>
        </header>
        {error && <div className="error-banner">{error}</div>}
        {selected ? <>
          <section className="property-hero">
            <div><div className="eyebrow">{selected.listing_source ?? 'Manual import'} {selected.mls_number ? `· ${selected.mls_number}` : ''}</div><h1>{selected.name}</h1><p>{selected.address}, {selected.city}, {selected.state} {selected.postal_code}</p></div>
            <div className="hero-actions"><select aria-label="Pipeline status" value={selected.status} onChange={(event) => void updateStatus(event.target.value)}>{statuses.map((status) => <option key={status}>{status}</option>)}</select>{selected.listing_url && <a href={selected.listing_url} target="_blank" rel="noreferrer">View listing ↗</a>}</div>
          </section>
          <KpiGrid property={selected} />
          <PipelineProgress property={selected} />
          <nav className="tabs" aria-label="Property sections">{tabs.map((tab) => <button key={tab} className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)}>{tab}</button>)}</nav>
          <section className="tab-content"><TabContent tab={activeTab} property={selected} memo={memo} notes={notes} tasks={tasks} documents={documents} refresh={() => loadWorkspace(selected.id)} /></section>
        </> : <EmptyState />}
      </main>
    </div>
  )
}

function PipelineProgress({ property }: { property: Property }) { return <section className="panel"><div className="panel-title"><span>Analysis progress</span><span>{Object.values(property.pipeline_state).filter((value) => value === 'completed').length}/6 complete</span></div><div className="chip-list">{Object.entries(property.pipeline_state).map(([step, state]) => <span key={step}>{labelize(step)}: {state}</span>)}</div>{Object.keys(property.provider_errors).length > 0 && <p className="muted">Some providers failed; partial results were preserved.</p>}</section> }
function KpiGrid({ property }: { property: Property }) {
  const output = property.underwriting_output
  const dashboard = output?.dashboard ?? {}
  const capRate = dashboard.noi_before_debt && dashboard.purchase_price ? dashboard.noi_before_debt / dashboard.purchase_price : null
  const values = [
    ['Overall score', score(property.overall_score), 'score'], ['Cash required', money(dashboard.total_cash_required), 'money'],
    ['Cash-on-cash', percent(dashboard.cash_on_cash_return), 'return'], ['IRR', percent(output?.projection.levered_irr), 'return'],
    ['Cap rate', percent(capRate), 'return'], ['Debt coverage', dashboard.dscr ? `${dashboard.dscr.toFixed(2)}×` : '—', 'ratio'],
    ['Renovation', money(dashboard.renovation_contingency), 'money'], ['Confidence', score(property.confidence_score), 'score'],
  ]
  return <section className="kpi-grid">{values.map(([label, value, kind]) => <article key={label}><span>{label}</span><strong className={kind}>{value}</strong></article>)}</section>
}

function TabContent({ tab, property, memo, notes, tasks, documents, refresh }: { tab: Tab; property: Property; memo: Memo | null; notes: Note[]; tasks: Task[]; documents: Document[]; refresh: () => Promise<void> }) {
  const output = property.underwriting_output
  if (tab === 'Overview') return <Overview property={property} memo={memo} tasks={tasks} refresh={refresh} />
  if (tab === 'Financials') return <DataSection title="Workbook financial summary" data={output?.dashboard ?? {}} />
  if (tab === 'Underwriting') return <div className="two-column"><DataSection title="Assumptions used" data={output?.assumptions ?? {}} /><DataSection title="Traceability" data={output?.traceability ?? {}} /></div>
  if (tab === 'Renovation') return <DataSection title="Renovation range and categories" data={output?.renovation ?? {}} />
  if (tab === 'Airbnb') return <Suitability title="Airbnb suitability" score={property.airbnb_score} field={property.enrichment_data.airbnb_suitability} />
  if (tab === 'Wedding') return <Suitability title="Wedding suitability" score={property.wedding_score} field={property.enrichment_data.wedding_suitability} />
  if (tab === 'Maps') return <EnrichmentGrid property={property} />
  if (tab === 'Comparable Sales') return <Comparables memo={memo} />
  if (tab === 'Documents') return <Documents propertyId={property.id} documents={documents} refresh={refresh} />
  return <NotesAndTasks propertyId={property.id} notes={notes} tasks={tasks} refresh={refresh} />
}

function Overview({ property, memo, tasks, refresh }: { property: Property; memo: Memo | null; tasks: Task[]; refresh: () => Promise<void> }) {
  return <div className="overview-grid">{property.images.length > 0 && <article className="panel"><div className="panel-title"><span>Listing gallery</span></div><div className="chip-list">{property.images.map((image) => <a key={image} href={image} target="_blank" rel="noreferrer">Listing photo ↗</a>)}</div></article>}<article className="panel memo-panel"><div className="panel-title"><span>Investment memo</span><span className="confidence-pill">{Math.round(property.confidence_score ?? 0)}% confidence</span></div><p className="summary">{memo?.executive_summary ?? 'Investment memo is being prepared.'}</p><MemoList title="Strengths" items={memo?.strengths ?? []} tone="positive" /><MemoList title="Risks & weaknesses" items={[...(memo?.weaknesses ?? []), ...(memo?.risks ?? [])]} tone="warning" /></article><article className="panel"><div className="panel-title"><span>Property facts</span></div><dl className="facts"><Fact label="Asking price" value={money(property.asking_price)} /><Fact label="Annual taxes" value={money(property.annual_taxes)} /><Fact label="Beds / baths" value={`${property.bedrooms ?? '—'} / ${property.bathrooms ?? '—'}`} /><Fact label="Square feet" value={property.square_feet?.toLocaleString() ?? '—'} /><Fact label="Acreage" value={property.acreage?.toString() ?? '—'} /><Fact label="County" value={property.county ?? '—'} /></dl></article><article className="panel task-panel"><div className="panel-title"><span>Open tasks</span><span>{tasks.filter((task) => !task.completed).length}</span></div>{tasks.slice(0, 4).map((task) => <TaskRow key={task.id} propertyId={property.id} task={task} refresh={refresh} />)}{!tasks.length && <p className="muted">No tasks yet. Add one in Notes.</p>}</article><article className="panel missing-panel"><div className="panel-title"><span>Missing information</span><span>{memo?.missing_information.length ?? 0}</span></div><div className="chip-list">{memo?.missing_information.map((item) => <span key={item}>{labelize(item)}</span>)}</div></article></div>
}

function EnrichmentGrid({ property }: { property: Property }) { return <div className="enrichment-grid">{Object.entries(property.enrichment_data).map(([key, field]) => <article className="panel" key={key}><div className="panel-title"><span>{labelize(key)}</span><span>{Math.round(field.confidence * 100)}%</span></div><strong className="enrichment-value">{field.value === null ? 'Needs verification' : String(field.value)}</strong><small>{field.source}</small><small>Updated {new Date(field.last_updated).toLocaleDateString()}{Date.now() - new Date(field.last_updated).getTime() > 30 * 86400000 ? ' · Stale' : ''}</small>{field.missing_reason && <small>{field.missing_reason}</small>}</article>)}</div> }
function Suitability({ title, score: value, field }: { title: string; score: number | null; field?: EnrichmentField }) { return <article className="panel suitability"><div className="score-ring">{Math.round(value ?? 0)}</div><div><div className="eyebrow">Bistate suitability model</div><h2>{title}</h2><p>{field?.value === null || !field ? 'Provider facts are incomplete. Verify local regulations, demand, and physical feasibility before approval.' : 'The initial suitability score uses available property facts. Validate it with market and regulatory diligence.'}</p><small>Source: {field?.source ?? 'Not available'} · Confidence {Math.round((field?.confidence ?? 0) * 100)}%</small></div></article> }
function DataSection({ title, data }: { title: string; data: Record<string, unknown> }) { return <article className="panel data-panel"><div className="panel-title"><span>{title}</span></div><div className="data-grid">{Object.entries(data).map(([key, value]) => <div key={key}><span>{labelize(key)}</span><strong>{formatValue(value)}</strong></div>)}</div></article> }
function Comparables({ memo }: { memo: Memo | null }) { return <article className="panel"><div className="panel-title"><span>Verified comparable sales</span><span>{memo?.comparable_properties.length ?? 0}</span></div>{memo?.comparable_properties.length ? <div className="data-grid">{memo.comparable_properties.map((item, index) => <div key={index}><strong>{String(item.address)}</strong><span>{money(item.sale_price as number | null)} · {String(item.square_feet ?? '—')} sq ft</span></div>)}</div> : <p className="muted">No verified comparable sales have been attached. Workbook sample comparables remain clearly marked as unverified.</p>}</article> }

function Documents({ propertyId, documents, refresh }: { propertyId: number; documents: Document[]; refresh: () => Promise<void> }) {
  const [type, setType] = useState('inspection')
  async function upload(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; const data = new FormData(); data.append('document_type', type); data.append('file', file); await fetch(`/api/properties/${propertyId}/documents`, { method: 'POST', body: data }); await refresh() }
  return <article className="panel"><div className="panel-title"><span>Due diligence documents</span><div className="upload-controls"><select value={type} onChange={(event) => setType(event.target.value)}><option value="inspection">Inspection</option><option value="survey">Survey</option><option value="permit">Permit</option><option value="photo">Photo</option><option value="floor_plan">Floor plan</option></select><label className="upload-button">Upload file<input type="file" onChange={(event) => void upload(event)} /></label></div></div><div className="document-list">{documents.map((document) => <a key={document.id} href={`/api/properties/${propertyId}/documents/${document.id}/download`}><span className="file-icon">▤</span><span><strong>{document.filename}</strong><small>{labelize(document.document_type)} · {Math.ceil(document.size_bytes / 1024)} KB</small></span><span>Download</span></a>)}{!documents.length && <p className="muted">Upload inspections, surveys, permits, photos, or floor plans.</p>}</div></article>
}

function NotesAndTasks({ propertyId, notes, tasks, refresh }: { propertyId: number; notes: Note[]; tasks: Task[]; refresh: () => Promise<void> }) {
  const [note, setNote] = useState(''); const [task, setTask] = useState('')
  async function add(path: 'notes' | 'tasks', body: Record<string, string>) { await fetch(`/api/properties/${propertyId}/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); await refresh() }
  return <div className="two-column"><article className="panel"><div className="panel-title"><span>Internal notes</span></div><form className="inline-create" onSubmit={(event) => { event.preventDefault(); if (note) void add('notes', { body: note }).then(() => setNote('')) }}><input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add a diligence note…" /><button>Add</button></form><div className="note-list">{notes.map((item) => <div key={item.id}><p>{item.body}</p><small>{item.author ?? 'Bistate team'} · {new Date(item.created_at).toLocaleDateString()}</small></div>)}</div></article><article className="panel"><div className="panel-title"><span>Tasks</span></div><form className="inline-create" onSubmit={(event) => { event.preventDefault(); if (task) void add('tasks', { title: task }).then(() => setTask('')) }}><input value={task} onChange={(event) => setTask(event.target.value)} placeholder="Call broker, verify zoning…" /><button>Add</button></form>{tasks.map((item) => <TaskRow key={item.id} propertyId={propertyId} task={item} refresh={refresh} />)}</article></div>
}

function TaskRow({ propertyId, task, refresh }: { propertyId: number; task: Task; refresh: () => Promise<void> }) { return <label className={`task-row ${task.completed ? 'complete' : ''}`}><input type="checkbox" checked={task.completed} onChange={async (event) => { await fetch(`/api/properties/${propertyId}/tasks/${task.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ completed: event.target.checked }) }); await refresh() }} /><span><strong>{task.title}</strong><small>{task.assignee ?? 'Unassigned'}{task.due_date ? ` · Due ${task.due_date}` : ''}</small></span></label> }
function MemoList({ title, items, tone }: { title: string; items: string[]; tone: string }) { return <div className={`memo-list ${tone}`}><strong>{title}</strong>{items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="muted">None identified yet.</p>}</div> }
function Fact({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div> }
function StatusDot({ status }: { status: string }) { return <span className={`status-dot status-${status.toLowerCase().replace(/ /g, '-')}`} title={status} /> }
function EmptyState() { return <section className="empty-state"><div className="empty-icon">⌂</div><h1>Build your acquisition pipeline</h1><p>Paste a listing URL, property address, or MLS number above. Bistate will create the property, run enrichment, execute the workbook underwriting engine, and prepare an investment memo.</p></section> }
function labelize(value: string) { return value.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase()) }
function money(value: number | null | undefined) { return value == null ? '—' : value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }) }
function percent(value: number | null | undefined) { return value == null ? '—' : `${(value * 100).toFixed(1)}%` }
function score(value: number | null | undefined) { return value == null ? '—' : `${Math.round(value)}/100` }
function formatValue(value: unknown): string { if (typeof value === 'number') return Math.abs(value) < 1 ? percent(value) : value.toLocaleString(undefined, { maximumFractionDigits: 2 }); if (value === null) return '—'; if (Array.isArray(value)) return `${value.length} records`; if (typeof value === 'object') return 'View detailed output'; return String(value) }
