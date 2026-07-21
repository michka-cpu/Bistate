import { useState } from 'react'
import DashboardPage from './pages/DashboardPage'
import SearchPage from './pages/SearchPage'

export default function App() {
  const [page, setPage] = useState<'search' | 'pipeline'>('search')
  return page === 'search' ? <SearchPage onPipeline={() => setPage('pipeline')} /> : <DashboardPage />
}
