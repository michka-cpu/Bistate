import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { PropertyIntelligence } from '../components/PropertyIntelligence'

const intelligence = { sections: [{ name: 'Access', fields: [{ key: 'nyc_drive_time', label: 'NYC driving time', value: { drive_time_minutes: 120 }, source: 'Routing', display_status: 'Verified', confidence: .95, last_updated: '2026-07-27T00:00:00Z', missing_reason: null }, { key: 'grocery', label: 'Grocery', value: null, source: null, display_status: 'Unavailable', confidence: 0, last_updated: null, missing_reason: 'No result' }] }], red_flags: [{ severity: 'High', factual_basis: 'Flood exposure.', affected_use_cases: ['Airbnb'], source_fields: ['fema_flood'], recommended_action: 'Review.' }], opportunities: [{ title: 'Strong NYC access', factual_basis: '120 minutes.', affected_use_cases: ['Second home'], source_fields: ['nyc_drive_time'] }], completeness: { percentage_complete: 50, verified_fields: 1, unavailable_fields: 1, providers_checked: 1, stale_fields: 0, manual_reviews_required: 0, method: 'Coverage only.' } }
const health = [{ provider: 'routing', source: 'Routing', configured: false, enabled: false, most_recent_success: null, most_recent_failure: null, latency_ms: null, cache_status: 'enabled', missing_credential_reason: 'routing_api_key is not configured' }]

test('renders intelligence states, insights, completeness, diagnostics, and refresh', async () => {
  const refreshed = vi.fn(async () => {})
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes('health') ? health : intelligence })))
  render(<PropertyIntelligence propertyId={1} onRefreshed={refreshed} />)
  expect(await screen.findByText('Data Completeness · 50%')).toBeInTheDocument()
  expect(screen.getByText('Verified')).toBeInTheDocument(); expect(screen.getByText('Unavailable')).toBeInTheDocument()
  expect(screen.getByText('Red flags')).toBeInTheDocument(); expect(screen.getByText('Opportunities')).toBeInTheDocument()
  expect(screen.getByText('Provider diagnostics')).toBeInTheDocument(); expect(screen.getByText(/routing_api_key/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Refresh intelligence/ }))
  await waitFor(() => expect(refreshed).toHaveBeenCalled())
  expect(fetch).toHaveBeenCalledWith('/api/properties/1/enrich', { method: 'POST' })
})
