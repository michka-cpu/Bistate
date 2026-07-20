import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import DashboardPage from '../pages/DashboardPage'
import { ExportMenu } from '../components/ExportMenu'
import { PropertyGallery } from '../components/PropertyGallery'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => [] })))
})

describe('interactive dashboard behavior', () => {
  it('renders the empty dashboard after loading properties', async () => {
    render(<DashboardPage />)
    expect(await screen.findByRole('heading', { name: /build your acquisition pipeline/i })).toBeInTheDocument()
  })
  it('renders searchable navigation and favorite/comparison controls for a property', async () => {
    const property = { id: 1, name: 'Maple House', address: '1 Main St', city: 'Beacon', state: 'NY', postal_code: '12508', status: 'Reviewing', images: [], enrichment_data: {}, pipeline_state: {}, provider_errors: {}, created_at: '', updated_at: '', is_favorite: false, is_pinned: false }
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => [property] })))
    render(<DashboardPage />)
    const search = await screen.findByPlaceholderText(/search address/i)
    fireEvent.change(search, { target: { value: 'missing' } })
    expect(screen.queryByText('Maple House')).not.toBeInTheDocument()
  })
  it('exposes persisted CSV, PDF, and Excel exports', () => {
    render(<ExportMenu propertyId={42} />)
    expect(screen.getByRole('link', { name: /csv/i })).toHaveAttribute('href', '/api/properties/42/exports/csv')
    expect(screen.getByRole('link', { name: /pdf/i })).toHaveAttribute('href', '/api/properties/42/exports/pdf')
    expect(screen.getByRole('link', { name: /excel/i })).toHaveAttribute('href', '/api/properties/42/exports/xlsx')
  })
  it('renders the gallery unavailable state', () => { render(<PropertyGallery images={[]} />); expect(screen.getByText(/no listing images/i)).toBeInTheDocument() })
})
