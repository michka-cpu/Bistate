import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import SearchPage from '../pages/SearchPage'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('searches discovery listings and saves a result to the watchlist', async () => {
  const user = userEvent.setup(); const onOpenPipeline = vi.fn(); const onOpenProperty = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: true, json: async () => [{ id: 1, address: '20 River Road', city: 'Hudson', state: 'NY', postal_code: '12534', county: 'Columbia', asking_price: 500000, acreage: 4, bedrooms: 3, bathrooms: 2, property_type: 'Single Family', photo_url: 'https://example.com/home.jpg', listing_source: 'Zillow', listing_date: '2026-07-20T00:00:00Z', is_watchlisted: false }] }).mockResolvedValueOnce({ ok: true }))
  render(<SearchPage onOpenPipeline={onOpenPipeline} onOpenProperty={onOpenProperty} />)
  await user.type(screen.getByLabelText('County'), 'Columbia'); await user.click(screen.getByRole('button', { name: 'Search listings' }))
  expect(await screen.findByText('20 River Road')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Save to Watchlist' }))
  expect(screen.getByRole('button', { name: 'Saved to Watchlist' })).toBeInTheDocument()
})

test('shows the empty-results message when a filtered search returns no matches', async () => {
  const user = userEvent.setup()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: true, json: async () => [] }))
  render(<SearchPage onOpenPipeline={vi.fn()} onOpenProperty={vi.fn()} />)
  await user.type(screen.getByLabelText('County'), 'Nowhere')
  await user.click(screen.getByRole('button', { name: 'Search listings' }))
  expect(await screen.findByText('No listings match these filters.')).toBeInTheDocument()
})

test('routes a known-address search through import into the property detail view', async () => {
  const user = userEvent.setup(); const onOpenProperty = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: 42 }) }))
  render(<SearchPage onOpenPipeline={vi.fn()} onOpenProperty={onOpenProperty} />)
  await user.type(screen.getByLabelText('Paste an address or listing URL'), '5 Birch Rd, Hudson, NY 12534')
  await user.click(screen.getByRole('button', { name: 'Search & Analyze' }))
  await waitFor(() => expect(onOpenProperty).toHaveBeenCalledWith(42))
})

test('rejects an unsupported listing site before importing', async () => {
  const user = userEvent.setup(); const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<SearchPage onOpenPipeline={vi.fn()} onOpenProperty={vi.fn()} />)
  await user.type(screen.getByLabelText('Paste an address or listing URL'), 'https://example.com/listing/123')
  await user.click(screen.getByRole('button', { name: 'Search & Analyze' }))
  expect(await screen.findByText(/not a supported listing site/)).toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
})
