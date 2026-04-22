import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { supabase } from './lib/supabase'
import { ToastProvider } from './contexts/ToastContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import Duplicates from './pages/Duplicates'
import NeedsReview from './pages/NeedsReview'
import Profile from './pages/Profile'
import GmailSetup from './pages/GmailSetup'
import AuthPage from './pages/AuthPage'
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

function ProtectedRoutes({ session }) {
  if (!session) return <Navigate to="/sign-in" replace />
  return (
    <>
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
    </>
  )
}

function App() {
  const [session, setSession] = useState(undefined) // undefined = loading

  useEffect(() => {
    supabase.auth.getSession()
      .then(({ data: { session } }) => setSession(session))
      .catch(() => setSession(null))
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })
    return () => subscription.unsubscribe()
  }, [])

  if (session === undefined) return null // loading — prevents flash of sign-in

  return (
    <ToastProvider>
      <Router>
        <Routes>
          <Route path="/sign-in" element={session ? <Navigate to="/" replace /> : <AuthPage />} />
          <Route path="/*" element={<ProtectedRoutes session={session} />} />
        </Routes>
      </Router>
    </ToastProvider>
  )
}

export default App
