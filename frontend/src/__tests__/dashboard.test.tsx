import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import DashboardPage from '../pages/DashboardPage'

const property = (id: number, name: string, address: string) => ({
  id, name, address, city: 'Beacon', state: 'NY', postal_code: '12508', status: 'Reviewing',
  listing_source: null, listing_url: null, mls_number: null, county: null, acreage: null,
  bedrooms: null, bathrooms: null, square_feet: null, asking_price: null, annual_taxes: null,
  images: undefined, description: null, agent: null, latitude: null, longitude: null,
  enrichment_data: {}, underwriting_output: null, overall_score: null, buy_score: null,
  airbnb_score: null, wedding_score: null, personal_use_score: null, confidence_score: null,
  is_favorite: false, is_pinned: false, pipeline_state: {}, provider_errors: {},
  created_at: '2026-07-20T00:00:00Z', updated_at: '2026-07-20T00:00:00Z',
})

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('dashboard behavior', () => {
  it('filters sidebar navigation without clearing the selected property detail', async () => {
    const properties = [property(1, 'Maple House', '1 Maple Street'), property(2, 'River House', '2 River Road')]
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === '/api/properties') return Promise.resolve(new Response(JSON.stringify(properties)))
      if (url.includes('/report')) return Promise.resolve(new Response(JSON.stringify({})))
      return Promise.resolve(new Response(JSON.stringify([])))
    }))

    render(<DashboardPage />)
    await screen.findByRole('heading', { name: 'Maple House' })
    fireEvent.change(screen.getByPlaceholderText('Search address, county, status…'), { target: { value: 'river' } })

    await waitFor(() => expect(screen.queryByText('Maple House', { selector: '.property-row strong' })).not.toBeInTheDocument())
    expect(screen.getByRole('heading', { name: 'Maple House' })).toBeInTheDocument()
    expect(screen.getByText('River House')).toBeInTheDocument()
  })

  it('renders incomplete collection payloads without a React exception', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === '/api/properties') return Promise.resolve(new Response(JSON.stringify([property(1, 'Maple House', '1 Maple Street')])))
      if (url.includes('/report')) return Promise.resolve(new Response(JSON.stringify({ missing_information: undefined })))
      return Promise.resolve(new Response(JSON.stringify({})))
    }))

    render(<DashboardPage />)
    expect(await screen.findByRole('heading', { name: 'Maple House' })).toBeInTheDocument()
    expect(screen.getByText('Investment memo is being prepared.')).toBeInTheDocument()
  })
})
