/* ============================================================
   Task Board — mail.js
   Mail client: compose (POST /mail/send) + inbox (GET /mail/inbox)
   Polt de inbox elke POLL_INTERVAL milliseconden automatisch.
   ============================================================ */

const API = 'http://localhost:8000';
const POLL_INTERVAL = 5000; // ms

// ============================================================
// State
// ============================================================
const state = {
    messages: [],
    pollTimer: null,
    lastUpdate: null,
    polling: false,
};

// ============================================================
// Command-hint teksten (zelfde taal als de bot-replies)
// ============================================================
const CMD_HINTS = {
    ADD: 'ADD <titel>   — maak een nieuwe taak aan',
    DONE: 'DONE <id>     — markeer taak als afgerond (eerste 8 tekens van het ID)',
    DELETE: 'DELETE <id>   — verwijder een taak permanent',
    LIST: 'LIST          — toon alle taken',
};

// ============================================================
// API helper (zelfde patroon als app.js)
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
        throw err;
    }
    return body;
}

// ============================================================
// Compose — verstuur een mail
// ============================================================
async function sendMail() {
    const to = document.getElementById('input-to').value.trim();
    const subject = document.getElementById('input-subject').value.trim();
    const body = document.getElementById('input-body').value.trim();
    const errorEl = document.getElementById('send-error');

    if (!subject) {
        errorEl.textContent = 'Onderwerp is verplicht';
        document.getElementById('input-subject').focus();
        return;
    }
    errorEl.textContent = '';

    const btn = document.getElementById('btn-send');
    btn.disabled = true;
    btn.textContent = 'Verzenden…';

    try {
        await apiFetch('/mail/send', {
            method: 'POST',
            body: JSON.stringify({ to, subject, body }),
        });

        toast('Mail verstuurd ✓', 'success');

        // Velden leegmaken
        document.getElementById('input-subject').value = '';
        document.getElementById('input-body').value = '';
        document.getElementById('cmd-hint').textContent = '';

        // Na een korte wachttijd inbox verversen zodat de bot-reply er al in kan zitten
        setTimeout(() => loadInbox(), 800);
        setTimeout(() => loadInbox(), 8000); // tweede keer na de poll-cyclus van de poller

    } catch (err) {
        errorEl.textContent = err.message || 'Versturen mislukt';
        toast('Versturen mislukt', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Versturen →';
    }
}

// ============================================================
// Inbox — ophalen + renderen
// ============================================================
async function loadInbox() {
    flashPollDot();
    try {
        const messages = await apiFetch('/mail/inbox');
        state.messages = messages;
        state.lastUpdate = new Date();
        renderInbox();
    } catch {
        toast('Inbox laden mislukt', 'error');
    }
}

function renderInbox() {
    const list = document.getElementById('mail-list');
    const empty = document.getElementById('inbox-empty');
    const countEl = document.getElementById('inbox-count');
    const updateEl = document.getElementById('last-update');

    countEl.textContent = state.messages.length;

    if (state.lastUpdate) {
        const time = state.lastUpdate.toLocaleTimeString('nl-BE', { timeStyle: 'medium' });
        updateEl.textContent = `Bijgewerkt om ${time}`;
    }

    if (!state.messages.length) {
        list.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');

    // Bewaar welke cards open staan (op uid) zodat expand-staat behouden blijft bij refresh
    const expanded = new Set(
        [...list.querySelectorAll('.mail-card.expanded')].map(el => el.dataset.uid)
    );

    list.innerHTML = state.messages.map(msg => renderMailCard(msg, expanded.has(msg.uid))).join('');

    // Expand/collapse kliklisteners toevoegen
    list.querySelectorAll('.mail-card-header').forEach(header => {
        header.addEventListener('click', () => {
            header.closest('.mail-card').classList.toggle('expanded');
        });
    });
}

function renderMailCard(msg, startExpanded = false) {
    const date = formatDate(msg.date);
    const isReply = detectReply(msg.subject, msg.from_address);
    const typeClass = isReply ? 'reply' : 'command';
    const typeLabel = isReply ? '↩ reply' : '↑ command';

    const bodyText = msg.body
        ? escHtml(msg.body)
        : '<span class="mail-body-empty">Geen berichttekst</span>';

    return `
<div class="mail-card ${typeClass}${startExpanded ? ' expanded' : ''}" data-uid="${escHtml(msg.uid)}" role="listitem">
  <div class="mail-card-header" tabindex="0" role="button"
       aria-expanded="${startExpanded}"
       aria-label="${escHtml(msg.subject)}">
    <div class="mail-card-top">
      <span class="mail-type-badge ${typeClass}">${typeLabel}</span>
      <span class="mail-subject">${escHtml(msg.subject)}</span>
    </div>
    <div class="mail-meta">
      <span class="mail-from">${escHtml(msg.from_address)}</span>
      <span class="mail-date">${escHtml(date)}</span>
      <span class="mail-expand-icon" aria-hidden="true">▾</span>
    </div>
  </div>
  <div class="mail-card-body" role="region">
    <div class="mail-body">${bodyText}</div>
  </div>
</div>`.trim();
}

// ============================================================
// Hulp: is dit een bot-reply of een verstuurd commando?
// ============================================================
function detectReply(subject, fromAddress) {
    // Bot-replies herkennen aan typische subject-prefixen die de poller gebruikt
    const botPrefixes = [
        'Taak aangemaakt',
        'Taak bijgewerkt',
        'Afgerond:',
        'Al afgerond:',
        'Verwijderd:',
        'Takenlijst',
        'Niet gevonden',
        'Versieconflict',
        'Fout:',
        'Onbekend commando',
        'Meerdere matches',
        'Re:',          // standaard reply-prefix
    ];
    return botPrefixes.some(prefix => subject.startsWith(prefix));
}

// ============================================================
// Polling indicator (knippert bij elke fetch)
// ============================================================
function flashPollDot() {
    const dot = document.getElementById('poll-dot');
    const label = document.getElementById('poll-label');
    dot.classList.add('active');
    label.textContent = 'Laden…';
    setTimeout(() => {
        dot.classList.remove('active');
        label.textContent = `Auto-refresh ${POLL_INTERVAL / 1000}s`;
    }, 600);
}

// ============================================================
// Polling starten
// ============================================================
function startPolling() {
    state.pollTimer = setInterval(loadInbox, POLL_INTERVAL);
    document.getElementById('poll-label').textContent = `Auto-refresh ${POLL_INTERVAL / 1000}s`;
}

// ============================================================
// Hint voor snelcommando's
// ============================================================
function showCmdHint(rawSubject) {
    const cmd = rawSubject.trim().split(/\s+/)[0].toUpperCase();
    const el = document.getElementById('cmd-hint');
    el.textContent = CMD_HINTS[cmd] || '';
}

// ============================================================
// Datum formatteren
// ============================================================
function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        return new Date(dateStr).toLocaleString('nl-BE', {
            dateStyle: 'short',
            timeStyle: 'short',
        });
    } catch {
        return dateStr;
    }
}

// ============================================================
// Toast (zelfde als app.js)
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
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ============================================================
// Boot
// ============================================================
async function init() {
    // Haal het board-adres op om het "Aan"-veld automatisch in te vullen.
    // Bij fout blijft de hardcoded fallback staan.
    try {
        const { address } = await apiFetch('/mail/address');
        document.getElementById('input-to').value = address;
    } catch { /* fallback hardcoded value already in HTML */ }

    // ---- Snelcommando-knoppen ----
    document.querySelectorAll('.cmd-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const inputEl = document.getElementById('input-subject');
            inputEl.value = btn.dataset.cmd;
            inputEl.focus();
            // Cursor naar het einde plaatsen
            inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
            showCmdHint(btn.dataset.cmd);
        });
    });

    // ---- Hint bijhouden terwijl gebruiker typt ----
    document.getElementById('input-subject').addEventListener('input', e => {
        showCmdHint(e.target.value);
    });

    // ---- Enter in onderwerp-veld = versturen ----
    document.getElementById('input-subject').addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); sendMail(); }
    });

    // ---- Knoppen ----
    document.getElementById('btn-send').addEventListener('click', sendMail);
    document.getElementById('btn-refresh').addEventListener('click', loadInbox);

    // ---- Keyboard: spatie/enter op mail-card-header ----
    document.getElementById('mail-list').addEventListener('keydown', e => {
        if ((e.key === ' ' || e.key === 'Enter') && e.target.matches('.mail-card-header')) {
            e.preventDefault();
            e.target.closest('.mail-card').classList.toggle('expanded');
        }
    });

    // ---- Inbox laden + polling starten ----
    await loadInbox();
    startPolling();
}

document.addEventListener('DOMContentLoaded', init);
