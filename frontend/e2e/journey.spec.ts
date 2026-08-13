import { expect, test } from '@playwright/test'

// Unique per run so the tests stay deterministic against the shared, persistent database.
const uniq = () => `${Date.now()}${Math.floor(Math.random() * 1000)}`
const UNIVERSAL = 'Paste an address or listing URL'
const ANALYZE = 'Search & Analyze'

test.describe('Core property journey', () => {
  test('universal search imports an address and opens the property detail view', async ({ page }) => {
    await page.goto('/')
    const address = `${uniq()} Journey Way, Hudson, NY 12534`
    await page.getByLabel(UNIVERSAL).fill(address)
    await page.getByRole('button', { name: ANALYZE }).click()

    // Lands directly on the property detail (pipeline) view — not merely "added to a list".
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    await expect(page.locator('.score-summary')).toBeVisible()
    await expect(page.getByText('Why this scored this way')).toBeVisible()
  })

  test('an address-only import is clearly labeled as an estimate', async ({ page }) => {
    await page.goto('/')
    const address = `${uniq()} Estimate Way, Hudson, NY 12534`
    await page.getByLabel(UNIVERSAL).fill(address)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    await expect(page.getByText('Financial figures are estimates.')).toBeVisible()
  })

  test('a Zillow URL carrying only a zpid is incomplete and can be resolved', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel(UNIVERSAL).fill(`https://www.zillow.com/homedetails/${uniq()}_zpid/`)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.getByText('Listing information incomplete.')).toBeVisible()

    const resolved = `${uniq()} Resolved Rd, Hudson, NY 12534`
    await page.getByLabel('Full street address').fill(resolved)
    await page.getByRole('button', { name: 'Resolve with address' }).click()
    await expect(page.locator('.property-hero h1')).toContainText(resolved.split(',')[0])
    await expect(page.getByText('Listing information incomplete.')).toHaveCount(0)
  })

  test('a blank universal search is rejected before importing', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.getByText(/Enter a street address or a listing URL/)).toBeVisible()
  })

  test('an unsupported listing site is rejected', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel(UNIVERSAL).fill('https://example.com/listing/1')
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.getByText(/not a supported listing site/)).toBeVisible()
  })

  test('the diligence tabs (Personal Use, Wedding Venue, Risks) are present and navigable', async ({ page }) => {
    await page.goto('/')
    const address = `${uniq()} Tabs Way, Hudson, NY 12534`
    await page.getByLabel(UNIVERSAL).fill(address)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])

    for (const tab of ['Personal Use', 'Wedding Venue', 'Risks & Missing Data', 'Comparable Sales', 'Overview']) {
      await page.getByRole('button', { name: tab, exact: true }).click()
      await expect(page.locator('.tab-content')).toBeVisible()
    }
  })

  test('a duplicate search opens the existing property instead of erroring', async ({ page }) => {
    await page.goto('/')
    const address = `${uniq()} Dup Way, Hudson, NY 12534`
    await page.getByLabel(UNIVERSAL).fill(address)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])

    await page.getByRole('button', { name: '← Discovery' }).click()
    await page.getByLabel(UNIVERSAL).fill(address)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    await expect(page.locator('.error-banner')).toHaveCount(0)
  })
})
