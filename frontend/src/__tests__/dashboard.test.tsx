import { describe, expect, it } from 'vitest'

describe('dashboard contracts', () => {
  it('defines dashboard feature boundaries', async () => {
    const page = await import('../pages/DashboardPage')
    expect(page.default).toBeTypeOf('function')
  })
  it('exposes reusable property-detail composition', async () => {
    const detail = await import('../components/PropertyDetailPage')
    expect(detail.TabContent).toBeTypeOf('function')
    expect(detail.PipelineProgress).toBeTypeOf('function')
  })
})
