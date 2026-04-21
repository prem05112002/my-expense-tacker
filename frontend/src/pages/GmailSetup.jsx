import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../api/axios';

const REQUIRED_LABELS = ['sync-expense-tracker', 'expenses', 'non-transaction'];
const STORAGE_KEY = 'gmail_setup_step';

export default function GmailSetup() {
  const api = useApi();
  const navigate = useNavigate();
  const [step, setStep] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? parseInt(saved, 10) : 1;
  });
  const [email, setEmail] = useState('');
  const [appPassword, setAppPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [labelsFound, setLabelsFound] = useState([]);
  const [labelsMissing, setLabelsMissing] = useState([]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, step);
  }, [step]);

  async function handleConnect(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/gmail-setup/save', { email, app_password: appPassword });
      setLabelsFound(res.data.labels_found);
      setLabelsMissing(res.data.labels_missing);
      setStep(5); // show result step
    } catch (err) {
      setError(err.response?.data?.detail || 'Connection failed — check your email and app password.');
    } finally {
      setLoading(false);
    }
  }

  async function handleFinish() {
    setLoading(true);
    try {
      await api.post('/gmail-setup/mark-ready');
      localStorage.removeItem(STORAGE_KEY);
      navigate('/');
    } catch (err) {
      setError('Failed to save setup. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 560, margin: '60px auto', padding: '0 24px', fontFamily: 'sans-serif' }}>
      <h1 style={{ marginBottom: 4 }}>Gmail Setup</h1>
      <p style={{ color: '#64748b', marginBottom: 32 }}>
        Connect your Gmail so the expense tracker can sync your bank emails automatically.
      </p>

      {/* Progress bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 40 }}>
        {[1, 2, 3, 4].map(n => (
          <div key={n} style={{
            flex: 1, height: 4, borderRadius: 2,
            background: step >= n ? '#6366f1' : '#e2e8f0'
          }} />
        ))}
      </div>

      {/* Step 1 — Enable IMAP */}
      {step === 1 && (
        <div>
          <h2>Step 1 — Enable IMAP in Gmail</h2>
          <p>IMAP lets the expense tracker read your emails securely.</p>
          <ol style={{ lineHeight: 2 }}>
            <li>Open Gmail Settings</li>
            <li>Go to <strong>See all settings &rarr; Forwarding and POP/IMAP</strong></li>
            <li>Toggle <strong>Enable IMAP</strong> and click <strong>Save Changes</strong></li>
          </ol>
          <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
            <a
              href="https://mail.google.com/mail/u/0/#settings/fwdandpop"
              target="_blank"
              rel="noopener noreferrer"
              style={btnStyle('#6366f1')}
            >
              Open Gmail Settings
            </a>
            <button onClick={() => setStep(2)} style={btnStyle('#22c55e')}>
              Done, next step &rarr;
            </button>
          </div>
        </div>
      )}

      {/* Step 2 — Create Labels */}
      {step === 2 && (
        <div>
          <h2>Step 2 — Create 3 Gmail Labels</h2>
          <p>These labels tell the sync pipeline what to do with each email:</p>
          <ul style={{ lineHeight: 2 }}>
            <li><strong>sync-expense-tracker</strong> — source: unprocessed bank emails</li>
            <li><strong>expenses</strong> — done: successfully parsed transactions</li>
            <li><strong>non-transaction</strong> — ignored: not a bank transaction</li>
          </ul>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
            {REQUIRED_LABELS.map(label => (
              <a
                key={label}
                href={`https://mail.google.com/mail/u/0/#create-label?name=${encodeURIComponent(label)}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ ...btnStyle('#6366f1'), textAlign: 'center' }}
              >
                Create label: {label}
              </a>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
            <button onClick={() => setStep(1)} style={btnStyle('#94a3b8')}>Back</button>
            <button onClick={() => setStep(3)} style={btnStyle('#22c55e')}>Done, next step &rarr;</button>
          </div>
        </div>
      )}

      {/* Step 3 — Generate App Password */}
      {step === 3 && (
        <div>
          <h2>Step 3 — Generate a Gmail App Password</h2>
          <p>App Passwords let the tracker log in without your main Google password.</p>
          <ol style={{ lineHeight: 2 }}>
            <li>Open Google App Passwords (link below)</li>
            <li>Select app: <strong>Mail</strong></li>
            <li>Select device: <strong>Other</strong> — type <em>Expense Tracker</em></li>
            <li>Click <strong>Generate</strong> and copy the 16-character password shown</li>
          </ol>
          <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
            <a
              href="https://myaccount.google.com/apppasswords"
              target="_blank"
              rel="noopener noreferrer"
              style={btnStyle('#6366f1')}
            >
              Open App Passwords
            </a>
            <button onClick={() => setStep(2)} style={btnStyle('#94a3b8')}>Back</button>
            <button onClick={() => setStep(4)} style={btnStyle('#22c55e')}>Done, next step &rarr;</button>
          </div>
        </div>
      )}

      {/* Step 4 — Connect */}
      {step === 4 && (
        <div>
          <h2>Step 4 — Connect Your Gmail</h2>
          <p>Enter your Gmail address and the app password you just generated.</p>
          <form onSubmit={handleConnect} style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 16 }}>
            <label>
              <span style={labelStyle}>Gmail address</span>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="you@gmail.com"
                style={inputStyle}
              />
            </label>
            <label>
              <span style={labelStyle}>App password (16 characters)</span>
              <input
                type="password"
                value={appPassword}
                onChange={e => setAppPassword(e.target.value)}
                required
                placeholder="xxxx xxxx xxxx xxxx"
                style={inputStyle}
              />
            </label>
            {error && <p style={{ color: '#ef4444', margin: 0 }}>{error}</p>}
            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
              <button type="button" onClick={() => setStep(3)} style={btnStyle('#94a3b8')}>Back</button>
              <button type="submit" disabled={loading} style={btnStyle('#6366f1')}>
                {loading ? 'Connecting...' : 'Test & Connect'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Step 5 — Result */}
      {step === 5 && (
        <div>
          <h2>Connection Successful!</h2>
          {labelsMissing.length > 0 ? (
            <>
              <p style={{ color: '#f59e0b' }}>
                Some labels are missing. Create them before finishing:
              </p>
              <ul style={{ lineHeight: 2 }}>
                {labelsMissing.map(l => (
                  <li key={l}>
                    <a
                      href={`https://mail.google.com/mail/u/0/#create-label?name=${encodeURIComponent(l)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Create label: {l}
                    </a>
                  </li>
                ))}
              </ul>
              <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
                <button onClick={() => setStep(4)} style={btnStyle('#94a3b8')}>Back</button>
                <button onClick={handleFinish} disabled={loading} style={btnStyle('#6366f1')}>
                  {loading ? 'Saving...' : 'Finish anyway'}
                </button>
              </div>
            </>
          ) : (
            <>
              <p style={{ color: '#22c55e' }}>All {labelsFound.length} labels found. You are ready to go!</p>
              <button onClick={handleFinish} disabled={loading} style={{ ...btnStyle('#22c55e'), marginTop: 16 }}>
                {loading ? 'Saving...' : 'Finish Setup'}
              </button>
            </>
          )}
        </div>
      )}

      {/* Skip to step 4 */}
      {step < 4 && (
        <p style={{ marginTop: 40, color: '#94a3b8', fontSize: 13 }}>
          Already configured?{' '}
          <button
            onClick={() => setStep(4)}
            style={{ background: 'none', border: 'none', color: '#6366f1', cursor: 'pointer', textDecoration: 'underline' }}
          >
            Jump to Connect step
          </button>
        </p>
      )}
    </div>
  );
}

const btnStyle = (bg) => ({
  background: bg,
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '10px 20px',
  cursor: 'pointer',
  fontWeight: 600,
  textDecoration: 'none',
  display: 'inline-block',
});

const labelStyle = {
  display: 'block',
  marginBottom: 4,
  fontWeight: 600,
  fontSize: 14,
};

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  fontSize: 14,
  boxSizing: 'border-box',
};
