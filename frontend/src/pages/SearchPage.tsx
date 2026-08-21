import { useState, type FormEvent } from 'react'
import { buildImportBody } from '../lib/importInput'

type Listing = { id: number; address: string; city: string; state: string; postal_code: string | null; county: string | null; asking_price: number | null; acreage: number | null; bedrooms: number | null; bathrooms: number | null; property_type: string | null; photo_url: string | null; listing_source: string; listing_date: string | null; is_watchlisted: boolean }
type Filters = { county: string; town: string; postal_code: string; min_price: string; max_price: string; min_acreage: string; bedrooms: string; property_type: string }
const initial: Filters = { county: '', town: '', postal_code: '', min_price: '', max_price: '', min_acreage: '', bedrooms: '', property_type: '' }

const IMPORT_STEPS = ['Normalizing input', 'Detecting duplicates', 'Importing property', 'Running enrichment', 'Underwriting', 'Opening property']

export default function SearchPage({ onOpenPipeline, onOpenProperty }: { onOpenPipeline: () => void; onOpenProperty: (id: number) => void }) {
  const [importValue, setImportValue] = useState('')
  const [importError, setImportError] = useState('')
  const [importing, setImporting] = useState(false)
  const [filters, setFilters] = useState(initial)
  const [results, setResults] = useState<Listing[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (key: keyof Filters, value: string) => setFilters((current) => ({ ...current, [key]: value }))

  async function searchAndAnalyze(event: FormEvent) {
    event.preventDefault()
    const { body, error } = buildImportBody(importValue)
    if (error || !body) { setImportError(error ?? 'Enter a valid input.'); return }
    setImporting(true); setImportError('')
    try {
      const response = await fetch('/api/properties/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (response.status === 409) {
        // The property already exists — take the user straight to it instead of erroring.
        const detail = (await response.json().catch(() => ({}))) as { detail?: string }
        const match = /id=(\d+)/.exec(detail.detail ?? '')
        if (match) { onOpenProperty(Number(match[1])); return }
        throw new Error('This property is already in your pipeline.')
      }
      if (response.status === 422) throw new Error('That input could not be understood. Paste a full address or a supported listing URL.')
      if (!response.ok) throw new Error('Import failed. Check the address or listing URL and try again.')
      const property = await response.json() as { id: number }
      onOpenProperty(property.id)
    } catch (reason) {
      setImportError((reason as Error).message)
    } finally {
      setImporting(false)
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage('')
    const payload = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== '').map(([key, value]) => [key, ['min_price', 'max_price', 'min_acreage', 'bedrooms'].includes(key) ? Number(value) : value]))
    try {
      const response = await fetch('/api/discovery/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!response.ok) throw new Error('Search could not be completed.')
      const data = await response.json() as Listing[]
      setResults(data); setMessage(data.length ? '' : 'No listings match these filters.')
    } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) }
  }
  async function watch(listing: Listing) { const response = await fetch(`/api/discovery/listings/${listing.id}/watchlist`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_watchlisted: !listing.is_watchlisted }) }); if (response.ok) setResults((items) => items.map((item) => item.id === listing.id ? { ...item, is_watchlisted: !item.is_watchlisted } : item)) }
  async function analyze(listing: Listing) {
    setBusy(true)
    const response = await fetch(`/api/discovery/listings/${listing.id}/analyze`, { method: 'POST' })
    setBusy(false)
    if (response.ok) { const created = await response.json() as { id: number }; onOpenProperty(created.id) }
    else if (response.status === 409) { const detail = (await response.json().catch(() => ({}))) as { detail?: string }; const match = /id=(\d+)/.exec(detail.detail ?? ''); if (match) onOpenProperty(Number(match[1])); else onOpenPipeline() }
    else setMessage('This listing could not be analyzed.')
  }

  return (
    <main className="discovery-page">
      <header className="discovery-header">
        <div><span className="eyebrow">Bistate</span><h1>Analyze any property.</h1><p>Start from a known address or listing, or discover new candidates.</p></div>
        <button className="secondary-button" onClick={onOpenPipeline}>Open pipeline</button>
      </header>

      <section className="universal-import" aria-label="Analyze a known property">
        <form onSubmit={searchAndAnalyze}>
          <label htmlFor="universal-input">Paste an address or listing URL</label>
          <div className="universal-row">
            <input
              id="universal-input"
              aria-label="Paste an address or listing URL"
              value={importValue}
              onChange={(event) => { setImportValue(event.target.value); if (importError) setImportError('') }}
              placeholder="123 Main St, Hudson, NY  ·  or a Zillow / Realtor / Redfin / LandWatch link"
              disabled={importing}
            />
            <button type="submit" disabled={importing}>{importing ? 'Analyzing…' : 'Search & Analyze'}</button>
          </div>
          <small className="universal-help">Zillow, Realtor, Redfin, LandWatch, or street address</small>
        </form>
        {importError && <p className="universal-error" role="alert">{importError}</p>}
        {importing && (
          <ol className="import-progress" aria-live="polite">
            {IMPORT_STEPS.map((step) => <li key={step}>{step}</li>)}
          </ol>
        )}
      </section>

      <section className="discover-section">
        <div className="discover-heading"><h2>Discover properties</h2><p>Sample candidates across the target Catskills markets (Sullivan, Delaware, Ulster). Illustrative until a licensed listing feed is connected — not live inventory.</p></div>
        <form className="filter-panel" onSubmit={search}>
          {([['county', 'County'], ['town', 'Town'], ['postal_code', 'ZIP code'], ['min_price', 'Min price'], ['max_price', 'Max price'], ['min_acreage', 'Min acreage'], ['bedrooms', 'Bedrooms']] as Array<[keyof Filters, string]>).map(([key, label]) => (
            <label key={key}>{label}<input aria-label={label} type={key.includes('price') || key === 'min_acreage' || key === 'bedrooms' ? 'number' : 'text'} value={filters[key]} onChange={(e) => set(key, e.target.value)} /></label>
          ))}
          <label>Property type<select aria-label="Property type" value={filters.property_type} onChange={(e) => set('property_type', e.target.value)}><option value="">Any type</option><option>Single Family</option><option>Land</option><option>Condo</option></select></label>
          <button>{busy ? 'Searching…' : 'Search listings'}</button>
        </form>
        {message && <p className="discovery-message">{message}</p>}
        <section className="listing-grid" aria-live="polite">
          {results.map((listing) => (
            <article className="listing-card" key={listing.id}>
              <img src={listing.photo_url ?? ''} alt={`Property at ${listing.address}`} />
              <div className="listing-body">
                <div className="listing-meta"><span>{listing.listing_source}</span><time>{listing.listing_date ? new Date(listing.listing_date).toLocaleDateString() : 'Date unavailable'}</time></div>
                <h2>{listing.address}</h2>
                <p>{listing.city}, {listing.state} {listing.postal_code} · {listing.county} County</p>
                <strong>${listing.asking_price?.toLocaleString() ?? '—'}</strong>
                <div className="listing-facts">{listing.bedrooms ?? '—'} bd · {listing.bathrooms ?? '—'} ba · {listing.acreage ?? '—'} acres · {listing.property_type}</div>
                <div className="listing-actions">
                  <button className="secondary-button" onClick={() => void watch(listing)}>{listing.is_watchlisted ? 'Saved to Watchlist' : 'Save to Watchlist'}</button>
                  <button onClick={() => void analyze(listing)} disabled={busy}>Analyze</button>
                </div>
              </div>
            </article>
          ))}
        </section>
      </section>
    </main>
  )
}
