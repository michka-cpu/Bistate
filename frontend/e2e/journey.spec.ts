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
    await expect(page.getByText('Why this scored this way')).toBeVisible()
    // No asking price yet → default-workbook numbers are withheld, not shown as results.
    await expect(page.locator('.analysis-incomplete').first()).toBeVisible()
    await expect(page.getByText('$418,000')).toHaveCount(0)
  })

  test('a full address entered in the pipeline Import box opens the property, never "Import failed"', async ({ page }) => {
    await page.goto('/')
    const address = `${uniq()} Pipeline Rd, Hudson, NY 12534`
    // First create it via the pipeline import box.
    await page.getByRole('button', { name: 'Open pipeline' }).click()
    await page.getByLabel('Listing URL, address, or MLS number').fill(address)
    await page.getByRole('button', { name: 'Import & analyze' }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    // Re-enter the SAME address in the pipeline box: it must open the existing property, not error.
    await page.getByLabel('Listing URL, address, or MLS number').fill(address)
    await page.getByRole('button', { name: 'Import & analyze' }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    await expect(page.getByText('Import failed')).toHaveCount(0)
    await expect(page.getByText('did not contain a full street address')).toHaveCount(0)
  })

  test('an address-only import is gated as analysis-incomplete and the memo leaks no defaults', async ({ page }) => {
    await page.goto('/')
    const address = `${uniq()} Estimate Way, Hudson, NY 12534`
    await page.getByLabel(UNIVERSAL).fill(address)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    // The banner states results are withheld — not that default figures are usable.
    await expect(page.getByText('Analysis incomplete.')).toBeVisible()
    // The Investment memo must not leak default-workbook conclusions.
    await expect(page.getByText('Required to complete the analysis')).toBeVisible()
    await expect(page.getByText(/overall Bistate score of/)).toHaveCount(0)
    await expect(page.getByText(/Debt service coverage is at or above/)).toHaveCount(0)
    await expect(page.getByText('$418,000')).toHaveCount(0)
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

  test('a supported listing URL that blocks automated access fails honestly (no fake ingestion)', async ({ page }) => {
    await page.goto('/')
    // Zillow blocks server-side reads; the app must resolve the location but say listing
    // facts could not be retrieved — never presenting geocoding as a successful ingestion.
    const zpid = uniq()
    await page.getByLabel(UNIVERSAL).fill(`https://www.zillow.com/homedetails/${zpid}-Birch-Ln-Hudson-NY-12534/${zpid}_zpid/`)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.locator('.property-hero h1')).toBeVisible()
    await page.getByRole('button', { name: 'Listing', exact: true }).click()
    await expect(page.getByText(/recognized, but listing facts could not be retrieved/)).toBeVisible()
    await expect(page.getByText(/not a successfully ingested listing/)).toBeVisible()
    // No fabricated facts: the analysis stays incomplete.
    await page.getByRole('button', { name: 'Overview', exact: true }).click()
    await expect(page.locator('.analysis-incomplete').first()).toBeVisible()
  })

  test('an address-only import is never labeled a successful listing ingestion', async ({ page }) => {
    await page.goto('/')
    const address = `${uniq()} Ingest Way, Hudson, NY 12534`
    await page.getByLabel(UNIVERSAL).fill(address)
    await page.getByRole('button', { name: ANALYZE }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    await page.getByRole('button', { name: 'Listing', exact: true }).click()
    // No provider ingestion banner for a manually typed address; facts are unavailable.
    await expect(page.getByText(/recognized, but listing facts/)).toHaveCount(0)
    await expect(page.getByText(/Listing facts ingested/)).toHaveCount(0)
    await expect(page.getByText('Unavailable').first()).toBeVisible()
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
