/* eslint-disable no-undef */
// @ts-nocheck
import { useEffect, useState } from 'react'
import { PropertyIntelligence } from './PropertyIntelligence'
import { AnalysisIncomplete } from './AnalysisIncomplete'
import { analysisIncomplete } from '../lib/analysis'


export function TabContent({ tab, property, properties, memo, notes, tasks, documents, valuation, refresh, onResolve, onRefresh, liveProvidersOff }: { tab: Tab; property: Property; properties: Property[]; memo: Memo | null; notes: Note[]; tasks: Task[]; documents: Document[]; valuation: Valuation | null; refresh: () => Promise<void>; onResolve?: (address?: string) => void; onRefresh?: () => void; liveProvidersOff?: boolean }) {
  const output = property.underwriting_output
  const incomplete = analysisIncomplete(property)
  if (tab === 'Overview') return <Overview property={property} memo={memo} tasks={tasks} refresh={refresh} onResolve={onResolve} liveProvidersOff={liveProvidersOff} />
  if (tab === 'Listing') return <ListingSection property={property} onResolve={onResolve} onRefresh={onRefresh} />
  if (tab === 'Property Intelligence') return <PropertyIntelligence propertyId={property.id} onRefreshed={refresh} />
  if (tab === 'Activity Timeline') return <ActivityTimeline property={property} notes={notes} documents={documents} />
  if (tab === 'Financials') return incomplete ? <AnalysisIncomplete property={property} heading="Financials — analysis incomplete" context="workbook financial output" /> : <DataSection title="Workbook financial summary" data={output?.dashboard ?? {}} />
  if (tab === 'Underwriting') return incomplete ? <AnalysisIncomplete property={property} heading="Underwriting — analysis incomplete" context="workbook assumptions and traceability" /> : <div className="two-column"><DataSection title="Assumptions used" data={output?.assumptions ?? {}} /><DataSection title="Traceability" data={output?.traceability ?? {}} /></div>
  if (tab === 'Renovation') return incomplete ? <AnalysisIncomplete property={property} heading="Renovation — analysis incomplete" context="renovation budget and ranges" /> : <DataSection title="Renovation range and categories" data={output?.renovation ?? {}} />
  if (tab === 'Airbnb') return <Suitability title="Airbnb suitability" score={property.airbnb_score} field={property.enrichment_data.airbnb_suitability} />
  if (tab === 'Wedding Venue') return <Suitability title="Wedding venue suitability" score={property.wedding_score} field={property.enrichment_data.wedding_suitability} />
  if (tab === 'Personal Use') return <PersonalUse property={property} />
  if (tab === 'Maps') return <><PropertyMap property={property} /><EnrichmentGrid property={property} /></>
  if (tab === 'Comparable Sales') return properties.length > 1 ? <ComparisonTable properties={properties} /> : <Comparables memo={memo} valuation={valuation} />
  if (tab === 'Risks & Missing Data') return <RisksAndMissingData property={property} memo={memo} liveProvidersOff={liveProvidersOff} onResolve={onResolve} onRefresh={onRefresh} />
  if (tab === 'Valuation') return <ValuationPanel property={property} valuation={valuation} />
  if (tab === 'Documents') return <Documents propertyId={property.id} documents={documents} refresh={refresh} />
  return <NotesAndTasks propertyId={property.id} notes={notes} tasks={tasks} refresh={refresh} />
}

export function Dashboard({ properties }: { properties: Property[] }) { const average = (values: Array<number | null>) => { const valid = values.filter((value): value is number => value != null); return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null }; const scored = properties.filter((property) => !analysisIncomplete(property)); const highest = [...scored].sort((a, b) => (b.overall_score ?? 0) - (a.overall_score ?? 0))[0]; return <section className="dashboard-grid"><Metric label="Properties imported" value={String(properties.length)} /><Metric label="Deals under review" value={String(properties.filter((property) => ['Reviewing', 'Underwriting'].includes(property.status)).length)} /><Metric label="Average Buy Score" value={score(average(scored.map((property) => property.buy_score)))} /><Metric label="Average IRR" value={percent(average(scored.map((property) => property.underwriting_output?.projection.levered_irr ?? null)))} /><Metric label="Highest-scoring property" value={highest ? `${highest.name} · ${Math.round(highest.overall_score ?? 0)}` : '—'} /><Metric label="Pipeline counts" value={`${properties.filter((property) => property.status === 'Closed').length} closed`} /></section> }
function Metric({ label, value }: { label: string; value: string }) { return <article><span>{label}</span><strong>{value}</strong></article> }
function Overview({ property, memo, tasks, refresh, onResolve, liveProvidersOff }: { property: Property; memo: Memo | null; tasks: Task[]; refresh: () => Promise<void>; onResolve?: (address?: string) => void; liveProvidersOff?: boolean }) {
  const images = Array.isArray(property.images) ? property.images : []; const missingInformation = Array.isArray(memo?.missing_information) ? memo.missing_information : []
  const estimate = Boolean(property.financials_are_estimates)
  const incomplete = analysisIncomplete(property)
  return <div className="overview">
    {incomplete
      ? <AnalysisIncomplete property={property} heading="Analysis incomplete" context="Overall/Buy/Airbnb/Wedding/Personal scores, cash required, cap rate, cash-on-cash, and IRR" />
      : <><ScoreSummary property={property} /><KeyFinancials property={property} estimate={estimate} /></>}
    <WhyPanel property={property} memo={memo} liveProvidersOff={liveProvidersOff} onResolve={onResolve} incomplete={incomplete} />
    <div className="overview-grid">
      {images.length > 0 && <article className="panel"><div className="panel-title"><span>Listing gallery</span></div><div className="chip-list">{images.map((image) => <a key={image} href={image} target="_blank" rel="noreferrer">Listing photo ↗</a>)}</div></article>}
      <article className="panel memo-panel"><div className="panel-title"><span>Investment memo</span><span className="confidence-pill">{Math.round(property.confidence_score ?? 0)}% confidence</span></div><p className="summary">{memo?.executive_summary ?? 'Investment memo is being prepared.'}</p>{memo?.analysis_incomplete
        ? <><MemoList title="Required to complete the analysis" items={Array.isArray(memo?.required_inputs) ? memo.required_inputs : []} tone="warning" /><MemoList title="Verified facts known" items={Array.isArray(memo?.verified_facts) ? memo.verified_facts : []} tone="positive" /></>
        : <><MemoList title="Strengths" items={Array.isArray(memo?.strengths) ? memo.strengths : []} tone="positive" /><MemoList title="Risks & weaknesses" items={[...(Array.isArray(memo?.weaknesses) ? memo.weaknesses : []), ...(Array.isArray(memo?.risks) ? memo.risks : [])]} tone="warning" /></>}</article>
      <article className="panel"><div className="panel-title"><span>Property facts</span></div><dl className="facts"><Fact label="Asking price" value={money(property.asking_price)} /><Fact label="Annual taxes" value={money(property.annual_taxes)} /><Fact label="Beds / baths" value={`${property.bedrooms ?? '—'} / ${property.bathrooms ?? '—'}`} /><Fact label="Square feet" value={property.square_feet?.toLocaleString() ?? '—'} /><Fact label="Acreage" value={property.acreage?.toString() ?? '—'} /><Fact label="County" value={property.county ?? '—'} /></dl></article>
      <article className="panel task-panel"><div className="panel-title"><span>Open tasks</span><span>{tasks.filter((task) => !task.completed).length}</span></div>{tasks.slice(0, 4).map((task) => <TaskRow key={task.id} propertyId={property.id} task={task} refresh={refresh} />)}{!tasks.length && <p className="muted">No tasks yet. Add one in Notes.</p>}</article>
      <article className="panel missing-panel"><div className="panel-title"><span>Missing information</span><span>{missingInformation.length}</span></div><div className="chip-list">{missingInformation.length ? missingInformation.map((item) => <span key={item}>{labelize(item)}</span>) : <span className="muted">None recorded.</span>}</div></article>
    </div>
  </div>
}

// The scores the calibrated model actually produces. "Investment / Risk score" are not
// separate model outputs, so they are represented honestly by the buy score and by the
// risk summary in the Why panel rather than invented numbers.
function ScoreSummary({ property }: { property: Property }) {
  const scores: Array<[string, number | null]> = [
    ['Overall Buy', property.buy_score], ['Overall Score', property.overall_score], ['Airbnb', property.airbnb_score],
    ['Wedding Venue', property.wedding_score], ['Personal Use', property.personal_use_score],
  ]
  const confidence = Math.round(property.confidence_score ?? 0)
  return <section className="panel score-summary"><div className="panel-title"><span>Scores</span><span className={`confidence-pill ${confidence < 40 ? 'low' : ''}`}>{confidence}% data confidence</span></div>
    <div className="score-summary-grid">{scores.map(([label, value]) => <div key={label} className="score-cell"><span>{label}</span><strong>{value == null ? '—' : `${Math.round(value)}`}<em>/100</em></strong></div>)}</div>
    {confidence < 40 && <p className="score-caveat">Low data confidence — scores rely on defaults or synthesized facts and should be treated as provisional until inputs are verified.</p>}
  </section>
}

function KeyFinancials({ property, estimate }: { property: Property; estimate: boolean }) {
  const dashboard = property.underwriting_output?.dashboard ?? {}
  const capRate = dashboard.noi_before_debt && dashboard.purchase_price ? dashboard.noi_before_debt / dashboard.purchase_price : null
  const cells: Array<[string, string]> = [
    ['Asking price', money(property.asking_price)], ['Cash required', money(dashboard.total_cash_required)],
    ['Expected renovation', money(dashboard.renovation_contingency)], ['Cap rate', percent(capRate)],
    ['Cash-on-cash', percent(dashboard.cash_on_cash_return)], ['IRR (levered)', percent(property.underwriting_output?.projection?.levered_irr)],
  ]
  return <section className={`panel key-financials ${estimate ? 'is-estimate' : ''}`}><div className="panel-title"><span>Key financials</span>{estimate ? <span className="estimate-pill">Estimate — inputs missing</span> : <span className="confidence-pill">From entered inputs</span>}</div>
    <div className="key-financials-grid">{cells.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    {estimate && <p className="score-caveat">No asking price was provided, so these figures come from the workbook's default scenario. Enter the asking price and taxes to calculate property-specific returns.</p>}
  </section>
}

// "Why this scored this way": strongest positives, biggest risks, hard-constraint failures,
// and the most important missing information — all read from persisted output; no new scoring.
function WhyPanel({ property, memo, liveProvidersOff, onResolve, incomplete }: { property: Property; memo: Memo | null; liveProvidersOff?: boolean; onResolve?: (address?: string) => void; incomplete?: boolean }) {
  const dashboard = property.underwriting_output?.dashboard ?? {}
  const zero = property.underwriting_output?.zero_revenue_affordability ?? {}
  // Positives and hard-constraint checks derive from the (default) workbook output, so
  // they are not meaningful until the analysis is complete; suppress them when gated.
  const positives = incomplete ? [] : (Array.isArray(memo?.strengths) ? memo.strengths : [])
  const risks = [...(Array.isArray(memo?.risks) ? memo.risks : []), ...(Array.isArray(memo?.weaknesses) ? memo.weaknesses : [])]
  const constraints: string[] = []
  if (!incomplete) {
    if (typeof dashboard.dscr === 'number' && dashboard.dscr < 1.25) constraints.push(`Debt service coverage is ${dashboard.dscr.toFixed(2)}× (below the 1.25× target).`)
    if (typeof dashboard.cash_on_cash_return === 'number' && dashboard.cash_on_cash_return <= 0) constraints.push('Base-case cash-on-cash return is not positive.')
    if (zero.status === 'FAIL') constraints.push('Zero-revenue affordability ceiling is exceeded.')
  }
  const missing = Array.isArray(memo?.missing_information) ? memo.missing_information.slice(0, 8) : []
  return <section className="panel why-panel"><div className="panel-title"><span>Why this scored this way</span></div>
    <div className="why-grid">
      <WhyList title="Strongest positives" tone="positive" items={positives} empty={incomplete ? 'Awaiting required inputs before assessing.' : 'No positive factors are supported by stored data yet.'} />
      <WhyList title="Biggest risks" tone="warning" items={risks} empty="No risks identified yet." />
      <WhyList title="Hard-constraint failures" tone="danger" items={constraints} empty={incomplete ? 'Awaiting required inputs before assessing.' : 'No hard-constraint failures in the current output.'} />
      <WhyList title="Important missing information" tone="muted" items={missing.map(labelize)} empty="Nothing critical is missing." />
    </div>
    {liveProvidersOff && <p className="score-caveat">Live enrichment providers are off in this environment, so location, flood, and market facts were not retrieved.</p>}
    {property.listing_incomplete && onResolve && <p className="score-caveat">This listing is unresolved. <button className="link-button" onClick={() => onResolve()}>Retry resolve</button> or add the full address to complete it.</p>}
  </section>
}
function WhyList({ title, items, tone, empty }: { title: string; items: string[]; tone: string; empty: string }) { return <div className={`why-list ${tone}`}><strong>{title}</strong>{items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="muted">{empty}</p>}</div> }

function EnrichmentGrid({ property }: { property: Property }) { return <div className="enrichment-grid">{Object.entries(property.enrichment_data).map(([key, field]) => <article className="panel" key={key}><div className="panel-title"><span>{labelize(key)}</span><span>{Math.round(field.confidence * 100)}%</span></div><strong className="enrichment-value">{field.value === null ? 'Unavailable' : formatValue(field.value)}</strong><small>{field.source ?? 'Provider not recorded'} · {field.retrieval_status ?? (field.value === null ? 'unavailable' : 'live')}</small>{field.last_updated && <small>Updated {new Date(field.last_updated).toLocaleDateString()}{Date.now() - new Date(field.last_updated).getTime() > 30 * 86400000 ? ' · Stale' : ''}</small>}{field.missing_reason && <small>{field.missing_reason}</small>}</article>)}</div> }
function Suitability({ title, score: value, field }: { title: string; score: number | null; field?: EnrichmentField }) { const scored = Boolean(field && field.value != null); return <article className="panel suitability"><div className="score-ring">{scored ? Math.round(value ?? 0) : 'n/a'}</div><div><div className="eyebrow">Bistate suitability model</div><h2>{title}</h2><p>{scored ? 'The initial suitability score uses available property facts. Validate it with market and regulatory diligence.' : 'Not scored — the property facts this score depends on (e.g. bedrooms, acreage) are not available. A default is not shown.'}</p><small>Source: {field?.source ?? 'Not available'} · Confidence {Math.round((field?.confidence ?? 0) * 100)}%</small></div></article> }
function DataSection({ title, data }: { title: string; data: Record<string, unknown> }) { return <article className="panel data-panel"><div className="panel-title"><span>{title}</span></div><div className="data-grid">{Object.entries(data).map(([key, value]) => <div key={key}><span>{labelize(key)}</span><strong>{formatValue(value)}</strong></div>)}</div></article> }
function ValuationPanel({ property, valuation }: { property: Property; valuation: Valuation | null }) { if (!valuation) return <article className="panel"><p className="muted">Loading valuation…</p></article>; return <div className="valuation-layout"><article className="panel"><div className="panel-title"><span>Market valuation</span><span className="confidence-pill">{Math.round(valuation.confidence_score)}% confidence</span></div><div className="valuation-summary"><div><span>Asking price</span><strong>{money(property.asking_price)}</strong></div><div><span>Estimated value</span><strong>{money(valuation.estimated_value)}</strong></div><div><span>Value range</span><strong>{valuation.value_range ? `${money(valuation.value_range.low)} – ${money(valuation.value_range.high)}` : '—'}</strong></div><div><span>Discount / premium</span><strong>{money(valuation.discount_premium)} {valuation.percent_difference != null ? `(${valuation.percent_difference.toFixed(1)}%)` : ''}</strong></div><div><span>Pricing signal</span><strong>{valuation.pricing_signal}</strong></div></div><p className="summary">{valuation.explanation}</p></article><article className="panel"><div className="panel-title"><span>Comparable map</span><span>Placeholder</span></div><div className="valuation-map-placeholder">Map markers will appear when comparable coordinates are available.</div></article><article className="panel comparison-table"><div className="panel-title"><span>Comparable sales</span><span>{valuation.comparables.length}</span></div><table><thead><tr><th>Address</th><th>Sale</th><th>Distance</th><th>Sale date</th><th>Similarity</th><th>Adjustments</th></tr></thead><tbody>{valuation.comparables.map((comp) => <tr key={String(comp.id)}><td>{String(comp.address)}</td><td>{money(comp.sale_price as number)}</td><td>{String(comp.distance_miles ?? '—')} mi</td><td>{String(comp.sale_date ?? '—')}</td><td>{String(comp.similarity_score ?? '—')}</td><td>{Array.isArray(comp.adjustments) && comp.adjustments.length ? (comp.adjustments as Array<{ field: string; percent: number }>).map((item) => `${item.field} ${(item.percent * 100).toFixed(1)}%`).join(', ') : 'None'}</td></tr>)}</tbody></table></article></div> }
function Comparables({ memo, valuation }: { memo: Memo | null; valuation?: Valuation | null }) {
  const memoComps = Array.isArray(memo?.comparable_properties) ? memo.comparable_properties : []
  const valuationComps = Array.isArray(valuation?.comparables) ? valuation.comparables : []
  const comps = memoComps.length ? memoComps : valuationComps
  return <article className="panel"><div className="panel-title"><span>Comparable sales</span><span>{comps.length}</span></div>{comps.length ? <div className="data-grid">{comps.map((item, index) => <div key={index}><strong>{String(item.address)}</strong><span>{money(item.sale_price as number | null)} · {String(item.square_feet ?? item.distance_miles ?? '—')}{item.square_feet ? ' sq ft' : item.distance_miles ? ' mi' : ''}</span></div>)}</div> : <p className="muted">No verified comparable sales have been attached. Live comparable data requires a configured provider; workbook sample comps remain clearly marked as unverified.</p>}</article>
}

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
export function StatusDot({ status }: { status: string }) { return <span className={`status-dot status-${status.toLowerCase().replace(/ /g, '-')}`} title={status} /> }
export function EmptyState() { return <section className="empty-state"><div className="empty-icon">⌂</div><h1>Build your acquisition pipeline</h1><p>Paste a listing URL, property address, or MLS number above. Bistate will create the property, run enrichment, execute the workbook underwriting engine, and prepare an investment memo.</p></section> }
function labelize(value: string) { return value.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase()) }
function money(value: number | null | undefined) { return value == null ? '—' : value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }) }
function percent(value: number | null | undefined) { return value == null ? '—' : `${(value * 100).toFixed(1)}%` }
function score(value: number | null | undefined) { return value == null ? '—' : `${Math.round(value)}/100` }
function formatValue(value: unknown): string { if (typeof value === 'number') return Math.abs(value) < 1 ? percent(value) : value.toLocaleString(undefined, { maximumFractionDigits: 2 }); if (value === null) return '—'; if (Array.isArray(value)) return `${value.length} records`; if (typeof value === 'object') { const fact = value as { name?: unknown; distance_miles?: unknown; drive_time_minutes?: unknown }; if (fact.name) return `${String(fact.name)}${fact.distance_miles != null ? ` · ${String(fact.distance_miles)} mi` : ''}${fact.drive_time_minutes != null ? ` · ${String(fact.drive_time_minutes)} min` : ''}`; return 'View detailed output' } return String(value) }

function PropertyMap({ property }: { property: Property }) { const lat = property.latitude ?? 42.65; const lng = property.longitude ?? -74; const delta = .08; const bbox = `${lng-delta}%2C${lat-delta}%2C${lng+delta}%2C${lat+delta}`; return <article className="panel map-panel"><div className="panel-title"><span>Interactive map</span><span>OpenStreetMap · subject location</span></div><iframe title="Property location map" src={`https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat}%2C${lng}`} /><p className="muted">Pan and zoom the map, then click the subject marker. Nearby airports, Amtrak, parcels, and comparables appear as live enrichment supplies locations.</p></article> }
function ComparisonTable({ properties }: { properties: Property[] }) {
  // `gated: true` rows derive from workbook output; they are withheld for any column whose
  // property is analysis-incomplete, so a comparison never leaks default-workbook numbers.
  const rows: Array<[string, (property: Property) => number | null, 'money' | 'percent' | 'score', boolean]> = [
    ['Purchase price', (p) => p.asking_price, 'money', false],
    ['Underwriting score', (p) => p.overall_score, 'score', true],
    ['Renovation', (p) => p.underwriting_output?.dashboard.renovation_contingency ?? null, 'money', true],
    ['Projected IRR', (p) => p.underwriting_output?.projection.levered_irr ?? null, 'percent', true],
    ['Airbnb score', (p) => p.airbnb_score, 'score', true],
    ['Wedding score', (p) => p.wedding_score, 'score', true],
    ['Cash required', (p) => p.underwriting_output?.dashboard.total_cash_required ?? null, 'money', true],
  ]
  const fmt = (value: number | null, kind: 'money' | 'percent' | 'score') => kind === 'money' ? money(value) : kind === 'percent' ? percent(value) : score(value)
  return <article className="panel comparison-table"><div className="panel-title"><span>Side-by-side comparison</span><span>{properties.length} selected</span></div><table><thead><tr><th>Metric</th>{properties.map((property) => <th key={property.id}>{property.name}</th>)}</tr></thead><tbody>{rows.map(([name, get, kind, gated]) => {
    const cells = properties.map((property) => (gated && analysisIncomplete(property)) ? undefined : get(property))
    const best = Math.max(...cells.map((value) => value == null ? -Infinity : value))
    return <tr key={name}><th>{name}</th>{cells.map((value, index) => <td className={value != null && value === best ? 'best' : ''} key={properties[index].id}>{value === undefined ? 'Incomplete' : fmt(value, kind)}</td>)}</tr>
  })}</tbody></table></article>
}
function ActivityTimeline({ property }: { property: Property; notes: Note[]; documents: Document[] }) { const [events, setEvents] = useState<Array<{ id: number; event_type: string; message: string; created_at: string; metadata: Record<string, unknown> }>|null>(null); const [failed, setFailed] = useState(false); useEffect(() => { void fetch(`/api/properties/${property.id}/activity`).then(async (response) => { if (!response.ok) throw Error(); setEvents(await response.json()) }).catch(() => setFailed(true)) }, [property.id]); if (failed) return <article className="panel"><p className="muted">Activity could not be loaded.</p></article>; if (events === null) return <article className="panel"><p className="muted">Loading activity…</p></article>; if (!events.length) return <article className="panel"><p className="muted">No persisted activity yet.</p></article>; return <article className="panel timeline"><div className="panel-title"><span>Activity timeline</span></div>{events.map((event) => <div key={event.id}><b>●</b><span>{event.message}<small>{event.event_type} · {new Date(event.created_at).toLocaleString()}</small></span></div>)}</article> }
// A persistent banner (rendered above the hero) when the analysis cannot be property-
// specific. It states the results are withheld — not that default figures are usable.
export function AnalysisIncompleteBanner({ property }: { property: Property }) {
  const missing = Array.isArray(property.missing_core_inputs) ? property.missing_core_inputs : []
  return <div className="estimate-banner" role="status"><strong>Analysis incomplete.</strong> Property-specific scores and financials are withheld — the workbook's default scenario is not this property's result. Missing critical inputs: {missing.length ? missing.map(labelize).join(', ') : 'core financial inputs'}. Enter them to run the analysis.</div>
}

// A banner offering to resolve a listing that has no confirmed street address.
export function IncompleteListingBanner({ property, busy, onResolve }: { property: Property; busy?: boolean; onResolve: (address?: string) => void }) {
  const [address, setAddress] = useState('')
  return <div className="incomplete-banner" role="alert">
    <div><strong>Listing information incomplete.</strong> The imported {property.listing_source ?? 'listing'} link did not contain a full street address, so this record cannot be trusted for diligence yet. We did not invent an address.</div>
    <form className="resolve-form" onSubmit={(event) => { event.preventDefault(); onResolve(address.trim() || undefined) }}>
      <input aria-label="Full street address" value={address} onChange={(event) => setAddress(event.target.value)} placeholder="123 Main St, Hudson, NY 12534" />
      <button type="submit" disabled={busy}>{busy ? 'Resolving…' : (address.trim() ? 'Resolve with address' : 'Retry from link')}</button>
    </form>
  </div>
}


const LISTING_FACT_ROWS: Array<[string, string, (value) => string]> = [
  ['Asking price', 'asking_price', (v) => money(v)],
  ['Bedrooms', 'bedrooms', (v) => String(v)],
  ['Bathrooms', 'bathrooms', (v) => String(v)],
  ['Square feet', 'square_feet', (v) => Number(v).toLocaleString()],
  ['Acreage / lot size', 'acreage', (v) => String(v)],
  ['Property type', 'property_type', (v) => String(v)],
  ['Listing status', 'listing_status', (v) => String(v)],
  ['Listing date', 'listing_date', (v) => String(v)],
  ['Annual taxes', 'annual_taxes', (v) => money(v)],
  ['Photos', 'photos', (v) => Array.isArray(v) ? `${v.length} photo${v.length === 1 ? '' : 's'}` : String(v)],
]

// Distinguishes listing facts (from the source) from geocoding/enrichment. When a
// provider is recognized but facts can't be retrieved, it says so — it never presents
// geocoding as if the listing were successfully ingested.
function ListingIngestionBanner({ ingestion, url, onRefresh }: { ingestion; url?: string | null; onRefresh?: () => void }) {
  if (!url || !ingestion?.provider) return null
  if (ingestion.facts_retrieved) {
    return <div className="disclosure-banner ingest-ok" role="status"><strong>Listing facts ingested from {ingestion.provider}.</strong> Retrieved: {(ingestion.fields_retrieved || []).map(labelize).join(', ')}. Fields the source did not publish are shown as unavailable, never invented.</div>
  }
  return <div className="incomplete-banner ingest-blocked" role="alert">
    <div><strong>{ingestion.provider} recognized, but listing facts could not be retrieved.</strong> {ingestion.reason} Only the geocoded location is available — this is not a successfully ingested listing, and price/beds/baths/etc. are shown as unavailable rather than guessed.</div>
    {onRefresh && <form className="resolve-form" onSubmit={(event) => { event.preventDefault(); onRefresh() }}><button type="submit">↻ Retry ingestion</button></form>}
  </div>
}

function ListingSection({ property, onResolve, onRefresh }: { property: Property; onResolve?: (address?: string) => void; onRefresh?: () => void }) {
  const listing = property.listing_data || {}
  const ingestion = property.listing_ingestion || {}
  return <div className="listing-layout">
    <ListingIngestionBanner ingestion={ingestion} url={property.listing_url} onRefresh={onRefresh} />
    <article className="panel"><div className="panel-title"><span>Listing facts</span><span>{ingestion.provider ?? 'Manual entry'}{ingestion.facts_retrieved ? ' · ingested' : ''}</span></div>
      <table className="listing-facts-table"><thead><tr><th>Field</th><th>Value</th><th>Source / status</th></tr></thead><tbody>
        {LISTING_FACT_ROWS.map(([label, key, fmt]) => { const item = listing[key] || {}; const available = item.value != null
          return <tr key={key}><td>{label}</td><td className={available ? 'fact-value' : 'muted'}>{available ? fmt(item.value) : 'Unavailable'}</td><td className="muted">{available ? (item.source ?? 'Listing') : (item.missing_reason ?? 'Not retrieved')}</td></tr> })}
      </tbody></table>
    </article>
    <article className="panel"><div className="panel-title"><span>Identity &amp; source</span><span>geocoding, not listing</span></div><dl className="facts">
      <Fact label="Resolved address" value={property.listing_incomplete ? 'Incomplete' : `${property.address}, ${property.city}, ${property.state} ${property.postal_code ?? ''}`} />
      <Fact label="County (enrichment)" value={property.county ?? '—'} />
      <Fact label="Provider" value={ingestion.provider ?? property.listing_source ?? 'Manual entry'} />
      <Fact label="MLS #" value={property.mls_number ?? '—'} />
    </dl>
    {property.listing_url ? <p className="muted"><a href={property.listing_url} target="_blank" rel="noreferrer">Open source listing ↗</a></p> : <p className="muted">No source URL recorded.</p>}
    {property.listing_incomplete && onResolve && <p className="muted"><button className="link-button" onClick={() => onResolve()}>Retry resolve from link</button></p>}
    </article>
  </div>
}

function PersonalUse({ property }: { property: Property }) {
  const facts = property.enrichment_data ?? {}
  const nyc = (facts.nyc_drive_time?.value as { drive_time_minutes?: number } | undefined)?.drive_time_minutes
  // The personal-use score depends on bedroom capacity; without it the value is a default, so withhold it.
  const scored = property.bedrooms != null
  return <article className="panel suitability"><div className="score-ring">{scored ? Math.round(property.personal_use_score ?? 0) : 'n/a'}</div><div>
    <div className="eyebrow">Bistate suitability model</div><h2>Personal use suitability</h2>
    <p>{scored ? 'Reflects bedroom capacity and stored access facts for use as a personal second home. Validate condition, seasonality, and travel time before relying on this score.' : 'Not scored — bedroom capacity is required and not available. A default is not shown.'}</p>
    <small>Bedrooms: {property.bedrooms ?? '—'} · Acreage: {property.acreage ?? '—'} · NYC drive time: {nyc != null ? `${nyc} min` : 'not retrieved'}</small>
  </div></article>
}

function RisksAndMissingData({ property, memo, liveProvidersOff, onResolve, onRefresh }: { property: Property; memo: Memo | null; liveProvidersOff?: boolean; onResolve?: (address?: string) => void; onRefresh?: () => void }) {
  const dashboard = property.underwriting_output?.dashboard ?? {}
  const zero = property.underwriting_output?.zero_revenue_affordability ?? {}
  const constraints: string[] = []
  if (typeof dashboard.dscr === 'number' && dashboard.dscr < 1.25) constraints.push(`Debt service coverage ${dashboard.dscr.toFixed(2)}× is below the 1.25× target.`)
  if (typeof dashboard.cash_on_cash_return === 'number' && dashboard.cash_on_cash_return <= 0) constraints.push('Base-case cash-on-cash return is not positive.')
  if (zero.status === 'FAIL') constraints.push('Zero-revenue monthly affordability ceiling is exceeded.')
  const risks = [...(Array.isArray(memo?.risks) ? memo.risks : []), ...(Array.isArray(memo?.weaknesses) ? memo.weaknesses : [])]
  const missing = Array.isArray(memo?.missing_information) ? memo.missing_information : []
  const providerErrors = Object.entries(property.provider_errors ?? {})
  return <div className="risks-layout">
    <div className="risks-actions"><span className="muted">Resolve gaps before relying on this analysis.</span><div>{property.listing_incomplete && onResolve && <button className="secondary-button" onClick={() => onResolve()}>Resolve listing</button>}{onRefresh && <button className="secondary-button" onClick={onRefresh}>↻ Re-run analysis</button>}</div></div>
    <div className="two-column">
      <article className="panel"><div className="panel-title"><span>Hard-constraint failures</span><span>{constraints.length}</span></div>{constraints.length ? <ul className="risk-list danger">{constraints.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="muted">No hard-constraint failures in the current workbook output.</p>}</article>
      <article className="panel"><div className="panel-title"><span>Risks & weaknesses</span><span>{risks.length}</span></div>{risks.length ? <ul className="risk-list warning">{risks.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="muted">None identified yet.</p>}</article>
    </div>
    {liveProvidersOff && <div className="disclosure-banner">Live enrichment providers are not configured, so external facts (flood, demographics, routing, market comps) were not retrieved. Missing items below are unverified, not confirmed absent.</div>}
    <article className="panel"><div className="panel-title"><span>Missing information</span><span>{missing.length}</span></div><div className="chip-list">{missing.length ? missing.map((item) => <span key={item}>{labelize(item)}</span>) : <span className="muted">Nothing recorded as missing.</span>}</div></article>
    {providerErrors.length > 0 && <article className="panel"><div className="panel-title"><span>Provider failures</span><span>{providerErrors.length}</span></div><div className="data-grid">{providerErrors.map(([key, value]) => <div key={key}><span>{labelize(key)}</span><strong>{String((value as { message?: string })?.message ?? value)}</strong></div>)}</div></article>}
  </div>
}

export { PipelineProgress } from './PipelineProgress'
export { KpiGrid } from './KPICards'
export { AcquisitionPipeline } from './AcquisitionStages'
