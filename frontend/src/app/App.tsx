import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Home } from '@/pages/Home'
import { ReportsList } from '@/pages/ReportsList'
import { ReportViewer } from '@/pages/ReportViewer'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30000, retry: 1 } },
})

export const App: React.FC = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/reports" element={<ReportsList />} />
        <Route path="/reports/:sessionId" element={<ReportViewer />} />
      </Routes>
    </BrowserRouter>
  </QueryClientProvider>
)
