const TASK_ICONS = {
  coding: '💻',
  writing: '✍️',
  creative: '🎨',
  analysis: '🔍',
  explanation: '🧠',
  research: '📚',
  data: '📊',
  design: '🖌️',
  other: '✦',
};

const HISTORY_STORAGE_KEY = 'promptalloy_history_v1';

const userInput = document.getElementById('userInput');
const charCounter = document.getElementById('charCounter');
const analyzeBtn = document.getElementById('analyzeBtn');
const analyzeBtnLabel = analyzeBtn.querySelector('.btn__label');
const generateBtn = document.getElementById('generateBtn');
const generateBtnLabel = generateBtn.querySelector('.btn__label');
const backBtn = document.getElementById('backBtn');
const copyBtn = document.getElementById('copyBtn');
const saveBtn = document.getElementById('saveBtn');
const startOverBtn = document.getElementById('startOverBtn');
const historyBtn = document.getElementById('historyBtn');
const historyOverlay = document.getElementById('historyOverlay');
const historyPopupList = document.getElementById('historyPopupList');
const historyCloseBtn = document.getElementById('historyCloseBtn');
const historyClearBtn = document.getElementById('historyClearBtn');
const taskBadge = document.getElementById('taskBadge');
const questionsContainer = document.getElementById('questionsContainer');
const mdOutput = document.getElementById('mdOutput');
const rawPrompt = document.getElementById('rawPrompt');
const statsBar = document.getElementById('statsBar');
const statChars = document.getElementById('statChars');
const statWords = document.getElementById('statWords');
const statTokens = document.getElementById('statTokens');
const explanation = document.getElementById('explanation');
const explanationList = document.getElementById('explanationList');
const toast = document.getElementById('toast');

const stepPanel1 = document.getElementById('stepPanel1');
const stepPanel2 = document.getElementById('stepPanel2');
const stepPanel3 = document.getElementById('stepPanel3');
const wizNav1 = document.getElementById('wizNav1');
const wizNav2 = document.getElementById('wizNav2');
const wizNav3 = document.getElementById('wizNav3');
const wizLine1 = document.getElementById('wizLine1');
const wizLine2 = document.getElementById('wizLine2');

let currentTaskType = 'other';
let questionBank = [];
let cooldownTimerId = null;
let cooldownActive = false;

function validateDescription(text) {
  if (text.length < 10) {
    return 'Too short — please write at least a sentence about your project.';
  }
  if (/(.)\1{4,}/.test(text)) {
    return 'Please provide a meaningful project description.';
  }
  const words = (text.match(/[a-zA-Z]{3,}/g) || []);
  if (words.length < 3) {
    return 'Please describe your project idea with at least a few real words.';
  }

  function isGibberish(word) {
    const w = word.toLowerCase();
    if (w.length < 4) return false;
    const vowels = (w.match(/[aeiou]/g) || []).length;
    const ratio = vowels / w.length;
    if (ratio < 0.15 || ratio > 0.85) return true;
    if (/[^aeiou]{4,}/.test(w)) return true;
    if (/(.)(\1){2,}/.test(w)) return true;
    const common = ['th','he','in','er','an','re','on','at','en','nd',
      'ti','es','or','te','of','ed','is','it','al','ar',
      'st','to','nt','ng','se','ha','as','ou','io','le',
      've','co','me','de','hi','ri','ro','ic','ne','ea',
      'ra','ce','li','ch','ll','be','ma','si','om','ur',
      'la','no','ta','el','ni','di','na','pe','ec','ca',
      'ad','bi','bu','da','do','fi','fo','ge','gi','go',
      'gr','gu','ho','hu','id','im','ke','ki','lo','lu',
      'mi','mo','mu','ob','op','ot','pa','pi','po','pr',
      'pu','qu','sa','sc','sh','sk','sl','sm','sn','so',
      'sp','sq','su','sw','sy','tr','tu','ty','ul','um',
      'un','up','us','ut','vi','vo','wa','we','wi','wo'];
    if (w.length >= 6 && !common.some(bg => w.includes(bg))) return true;
    return false;
  }

  const hasGibberish = words.some(isGibberish);
  if (hasGibberish) {
    return "Part of your description doesn't look like real words. Please describe your project clearly in plain English.";
  }
  const realWords = words.filter(w => !isGibberish(w));
  if (realWords.length < 3) {
    return 'Please describe your project idea with at least a few clear words.';
  }
  return null;
}

function setStep(step) {
  stepPanel1.hidden = step !== 1;
  stepPanel2.hidden = step !== 2;
  stepPanel3.hidden = step !== 3;

  [wizNav1, wizNav2, wizNav3].forEach((el) => el.classList.remove('wiz-step--active', 'wiz-step--done'));
  [wizLine1, wizLine2].forEach((el) => el.classList.remove('wiz-line--active'));

  if (step >= 1) wizNav1.classList.add(step === 1 ? 'wiz-step--active' : 'wiz-step--done');
  if (step >= 2) {
    wizLine1.classList.add('wiz-line--active');
    wizNav2.classList.add(step === 2 ? 'wiz-step--active' : 'wiz-step--done');
  }
  if (step >= 3) {
    wizLine2.classList.add('wiz-line--active');
    wizNav3.classList.add('wiz-step--active');
  }
}

function showToast(msg, type = 'default') {
  clearTimeout(showToast.timerId);
  toast.textContent = msg;
  toast.className = `toast toast--${type} toast--show`;
  showToast.timerId = setTimeout(() => {
    toast.classList.remove('toast--show');
  }, 2800);
}

function setBtnLoading(button, on) {
  button.disabled = on;
  button.classList.toggle('btn--loading', on);
}

function extractRetrySeconds(message) {
  const match = String(message || '').match(/(\d+)\s*seconds?/i);
  if (!match) return null;
  const n = Number.parseInt(match[1], 10);
  return Number.isNaN(n) ? null : n;
}

function startRateLimitCooldown(seconds) {
  const total = Math.max(1, Number.parseInt(seconds, 10) || 5);
  let remaining = total;

  if (cooldownTimerId) clearInterval(cooldownTimerId);
  cooldownActive = true;
  setBtnLoading(generateBtn, false);
  generateBtn.disabled = true;
  generateBtnLabel.textContent = `Retry in ${remaining}s`;

  cooldownTimerId = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(cooldownTimerId);
      cooldownTimerId = null;
      cooldownActive = false;
      generateBtn.disabled = false;
      generateBtnLabel.textContent = 'Generate My Prompt →';
      showToast('You can generate again now.', 'success');
      return;
    }
    generateBtnLabel.textContent = `Retry in ${remaining}s`;
  }, 1000);
}

function countWords(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function estimateTokens(text) {
  return Math.max(1, Math.ceil(text.length / 4));
}

function updateStats(text) {
  statChars.textContent = text.length.toLocaleString();
  statWords.textContent = countWords(text).toLocaleString();
  statTokens.textContent = estimateTokens(text).toLocaleString();
}

function renderExplanation(raw) {
  explanationList.innerHTML = '';
  const lines = String(raw || '')
    .split(/\n|(?=•)/)
    .map((l) => l.replace(/^[•\-\*]\s*/, '').trim())
    .filter(Boolean);

  if (!lines.length) {
    explanation.hidden = true;
    return;
  }

  lines.forEach((line) => {
    const li = document.createElement('li');
    li.textContent = line;
    explanationList.appendChild(li);
  });
  explanation.hidden = false;
}

function renderQuestions(questions) {
  questionsContainer.innerHTML = '';
  if (!questions.length) {
    questionsContainer.innerHTML = '<p class="panel__hint">No extra clarification needed. You can generate immediately.</p>';
    return;
  }

  questions.forEach((item, idx) => {
    const row = document.createElement('div');
    row.className = 'question-row';
    const qId = Number(item.id) || idx + 1;
    const category = String(item.category || 'scope').trim().toLowerCase();
    const why = String(item.why || '').trim();
    const hint = item.hint ? ` placeholder="${String(item.hint).replace(/"/g, '&quot;')}"` : '';
    row.innerHTML = `
      <div class="question-meta">
        <span class="question-category">${category}</span>
      </div>
      <label class="question-label" for="answer-${qId}">${qId}. ${item.question}</label>
      ${why ? `<p class="question-why">Why: ${why}</p>` : ''}
      <div class="answer-row">
        <textarea id="answer-${qId}" class="textarea question-input" rows="3"${hint}>${item.answer || ''}</textarea>
        <button class="btn btn--auto-answer" type="button" data-qid="${qId}" title="Auto-generate answer">
          <span class="auto-label">Generate</span>
          <span class="auto-spinner" hidden>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </span>
        </button>
      </div>
    `;
    questionsContainer.appendChild(row);
  });

  // Attach auto-answer handlers
  questionsContainer.querySelectorAll('.btn--auto-answer').forEach((btn) => {
    btn.addEventListener('click', () => autoAnswerQuestion(btn));
  });
}

function syncAnswersFromUI() {
  questionBank = questionBank.map((q, idx) => {
    const qId = Number(q.id) || idx + 1;
    const input = document.getElementById(`answer-${qId}`);
    return { ...q, answer: input ? input.value.trim() : (q.answer || '') };
  });
}

function getAnsweredItems() {
  syncAnswersFromUI();
  return questionBank
    .map((q) => ({ question: q.question, answer: (q.answer || '').trim() }))
    .filter((qa) => qa.answer);
}

function normalizeForDedup(text) {
  return text.toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .filter(w => w.length > 2)
    .sort()
    .join(' ');
}

function isSimilarQuestion(q1, q2) {
  const words1 = new Set(normalizeForDedup(q1).split(' '));
  const words2 = new Set(normalizeForDedup(q2).split(' '));
  if (words1.size === 0 || words2.size === 0) return q1.toLowerCase() === q2.toLowerCase();
  const intersection = [...words1].filter(w => words2.has(w)).length;
  const union = new Set([...words1, ...words2]).size;
  return (intersection / union) > 0.55;
}

function mergeQuestions(newQuestions) {
  syncAnswersFromUI();
  let nextId = questionBank.length + 1;

  newQuestions.forEach((item) => {
    const questionText = String(item.question || '').trim();
    if (!questionText) return;
    const isDuplicate = questionBank.some(existing => isSimilarQuestion(existing.question, questionText));
    if (isDuplicate) return;

    questionBank.push({
      id: nextId,
      category: String(item.category || 'scope').trim().toLowerCase(),
      question: questionText,
      hint: String(item.hint || '').trim(),
      why: String(item.why || '').trim(),
      answer: '',
    });
    nextId += 1;
  });
}

async function autoAnswerQuestion(btn) {
  const qId = btn.dataset.qid;
  const textarea = document.getElementById(`answer-${qId}`);
  const labelEl = btn.querySelector('.auto-label');
  const spinnerEl = btn.querySelector('.auto-spinner');
  if (!textarea) return;

  const question = questionBank.find((q) => String(q.id) === String(qId));
  if (!question) return;

  // Show loading
  btn.disabled = true;
  labelEl.hidden = true;
  spinnerEl.hidden = false;

  try {
    const data = await fetchJson('/auto-answer', {
      project_description: userInput.value.trim(),
      question: question.question,
    });
    textarea.value = data.answer || '';
    showToast('Answer generated!', 'success');
  } catch (err) {
    showToast(err.message || 'Failed to generate answer', 'error');
  } finally {
    btn.disabled = false;
    labelEl.hidden = false;
    spinnerEl.hidden = true;
  }
}

function renderMarkdown(markdownText) {
  mdOutput.textContent = markdownText;
}

async function fetchJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok || data.error) {
    const err = new Error(data.error || 'Unknown error from server.');
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function saveHistorySession(payload) {
  const existing = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY) || '[]');
  const history = Array.isArray(existing) ? existing : [];
  history.unshift(payload);
  localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history.slice(0, 100)));

  fetch('/api/history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {
    // Keep local backup even if server sync fails.
  });
}

async function getHistorySessions() {
  try {
    const res = await fetch('/api/history');
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.items) && data.items.length) {
        return data.items;
      }
    }
  } catch {
    // Fall through to local fallback.
  }

  const raw = localStorage.getItem(HISTORY_STORAGE_KEY) || '[]';
  try {
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

async function renderHistoryPopup() {
  const history = await getHistorySessions();
  if (!history.length) {
    historyPopupList.innerHTML = '<p class="panel__hint">No history yet. Generate a prompt to create your first session.</p>';
    return;
  }

  historyPopupList.innerHTML = history.map((item) => {
    const title = String(item.description || 'Untitled request').slice(0, 96);
    const createdAt = new Date(item.createdAt || Date.now()).toLocaleString();
    const taskType = item.taskType || 'other';
    const tokens = item.stats?.tokens || 0;
    return `
      <article class="history-item" data-open-session="${item.id}">
        <div class="history-item-top">
          <h3>${title}</h3>
          <span class="question-category">${taskType}</span>
        </div>
        <p class="history-meta">${createdAt} · ${tokens} tokens est.</p>
      </article>
    `;
  }).join('');
}

function openHistoryPopup() {
  renderHistoryPopup();
  historyOverlay.classList.add('is-open');
  historyOverlay.hidden = false;
}

function closeHistoryPopup() {
  historyOverlay.classList.remove('is-open');
  historyOverlay.hidden = true;
}

function createSmartFileName(description, taskType) {
  const text = String(description || '').toLowerCase();
  const words = (text.match(/[a-z0-9]+/g) || [])
    .filter((w) => w.length > 2 && !['web', 'app', 'build', 'create', 'make', 'want', 'that'].includes(w))
    .slice(0, 4);

  const base = words.length ? words.join('-') : `${taskType || 'project'}-plan`;
  return base.replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 48);
}

function buildSessionRecord(markdownPrompt, explanationText) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: new Date().toISOString(),
    description: userInput.value.trim(),
    style: "structured",
    taskType: currentTaskType,
    questions: questionBank,
    answers: getAnsweredItems(),
    refinedPrompt: markdownPrompt,
    explanation: explanationText,
    stats: {
      characters: markdownPrompt.length,
      words: countWords(markdownPrompt),
      tokens: estimateTokens(markdownPrompt),
    },
  };
}

analyzeBtn.addEventListener('click', async () => {
  const description = userInput.value.trim();
  if (!description) {
    userInput.focus();
    showToast('Please describe what you need first.', 'error');
    return;
  }

  const validationError = validateDescription(description);
  if (validationError) {
    userInput.focus();
    showToast(validationError, 'error');
    return;
  }

  setBtnLoading(analyzeBtn, true);
  try {
    questionBank = [];

    const data = await fetchJson('/ask', {
      description,
      answers: [],
      asked_questions: [],
    });
    currentTaskType = String(data.task_type || 'other').toLowerCase();
    taskBadge.textContent = `${TASK_ICONS[currentTaskType] || TASK_ICONS.other} ${currentTaskType}`;
    taskBadge.setAttribute('data-type', currentTaskType);
    taskBadge.hidden = false;

    const questions = Array.isArray(data.questions) ? data.questions : [];
    mergeQuestions(questions);
    renderQuestions(questionBank);
    setStep(2);
    showToast('Questions ready — answer what you can, then generate.', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    setBtnLoading(analyzeBtn, false);
  }
});

generateBtn.addEventListener('click', async () => {
  const description = userInput.value.trim();
  if (!description) {
    setStep(1);
    userInput.focus();
    showToast('Please add your description first.', 'error');
    return;
  }

  setBtnLoading(generateBtn, true);
  try {
    const data = await fetchJson('/generate', {
      description,
      style: 'structured',
      answers: getAnsweredItems(),
    });

    const markdownPrompt = data.refined_prompt || '';
    rawPrompt.value = markdownPrompt;
    renderMarkdown(markdownPrompt);
    updateStats(markdownPrompt);
    renderExplanation(data.explanation || '');
    saveHistorySession(buildSessionRecord(markdownPrompt, data.explanation || ''));
    setStep(3);
    showToast('Prompt generated.', 'success');
  } catch (err) {
    if (err.status === 429) {
      const retrySeconds = err.data?.retry_seconds || extractRetrySeconds(err.message) || 5;
      startRateLimitCooldown(retrySeconds);
    }
    showToast(err.message, 'error');
  } finally {
    if (!cooldownActive) setBtnLoading(generateBtn, false);
  }
});

backBtn.addEventListener('click', () => {
  setStep(1);
});

copyBtn.addEventListener('click', async () => {
  const text = rawPrompt.value;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    showToast('Prompt copied.', 'success');
  } catch {
    showToast('Could not copy automatically.', 'error');
  }
});

saveBtn.addEventListener('click', () => {
  const text = rawPrompt.value;
  if (!text) return;
  const filename = `${createSmartFileName(userInput.value, currentTaskType).replace('.md', '')}-blueprint.md`;
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  showToast(`Saved ${filename}`, 'success');
});

historyBtn.addEventListener('click', () => {
  openHistoryPopup();
});

historyCloseBtn.addEventListener('click', () => {
  closeHistoryPopup();
});

historyClearBtn.addEventListener('click', async () => {
  const confirmed = window.confirm('Are you sure you want to clear all history? This cannot be undone.');
  if (!confirmed) return;

  localStorage.removeItem(HISTORY_STORAGE_KEY);
  try {
    await fetch('/api/history', { method: 'DELETE' });
  } catch {
    // Keep local clear behavior even if server call fails.
  }
  renderHistoryPopup();
  showToast('History cleared.', 'success');
});

historyOverlay.addEventListener('click', (event) => {
  const target = event.target;
  if (target === historyOverlay) {
    closeHistoryPopup();
    return;
  }

  const el = target instanceof HTMLElement ? target.closest('[data-open-session]') : null;
  if (!(el instanceof HTMLElement)) return;
  const sessionId = el.getAttribute('data-open-session');
  if (!sessionId) return;
  window.open(`/session?id=${encodeURIComponent(sessionId)}`, '_blank', 'noopener');
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !historyOverlay.hidden) {
    closeHistoryPopup();
  }
});

startOverBtn.addEventListener('click', () => {
  currentTaskType = 'other';
  questionBank = [];
  taskBadge.hidden = true;
  questionsContainer.innerHTML = '';
  rawPrompt.value = '';
  mdOutput.textContent = '';
  explanationList.innerHTML = '';
  explanation.hidden = true;
  setStep(1);
  userInput.focus();
});

userInput.addEventListener('input', () => {
  const len = userInput.value.length;
  charCounter.textContent = `${len} / 2000`;
  charCounter.className = `char-counter${len >= 2000 ? ' limit' : len >= 1600 ? ' warn' : ''}`;
});

userInput.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    analyzeBtn.click();
  }
});

statsBar.hidden = false;
explanation.hidden = true;
setStep(1);
closeHistoryPopup();
