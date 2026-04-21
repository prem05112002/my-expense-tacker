import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Tag, Key, Wifi, CheckCircle, XCircle, ArrowRight, ArrowLeft, ExternalLink, Loader2 } from 'lucide-react';
import { useApi } from '../api/axios';

const REQUIRED_LABELS = ['sync-expense-tracker', 'expenses', 'non-transaction'];
const STORAGE_KEY = 'gmail_setup_step';

const STEPS = [
  { icon: Wifi,      title: 'Enable IMAP'     },
  { icon: Tag,       title: 'Create Labels'   },
  { icon: Key,       title: 'App Password'    },
  { icon: Mail,      title: 'Connect'         },
];

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
      setStep(5);
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
    <div className="p-6 text-white h-[calc(100vh-4rem)] overflow-y-auto custom-scrollbar">
      <div className="max-w-xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Gmail Setup</h1>
          <p className="text-slate-400">
            Connect your Gmail so the expense tracker can sync your bank emails automatically.
          </p>
        </div>

        {/* Step progress */}
        {step < 5 && (
          <div className="flex items-center gap-2 mb-8">
            {STEPS.map((s, i) => {
              const n = i + 1;
              const done = step > n;
              const active = step === n;
              return (
                <React.Fragment key={n}>
                  <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                    active  ? 'bg-indigo-600 text-white' :
                    done    ? 'bg-teal-600/20 text-teal-400' :
                              'bg-white/5 text-slate-500'
                  }`}>
                    <s.icon size={14} />
                    <span className="hidden sm:inline">{s.title}</span>
                    <span className="sm:hidden">{n}</span>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div className={`flex-1 h-0.5 rounded ${step > n ? 'bg-teal-500' : 'bg-white/10'}`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        )}

        {/* Step 1 — Enable IMAP */}
        {step === 1 && (
          <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 space-y-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Wifi className="text-indigo-400" size={20} /> Enable IMAP in Gmail
            </h2>
            <p className="text-slate-400 text-sm">IMAP lets the expense tracker read your emails securely over an encrypted connection.</p>
            <ol className="space-y-2 text-sm text-slate-300 list-decimal list-inside leading-7">
              <li>Open Gmail Settings (gear icon → <strong>See all settings</strong>)</li>
              <li>Go to <strong>Forwarding and POP/IMAP</strong> tab</li>
              <li>Toggle <strong>Enable IMAP</strong> and click <strong>Save Changes</strong></li>
            </ol>
            <div className="flex gap-3 pt-2">
              <a
                href="https://mail.google.com/mail/u/0/#settings/fwdandpop"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors"
              >
                <ExternalLink size={14} /> Open Gmail Settings
              </a>
              <button onClick={() => setStep(2)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-bold transition-colors ml-auto">
                Done <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Step 2 — Create Labels */}
        {step === 2 && (
          <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 space-y-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Tag className="text-indigo-400" size={20} /> Create 3 Gmail Labels
            </h2>
            <p className="text-slate-400 text-sm">These labels control how the sync pipeline routes each email:</p>
            <div className="space-y-2">
              {[
                { name: 'sync-expense-tracker', desc: 'Source — unprocessed bank emails to sync' },
                { name: 'expenses',              desc: 'Done — successfully parsed transactions' },
                { name: 'non-transaction',       desc: 'Ignored — not a bank transaction' },
              ].map(({ name, desc }) => (
                <div key={name} className="flex items-center justify-between bg-[#222] rounded-lg px-4 py-3 border border-white/5">
                  <div>
                    <p className="text-sm font-mono font-bold text-white">{name}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{desc}</p>
                  </div>
                  <a
                    href={`https://mail.google.com/mail/u/0/#create-label?name=${encodeURIComponent(name)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-md text-xs font-medium transition-colors whitespace-nowrap ml-3"
                  >
                    <ExternalLink size={12} /> Create
                  </a>
                </div>
              ))}
            </div>
            <div className="flex gap-3 pt-2">
              <button onClick={() => setStep(1)} className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors">
                <ArrowLeft size={14} /> Back
              </button>
              <button onClick={() => setStep(3)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-bold transition-colors ml-auto">
                Done <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3 — App Password */}
        {step === 3 && (
          <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 space-y-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Key className="text-indigo-400" size={20} /> Generate a Gmail App Password
            </h2>
            <p className="text-slate-400 text-sm">App Passwords let the tracker log in without your main Google password. You need 2-Step Verification enabled.</p>
            <ol className="space-y-2 text-sm text-slate-300 list-decimal list-inside leading-7">
              <li>Open Google App Passwords (link below)</li>
              <li>Name it <strong>Expense Tracker</strong> and click <strong>Create</strong></li>
              <li>Copy the 16-character password shown — you'll need it in the next step</li>
            </ol>
            <div className="flex gap-3 pt-2">
              <a
                href="https://myaccount.google.com/apppasswords"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors"
              >
                <ExternalLink size={14} /> Open App Passwords
              </a>
              <button onClick={() => setStep(2)} className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors">
                <ArrowLeft size={14} /> Back
              </button>
              <button onClick={() => setStep(4)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-bold transition-colors ml-auto">
                Done <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Step 4 — Connect */}
        {step === 4 && (
          <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 space-y-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Mail className="text-indigo-400" size={20} /> Connect Your Gmail
            </h2>
            <p className="text-slate-400 text-sm">Enter your Gmail address and the app password you generated. We'll test the connection before saving.</p>
            <form onSubmit={handleConnect} className="space-y-4">
              <div>
                <label className="text-xs text-slate-400 font-bold uppercase block mb-2">Gmail Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  placeholder="you@gmail.com"
                  className="w-full bg-[#222] border border-white/10 rounded-lg p-3 text-white text-sm outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 font-bold uppercase block mb-2">App Password (16 characters)</label>
                <input
                  type="password"
                  value={appPassword}
                  onChange={e => setAppPassword(e.target.value)}
                  required
                  placeholder="xxxx xxxx xxxx xxxx"
                  className="w-full bg-[#222] border border-white/10 rounded-lg p-3 text-white text-sm outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              {/* Connection test status */}
              {loading && (
                <div className="flex items-center gap-3 bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-4">
                  <Loader2 size={18} className="text-indigo-400 animate-spin shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-indigo-300">Testing IMAP connection…</p>
                    <p className="text-xs text-slate-400 mt-0.5">Connecting to imap.gmail.com and verifying credentials</p>
                  </div>
                </div>
              )}
              {error && (
                <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                  <XCircle size={18} className="text-red-400 shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-red-300">Connection Failed</p>
                    <p className="text-xs text-slate-400 mt-0.5">{error}</p>
                  </div>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setStep(3)} className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors">
                  <ArrowLeft size={14} /> Back
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex items-center gap-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-bold transition-colors ml-auto"
                >
                  {loading ? <><Loader2 size={14} className="animate-spin" /> Testing…</> : <><Wifi size={14} /> Test & Connect</>}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Step 5 — Result */}
        {step === 5 && (
          <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 space-y-4">
            <div className="flex items-center gap-3">
              <CheckCircle size={24} className="text-green-400 shrink-0" />
              <h2 className="text-xl font-bold">IMAP Connection Successful</h2>
            </div>

            {/* Labels status */}
            <div className="space-y-2">
              <p className="text-xs text-slate-400 font-bold uppercase">Gmail Label Check</p>
              {REQUIRED_LABELS.map(label => {
                const found = labelsFound.includes(label);
                return (
                  <div key={label} className={`flex items-center gap-3 rounded-lg px-4 py-3 border ${found ? 'bg-green-500/5 border-green-500/20' : 'bg-amber-500/5 border-amber-500/20'}`}>
                    {found
                      ? <CheckCircle size={16} className="text-green-400 shrink-0" />
                      : <XCircle    size={16} className="text-amber-400 shrink-0" />}
                    <span className="font-mono text-sm text-white">{label}</span>
                    {!found && (
                      <a
                        href={`https://mail.google.com/mail/u/0/#create-label?name=${encodeURIComponent(label)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-auto flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300"
                      >
                        <ExternalLink size={12} /> Create
                      </a>
                    )}
                  </div>
                );
              })}
            </div>

            {labelsMissing.length > 0 && (
              <p className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-3">
                Create the missing labels in Gmail before finishing, then return here and click Finish Setup.
              </p>
            )}

            <div className="flex gap-3 pt-2">
              <button onClick={() => setStep(4)} className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors">
                <ArrowLeft size={14} /> Change Credentials
              </button>
              <button
                onClick={handleFinish}
                disabled={loading}
                className="flex items-center gap-2 px-5 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-bold transition-colors ml-auto"
              >
                {loading ? <><Loader2 size={14} className="animate-spin" /> Saving…</> : 'Finish Setup'}
              </button>
            </div>
          </div>
        )}

        {step < 4 && (
          <p className="mt-6 text-xs text-slate-500 text-center">
            Already set up IMAP and app password?{' '}
            <button
              onClick={() => setStep(4)}
              className="text-indigo-400 hover:text-indigo-300 underline"
            >
              Jump to Connect step
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
