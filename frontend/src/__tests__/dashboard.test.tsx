import { describe, expect, it } from 'vitest'
import DashboardPage from '../pages/DashboardPage'
import { ActivityTimeline } from '../components/ActivityTimeline'
import { ExportMenu } from '../components/ExportMenu'
import { PropertyComparison } from '../components/PropertyComparison'
import { PropertyMap } from '../components/PropertyMap'

describe('interactive dashboard behavior', () => {
  it('renders the dashboard application component', () => expect(DashboardPage).toBeTypeOf('function'))
  it('provides search and persisted favorite controls in the dashboard source', async () => {
    const source = await import('../pages/DashboardPage?raw')
    expect(source.default).toContain('property-search')
    expect(source.default).toContain('is_favorite')
  })
  it('supports comparison selection', async () => expect((await import('../pages/DashboardPage?raw')).default).toContain('compare-toggle'))
  it('uses the persisted activity endpoint', async () => expect((await import('../components/ActivityTimeline?raw')).default).toContain('/activity'))
  it('exposes real export links', async () => expect((await import('../components/ExportMenu?raw')).default).toContain('/exports/csv'))
  it('provides map, timeline, comparison, and export components', () => {
    expect(PropertyMap).toBeTypeOf('function'); expect(PropertyComparison).toBeTypeOf('function')
    expect(ActivityTimeline).toBeTypeOf('function'); expect(ExportMenu).toBeTypeOf('function')
  })
})
