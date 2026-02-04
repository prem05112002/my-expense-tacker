import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ToastProvider } from './contexts/ToastContext';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Duplicates from './pages/Duplicates';
import NeedsReview from './pages/NeedsReview';
import Profile from './pages/Profile';
import ChatBot from './components/ChatBot';

function App() {
  return (
    <ToastProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/duplicates" element={<Duplicates />} />
            <Route path="/needs-review" element={<NeedsReview />} />
          </Routes>
        </Layout>
        <ChatBot />
      </Router>
    </ToastProvider>
  );
}

export default App;