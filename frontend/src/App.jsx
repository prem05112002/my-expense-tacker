import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { ToastProvider } from './contexts/ToastContext'
import { supabase } from './lib/supabase'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import Duplicates from './pages/Duplicates'
import NeedsReview from './pages/NeedsReview'
import Profile from './pages/Profile'
import GmailSetup from './pages/GmailSetup'
import AuthPage from './pages/AuthPage'
import { useApi } from './api/axios'

function AppInitializer({ session }) {
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

  return (
    <Layout session={session}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/duplicates" element={<Duplicates />} />
        <Route path="/needs-review" element={<NeedsReview />} />
        <Route path="/setup" element={<GmailSetup />} />
      </Routes>
    </Layout>
  )
}

function LoadingScreen() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function App() {
  const [session, setSession] = useState(undefined)

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
    })
    return () => subscription.unsubscribe()
  }, [])

  if (session === undefined) return <LoadingScreen />

  return (
    <ToastProvider>
      <Router>
        <Routes>
          <Route
            path="/auth"
            element={session ? <Navigate to="/" replace /> : <AuthPage />}
          />
          <Route
            path="/*"
            element={session ? <AppInitializer session={session} /> : <Navigate to="/auth" replace />}
          />
        </Routes>
      </Router>
    </ToastProvider>
  )
}

export default App
