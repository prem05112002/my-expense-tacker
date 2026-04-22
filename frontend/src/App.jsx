import React, { useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { ToastProvider } from './contexts/ToastContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import Duplicates from './pages/Duplicates'
import NeedsReview from './pages/NeedsReview'
import Profile from './pages/Profile'
import GmailSetup from './pages/GmailSetup'
import { useApi } from './api/axios'

function AppInitializer() {
  const api = useApi()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    ;(async () => {
      try { await api.post('/provision') } catch (e) { console.error('provision failed', e) }
      if (location.pathname === '/setup') return
      try {
        const res = await api.get('/gmail-setup/status')
        if (!res.data.configured) navigate('/setup', { replace: true })
      } catch (e) { console.error('setup status check failed', e) }
    })()
  }, [])

  return null
}

function App() {
  return (
    <ToastProvider>
      <Router>
        <AppInitializer />
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/duplicates" element={<Duplicates />} />
            <Route path="/needs-review" element={<NeedsReview />} />
            <Route path="/setup" element={<GmailSetup />} />
          </Routes>
        </Layout>
      </Router>
    </ToastProvider>
  )
}

export default App
