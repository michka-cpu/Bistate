import { useState } from 'react'
import DashboardPage from './pages/DashboardPage'
import SearchPage from './pages/SearchPage'

export default function App() {
  const [page, setPage] = useState<'search' | 'pipeline'>('search')
  // The property a completed search/import should land on in the pipeline detail view.
  const [focusPropertyId, setFocusPropertyId] = useState<number | null>(null)

  const openProperty = (id: number) => { setFocusPropertyId(id); setPage('pipeline') }

  return page === 'search'
    ? <SearchPage onOpenPipeline={() => setPage('pipeline')} onOpenProperty={openProperty} />
    : <DashboardPage focusPropertyId={focusPropertyId} onOpenDiscovery={() => setPage('search')} />
}
