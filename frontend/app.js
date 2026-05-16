/* ============================================================
   Task Board — app.js
   Communicates with FastAPI backend on http://localhost:8000
   WebSocket:  ws://localhost:8000/ws/tasks
   ============================================================ */

const API = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/tasks';

// ============================================================
// State
// ============================================================
const state = {
    tasks: new Map(),   // id → task object
    ws: null,
    wsRetryDelay: 1000,
};

// ============================================================
// API helpers
// ============================================================
async function apiFetch(path, options = {}) {
    const res = await fetch(`${API}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (res.status === 204) return null;
    const body = await res.json();
    if (!res.ok) {
        const err = new Error(body.detail || `HTTP ${res.status}`);
        err.status = res.status;
        err.body = body;
        throw err;
    }
    return body;
}

const api = {
    list: () => apiFetch('/tasks/'),
    create: (data) => apiFetch('/tasks/', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => apiFetch(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    complete: (id, version) => apiFetch(`/tasks/${id}/complete`, { method: 'POST', body: JSON.stringify({ expected_version: version }) }),
    delete: (id, version) => apiFetch(`/tasks/${id}?expected_version=${version}`, { method: 'DELETE' }),
};

// ============================================================
// WebSocket
// ============================================================
function connectWS() {
    setWsStatus('connecting');
    const ws = new WebSocket(WS_URL);
    state.ws = ws;

    ws.addEventListener('open', () => {
        setWsStatus('connected');
        state.wsRetryDelay = 1000;
    });

    ws.addEventListener('message', (e) => {
        try {
            const event = JSON.parse(e.data);
            handleServerEvent(event);
        } catch { /* ignore malformed frames */ }
    });

    ws.addEventListener('close', () => {
        setWsStatus('disconnected');
        // Exponential back-off, max 16 s
        setTimeout(connectWS, state.wsRetryDelay);
        state.wsRetryDelay = Math.min(state.wsRetryDelay * 2, 16000);
    });

    ws.addEventListener('error', () => ws.close());
}

function handleServerEvent(event) {
    const { type, task, task_id } = event;

    switch (type) {
        case 'task_created':
        case 'task_updated':
        case 'task_completed':
            if (task) {
                state.tasks.set(task.id, task);
                renderBoard();
            }
            break;
        case 'task_deleted':
            state.tasks.delete(task_id);
            renderBoard();
            break;
    }
}

function setWsStatus(status) {
    const el = document.getElementById('ws-indicator');
    const label = document.getElementById('ws-label');
    el.className = `ws-indicator ${status === 'connected' ? 'connected' : status === 'disconnected' ? 'disconnected' : ''}`;
    label.textContent = { connected: 'Live', disconnected: 'Verbroken', connecting: 'Verbinden…' }[status];
}

// ============================================================
// Rendering
// ============================================================
function renderBoard() {
    const todo = [...state.tasks.values()].filter(t => t.status === 'todo');
    const done = [...state.tasks.values()].filter(t => t.status === 'done');

    document.getElementById('count-todo').textContent = todo.length;
    document.getElementById('count-done').textContent = done.length;

    document.getElementById('list-todo').innerHTML = todo.map(renderCard).join('');
    document.getElementById('list-done').innerHTML = done.map(renderCard).join('');

    const empty = document.getElementById('empty-state');
    state.tasks.size === 0 ? empty.classList.remove('hidden') : empty.classList.add('hidden');

    attachCardListeners();
}

function formatDeadline(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    const now = new Date();
    const overdue = d < now;
    const label = d.toLocaleString('nl-BE', { dateStyle: 'short', timeStyle: 'short' });
    return { label, overdue };
}

function renderCard(task) {
    const deadline = formatDeadline(task.deadline);
    const deadlineTag = deadline
        ? `<span class="meta-tag deadline ${deadline.overdue ? 'overdue' : ''}">⏰ ${deadline.label}</span>`
        : '';
    const locationTag = task.location
        ? `<span class="meta-tag location">📍 ${escHtml(task.location)}</span>`
        : '';
    const weatherTag = task.weather
        ? `<span class="meta-tag weather">${escHtml(task.weather)}</span>`
        : '';
    const versionTag = `<span class="meta-tag version">v${task.version}</span>`;

    const completeBtn = task.status === 'todo'
        ? `<button class="btn-icon complete" data-action="complete" data-id="${task.id}" data-version="${task.version}" title="Markeer als afgerond">✓</button>`
        : '';

    return `
    <div class="task-card ${task.status === 'done' ? 'done' : ''}" data-id="${task.id}">
      <div class="task-card-top">
        <div class="task-check ${task.status === 'done' ? 'done' : ''}"
             data-action="complete" data-id="${task.id}" data-version="${task.version}"
             title="Status wisselen">
          ${task.status === 'done' ? '✓' : ''}
        </div>
        <div class="task-body">
          <div class="task-title">${escHtml(task.title)}</div>
          <div class="task-meta">
            ${locationTag}${weatherTag}${deadlineTag}${versionTag}
          </div>
        </div>
        <div class="task-actions">
          <button class="btn-icon" data-action="edit" data-id="${task.id}" title="Bewerk">✎</button>
          <button class="btn-icon danger" data-action="delete" data-id="${task.id}" data-version="${task.version}" title="Verwijder">✕</button>
        </div>
      </div>
    </div>`;
}

function attachCardListeners() {
    document.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', handleCardAction);
    });
}

async function handleCardAction(e) {
    const { action, id, version } = e.currentTarget.dataset;

    if (action === 'complete') {
        const task = state.tasks.get(id);
        if (!task || task.status === 'done') return; // already done
        try {
            const updated = await api.complete(id, parseInt(version, 10));
            state.tasks.set(id, updated);
            renderBoard();
            toast('Taak afgerond', 'success');
        } catch (err) {
            handleApiError(err, id);
        }
    }

    if (action === 'edit') {
        openEditModal(id);
    }

    if (action === 'delete') {
        await deleteTask(id, parseInt(version, 10));
    }
}

// ============================================================
// Modal — create / edit
// ============================================================
let _editingId = null;

function openCreateModal() {
    _editingId = null;
    document.getElementById('modal-title').textContent = 'Nieuwe taak';
    document.getElementById('input-title').value = '';
    document.getElementById('input-location').value = '';
    document.getElementById('input-deadline').value = '';
    document.getElementById('input-status').value = 'todo';
    document.getElementById('field-status').style.display = 'none';
    document.getElementById('modal-error').textContent = '';
    document.getElementById('weather-hint').textContent = '';
    showModal(true);
    setTimeout(() => document.getElementById('input-title').focus(), 50);
}

function openEditModal(id) {
    const task = state.tasks.get(id);
    if (!task) return;
    _editingId = id;

    document.getElementById('modal-title').textContent = 'Taak bewerken';
    document.getElementById('input-title').value = task.title;
    document.getElementById('input-location').value = task.location ?? '';
    document.getElementById('input-deadline').value = task.deadline
        ? toLocalDatetimeInput(task.deadline) : '';
    document.getElementById('input-status').value = task.status;
    document.getElementById('field-status').style.display = 'block';
    document.getElementById('modal-error').textContent = '';
    document.getElementById('weather-hint').textContent = task.location ? `Weer voor "${task.location}" wordt getoond als de backend integratie actief is.` : '';
    showModal(true);
    setTimeout(() => document.getElementById('input-title').focus(), 50);
}

function showModal(show) {
    document.getElementById('modal-backdrop').classList.toggle('hidden', !show);
}

function toLocalDatetimeInput(iso) {
    const d = new Date(iso);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function saveModal() {
    const title = document.getElementById('input-title').value.trim();
    const location = document.getElementById('input-location').value.trim() || null;
    const deadlineRaw = document.getElementById('input-deadline').value;
    const status = document.getElementById('input-status').value;
    const errorEl = document.getElementById('modal-error');

    if (!title) { errorEl.textContent = 'Titel is verplicht'; return; }
    errorEl.textContent = '';

    // Convert local datetime to ISO
    const deadline = deadlineRaw ? new Date(deadlineRaw).toISOString() : null;

    try {
        if (_editingId) {
            // Edit: send only fields that changed
            const task = state.tasks.get(_editingId);
            const body = { expected_version: task.version };

            if (title !== task.title) body.title = title;
            if (status !== task.status) body.status = status;

            // location: send null to clear, string to update, omit if unchanged
            const locChanged = location !== (task.location ?? null);
            if (locChanged) body.location = location; // null = clear, string = update

            // deadline: send null to clear, ISO string to update, omit if unchanged
            const newDeadline = deadline;
            const oldDeadline = task.deadline;
            const deadlineChanged = newDeadline !== oldDeadline;
            if (deadlineChanged) body.deadline = newDeadline;

            const updated = await api.update(_editingId, body);
            state.tasks.set(_editingId, updated);
            toast('Taak bijgewerkt', 'success');
        } else {
            // Create
            const body = { title };
            if (location) body.location = location;
            if (deadline) body.deadline = deadline;
            const created = await api.create(body);
            state.tasks.set(created.id, created);
            toast('Taak aangemaakt', 'success');
        }

        showModal(false);
        renderBoard();
    } catch (err) {
        handleApiError(err, _editingId, errorEl);
    }
}

// ============================================================
// Delete
// ============================================================
async function deleteTask(id, version) {
    try {
        await api.delete(id, version);
        state.tasks.delete(id);
        renderBoard();
        toast('Taak verwijderd', 'info');
    } catch (err) {
        handleApiError(err, id);
    }
}

// ============================================================
// Error handling
// ============================================================
function handleApiError(err, taskId, inlineEl = null) {
    if (err.status === 409) {
        // Version conflict — refresh this task from server state
        // (WebSocket will already have pushed the latest version,
        //  but we show the conflict dialog explicitly)
        showConflictDialog();
        return;
    }
    const msg = err.message || 'Onbekende fout';
    if (inlineEl) {
        inlineEl.textContent = msg;
    } else {
        toast(msg, 'error');
    }
}

function showConflictDialog() {
    showModal(false);
    document.getElementById('conflict-backdrop').classList.remove('hidden');
}

// ============================================================
// Toasts
// ============================================================
function toast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
        el.style.animation = 'toast-out 250ms ease forwards';
        setTimeout(() => el.remove(), 250);
    }, duration);
}

// ============================================================
// Utility
// ============================================================
function escHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ============================================================
// Boot
// ============================================================
async function init() {
    // Load initial tasks
    try {
        const tasks = await api.list();
        tasks.forEach(t => state.tasks.set(t.id, t));
        renderBoard();
    } catch {
        toast('Kan geen verbinding maken met de backend', 'error', 8000);
    }

    // Connect WebSocket
    connectWS();

    // Button wiring
    document.getElementById('btn-new-task').addEventListener('click', openCreateModal);
    document.getElementById('btn-cancel').addEventListener('click', () => showModal(false));
    document.getElementById('modal-close').addEventListener('click', () => showModal(false));
    document.getElementById('btn-save').addEventListener('click', saveModal);
    document.getElementById('btn-conflict-ok').addEventListener('click', () => {
        document.getElementById('conflict-backdrop').classList.add('hidden');
    });
    document.getElementById('btn-clear-deadline').addEventListener('click', () => {
        document.getElementById('input-deadline').value = '';
    });

    // Location → weather hint
    document.getElementById('input-location').addEventListener('input', e => {
        const val = e.target.value.trim();
        document.getElementById('weather-hint').textContent = val
            ? `Weer voor "${val}" wordt getoond als de backend integratie actief is.`
            : '';
    });

    // Close modal on backdrop click
    document.getElementById('modal-backdrop').addEventListener('click', e => {
        if (e.target === e.currentTarget) showModal(false);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            showModal(false);
            document.getElementById('conflict-backdrop').classList.add('hidden');
        }
        if (e.key === 'Enter' && !document.getElementById('modal-backdrop').classList.contains('hidden')) {
            // Enter in modal = save (unless in textarea)
            if (document.activeElement.tagName !== 'TEXTAREA') {
                e.preventDefault();
                saveModal();
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', init);
