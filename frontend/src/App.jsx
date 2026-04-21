import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { SignedIn, SignedOut, RedirectToSignIn, SignIn, useUser } from '@clerk/clerk-react';
import { ToastProvider } from './contexts/ToastContext';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Duplicates from './pages/Duplicates';
import NeedsReview from './pages/NeedsReview';
import Profile from './pages/Profile';
import GmailSetup from './pages/GmailSetup';
import { useApi } from './api/axios';

function AppInitializer() {
  const { isSignedIn } = useUser();
  const api = useApi();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!isSignedIn) return;

    (async () => {
      try {
        await api.post('/provision');
      } catch (e) {
        console.error('provision failed', e);
      }

      if (location.pathname === '/setup') return;

      try {
        const res = await api.get('/gmail-setup/status');
        if (!res.data.configured) {
          navigate('/setup', { replace: true });
        }
      } catch (e) {
        console.error('setup status check failed', e);
      }
    })();
  }, [isSignedIn]);

  return null;
}

function App() {
  return (
    <ToastProvider>
      <Router>
        <Routes>
          {/* Public sign-in route */}
          <Route path="/sign-in/*" element={<SignIn routing="path" path="/sign-in" />} />

          {/* All other routes require auth */}
          <Route path="/*" element={
            <>
              <SignedIn>
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
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          } />
        </Routes>
      </Router>
    </ToastProvider>
  );
}

export default App;
