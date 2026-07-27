import { expect, test } from '@playwright/test'

// Listing discovery is the default landing view.
test.describe('Listing discovery', () => {
  test('a filtered search excludes listings that do not match the filters', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('County').fill('Zzz Nonexistent County')
    await page.getByRole('button', { name: 'Search listings' }).click()
    await expect(page.getByText('No listings match these filters.')).toBeVisible()
    await expect(page.locator('.listing-card')).toHaveCount(0)
  })

  test('a blank search returns candidate listings from the providers', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Search listings' }).click()
    await expect(page.locator('.listing-card').first()).toBeVisible()
    const sources = await page.locator('.listing-meta span').allTextContents()
    expect(sources.some((s) => ['Zillow', 'Realtor', 'Redfin', 'LandWatch'].includes(s))).toBeTruthy()
  })

  test('a listing can be added to and removed from the watchlist', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Search listings' }).click()
    const firstCard = page.locator('.listing-card').first()
    await expect(firstCard).toBeVisible()
    await firstCard.getByRole('button', { name: 'Save to Watchlist' }).click()
    await expect(firstCard.getByRole('button', { name: 'Saved to Watchlist' })).toBeVisible()
    await firstCard.getByRole('button', { name: 'Saved to Watchlist' }).click()
    await expect(firstCard.getByRole('button', { name: 'Save to Watchlist' })).toBeVisible()
  })

  test('the pipeline is reachable from discovery', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Open pipeline' }).click()
    await expect(page.getByPlaceholder(/Paste a Zillow/)).toBeVisible()
  })
})
