import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { TabContent } from '../components/PropertyDetailPage'

afterEach(() => cleanup())

const base = (over: Record<string, unknown> = {}) => ({
  id: 1, name: '88 Union St', address: '88 Union St', city: 'Hudson', state: 'NY', postal_code: '12534',
  status: 'Reviewing', listing_source: 'Redfin', listing_url: 'https://www.redfin.com/NY/Hudson/88-Union-St-12534/home/1',
  mls_number: null, county: 'Columbia', acreage: null, bedrooms: null, bathrooms: null, square_feet: null,
  asking_price: null, annual_taxes: null, images: [], description: null, agent: null, latitude: 42.2, longitude: -73.7,
  enrichment_data: {}, underwriting_output: null, overall_score: null, buy_score: null, airbnb_score: null,
  wedding_score: null, personal_use_score: null, confidence_score: null, is_favorite: false, is_pinned: false,
  pipeline_state: {}, provider_errors: {}, created_at: '2026-08-13T00:00:00Z', updated_at: '2026-08-13T00:00:00Z',
  listing_incomplete: false, ...over,
})

const listing = (tab: string, property: Record<string, unknown>) => render(
  <TabContent tab={tab as never} property={property as never} properties={[]} memo={null} notes={[]} tasks={[]} documents={[]} valuation={null} refresh={async () => {}} onRefresh={() => {}} />,
)

describe('Listing tab — populated vs unavailable', () => {
  it('shows retrieved listing facts with their source, and unavailable facts with a reason', () => {
    const property = base({
      asking_price: 625000, bedrooms: 4, bathrooms: 2.5, square_feet: 2100, property_type: 'Single Family',
      listing_ingestion: { provider: 'Redfin', status: 'ingested', facts_retrieved: true, fields_retrieved: ['asking_price', 'bedrooms', 'bathrooms', 'square_feet'], reason: null, canonical_url: null },
      listing_data: {
        asking_price: { value: 625000, source: 'Redfin', retrieval_status: 'listing', missing_reason: null },
        bedrooms: { value: 4, source: 'Redfin', retrieval_status: 'listing', missing_reason: null },
        square_feet: { value: 2100, source: 'Redfin', retrieval_status: 'listing', missing_reason: null },
        annual_taxes: { value: null, source: 'Redfin', retrieval_status: 'unavailable', missing_reason: 'Redfin did not publish annual taxes in its listing metadata.' },
      },
    })
    listing('Listing', property)
    expect(screen.getByText(/Listing facts ingested from Redfin/)).toBeInTheDocument()
    expect(screen.getByText('$625,000')).toBeInTheDocument()
    expect(screen.getByText('2,100')).toBeInTheDocument()
    // Unavailable field is explicit with a reason, not a fabricated value.
    expect(screen.getByText(/did not publish annual taxes/)).toBeInTheDocument()
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
  })

  it('when a provider is recognized but blocked, says so and does not present geocoding as ingestion', () => {
    const property = base({
      listing_source: 'Zillow', listing_url: 'https://www.zillow.com/homedetails/1_zpid/',
      listing_ingestion: { provider: 'Zillow', status: 'blocked', facts_retrieved: false, fields_retrieved: [], reason: 'Zillow provider blocked automated access (HTTP 403); a licensed data API is required.', canonical_url: null },
      listing_data: {
        asking_price: { value: null, source: 'Zillow', retrieval_status: 'unavailable', missing_reason: 'Zillow provider blocked automated access (HTTP 403); a licensed data API is required to read its listing facts.' },
      },
    })
    listing('Listing', property)
    expect(screen.getByText(/Zillow recognized, but listing facts could not be retrieved/)).toBeInTheDocument()
    expect(screen.getByText(/not a successfully ingested listing/)).toBeInTheDocument()
    // Every listing fact row shows Unavailable, never a guessed value.
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThanOrEqual(10)
  })
})
