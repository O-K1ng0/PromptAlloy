const HISTORY_STORAGE_KEY = 'promptalloy_history_v1';
const sessionMeta = document.getElementById('sessionMeta');
const sessionPrompt = document.getElementById('sessionPrompt');
const sessionExplanation = document.getElementById('sessionExplanation');
const sessionExplanationWrap = document.getElementById('sessionExplanationWrap');
const toast = document.getElementById('toast');

const copyBtn = document.getElementById('copyBtn');
const saveFormatBtn = document.getElementById('saveFormatBtn');
const formatMenu = document.getElementById('formatMenu');
const formatItems = document.querySelectorAll('.format-item');
const editBtn = document.getElementById('editBtn');
const closeBtn = document.getElementById('closeBtn');

let currentSession = null;

function showToast(msg, type = 'default') {
  clearTimeout(showToast.timerId);
  toast.textContent = msg;
  toast.className = `toast toast--${type} toast--show`;
  showToast.timerId = setTimeout(() => toast.classList.remove('toast--show'), 2500);
}

function getHistory() {
  const raw = localStorage.getItem(HISTORY_STORAGE_KEY) || '[]';
  try {
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function getSessionId() {
  const url = new URL(window.location.href);
  return url.searchParams.get('id') || '';
}

async function fetchSessionFromServer(id) {
  const res = await fetch(`/api/history/${encodeURIComponent(id)}`);
  if (!res.ok) return null;
  const data = await res.json();
  return data && data.item ? data.item : null;
}

function renderExplanation(raw) {
  sessionExplanation.innerHTML = '';
  const lines = String(raw || '')
    .split(/\n|(?=•)/)
    .map((l) => l.replace(/^[•\-\*]\s*/, '').trim())
    .filter(Boolean);

  if (!lines.length) {
    sessionExplanationWrap.hidden = true;
    return;
  }

  sessionExplanationWrap.hidden = false;
  lines.forEach((line) => {
    const li = document.createElement('li');
    li.textContent = line;
    sessionExplanation.appendChild(li);
  });
}

function downloadFile(content, filename, mimeType = 'text/plain') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function getDownloadFilename(format, description) {
  const base = String(description || 'blueprint')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 40);
  const ext = format === 'md' ? 'md' : format === 'json' ? 'json' : 'txt';
  return `${base}-blueprint.${ext}`;
}

async function renderSession() {
  const id = getSessionId();
  let item = null;
  if (id) {
    try {
      item = await fetchSessionFromServer(id);
    } catch {
      item = null;
    }
  }
  if (!item) {
    item = getHistory().find((x) => String(x.id) === String(id));
  }

  if (!id || !item) {
    sessionMeta.innerHTML = '<p class="panel__hint">Session not found in local history.</p>';
    sessionPrompt.textContent = '';
    sessionExplanationWrap.hidden = true;
    return;
  }

  currentSession = item;
  const createdAt = new Date(item.createdAt || Date.now()).toLocaleString();
  sessionMeta.innerHTML = `
    <p class="history-meta"><strong>Created:</strong> ${createdAt}</p>
    <p class="history-meta"><strong>Project Type:</strong> ${item.taskType || 'other'} · <strong>Style:</strong> ${item.style || 'structured'}</p>
    <p class="history-meta"><strong>Description:</strong> ${item.description || ''}</p>
  `;

  sessionPrompt.textContent = item.refinedPrompt || '';
  renderExplanation(item.explanation || '');
  showToast('✓ Session loaded', 'success');
}

// Copy button handler
if (copyBtn) {
  copyBtn.addEventListener('click', () => {
    if (!currentSession) return;
    const text = currentSession.refinedPrompt || '';
    navigator.clipboard.writeText(text).then(() => {
      showToast('✓ Copied to clipboard!', 'success');
    }).catch(() => {
      showToast('Failed to copy', 'error');
    });
  });
}

// Format dropdown toggle
if (saveFormatBtn) {
  saveFormatBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    formatMenu.classList.toggle('show');
  });
}

// Format selection
formatItems.forEach((item) => {
  item.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!currentSession) return;
    const format = e.target.dataset.format;
    const content = currentSession.refinedPrompt || '';
    const filename = getDownloadFilename(format, currentSession.description || 'blueprint');
    let mimeType = 'text/plain';
    
    if (format === 'md') {
      mimeType = 'text/markdown';
      downloadFile(content, filename, mimeType);
    } else if (format === 'json') {
      mimeType = 'application/json';
      const jsonData = JSON.stringify(currentSession, null, 2);
      downloadFile(jsonData, filename, mimeType);
    } else {
      downloadFile(content, filename, mimeType);
    }
    
    showToast(`✓ Downloaded as ${format.toUpperCase()}!`, 'success');
    formatMenu.classList.remove('show');
  });
});

// Edit button - go back to main page with session data
if (editBtn) {
  editBtn.addEventListener('click', () => {
    if (!currentSession) return;
    localStorage.setItem('promptalloy_edit_session', JSON.stringify(currentSession));
    window.location.href = '/';
  });
}

// Close button - go back to history
if (closeBtn) {
  closeBtn.addEventListener('click', () => {
    window.history.back();
  });
}

// Close format menu when clicking outside
document.addEventListener('click', (e) => {
  if (formatMenu && !e.target.closest('.format-dropdown')) {
    formatMenu.classList.remove('show');
  }
});

renderSession();
