import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import SearchPage from '../pages/SearchPage'

test('searches discovery listings and saves a result to the watchlist', async () => {
  const user = userEvent.setup(); const onPipeline = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: true, json: async () => [{ id: 1, address: '20 River Road', city: 'Hudson', state: 'NY', postal_code: '12534', county: 'Columbia', asking_price: 500000, acreage: 4, bedrooms: 3, bathrooms: 2, property_type: 'Single Family', photo_url: 'https://example.com/home.jpg', listing_source: 'Zillow', listing_date: '2026-07-20T00:00:00Z', is_watchlisted: false }] }).mockResolvedValueOnce({ ok: true }))
  render(<SearchPage onPipeline={onPipeline} />)
  await user.type(screen.getByLabelText('County'), 'Columbia'); await user.click(screen.getByRole('button', { name: 'Search listings' }))
  expect(await screen.findByText('20 River Road')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Save to Watchlist' }))
  expect(screen.getByRole('button', { name: 'Saved to Watchlist' })).toBeInTheDocument()
})
