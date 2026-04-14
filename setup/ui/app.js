/**
 * Expense Tracker Setup Wizard
 * Multi-step wizard state machine — vanilla JS, no build step needed.
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  step: 1,          // current step (1-8)
  totalSteps: 8,
  prereqs: null,
  dbConfig: {},
  gmailConfig: {},
  llmConfig: {},
  emailCount: 0,
};

// Human-readable step labels for the progress bar
const STEP_LABELS = [
  'Welcome', 'System', 'Database', 'Gmail',
  'Labels', 'AI Setup', 'Install', 'Launch',
];

// ---------------------------------------------------------------------------
// Bootstrap: check if setup is already done and auto-launch if ?launch=1
// ---------------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  const launchOnly = params.get('launch') === '1';

  if (launchOnly) {
    state.step = 8;
    render();
    return;
  }

  try {
    const res = await api('/api/status');
    if (res.setup_complete) {
      state.step = 8;
      render();
      return;
    }
  } catch (_) {}

  render();
});

// ---------------------------------------------------------------------------
// Router: decide which step to render
// ---------------------------------------------------------------------------
function render() {
  updateProgressBar();
  const el = document.getElementById('content');
  el.innerHTML = '';

  const steps = {
    1: renderWelcome,
    2: renderPrereqs,
    3: renderDatabase,
    4: renderGmail,
    5: renderLabels,
    6: renderLLM,
    7: renderInstall,
    8: renderLaunch,
  };

  const fn = steps[state.step];
  if (fn) fn(el);
}

function goTo(n) {
  state.step = n;
  render();
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------
function updateProgressBar() {
  const bar = document.getElementById('progress-bar');
  const container = document.getElementById('step-indicators');

  if (state.step === 1) { bar.classList.add('hidden'); return; }
  bar.classList.remove('hidden');

  container.innerHTML = STEP_LABELS.map((label, i) => {
    const n = i + 1;
    const done = n < state.step;
    const active = n === state.step;
    const circleClass = done
      ? 'bg-indigo-600 text-white'
      : active
        ? 'bg-indigo-600 text-white ring-2 ring-indigo-300'
        : 'bg-gray-200 text-gray-500';
    const labelClass = active ? 'font-semibold text-indigo-700' : done ? 'text-gray-500' : 'text-gray-400';
    const connector = i < STEP_LABELS.length - 1
      ? `<div class="step-connector ${done ? 'bg-indigo-400' : 'bg-gray-200'}"></div>`
      : '';
    return `
      <div class="flex items-center gap-1">
        <div class="flex flex-col items-center gap-0.5">
          <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${circleClass}">
            ${done ? '✓' : n}
          </div>
          <span class="hidden sm:block ${labelClass}" style="font-size:0.6rem;white-space:nowrap">${label}</span>
        </div>
      </div>
      ${connector}
    `;
  }).join('');
}

// ---------------------------------------------------------------------------
// Step 1 — Welcome
// ---------------------------------------------------------------------------
function renderWelcome(el) {
  el.innerHTML = `
    <div class="step-card text-center py-4">
      <div class="w-20 h-20 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg class="w-10 h-10 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <h1 class="text-2xl font-bold text-gray-900 mb-2">Expense Tracker Setup</h1>
      <p class="text-gray-500 mb-1">Let's get your personal finance tracker running.</p>
      <p class="text-sm text-gray-400 mb-8">Takes about <strong class="text-gray-600">5 minutes</strong> — we'll walk you through every step.</p>

      <div class="flex justify-center gap-6 text-sm text-gray-500 mb-8">
        <div class="flex items-center gap-1.5">
          <span class="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-600 text-xs">✓</span>
          Database
        </div>
        <div class="flex items-center gap-1.5">
          <span class="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-600 text-xs">✓</span>
          Gmail
        </div>
        <div class="flex items-center gap-1.5">
          <span class="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-600 text-xs">✓</span>
          AI Assistant
        </div>
      </div>

      <button onclick="goTo(2)" class="w-full btn-primary py-3 text-base font-semibold">
        Let's Get Started →
      </button>
    </div>
  `;
  injectButtonStyles();
}

// ---------------------------------------------------------------------------
// Step 2 — Prerequisites
// ---------------------------------------------------------------------------
async function renderPrereqs(el) {
  el.innerHTML = `
    <div class="step-card">
      <h2 class="text-xl font-bold text-gray-900 mb-1">System Check</h2>
      <p class="text-gray-500 text-sm mb-6">Making sure your computer has everything needed.</p>
      <div id="prereq-list" class="space-y-3 mb-6">
        <div class="text-center text-gray-400 py-4"><span class="spinner"></span> Checking...</div>
      </div>
      <div class="flex gap-3">
        <button id="recheck-btn" onclick="renderPrereqs(document.getElementById('content'))"
          class="flex-1 btn-secondary py-2.5 font-medium">Re-check</button>
        <button id="next-prereqs" onclick="goTo(3)"
          class="flex-1 btn-primary py-2.5 font-medium" disabled>Next →</button>
      </div>
    </div>
  `;
  injectButtonStyles();

  try {
    const data = await api('/api/check-prereqs');
    state.prereqs = data;
    renderPrereqList(data);
    document.getElementById('next-prereqs').disabled = !data.ok;
  } catch (e) {
    document.getElementById('prereq-list').innerHTML = errorBox(`Could not run system check: ${e.message}`);
  }
}

function renderPrereqList(data) {
  const list = document.getElementById('prereq-list');
  const items = Object.values(data.results);
  list.innerHTML = items.map(item => `
    <div class="flex items-start justify-between p-4 rounded-xl border ${item.ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}">
      <div>
        <div class="font-medium text-gray-800">${item.name}</div>
        ${item.found
          ? `<div class="text-xs text-gray-500 mt-0.5">Found: v${item.found}</div>`
          : `<div class="text-xs text-red-600 mt-0.5">Not found — <a href="${item.download}" target="_blank" class="underline">Download here</a></div>`
        }
        ${!item.ok && item.instruction ? `<div class="text-xs text-gray-600 mt-1">${item.instruction}</div>` : ''}
      </div>
      <span class="text-lg ml-4 mt-0.5">${item.ok ? '✅' : '❌'}</span>
    </div>
  `).join('');
}

// ---------------------------------------------------------------------------
// Step 3 — Database
// ---------------------------------------------------------------------------
function renderDatabase(el) {
  el.innerHTML = `
    <div class="step-card">
      <h2 class="text-xl font-bold text-gray-900 mb-1">Database Setup</h2>
      <p class="text-gray-500 text-sm mb-6">
        We'll create a private database to store your expense data.
      </p>

      <div class="space-y-4 mb-6">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">PostgreSQL Admin Password</label>
          <p class="text-xs text-gray-400 mb-2">The password you chose when you installed PostgreSQL.</p>
          <input id="admin-pass" type="password" placeholder="postgres admin password"
            class="w-full input-field" autocomplete="off" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">New Database Password</label>
          <p class="text-xs text-gray-400 mb-2">Choose any password for the expense tracker database.</p>
          <input id="db-pass" type="password" placeholder="choose a password"
            class="w-full input-field mb-2" autocomplete="new-password" />
          <input id="db-pass-confirm" type="password" placeholder="confirm password"
            class="w-full input-field" autocomplete="new-password" />
        </div>
      </div>

      <div id="db-status" class="mb-4"></div>

      <div class="flex gap-3">
        <button onclick="goTo(2)" class="flex-1 btn-secondary py-2.5 font-medium">← Back</button>
        <button id="db-btn" onclick="doSetupDatabase()" class="flex-1 btn-primary py-2.5 font-medium">
          Create Database →
        </button>
      </div>
    </div>
  `;
  injectButtonStyles();
  injectInputStyles();
}

async function doSetupDatabase() {
  const adminPass = document.getElementById('admin-pass').value.trim();
  const dbPass = document.getElementById('db-pass').value.trim();
  const dbPassConfirm = document.getElementById('db-pass-confirm').value.trim();
  const statusEl = document.getElementById('db-status');
  const btn = document.getElementById('db-btn');

  if (!adminPass) { statusEl.innerHTML = warnBox('Please enter your PostgreSQL admin password.'); return; }
  if (!dbPass) { statusEl.innerHTML = warnBox('Please choose a database password.'); return; }
  if (dbPass !== dbPassConfirm) { statusEl.innerHTML = warnBox('Passwords do not match.'); return; }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Creating...';
  statusEl.innerHTML = '';

  try {
    const res = await api('/api/setup-database', 'POST', { admin_pass: adminPass, db_pass: dbPass });
    if (res.ok) {
      state.dbConfig = { admin_pass: adminPass, db_pass: dbPass };
      statusEl.innerHTML = successBox('Database created successfully!');
      setTimeout(() => goTo(4), 800);
    } else {
      statusEl.innerHTML = errorBox(res.message);
      btn.disabled = false;
      btn.innerHTML = 'Try Again →';
    }
  } catch (e) {
    statusEl.innerHTML = errorBox(`Request failed: ${e.message}`);
    btn.disabled = false;
    btn.innerHTML = 'Try Again →';
  }
}

// ---------------------------------------------------------------------------
// Step 4 — Gmail connection
// ---------------------------------------------------------------------------
function renderGmail(el) {
  el.innerHTML = `
    <div class="step-card">
      <h2 class="text-xl font-bold text-gray-900 mb-1">Connect Gmail</h2>
      <p class="text-gray-500 text-sm mb-5">
        The app reads your bank notification emails to extract transactions.
        We need a special <strong>App Password</strong> (not your regular Gmail password).
      </p>

      <!-- Sub-step 4a: Enable IMAP -->
      <details class="mb-4 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden" open>
        <summary class="px-4 py-3 cursor-pointer font-medium text-gray-700 text-sm flex items-center justify-between">
          <span>Step 1 — Enable IMAP in Gmail</span>
          <span class="text-gray-400 text-xs">click to expand</span>
        </summary>
        <div class="px-4 pb-4 text-sm text-gray-600 space-y-2">
          <ol class="list-decimal list-inside space-y-1.5">
            <li>Open <a href="https://mail.google.com/mail/u/0/#settings/fwdandpop" target="_blank" class="text-indigo-600 underline">Gmail → Settings → Forwarding and POP/IMAP</a></li>
            <li>Under <strong>IMAP access</strong>, select <strong>Enable IMAP</strong></li>
            <li>Click <strong>Save Changes</strong></li>
          </ol>
        </div>
      </details>

      <!-- Sub-step 4b: App Password -->
      <details class="mb-5 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden" open>
        <summary class="px-4 py-3 cursor-pointer font-medium text-gray-700 text-sm flex items-center justify-between">
          <span>Step 2 — Generate an App Password</span>
          <span class="text-gray-400 text-xs">click to expand</span>
        </summary>
        <div class="px-4 pb-4 text-sm text-gray-600 space-y-2">
          <ol class="list-decimal list-inside space-y-1.5">
            <li>Go to <a href="https://myaccount.google.com/apppasswords" target="_blank" class="text-indigo-600 underline">Google App Passwords</a>
              <span class="text-gray-400 text-xs">(requires 2-Step Verification to be enabled)</span>
            </li>
            <li>In "App name", type <strong>Expense Tracker</strong> and click <strong>Create</strong></li>
            <li>Google will show a 16-character password — copy it below</li>
          </ol>
          <p class="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2 mt-2">
            💡 If you don't see the App Passwords page, first enable
            <a href="https://myaccount.google.com/signinoptions/two-step-verification" target="_blank" class="underline">2-Step Verification</a>.
          </p>
        </div>
      </details>

      <div class="space-y-3 mb-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Gmail Address</label>
          <input id="gmail-email" type="email" placeholder="you@gmail.com"
            class="w-full input-field" value="${state.gmailConfig.email || ''}" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">App Password <span class="text-gray-400 font-normal text-xs">(16 characters, no spaces)</span></label>
          <input id="gmail-pass" type="password" placeholder="xxxx xxxx xxxx xxxx"
            class="w-full input-field" autocomplete="off" />
        </div>
      </div>

      <div id="gmail-status" class="mb-4"></div>

      <div class="flex gap-3">
        <button onclick="goTo(3)" class="flex-1 btn-secondary py-2.5 font-medium">← Back</button>
        <button id="gmail-btn" onclick="doTestGmail()" class="flex-1 btn-primary py-2.5 font-medium">
          Test Connection →
        </button>
      </div>
    </div>
  `;
  injectButtonStyles();
  injectInputStyles();
}

async function doTestGmail() {
  const email = document.getElementById('gmail-email').value.trim();
  const password = document.getElementById('gmail-pass').value.replace(/\s/g, '');
  const statusEl = document.getElementById('gmail-status');
  const btn = document.getElementById('gmail-btn');

  if (!email) { statusEl.innerHTML = warnBox('Please enter your Gmail address.'); return; }
  if (!password) { statusEl.innerHTML = warnBox('Please enter your App Password.'); return; }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Testing...';
  statusEl.innerHTML = '';

  try {
    const res = await api('/api/test-gmail', 'POST', { email, password });
    if (res.ok) {
      state.gmailConfig = { email, password };
      statusEl.innerHTML = successBox('Gmail connected!');
      setTimeout(() => goTo(5), 800);
    } else {
      statusEl.innerHTML = errorBox(res.message);
      btn.disabled = false;
      btn.innerHTML = 'Try Again →';
    }
  } catch (e) {
    statusEl.innerHTML = errorBox(`Request failed: ${e.message}`);
    btn.disabled = false;
    btn.innerHTML = 'Try Again →';
  }
}

// ---------------------------------------------------------------------------
// Step 5 — Gmail labels
// ---------------------------------------------------------------------------
function renderLabels(el) {
  const { email, password } = state.gmailConfig;

  el.innerHTML = `
    <div class="step-card">
      <h2 class="text-xl font-bold text-gray-900 mb-1">Email Setup</h2>
      <p class="text-gray-500 text-sm mb-5">
        We'll create the Gmail folders the app needs, and optionally move your existing bank emails.
      </p>

      <!-- Part A: Create labels -->
      <div class="rounded-xl border border-gray-200 p-4 mb-4">
        <div class="flex items-start justify-between mb-3">
          <div>
            <div class="font-medium text-gray-800 text-sm">Create Gmail Labels</div>
            <div class="text-xs text-gray-500 mt-0.5">Creates 3 folders in your Gmail account automatically.</div>
          </div>
          <span id="labels-status-icon" class="text-lg ml-3"></span>
        </div>
        <div id="labels-detail" class="text-xs text-gray-500 space-y-1 mb-3 hidden"></div>
        <button id="create-labels-btn" onclick="doCreateLabels()"
          class="w-full btn-primary py-2 text-sm font-medium">
          Create Labels Automatically
        </button>
      </div>

      <!-- Part B: Gmail filter guide -->
      <details class="mb-4 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden">
        <summary class="px-4 py-3 cursor-pointer font-medium text-gray-700 text-sm">
          Set Up Gmail Filter (so future emails auto-sort)
        </summary>
        <div class="px-4 pb-4 text-sm text-gray-600 space-y-2">
          <ol class="list-decimal list-inside space-y-1.5">
            <li>Open <a href="https://mail.google.com/mail/u/0/#settings/filters" target="_blank" class="text-indigo-600 underline">Gmail → Settings → Filters → Create new filter</a></li>
            <li>In the <strong>From</strong> field, paste:<br>
              <code class="bg-gray-100 rounded px-1.5 py-0.5 text-xs select-all">alerts@hdfcbank.net OR noreply@hdfcbank.com</code>
            </li>
            <li>Click <strong>Create filter</strong></li>
            <li>Check <strong>Apply the label</strong> → choose <strong>sync-expense-tracker</strong></li>
            <li>Check <strong>Skip the Inbox</strong>, then click <strong>Create filter</strong></li>
          </ol>
        </div>
      </details>

      <!-- Part C: Move existing emails -->
      <div class="rounded-xl border border-gray-200 p-4 mb-5">
        <div class="font-medium text-gray-800 text-sm mb-1">Move Existing Bank Emails</div>
        <div class="text-xs text-gray-500 mb-3">
          Searches your inbox for existing HDFC emails and moves them to <code class="bg-gray-100 rounded px-1">sync-expense-tracker</code>.
        </div>
        <div id="move-status" class="text-xs mb-2"></div>
        <button id="move-btn" onclick="doMoveEmails()"
          class="w-full btn-secondary py-2 text-sm font-medium">
          Find &amp; Move Existing Emails
        </button>
      </div>

      <div class="flex gap-3">
        <button onclick="goTo(4)" class="flex-1 btn-secondary py-2.5 font-medium">← Back</button>
        <button id="next-labels-btn" onclick="goTo(6)" class="flex-1 btn-primary py-2.5 font-medium">Next →</button>
      </div>
    </div>
  `;
  injectButtonStyles();
}

async function doCreateLabels() {
  const btn = document.getElementById('create-labels-btn');
  const icon = document.getElementById('labels-status-icon');
  const detail = document.getElementById('labels-detail');
  const { email, password } = state.gmailConfig;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Creating...';

  try {
    const res = await api('/api/create-gmail-labels', 'POST', { email, password });
    if (res.ok) {
      icon.textContent = '✅';
      detail.classList.remove('hidden');
      detail.innerHTML = Object.entries(res.labels).map(([label, status]) =>
        `<div>• <strong>${label}</strong>: ${status === 'created' ? '✓ Created' : status === 'already_exists' ? 'Already exists' : status}</div>`
      ).join('');
      btn.innerHTML = '✓ Labels Ready';
      btn.classList.replace('btn-primary', 'btn-success');
    } else {
      icon.textContent = '❌';
      btn.disabled = false;
      btn.innerHTML = 'Try Again';
      document.getElementById('labels-detail').innerHTML = `<div class="text-red-600">${res.message}</div>`;
      detail.classList.remove('hidden');
    }
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = 'Try Again';
  }
}

async function doMoveEmails() {
  const btn = document.getElementById('move-btn');
  const statusEl = document.getElementById('move-status');
  const { email, password } = state.gmailConfig;

  // First check how many exist
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Searching...';
  statusEl.innerHTML = '';

  try {
    const found = await api('/api/find-bank-emails', 'POST', { email, password });
    if (!found.ok) {
      statusEl.innerHTML = `<span class="text-red-600">${found.message}</span>`;
      btn.disabled = false;
      btn.innerHTML = 'Find &amp; Move Existing Emails';
      return;
    }

    if (found.count === 0) {
      statusEl.innerHTML = `<span class="text-gray-500">No existing HDFC emails found in your inbox.</span>`;
      btn.disabled = false;
      btn.innerHTML = 'Re-check';
      return;
    }

    // Confirm + move
    btn.innerHTML = `<span class="spinner"></span> Moving ${found.count} email${found.count > 1 ? 's' : ''}...`;
    const move = await api('/api/move-existing-emails', 'POST', { email, password });
    if (move.ok) {
      statusEl.innerHTML = `<span class="text-green-700">✓ Moved ${move.moved} email${move.moved !== 1 ? 's' : ''} to sync-expense-tracker</span>`;
      btn.innerHTML = '✓ Done';
    } else {
      statusEl.innerHTML = `<span class="text-red-600">${move.message}</span>`;
      btn.disabled = false;
      btn.innerHTML = 'Try Again';
    }
  } catch (e) {
    statusEl.innerHTML = `<span class="text-red-600">Error: ${e.message}</span>`;
    btn.disabled = false;
    btn.innerHTML = 'Try Again';
  }
}

// ---------------------------------------------------------------------------
// Step 6 — LLM / AI setup
// ---------------------------------------------------------------------------
function renderLLM(el) {
  el.innerHTML = `
    <div class="step-card">
      <h2 class="text-xl font-bold text-gray-900 mb-1">AI Assistant Setup</h2>
      <p class="text-gray-500 text-sm mb-5">
        The app uses an AI assistant to answer questions about your spending.
        Choose a provider and enter your API key — both are free to start.
      </p>

      <div class="grid grid-cols-2 gap-3 mb-5">
        <label id="gemini-card" class="provider-card selected cursor-pointer rounded-xl border-2 border-indigo-500 bg-indigo-50 p-4 text-center"
          onclick="selectProvider('GEMINI')">
          <div class="font-semibold text-gray-800">Gemini</div>
          <div class="text-xs text-gray-500 mt-1">by Google<br><span class="text-green-600 font-medium">Recommended · Free</span></div>
          <input type="radio" name="provider" value="GEMINI" checked class="hidden" />
        </label>
        <label id="groq-card" class="provider-card cursor-pointer rounded-xl border-2 border-gray-200 bg-gray-50 p-4 text-center"
          onclick="selectProvider('GROQ')">
          <div class="font-semibold text-gray-800">Groq</div>
          <div class="text-xs text-gray-500 mt-1">Faster inference<br><span class="text-green-600 font-medium">Also free</span></div>
          <input type="radio" name="provider" value="GROQ" class="hidden" />
        </label>
      </div>

      <div id="api-key-section">
        <label class="block text-sm font-medium text-gray-700 mb-1">
          <span id="provider-label">Gemini</span> API Key
          <a id="key-link" href="https://aistudio.google.com/apikey" target="_blank"
            class="ml-2 text-indigo-500 text-xs underline">Get a free key →</a>
        </label>
        <input id="api-key" type="password" placeholder="paste your API key here"
          class="w-full input-field mb-2" autocomplete="off" />
      </div>

      <div id="llm-status" class="mb-4"></div>

      <div class="flex gap-3">
        <button onclick="goTo(5)" class="flex-1 btn-secondary py-2.5 font-medium">← Back</button>
        <button id="llm-btn" onclick="doVerifyLLM()" class="flex-1 btn-primary py-2.5 font-medium">
          Verify Key →
        </button>
      </div>
    </div>
  `;
  injectButtonStyles();
  injectInputStyles();
}

let selectedProvider = 'GEMINI';
function selectProvider(p) {
  selectedProvider = p;
  ['GEMINI', 'GROQ'].forEach(prov => {
    const card = document.getElementById(`${prov.toLowerCase()}-card`);
    if (prov === p) {
      card.classList.add('border-indigo-500', 'bg-indigo-50');
      card.classList.remove('border-gray-200', 'bg-gray-50');
    } else {
      card.classList.remove('border-indigo-500', 'bg-indigo-50');
      card.classList.add('border-gray-200', 'bg-gray-50');
    }
  });
  document.getElementById('provider-label').textContent = p === 'GEMINI' ? 'Gemini' : 'Groq';
  document.getElementById('key-link').href = p === 'GEMINI'
    ? 'https://aistudio.google.com/apikey'
    : 'https://console.groq.com/keys';
}

async function doVerifyLLM() {
  const apiKey = document.getElementById('api-key').value.trim();
  const statusEl = document.getElementById('llm-status');
  const btn = document.getElementById('llm-btn');

  if (!apiKey) { statusEl.innerHTML = warnBox('Please enter your API key.'); return; }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Verifying...';
  statusEl.innerHTML = '';

  try {
    const res = await api('/api/test-llm-key', 'POST', { provider: selectedProvider, api_key: apiKey });
    if (res.ok) {
      state.llmConfig = { provider: selectedProvider, api_key: apiKey };
      statusEl.innerHTML = successBox(res.message);
      setTimeout(() => goTo(7), 800);
    } else {
      statusEl.innerHTML = errorBox(res.message);
      btn.disabled = false;
      btn.innerHTML = 'Try Again →';
    }
  } catch (e) {
    statusEl.innerHTML = errorBox(`Request failed: ${e.message}`);
    btn.disabled = false;
    btn.innerHTML = 'Try Again →';
  }
}

// ---------------------------------------------------------------------------
// Step 7 — Install dependencies
// ---------------------------------------------------------------------------
function renderInstall(el) {
  el.innerHTML = `
    <div class="step-card">
      <h2 class="text-xl font-bold text-gray-900 mb-1">Installing Everything</h2>
      <p class="text-gray-500 text-sm mb-4">
        This installs all required packages. It takes a few minutes the first time.
      </p>

      <!-- Progress stages -->
      <div id="stages" class="flex gap-2 text-xs mb-4 flex-wrap">
        ${['Config', 'Backend', 'Email Pipeline', 'Frontend'].map((s, i) =>
          `<div id="stage-${i}" class="px-2.5 py-1 rounded-full border border-gray-200 text-gray-400">${s}</div>`
        ).join('')}
      </div>

      <!-- Terminal output -->
      <div id="terminal-wrap" class="bg-gray-900 rounded-xl overflow-y-auto mb-4" style="height:240px;">
        <div id="terminal" class="text-gray-300 p-3">Waiting to start...\n</div>
      </div>

      <div id="install-status" class="mb-4"></div>

      <div class="flex gap-3">
        <button onclick="goTo(6)" id="back-install-btn" class="flex-1 btn-secondary py-2.5 font-medium">← Back</button>
        <button id="install-btn" onclick="doInstall()" class="flex-1 btn-primary py-2.5 font-medium">
          Start Installation →
        </button>
      </div>
    </div>
  `;
  injectButtonStyles();
}

function setStageActive(i) {
  for (let j = 0; j < 4; j++) {
    const el = document.getElementById(`stage-${j}`);
    if (!el) continue;
    el.className = j < i
      ? 'px-2.5 py-1 rounded-full border border-green-300 bg-green-50 text-green-700'
      : j === i
        ? 'px-2.5 py-1 rounded-full border border-indigo-400 bg-indigo-50 text-indigo-700 font-semibold'
        : 'px-2.5 py-1 rounded-full border border-gray-200 text-gray-400';
  }
}

function doInstall() {
  const btn = document.getElementById('install-btn');
  const backBtn = document.getElementById('back-install-btn');
  const terminal = document.getElementById('terminal');
  const wrap = document.getElementById('terminal-wrap');
  const statusEl = document.getElementById('install-status');

  btn.disabled = true;
  backBtn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Installing...';
  terminal.textContent = '';
  setStageActive(0);

  const es = new EventSource('/api/install');

  es.onmessage = (e) => {
    const line = e.data;
    terminal.textContent += line + '\n';
    wrap.scrollTop = wrap.scrollHeight;

    // Update stage indicators based on output
    if (line.includes('Writing configuration')) setStageActive(0);
    if (line.includes('Installing backend')) setStageActive(1);
    if (line.includes('email pipeline')) setStageActive(2);
    if (line.includes('frontend dep')) setStageActive(3);
  };

  es.addEventListener('done', () => {
    es.close();
    setStageActive(4); // all done
    statusEl.innerHTML = successBox('Installation complete! Ready to launch.');
    btn.disabled = false;
    btn.innerHTML = 'Launch App →';
    btn.onclick = () => goTo(8);
    backBtn.disabled = false;
  });

  es.addEventListener('error_event', (e) => {
    es.close();
    statusEl.innerHTML = errorBox(`Installation failed: ${e.data}`);
    btn.disabled = false;
    btn.innerHTML = 'Retry →';
    btn.onclick = doInstall;
    backBtn.disabled = false;
  });

  es.onerror = () => {
    // SSE connection closed (expected after done event)
    es.close();
  };
}

// ---------------------------------------------------------------------------
// Step 8 — Launch
// ---------------------------------------------------------------------------
function renderLaunch(el) {
  el.innerHTML = `
    <div class="step-card text-center py-4">
      <div id="launch-icon" class="w-20 h-20 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg class="w-10 h-10 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
            d="M5 3l14 9-14 9V3z" />
        </svg>
      </div>
      <h2 id="launch-title" class="text-2xl font-bold text-gray-900 mb-2">Ready to Launch!</h2>
      <p id="launch-desc" class="text-gray-500 text-sm mb-6">
        Click below to start all services and open your Expense Tracker.
      </p>
      <div id="launch-status" class="mb-4"></div>
      <button id="launch-btn" onclick="doLaunch()" class="w-full btn-primary py-3 text-base font-semibold">
        Launch Expense Tracker 🚀
      </button>
      <p class="text-xs text-gray-400 mt-4">
        Keep this terminal open — closing it will stop the app.<br>
        Next time, double-click <strong>Start App</strong> to launch directly.
      </p>
    </div>
  `;
  injectButtonStyles();
}

async function doLaunch() {
  const btn = document.getElementById('launch-btn');
  const statusEl = document.getElementById('launch-status');
  const title = document.getElementById('launch-title');
  const desc = document.getElementById('launch-desc');

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting services...';
  statusEl.innerHTML = '';

  try {
    const res = await api('/api/launch', 'POST', {});
    if (res.ok) {
      title.textContent = 'Your Expense Tracker is Running!';
      desc.innerHTML = 'Services started successfully. Click below to open the app.';
      statusEl.innerHTML = `
        <div class="flex justify-center gap-4 text-xs text-gray-500 mb-2">
          <span class="flex items-center gap-1">✅ Backend <code>:8000</code></span>
          <span class="flex items-center gap-1">✅ Frontend <code>:5173</code></span>
        </div>
      `;
      btn.disabled = false;
      btn.innerHTML = 'Open Expense Tracker →';
      btn.onclick = () => window.open('http://localhost:5173', '_blank');
    } else {
      statusEl.innerHTML = errorBox(res.message || 'Failed to start services. Check that PostgreSQL is running.');
      btn.disabled = false;
      btn.innerHTML = 'Try Again';
      btn.onclick = doLaunch;
    }
  } catch (e) {
    statusEl.innerHTML = errorBox(`Error: ${e.message}`);
    btn.disabled = false;
    btn.innerHTML = 'Try Again';
    btn.onclick = doLaunch;
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
async function api(path, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function successBox(msg) {
  return `<div class="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
    <span class="text-base">✅</span> ${msg}
  </div>`;
}

function errorBox(msg) {
  return `<div class="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
    <span class="text-base mt-0.5">❌</span> <span>${msg}</span>
  </div>`;
}

function warnBox(msg) {
  return `<div class="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
    <span class="text-base">⚠️</span> ${msg}
  </div>`;
}

function injectButtonStyles() {
  if (document.getElementById('btn-styles')) return;
  const style = document.createElement('style');
  style.id = 'btn-styles';
  style.textContent = `
    .btn-primary {
      background: #4f46e5; color: white; border-radius: 0.75rem;
      border: none; cursor: pointer; transition: background 0.15s;
      display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem;
    }
    .btn-primary:hover:not(:disabled) { background: #4338ca; }
    .btn-primary:disabled { background: #a5b4fc; cursor: not-allowed; }
    .btn-secondary {
      background: white; color: #374151; border-radius: 0.75rem;
      border: 1.5px solid #e5e7eb; cursor: pointer; transition: border-color 0.15s;
      display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem;
    }
    .btn-secondary:hover:not(:disabled) { border-color: #6366f1; color: #4f46e5; }
    .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-success {
      background: #16a34a; color: white; border-radius: 0.75rem;
      border: none; cursor: default;
      display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem;
    }
  `;
  document.head.appendChild(style);
}

function injectInputStyles() {
  if (document.getElementById('input-styles')) return;
  const style = document.createElement('style');
  style.id = 'input-styles';
  style.textContent = `
    .input-field {
      border: 1.5px solid #e5e7eb; border-radius: 0.65rem; padding: 0.6rem 0.85rem;
      font-size: 0.9rem; outline: none; transition: border-color 0.15s;
      width: 100%; box-sizing: border-box;
    }
    .input-field:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.12); }
  `;
  document.head.appendChild(style);
}
