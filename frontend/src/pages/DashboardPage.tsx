import { useEffect, useState } from 'react'
import { AcquisitionPipeline, Dashboard, KpiGrid, PipelineProgress, TabContent, StatusDot, EmptyState } from '../components/PropertyDetailPage'
import type { FormEvent } from 'react'

type EnrichmentField = { value: unknown; source: string; retrieval_status?: 'live' | 'unavailable'; last_updated: string | null; confidence: number; missing_reason?: string | null }
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
  personal_use_score: number | null; confidence_score: number | null; is_favorite: boolean; is_pinned: boolean; pipeline_state: Record<string, string>; provider_errors: Record<string, unknown>; created_at: string; updated_at: string
}
type Note = { id: number; body: string; author: string | null; created_at: string }
type Task = { id: number; title: string; assignee: string | null; due_date: string | null; completed: boolean }
type Document = { id: number; filename: string; document_type: string; size_bytes: number }
type Memo = { executive_summary: string; strengths: string[]; weaknesses: string[]; risks: string[]; comparable_properties: Array<Record<string, unknown>>; missing_information: string[] }

const tabs = ['Overview', 'Listing', 'Financials', 'Underwriting', 'Renovation', 'Airbnb', 'Wedding', 'Maps', 'Comparable Sales', 'Documents', 'Notes', 'Activity Timeline'] as const
const statuses = ['New', 'Reviewing', 'Underwriting', 'Needs Info', 'Approved', 'Rejected', 'Under Contract', 'Closed']
type Tab = typeof tabs[number]

export default function DashboardPage() {
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
  const [search, setSearch] = useState('')
  const [comparison, setComparison] = useState<number[]>([])

  const selected = properties.find((property) => property.id === selectedId) ?? null
  const visibleProperties = properties.filter((property) => `${property.address} ${property.county ?? ''} ${property.status}`.toLowerCase().includes(search.toLowerCase()))

  async function loadProperties(preferredId?: number) {
    const response = await fetch('/api/properties')
    if (!response.ok) throw new Error('Unable to load the acquisition pipeline.')
    const payload = await response.json() as unknown
    // Older records and unavailable providers can legitimately omit collections.
    // Treat any non-list response as an empty pipeline instead of letting the UI
    // fail while it is trying to render a recoverable state.
    const data = Array.isArray(payload) ? payload as Property[] : []
    setProperties(data)
    setSelectedId(preferredId ?? selectedId ?? data[0]?.id ?? null)
  }

  async function loadWorkspace(propertyId: number) {
    const [notesResponse, tasksResponse, documentsResponse, memoResponse] = await Promise.all([
      fetch(`/api/properties/${propertyId}/notes`), fetch(`/api/properties/${propertyId}/tasks`),
      fetch(`/api/properties/${propertyId}/documents`), fetch(`/api/properties/${propertyId}/report`),
    ])
    const listOrEmpty = async <T,>(response: Response): Promise<T[]> => {
      if (!response.ok) return []
      const payload = await response.json() as unknown
      return Array.isArray(payload) ? payload as T[] : []
    }
    setNotes(await listOrEmpty<Note>(notesResponse))
    setTasks(await listOrEmpty<Task>(tasksResponse))
    setDocuments(await listOrEmpty<Document>(documentsResponse))
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

  async function updatePreference(propertyId: number, preference: Record<string, boolean>) { const response = await fetch(`/api/properties/${propertyId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preference) }); if (response.ok) await loadProperties(propertyId) }

  async function updateStatus(status: string) {
    if (!selected) return
    const response = await fetch(`/api/properties/${selected.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) })
    if (response.ok) await loadProperties(selected.id)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">B</span><div><strong>Bistate</strong><small>Acquisition OS</small></div></div>
        <input className="property-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search address, county, status…" />
        <div className="pipeline-label"><span>Property pipeline</span><span>{properties.length}</span></div>
        <nav className="property-list" aria-label="Property pipeline">
          {visibleProperties.map((property) => <div key={property.id} className={`property-row ${property.id === selectedId ? 'active' : ''}`}><button onClick={() => { setSelectedId(property.id); setActiveTab('Overview') }}><span className="property-score">{Math.round(property.overall_score ?? 0)}</span><span><strong>{property.name}</strong><small>{property.city}, {property.state}</small></span><StatusDot status={property.status} /></button><button className="favorite" onClick={() => void updatePreference(property.id, { is_favorite: !property.is_favorite })}>{property.is_favorite ? '★' : '☆'}</button><label className="compare-toggle"><input type="checkbox" checked={comparison.includes(property.id)} onChange={() => setComparison((items) => items.includes(property.id) ? items.filter((id) => id !== property.id) : [...items, property.id])} /> Compare</label></div>)}
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
          <Dashboard properties={properties} />
          <KpiGrid property={selected} />
          <PipelineProgress property={selected} onRetry={() => void fetch(`/api/properties/${selected.id}/refresh`, { method: 'POST' }).then(() => loadProperties(selected.id))} />
          <AcquisitionPipeline property={selected} />
          <nav className="tabs" aria-label="Property sections">{tabs.map((tab) => <button key={tab} className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)}>{tab}</button>)}</nav>
          <section className="tab-content"><TabContent tab={activeTab} property={selected} properties={properties.filter((item) => comparison.includes(item.id))} memo={memo} notes={notes} tasks={tasks} documents={documents as never} refresh={() => loadWorkspace(selected.id)} /></section>
        </> : <EmptyState />}
      </main>
    </div>
  )
}
