import { expect, test } from '@playwright/test'

// Unique per run so tests stay deterministic against a shared, persistent database.
const uniqueAddress = () => {
  const tag = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  return `${tag} Diligence Way, Hudson, NY 12534`
}

test.describe('Acquisition pipeline', () => {
  test('imports a property and exposes its exports in the hero', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Open pipeline' }).click()
    const address = uniqueAddress()
    await page.getByLabel('Listing URL, address, or MLS number').fill(address)
    await page.getByRole('button', { name: 'Import & analyze' }).click()

    // The imported property becomes the active hero.
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])
    // Exports are wired to the persisted endpoints (CSV/XLSX always available).
    await expect(page.getByTestId('export-csv')).toHaveAttribute('href', /\/exports\/csv$/)
    await expect(page.getByTestId('export-xlsx')).toHaveAttribute('href', /\/exports\/xlsx$/)
  })

  test('rejects a duplicate address that differs only by punctuation', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Open pipeline' }).click()
    const base = uniqueAddress()
    const importField = page.getByLabel('Listing URL, address, or MLS number')

    await importField.fill(base)
    await page.getByRole('button', { name: 'Import & analyze' }).click()
    await expect(page.locator('.property-hero h1')).toContainText(base.split(',')[0])

    // Re-import the same address with a trailing period; the UI should surface the conflict.
    const punctuated = base.replace('Way,', 'Way.,')
    await importField.fill(punctuated)
    await page.getByRole('button', { name: 'Import & analyze' }).click()
    await expect(page.locator('.error-banner')).toBeVisible()
  })

  test('Property Intelligence loads for a property that has acreage', async ({ page, request }) => {
    // Seed a property with acreage via the API so the synthesized diligence facts exercise
    // the (previously crashing) staleness path. Regression for the intelligence 500.
    const address = uniqueAddress()
    const created = await request.post('/api/properties/import', { data: { raw_address: address } })
    expect(created.ok()).toBeTruthy()
    const property = await created.json()
    const updated = await request.put(`/api/properties/${property.id}`, { data: { acreage: 11, annual_taxes: 9000 } })
    expect(updated.ok()).toBeTruthy()

    // Confirm the endpoint no longer 500s for an acreage-bearing property.
    const intelligence = await request.get(`/api/properties/${property.id}/intelligence`)
    expect(intelligence.status()).toBe(200)

    // And the tab renders its content instead of the error banner.
    await page.goto('/')
    await page.getByRole('button', { name: 'Open pipeline' }).click()
    await page.getByPlaceholder('Search address, county, status…').fill(address.split(',')[0])
    await page.locator('.property-list button').first().click()
    await page.getByRole('button', { name: 'Property Intelligence' }).click()
    await expect(page.getByRole('heading', { name: /Data Completeness/ })).toBeVisible()
    await expect(page.getByText('Property intelligence could not be loaded.')).toHaveCount(0)
  })

  test('navigates between property detail tabs', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Open pipeline' }).click()
    const address = uniqueAddress()
    await page.getByLabel('Listing URL, address, or MLS number').fill(address)
    await page.getByRole('button', { name: 'Import & analyze' }).click()
    await expect(page.locator('.property-hero h1')).toContainText(address.split(',')[0])

    for (const tab of ['Financials', 'Underwriting', 'Valuation', 'Notes', 'Overview']) {
      await page.getByRole('button', { name: tab, exact: true }).click()
      await expect(page.locator('.tab-content')).toBeVisible()
    }
  })
})
