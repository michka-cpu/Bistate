import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import DashboardPage from '../pages/DashboardPage'
import { buildImportBody } from '../lib/importInput'
import { KpiGrid } from '../components/KPICards'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('universal input classification', () => {
  it('treats a full US street address (with abbreviated road forms) as an address', () => {
    for (const address of [
      '139 County Route 21c, Ghent, NY 12075',
      '88 Co Rd 9, Chatham, NY 12037',
      '410 State Route 203, Valatie, NY',
    ]) {
      expect(buildImportBody(address)).toEqual({ body: { raw_address: address } })
    }
  })
  it('classifies supported URLs, MLS numbers, and rejects blanks/unsupported sites', () => {
    expect(buildImportBody('https://www.zillow.com/homedetails/1_zpid/')).toEqual({ body: { listing_url: 'https://www.zillow.com/homedetails/1_zpid/' } })
    expect(buildImportBody('MLS# 12345').body).toEqual({ mls_number: 'MLS# 12345' })
    expect(buildImportBody('   ').error).toMatch(/Enter a street address/)
    expect(buildImportBody('https://example.com/x').error).toMatch(/not a supported listing site/)
  })
})

const property = (over: Record<string, unknown> = {}) => ({
  id: 5, name: '139 County Route 21c', address: '139 County Route 21c', city: 'Ghent', state: 'NY', postal_code: '12075',
  status: 'Reviewing', listing_source: 'manual', listing_url: null, mls_number: null, county: 'Columbia', acreage: null,
  bedrooms: null, bathrooms: null, square_feet: null, asking_price: null, annual_taxes: null, images: [], description: null,
  agent: null, latitude: 42.26, longitude: -73.6, enrichment_data: {}, underwriting_output: { dashboard: {}, projection: {} },
  overall_score: 71, buy_score: 100, airbnb_score: 50, wedding_score: 50, personal_use_score: 55, confidence_score: 5,
  is_favorite: false, is_pinned: false, pipeline_state: {}, provider_errors: {}, created_at: '2026-08-13T00:00:00Z',
  updated_at: '2026-08-13T00:00:00Z', financials_are_estimates: true, missing_core_inputs: ['asking_price', 'annual_taxes'], listing_incomplete: false, ...over,
})

describe('importing an already-imported address (pipeline box)', () => {
  it('opens the existing property instead of showing "Import failed"', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string, opts?: { method?: string }) => {
      if (url === '/api/properties' && (!opts || opts.method !== 'POST')) return Promise.resolve(new Response(JSON.stringify([property()])))
      if (url === '/api/properties/import') return Promise.resolve(new Response(JSON.stringify({ detail: 'Property already exists (id=5)' }), { status: 409 }))
      if (url.includes('/report')) return Promise.resolve(new Response(JSON.stringify({}), { status: 409 }))
      return Promise.resolve(new Response(JSON.stringify([])))
    }))
    render(<DashboardPage />)
    await screen.findByRole('heading', { name: '139 County Route 21c' })
    fireEvent.change(screen.getByLabelText('Listing URL, address, or MLS number'), { target: { value: '139 County Route 21c, Ghent, NY 12075' } })
    fireEvent.click(screen.getByRole('button', { name: 'Import & analyze' }))
    await waitFor(() => expect(screen.queryByText(/Import failed/)).not.toBeInTheDocument())
    expect(screen.getByRole('heading', { name: '139 County Route 21c' })).toBeInTheDocument()
  })
})

describe('analysis-incomplete gating', () => {
  it('withholds default-workbook KPIs when core inputs are missing', () => {
    render(<KpiGrid property={property({ financials_are_estimates: true })} />)
    expect(screen.getByText(/analysis incomplete/i)).toBeInTheDocument()
    expect(screen.queryByText('$418,000')).not.toBeInTheDocument()
    expect(screen.getByText(/Asking price/)).toBeInTheDocument()
  })
  it('shows KPIs once analysis is complete', () => {
    const dashboard = { total_cash_required: 418000, cash_on_cash_return: 0.193, dscr: 3.59, renovation_contingency: 172500, noi_before_debt: 100000, purchase_price: 640000 }
    render(<KpiGrid property={property({ financials_are_estimates: false, asking_price: 640000, missing_core_inputs: [], underwriting_output: { dashboard, projection: { levered_irr: 0.223 } } })} />)
    expect(screen.queryByText(/analysis incomplete/i)).not.toBeInTheDocument()
    expect(screen.getByText('Cash required')).toBeInTheDocument()
  })
})
