const HISTORY_STORAGE_KEY = 'promptalloy_history_v1';
const historyList = document.getElementById('historyList');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const toast = document.getElementById('toast');

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

function renderHistory() {
  const items = getHistory();
  if (!items.length) {
    historyList.innerHTML = '<p class="panel__hint">No history found yet. Generate a prompt first.</p>';
    return;
  }

  historyList.innerHTML = items.map((item) => {
    const createdAt = new Date(item.createdAt || Date.now()).toLocaleString();
    const title = String(item.description || '').slice(0, 90) || 'Untitled request';
    const task = item.taskType || 'other';
    return `
      <article class="history-item" data-open-session="${item.id}">
        <div class="history-item-top">
          <h3>${title}</h3>
          <span class="question-category">${task}</span>
        </div>
        <p class="history-meta">${createdAt} · ${item.style || 'auto'} · ${item.stats?.tokens || 0} tokens est.</p>
        <div class="history-actions">
          <button class="btn btn--action" data-open-session="${item.id}">Open In New Tab</button>
        </div>
      </article>
    `;
  }).join('');
}

historyList.addEventListener('click', (event) => {
  const target = event.target instanceof HTMLElement ? event.target : null;
  if (!target) return;
  const clickable = target.closest('[data-open-session]');
  if (!(clickable instanceof HTMLElement)) return;
  const sessionId = clickable.getAttribute('data-open-session');
  if (!sessionId) return;
  window.open(`/session?id=${encodeURIComponent(sessionId)}`, '_blank', 'noopener');
});

clearHistoryBtn.addEventListener('click', () => {
  localStorage.removeItem(HISTORY_STORAGE_KEY);
  renderHistory();
  showToast('History cleared.', 'success');
});

renderHistory();
