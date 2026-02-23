/**
 * GRACE Dashboard - Vanilla JS Logic
 * No build tools, no React, purely operational DOM manipulation.
 */

// 1. Mock Data Source
const isoAgo = (msAgo) => new Date(Date.now() - msAgo).toISOString();

const mockTickets = [
    { id: 'TCK-9042', customer: 'Sarah Jenkins', source: 'Telegram', subject: 'Spa booking failed', severity: 'high', status: 'Open', notes: 'System encountered API 404 while booking Spa package. Webhook intercepted.' },
    { id: 'TCK-9041', customer: 'Dr. House', source: 'Voice (Room 211)', subject: 'Water leak in bathroom', severity: 'critical', status: 'Open', notes: 'Transcript: "There is water leaking rapidly from the ceiling in the bathroom, please send maintenance immediately."' },
    { id: 'TCK-9040', customer: 'Mr. Anderson', source: 'Voice (Room 509)', subject: 'Late checkout request', severity: 'low', status: 'Resolved', notes: 'Transcript: "Hi Grace, can I stay until 2 PM?" System approved based on loyalty tier.' },
    { id: 'TCK-9039', customer: 'Emily Chen', source: 'Web Chat', subject: 'Inquiring about suite upgrade', severity: 'medium', status: 'Open', notes: 'User asking about cost delta for upgrading to Presidential Suite for 2 nights.' },
    { id: 'TCK-9038', customer: 'Anonymous', source: 'Voice (Lobby)', subject: 'Lost item inquiry', severity: 'medium', status: 'In Progress', notes: 'Guest left a black leather wallet at the main bar. Agent checking lost and found database.' },
    { id: 'TCK-9037', customer: 'John Doe', source: 'Telegram', subject: 'Cancel reservation', severity: 'high', status: 'Open', notes: 'User triggered /cancel command. Requires manual refund authorization.' },
];

const mockCalls = [
    { id: 'CALL-1182', from: '+1 (415) 555-0134', channel: 'Voice', status: 'Active', intent: 'Late checkout', latency_ms: 320, started_at: isoAgo(1000 * 60 * 3), transcript_snippet: 'Hi — I’m in room 509. Can I extend checkout to 2 PM? I have a late flight.', handoff_to: 'Front Desk' },
    { id: 'CALL-1181', from: '+1 (212) 555-0199', channel: 'Voice', status: 'Ringing', intent: 'Room service', latency_ms: 410, started_at: isoAgo(1000 * 45), transcript_snippet: 'Hello, I’d like to order breakfast. What’s available for vegetarian options?', handoff_to: '' },
    { id: 'CALL-1179', from: 'Telegram @maria.s', channel: 'Telegram', status: 'Active', intent: 'Spa booking', latency_ms: 220, started_at: isoAgo(1000 * 60 * 8), transcript_snippet: 'Can you book a couples massage for tonight around 8?', handoff_to: 'Spa Desk' },
    { id: 'CALL-1176', from: 'Web Chat #4821', channel: 'Web', status: 'Handoff Pending', intent: 'Refund request', latency_ms: 780, started_at: isoAgo(1000 * 60 * 12), transcript_snippet: 'My reservation was cancelled — I need a refund confirmation for my card.', handoff_to: 'Billing' },
    { id: 'CALL-1168', from: '+1 (646) 555-0142', channel: 'Voice', status: 'Ended', intent: 'Wi‑Fi help', latency_ms: 510, started_at: isoAgo(1000 * 60 * 22), transcript_snippet: 'The Wi‑Fi keeps disconnecting on my laptop. Is there a stronger network?', handoff_to: '' }
];

const mockEscalations = [
    {
        id: 'ESC-2301',
        ticket_id: 'TCK-9041',
        severity: 'critical',
        status: 'Open',
        owner: '',
        created_at: isoAgo(1000 * 60 * 14),
        updates: [
            { at: isoAgo(1000 * 60 * 14), text: 'Escalation created from voice transcript classifier.', type: 'info' },
            { at: isoAgo(1000 * 60 * 12), text: 'Detected keywords: “leaking rapidly”, “ceiling”.', type: 'warn' }
        ]
    },
    {
        id: 'ESC-2298',
        ticket_id: 'TCK-9042',
        severity: 'high',
        status: 'In Progress',
        owner: 'Nadia (Ops)',
        created_at: isoAgo(1000 * 60 * 46),
        updates: [
            { at: isoAgo(1000 * 60 * 46), text: 'Webhook booking failure confirmed (API 404).', type: 'warn' },
            { at: isoAgo(1000 * 60 * 41), text: 'Assigned to Nadia. Retrying against fallback supplier.', type: 'info' }
        ]
    },
    {
        id: 'ESC-2293',
        ticket_id: 'TCK-9037',
        severity: 'high',
        status: 'Resolved',
        owner: 'Omar (Finance)',
        created_at: isoAgo(1000 * 60 * 90),
        updates: [
            { at: isoAgo(1000 * 60 * 90), text: 'Manual refund authorization required.', type: 'info' },
            { at: isoAgo(1000 * 60 * 72), text: 'Refund approved and confirmation sent to guest.', type: 'success' }
        ]
    }
];

const mockEventLog = [
    { at: isoAgo(1000 * 60 * 3), type: 'info', source: 'calls', text: 'Call connected: +1 (415) 555-0134 (Late checkout).' },
    { at: isoAgo(1000 * 60 * 10), type: 'warn', source: 'calls', text: 'Latency spike observed on CALL-1176 (780ms).' },
    { at: isoAgo(1000 * 60 * 14), type: 'alert', source: 'escalations', text: 'Critical escalation opened for TCK-9041.' },
    { at: isoAgo(1000 * 60 * 22), type: 'success', source: 'system', text: 'PMS sync complete. 0 conflicts.' }
];

const mockStaff = [
    { id: 'STF-101', name: 'Aisha Khan', role: 'Front Desk', shift: '07:00–15:00', phone: '+1 (415) 555-0101', status: 'On duty', languages: ['EN', 'AR'] },
    { id: 'STF-102', name: 'Nadia Ali', role: 'Ops Lead', shift: '09:00–17:00', phone: '+1 (415) 555-0102', status: 'Busy', languages: ['EN', 'FR'] },
    { id: 'STF-103', name: 'Omar Rahman', role: 'Finance', shift: '10:00–18:00', phone: '+1 (415) 555-0103', status: 'On duty', languages: ['EN'] },
    { id: 'STF-104', name: 'Miguel Santos', role: 'Maintenance', shift: '06:00–14:00', phone: '+1 (415) 555-0104', status: 'On duty', languages: ['EN', 'ES'] },
    { id: 'STF-105', name: 'Lina Chen', role: 'Concierge', shift: '14:00–22:00', phone: '+1 (415) 555-0105', status: 'Off duty', languages: ['EN', 'ZH'] },
    { id: 'STF-106', name: 'Sara Novak', role: 'Spa Desk', shift: '12:00–20:00', phone: '+1 (415) 555-0106', status: 'On duty', languages: ['EN', 'DE'] }
];

const mockEvents = [
    { text: 'AI handled incoming call from +971 50 *** 4567.', type: 'info' },
    { text: 'Telegram webhook processed `/status` command.', type: 'info' },
    { text: 'Grace autonomously booked Appointment #882.', type: 'success' },
    { text: 'PMS Database synchronization complete.', type: 'success' },
    { text: 'User dropped call during intent classification.', type: 'warn' },
    { text: 'High latency detected on OpenRouter endpoint.', type: 'warn' },
    { text: 'New critical ticket generated from Voice interface.', type: 'alert' }
];

// 2. Helper Functions
function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[ch]));
}

function normalizeEventType(type) {
    if (type === 'warning') return 'warn';
    return type || 'info';
}

function formatRelativeTime(isoString) {
    const t = new Date(isoString).getTime();
    if (!Number.isFinite(t)) return '--';
    const seconds = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainderSeconds = seconds % 60;
    if (minutes < 60) return `${minutes}m ${remainderSeconds}s`;
    const hours = Math.floor(minutes / 60);
    const remainderMinutes = minutes % 60;
    return `${hours}h ${remainderMinutes}m`;
}

function getSeverityStyles(severity) {
    switch (severity) {
        case 'critical': return 'bg-rose-100 text-rose-700 border border-rose-200';
        case 'high': return 'bg-orange-100 text-orange-700 border border-orange-200';
        case 'medium': return 'bg-amber-100 text-amber-700 border border-amber-200';
        case 'low': return 'bg-slate-100 text-slate-600 border border-slate-200';
        default: return 'bg-slate-100 text-slate-600 border border-slate-200';
    }
}

function getStatusStyles(status) {
    if (status === 'Resolved') return 'text-emerald-600 bg-emerald-50 border border-emerald-100';
    if (status === 'In Progress') return 'text-sky-600 bg-sky-50 border border-sky-100';
    return 'text-slate-600 bg-slate-50 border border-slate-200'; // Open
}

function getEventTypeStyles(type) {
    const t = normalizeEventType(type);
    if (t === 'alert') return { border: 'border-rose-200', icon: 'text-rose-500', pill: 'bg-rose-100 text-rose-700 border border-rose-200' };
    if (t === 'success') return { border: 'border-emerald-200', icon: 'text-emerald-500', pill: 'bg-emerald-100 text-emerald-700 border border-emerald-200' };
    if (t === 'warn') return { border: 'border-amber-200', icon: 'text-amber-500', pill: 'bg-amber-100 text-amber-700 border border-amber-200' };
    return { border: 'border-slate-200', icon: 'text-slate-400', pill: 'bg-slate-100 text-slate-700 border border-slate-200' };
}

function getCallStatusStyles(status) {
    if (status === 'Active') return 'text-emerald-700 bg-emerald-50 border border-emerald-100';
    if (status === 'Ringing') return 'text-sky-700 bg-sky-50 border border-sky-100';
    if (status === 'Handoff Pending') return 'text-amber-700 bg-amber-50 border border-amber-100';
    if (status === 'Ended') return 'text-slate-600 bg-slate-50 border border-slate-200';
    return 'text-slate-600 bg-slate-50 border border-slate-200';
}

function getStaffStatusStyles(status) {
    if (status === 'On duty') return 'text-emerald-700 bg-emerald-50 border border-emerald-100';
    if (status === 'Busy') return 'text-amber-700 bg-amber-50 border border-amber-100';
    if (status === 'Off duty') return 'text-slate-600 bg-slate-50 border border-slate-200';
    return 'text-slate-600 bg-slate-50 border border-slate-200';
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('[dashboard] boot ok', { hasTailwind: !!window.tailwind, ts: Date.now() });

    // 3. DOM Elements
    const tbody = document.getElementById('ticket-table-body');
    const drawer = document.getElementById('ticket-drawer');
    const overlay = document.getElementById('drawer-overlay');
    const filterGroup = document.getElementById('filter-group');
    const streamContainer = document.getElementById('event-stream-container');

    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    const btnAssign = document.getElementById('btn-assign');
    const btnEscalate = document.getElementById('btn-escalate');
    const btnResolve = document.getElementById('btn-resolve');

    const kpiOpen = document.getElementById('kpi-open-tickets');
    const kpiCritical = document.getElementById('kpi-critical');

    // Live Calls
    const callsTableBody = document.getElementById('calls-table-body');
    const callsSearchInput = document.getElementById('calls-search');
    const callsCountBadge = document.getElementById('calls-count-badge');
    const callsKpiActive = document.getElementById('calls-kpi-active');
    const callsKpiAvgLatency = document.getElementById('calls-kpi-avg-latency');
    const callsKpiHandoffs = document.getElementById('calls-kpi-handoffs');
    const callsKpiIntent = document.getElementById('calls-kpi-intent');
    const callsBtnSimulate = document.getElementById('calls-btn-simulate');
    const callsBtnClearEnded = document.getElementById('calls-btn-clear-ended');
    const callTranscriptOverlay = document.getElementById('call-transcript-overlay');
    const callTranscriptModal = document.getElementById('call-transcript-modal');
    const callTranscriptClose = document.getElementById('call-transcript-close');
    const callTranscriptMeta = document.getElementById('call-transcript-meta');
    const callTranscriptTitle = document.getElementById('call-transcript-title');
    const callTranscriptTags = document.getElementById('call-transcript-tags');
    const callTranscriptBody = document.getElementById('call-transcript-body');

    // Escalations
    const escalationsList = document.getElementById('escalations-list');
    const escalationsCount = document.getElementById('escalations-count');
    const escalationsSearchInput = document.getElementById('escalations-search');
    const escalationsFilterGroup = document.getElementById('escalations-filter-group');

    // Event Log
    const eventLogList = document.getElementById('eventlog-list');
    const eventLogSearchInput = document.getElementById('eventlog-search');
    const eventLogFilterGroup = document.getElementById('eventlog-filter-group');
    const eventLogBtnClear = document.getElementById('eventlog-btn-clear');
    const eventLogBtnExport = document.getElementById('eventlog-btn-export');

    // Staff
    const staffTableBody = document.getElementById('staff-table-body');
    const staffCountBadge = document.getElementById('staff-count-badge');
    const staffSearchInput = document.getElementById('staff-search');
    const staffFilterGroup = document.getElementById('staff-filter-group');

    const navLinks = Array.from(document.querySelectorAll('[data-view]'));
    const panels = Array.from(document.querySelectorAll('[data-panel]'));

    const warn = (message, detail) => {
        console.warn(`[dashboard] ${message}`, detail || '');
    };

    let activeView = null;
    let callsHandoffCount = 0;

    const state = {
        callsSearch: '',
        escalationsSearch: '',
        escalationsStatus: 'all',
        eventLogSearch: '',
        eventLogType: 'all',
        staffSearch: '',
        staffStatus: 'all'
    };

    function ensureToastContainer() {
        let container = document.getElementById('toast-container');
        if (container) return container;
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-4 right-4 z-[80] flex flex-col gap-2';
        document.body.appendChild(container);
        return container;
    }

    function toast(message, options = {}) {
        const type = normalizeEventType(options.type || 'info');
        const container = ensureToastContainer();
        const styles = getEventTypeStyles(type);

        const node = document.createElement('div');
        node.className = `px-3 py-2 rounded-lg shadow-sm border ${styles.border} bg-white text-sm text-slate-800 max-w-sm`;
        node.setAttribute('role', 'status');
        node.textContent = message;
        container.appendChild(node);

        setTimeout(() => node.classList.add('opacity-0', 'translate-y-1'), 1800);
        setTimeout(() => node.remove(), 2300);
    }

    function logEvent({ type = 'info', source = 'system', text }) {
        const entry = {
            at: new Date().toISOString(),
            type: normalizeEventType(type),
            source: source || 'system',
            text: String(text || '')
        };
        mockEventLog.unshift(entry);
        if (mockEventLog.length > 250) mockEventLog.pop();

        if (activeView === 'eventlog') {
            renderEventLog();
        }
    }

    function updateKPIs() {
        if (!kpiOpen || !kpiCritical) {
            warn('missing KPI nodes');
            return;
        }
        const openTickets = mockTickets.filter(t => t.status !== 'Resolved').length;
        const criticalTickets = mockTickets.filter(t => t.severity === 'critical' && t.status !== 'Resolved').length;
        kpiOpen.innerText = openTickets;
        kpiCritical.innerText = criticalTickets;
    }

    // 4. Render Table
    function renderTable(filter = 'all') {
        if (!tbody) {
            warn('missing ticket table body');
            return;
        }
        tbody.innerHTML = '';

        const filteredData = filter === 'all'
            ? mockTickets
            : mockTickets.filter(t => t.severity === filter);

        filteredData.forEach(ticket => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 cursor-pointer transition-colors group';
            tr.dataset.ticketId = ticket.id;

            tr.innerHTML = `
            <td class="px-4 md:px-6 py-4 font-mono text-xs font-semibold text-slate-500 group-hover:text-accent transition-colors">${ticket.id}</td>
            <td class="px-4 md:px-6 py-4 font-medium text-graphite">${ticket.customer}</td>
            <td class="px-4 md:px-6 py-4 text-slate-600 truncate max-w-[150px] sm:max-w-xs md:max-w-sm lg:max-w-md" title="${ticket.subject}">${ticket.subject}</td>
            <td class="px-4 md:px-6 py-4">
                <span class="status-badge ${getSeverityStyles(ticket.severity)}">${ticket.severity}</span>
            </td>
            <td class="px-4 md:px-6 py-4">
                <span class="status-badge ${getStatusStyles(ticket.status)}">${ticket.status}</span>
            </td>
        `;
            tbody.appendChild(tr);
        });

        updateKPIs();
    }

    // Live Calls
    function getFilteredCalls() {
        const term = state.callsSearch.trim().toLowerCase();
        const sorted = [...mockCalls].sort((a, b) => {
            const aEnded = a.status === 'Ended';
            const bEnded = b.status === 'Ended';
            if (aEnded !== bEnded) return aEnded ? 1 : -1;
            return new Date(b.started_at).getTime() - new Date(a.started_at).getTime();
        });
        if (!term) return sorted;
        return sorted.filter(c => {
            const hay = `${c.id} ${c.from} ${c.channel} ${c.status} ${c.intent}`.toLowerCase();
            return hay.includes(term);
        });
    }

    function renderCalls() {
        if (!callsTableBody) {
            warn('missing calls table body');
            return;
        }
        const calls = getFilteredCalls();

        const activeCalls = mockCalls.filter(c => c.status !== 'Ended');
        const avgLatency = activeCalls.length
            ? Math.round(activeCalls.reduce((sum, c) => sum + (c.latency_ms || 0), 0) / activeCalls.length)
            : 0;

        if (callsKpiActive) callsKpiActive.innerText = String(activeCalls.length);
        if (callsKpiAvgLatency) callsKpiAvgLatency.innerText = activeCalls.length ? String(avgLatency) : '--';
        if (callsKpiHandoffs) callsKpiHandoffs.innerText = String(callsHandoffCount);

        if (callsKpiIntent) {
            const counts = new Map();
            activeCalls.forEach(c => counts.set(c.intent, (counts.get(c.intent) || 0) + 1));
            let topIntent = '--';
            let topCount = 0;
            counts.forEach((count, intent) => {
                if (count > topCount) {
                    topCount = count;
                    topIntent = intent;
                }
            });
            callsKpiIntent.innerText = topIntent;
        }

        if (callsCountBadge) callsCountBadge.innerText = String(calls.length);

        callsTableBody.innerHTML = '';
        if (!calls.length) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td class="px-4 md:px-6 py-6 text-sm text-slate-500" colspan="7">No calls match your search.</td>`;
            callsTableBody.appendChild(tr);
            return;
        }

        calls.forEach(call => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 transition-colors';
            tr.dataset.callId = call.id;

            tr.innerHTML = `
                <td class="px-4 md:px-6 py-4 font-medium text-graphite">${escapeHtml(call.from)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(call.channel)}</td>
                <td class="px-4 md:px-6 py-4"><span class="status-badge ${getCallStatusStyles(call.status)}">${escapeHtml(call.status)}</span></td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(call.intent)}</td>
                <td class="px-4 md:px-6 py-4 font-mono text-xs text-slate-500">${escapeHtml(call.latency_ms)}ms</td>
                <td class="px-4 md:px-6 py-4 text-slate-500" title="${escapeHtml(call.started_at)}">${escapeHtml(formatRelativeTime(call.started_at))}</td>
                <td class="px-4 md:px-6 py-4 text-right">
                    <div class="flex justify-end gap-2">
                        <button data-call-action="transcript" data-call-id="${escapeHtml(call.id)}"
                            class="px-2.5 py-1.5 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                            Transcript
                        </button>
                        <button data-call-action="handoff" data-call-id="${escapeHtml(call.id)}" ${call.status === 'Ended' ? 'disabled' : ''}
                            class="px-2.5 py-1.5 text-xs font-semibold rounded bg-graphite text-white hover:bg-slate-800 transition disabled:opacity-40 disabled:cursor-not-allowed">
                            Handoff
                        </button>
                    </div>
                </td>
            `;

            callsTableBody.appendChild(tr);
        });
    }

    function openCallTranscript(callId) {
        if (!callTranscriptOverlay || !callTranscriptModal) {
            warn('missing call transcript modal nodes');
            return;
        }
        const call = mockCalls.find(c => c.id === callId);
        if (!call) return;

        if (callTranscriptMeta) callTranscriptMeta.innerText = `${call.id} • ${call.channel} • started ${formatRelativeTime(call.started_at)} ago`;
        if (callTranscriptTitle) callTranscriptTitle.innerText = `From ${call.from}`;
        if (callTranscriptBody) {
            const body = [
                `[${call.channel}] ${call.from}`,
                `Intent: ${call.intent}`,
                `Latency: ${call.latency_ms}ms`,
                '',
                call.transcript_snippet,
                '',
                '—',
                'AI Notes: Sentiment neutral. Next best action: confirm policy + offer options.'
            ].join('\n');
            callTranscriptBody.innerText = body;
        }
        if (callTranscriptTags) {
            callTranscriptTags.innerHTML = `
                <span class="status-badge ${getCallStatusStyles(call.status)}">${escapeHtml(call.status)}</span>
                <span class="status-badge bg-slate-100 text-slate-700 border border-slate-200">${escapeHtml(call.intent)}</span>
                <span class="status-badge bg-slate-100 text-slate-700 border border-slate-200">${escapeHtml(call.latency_ms)}ms</span>
                ${call.handoff_to ? `<span class="status-badge bg-slate-100 text-slate-700 border border-slate-200">Handoff: ${escapeHtml(call.handoff_to)}</span>` : ''}
            `;
        }

        callTranscriptOverlay.classList.remove('hidden');
        callTranscriptModal.classList.remove('hidden');
    }

    function closeCallTranscript() {
        callTranscriptOverlay?.classList.add('hidden');
        callTranscriptModal?.classList.add('hidden');
    }

    function simulateNewCall(options = {}) {
        const showToast = options.showToast !== false;
        const shouldRender = options.render !== false;
        const source = options.source || 'calls';

        const id = `CALL-${String(Date.now()).slice(-4)}`;
        const channels = ['Voice', 'Web', 'Telegram'];
        const intents = ['Late checkout', 'Room service', 'Spa booking', 'Wi‑Fi help', 'Upgrade request'];
        const channel = channels[Math.floor(Math.random() * channels.length)];
        const intent = intents[Math.floor(Math.random() * intents.length)];
        const from = channel === 'Telegram'
            ? `Telegram @guest${Math.floor(Math.random() * 900 + 100)}`
            : (channel === 'Web' ? `Web Chat #${Math.floor(Math.random() * 9000 + 1000)}` : `+1 (415) 555-${Math.floor(Math.random() * 9000 + 1000)}`);

        const call = {
            id,
            from,
            channel,
            status: 'Ringing',
            intent,
            latency_ms: Math.floor(Math.random() * 350 + 180),
            started_at: new Date().toISOString(),
            transcript_snippet: 'Hello — I need help with my stay. Can you assist?',
            handoff_to: ''
        };
        mockCalls.unshift(call);
        logEvent({ type: 'info', source, text: `New inbound ${channel} call (${id}) intent=${intent}.` });
        if (showToast) toast(`New call: ${intent}`, { type: 'info' });

        if (shouldRender && activeView === 'calls') renderCalls();
    }

    // Escalations
    function getFilteredEscalations() {
        const status = state.escalationsStatus;
        const term = state.escalationsSearch.trim().toLowerCase();
        const filtered = mockEscalations.filter(e => (status === 'all' ? true : e.status === status));
        if (!term) return filtered;
        return filtered.filter(e => {
            const hay = `${e.id} ${e.ticket_id} ${e.owner} ${e.status} ${e.severity}`.toLowerCase();
            return hay.includes(term);
        });
    }

    function renderEscalations() {
        if (!escalationsList) {
            warn('missing escalations list');
            return;
        }
        const items = getFilteredEscalations();
        if (escalationsCount) escalationsCount.innerText = String(items.length);

        escalationsList.innerHTML = '';
        if (!items.length) {
            escalationsList.innerHTML = `<div class="p-6 text-sm text-slate-500">No escalations match your filters.</div>`;
            return;
        }

        items.forEach(escalation => {
            const container = document.createElement('div');
            container.className = 'p-4 md:p-6 bg-white';
            container.dataset.escalationId = escalation.id;

            const ownerText = escalation.owner ? escalation.owner : 'Unassigned';
            const updates = [...(escalation.updates || [])].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
            const created = formatRelativeTime(escalation.created_at);

            const actionButtons = escalation.status === 'Resolved'
                ? ''
                : `
                    <div class="flex gap-2">
                        <button data-esc-action="assign" data-esc-id="${escapeHtml(escalation.id)}"
                            class="px-2.5 py-1.5 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                            Assign to me
                        </button>
                        <button data-esc-action="resolve" data-esc-id="${escapeHtml(escalation.id)}"
                            class="px-2.5 py-1.5 text-xs font-semibold rounded bg-graphite text-white hover:bg-slate-800 transition">
                            Resolve
                        </button>
                    </div>
                `;

            container.innerHTML = `
                <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div class="min-w-0">
                        <div class="flex items-center gap-2 flex-wrap">
                            <span class="text-xs font-mono font-semibold text-slate-500">${escapeHtml(escalation.id)}</span>
                            <span class="text-xs font-semibold text-graphite">Ticket ${escapeHtml(escalation.ticket_id)}</span>
                            <span class="status-badge ${getSeverityStyles(escalation.severity)}">${escapeHtml(escalation.severity)}</span>
                            <span class="status-badge ${getStatusStyles(escalation.status)}">${escapeHtml(escalation.status)}</span>
                        </div>
                        <p class="text-xs text-slate-500 mt-2">Owner: <span class="font-semibold text-slate-700">${escapeHtml(ownerText)}</span> • Created ${escapeHtml(created)} ago</p>
                    </div>
                    ${actionButtons}
                </div>
                <div class="mt-4 space-y-3">
                    ${updates.map(u => {
                const styles = getEventTypeStyles(u.type);
                const at = formatRelativeTime(u.at);
                return `
                            <div class="pl-4 border-l-2 ${styles.border}">
                                <div class="flex items-center gap-2">
                                    <svg class="w-3 h-3 ${styles.icon}" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"></circle></svg>
                                    <span class="text-[10px] text-slate-400 font-mono tracking-wider uppercase">${escapeHtml(at)} ago</span>
                                    <span class="status-badge ${styles.pill}">${escapeHtml(normalizeEventType(u.type))}</span>
                                </div>
                                <p class="text-sm text-slate-700 mt-1">${escapeHtml(u.text)}</p>
                            </div>
                        `;
            }).join('')}
                </div>
            `;

            escalationsList.appendChild(container);
        });
    }

    function updateEscalation(escalationId, action) {
        const esc = mockEscalations.find(e => e.id === escalationId);
        if (!esc) return;
        const nowIso = new Date().toISOString();

        if (action === 'assign') {
            esc.owner = 'Admin User';
            if (esc.status !== 'Resolved') esc.status = 'In Progress';
            esc.updates = esc.updates || [];
            esc.updates.push({ at: nowIso, text: 'Assigned to Admin User.', type: 'info' });
            logEvent({ type: 'info', source: 'escalations', text: `${esc.id} assigned to Admin User.` });
            toast(`Assigned ${esc.ticket_id}`, { type: 'info' });
            renderEscalations();
            return;
        }

        if (action === 'resolve') {
            esc.status = 'Resolved';
            esc.updates = esc.updates || [];
            esc.updates.push({ at: nowIso, text: 'Marked resolved. Follow-up sent to guest.', type: 'success' });
            logEvent({ type: 'success', source: 'escalations', text: `${esc.id} resolved for ${esc.ticket_id}.` });
            toast(`Resolved ${esc.ticket_id}`, { type: 'success' });
            renderEscalations();
        }
    }

    // Event Log
    function renderEventLog() {
        if (!eventLogList) {
            warn('missing event log list');
            return;
        }
        const term = state.eventLogSearch.trim().toLowerCase();
        const type = state.eventLogType;

        let items = [...mockEventLog];
        if (type !== 'all') items = items.filter(e => normalizeEventType(e.type) === type);
        if (term) {
            items = items.filter(e => {
                const hay = `${e.at} ${e.type} ${e.source} ${e.text}`.toLowerCase();
                return hay.includes(term);
            });
        }

        eventLogList.innerHTML = '';
        if (!items.length) {
            eventLogList.innerHTML = `<div class="p-6 text-sm text-slate-500 bg-white border border-slate-200 rounded-md">No events match your filters.</div>`;
            return;
        }

        items.slice(0, 120).forEach(eventObj => {
            const styles = getEventTypeStyles(eventObj.type);
            const time = new Date(eventObj.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const card = document.createElement('div');
            card.className = `event-card-new p-3 bg-white border ${styles.border} rounded-md shadow-sm`;
            card.innerHTML = `
                <div class="flex items-center justify-between gap-3">
                    <div class="flex items-center gap-2 min-w-0">
                        <svg class="w-3 h-3 ${styles.icon}" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"></circle></svg>
                        <span class="text-[10px] text-slate-400 font-mono tracking-wider uppercase">${escapeHtml(time)}</span>
                        <span class="status-badge ${styles.pill}">${escapeHtml(normalizeEventType(eventObj.type))}</span>
                        <span class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-slate-200 text-slate-700 uppercase tracking-wider">${escapeHtml(eventObj.source || 'system')}</span>
                    </div>
                </div>
                <p class="text-sm text-slate-700 leading-relaxed mt-2">${escapeHtml(eventObj.text)}</p>
            `;
            eventLogList.appendChild(card);
        });
    }

    function exportEventLog() {
        const fileName = `grace-event-log-${new Date().toISOString().slice(0, 10)}.json`;
        const blob = new Blob([JSON.stringify(mockEventLog, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        toast(`Exported ${fileName}`, { type: 'success' });
    }

    // Staff Directory
    function getFilteredStaff() {
        const status = state.staffStatus;
        const term = state.staffSearch.trim().toLowerCase();
        let items = [...mockStaff];
        if (status !== 'all') items = items.filter(s => s.status === status);
        if (!term) return items;
        return items.filter(s => {
            const languages = Array.isArray(s.languages) ? s.languages.join(' ') : String(s.languages || '');
            const hay = `${s.id} ${s.name} ${s.role} ${s.shift} ${s.phone} ${s.status} ${languages}`.toLowerCase();
            return hay.includes(term);
        });
    }

    function renderStaff() {
        if (!staffTableBody) {
            warn('missing staff table body');
            return;
        }
        const items = getFilteredStaff();
        if (staffCountBadge) staffCountBadge.innerText = String(items.length);

        staffTableBody.innerHTML = '';
        if (!items.length) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td class="px-4 md:px-6 py-6 text-sm text-slate-500" colspan="6">No staff match your search.</td>`;
            staffTableBody.appendChild(tr);
            return;
        }

        items.forEach(staff => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 transition-colors';
            const languages = Array.isArray(staff.languages) ? staff.languages.join(', ') : String(staff.languages || '');
            tr.innerHTML = `
                <td class="px-4 md:px-6 py-4 font-medium text-graphite">${escapeHtml(staff.name)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(staff.role)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(staff.shift)}</td>
                <td class="px-4 md:px-6 py-4 font-mono text-xs text-slate-500">${escapeHtml(staff.phone)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(languages)}</td>
                <td class="px-4 md:px-6 py-4"><span class="status-badge ${getStaffStatusStyles(staff.status)}">${escapeHtml(staff.status)}</span></td>
            `;
            staffTableBody.appendChild(tr);
        });
    }

    // 5. Drawer Controls
    function openDrawer(ticketId) {
        if (!drawer || !overlay) {
            warn('missing drawer/overlay');
            return;
        }
        const ticket = mockTickets.find(t => t.id === ticketId);
        if (!ticket) return;

        const drawerTicketId = document.getElementById('drawer-ticket-id');
        const drawerTicketSubject = document.getElementById('drawer-ticket-subject');
        const drawerCustomerName = document.getElementById('drawer-customer-name');
        const drawerCustomerMeta = document.getElementById('drawer-customer-meta');
        const drawerCustomerAvatar = document.getElementById('drawer-customer-avatar');
        const drawerTicketNotes = document.getElementById('drawer-ticket-notes');
        const drawerTags = document.getElementById('drawer-tags');

        if (!drawerTicketId || !drawerTicketSubject || !drawerCustomerName || !drawerCustomerMeta || !drawerCustomerAvatar || !drawerTicketNotes || !drawerTags) {
            warn('missing drawer detail nodes');
            return;
        }

        drawerTicketId.innerText = ticket.id;
        drawerTicketSubject.innerText = ticket.subject;
        drawerCustomerName.innerText = ticket.customer;
        drawerCustomerMeta.innerText = `Source: ${ticket.source}`;
        drawerCustomerAvatar.innerText = ticket.customer.charAt(0).toUpperCase();
        drawerTicketNotes.innerText = ticket.notes;

        drawerTags.innerHTML = `
        <span class="status-badge ${getSeverityStyles(ticket.severity)}">${ticket.severity}</span>
        <span class="status-badge ${getStatusStyles(ticket.status)}">${ticket.status}</span>
    `;

        drawer.classList.remove('drawer-exit');
        drawer.classList.add('drawer-enter');
        overlay.classList.remove('hidden');
        setTimeout(() => {
            overlay.classList.remove('overlay-fade-out');
            overlay.classList.add('overlay-fade-in');
        }, 10);
    }

    function closeDrawer() {
        if (!drawer || !overlay) return;
        drawer.classList.remove('drawer-enter');
        drawer.classList.add('drawer-exit');
        overlay.classList.remove('overlay-fade-in');
        overlay.classList.add('overlay-fade-out');
        setTimeout(() => overlay.classList.add('hidden'), 300);
    }

    // 6. Filtering Logic
    function bindFilters() {
        if (!filterGroup) {
            warn('missing filter group');
            return;
        }
        filterGroup.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON') return;

            const buttons = Array.from(filterGroup.querySelectorAll('button'));
            buttons.forEach(btn => {
                btn.className = 'px-3 py-1 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition';
            });
            e.target.className = 'px-3 py-1 text-xs font-semibold rounded bg-graphite text-white transition';
            renderTable(e.target.dataset.filter);
        });
    }

    // 7. Event Stream Simulation
    function appendStreamEvent(eventObj) {
        if (!streamContainer) return;
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        let borderClass = 'border-slate-200', iconColor = 'text-slate-400';
        if (eventObj.type === 'alert') { borderClass = 'border-rose-200'; iconColor = 'text-rose-500'; }
        if (eventObj.type === 'success') { borderClass = 'border-emerald-200'; iconColor = 'text-emerald-500'; }
        if (normalizeEventType(eventObj.type) === 'warn') { borderClass = 'border-amber-200'; iconColor = 'text-amber-500'; }

        const div = document.createElement('div');
        div.className = `event-card-new p-3 bg-white border ${borderClass} rounded-md shadow-sm`;
        div.innerHTML = `
        <div class="flex items-center gap-2 mb-1">
            <svg class="w-3 h-3 ${iconColor}" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"></circle></svg>
            <span class="text-[10px] text-slate-400 font-mono tracking-wider uppercase">${time}</span>
        </div>
        <p class="text-xs text-slate-700 leading-relaxed">${eventObj.text}</p>
    `;

        streamContainer.insertBefore(div, streamContainer.firstChild);
        if (streamContainer.children.length > 12) {
            streamContainer.removeChild(streamContainer.lastChild);
        }
    }

    function startStreamSimulation() {
        if (!streamContainer) {
            warn('missing event stream container');
            return;
        }
        appendStreamEvent({ text: 'GRACE Command Center initialized.', type: 'info' });
        logEvent({ type: 'info', source: 'system', text: 'GRACE Command Center initialized.' });

        function triggerRandom() {
            const randomEvent = mockEvents[Math.floor(Math.random() * mockEvents.length)];
            appendStreamEvent(randomEvent);
            logEvent({ type: randomEvent.type, source: 'system', text: randomEvent.text });
            const nextTick = Math.floor(Math.random() * (15000 - 8000 + 1) + 8000);
            setTimeout(triggerRandom, nextTick);
        }
        setTimeout(triggerRandom, 2000);
    }

    // 8. Panel Bindings / Search / Filters
    function setFilterButtonActive(group, activeButton) {
        if (!group) return;
        const buttons = Array.from(group.querySelectorAll('button'));
        buttons.forEach(btn => {
            btn.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition';
        });
        activeButton.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-graphite text-white transition';
    }

    function bindSearchAndFilters() {
        callsSearchInput?.addEventListener('input', () => {
            state.callsSearch = callsSearchInput.value || '';
            if (activeView === 'calls') renderCalls();
        });

        callsBtnSimulate?.addEventListener('click', () => simulateNewCall());
        callsBtnClearEnded?.addEventListener('click', () => {
            const before = mockCalls.length;
            for (let i = mockCalls.length - 1; i >= 0; i -= 1) {
                if (mockCalls[i].status === 'Ended') mockCalls.splice(i, 1);
            }
            const removed = before - mockCalls.length;
            toast(removed ? `Cleared ${removed} ended call(s).` : 'No ended calls to clear.', { type: 'info' });
            logEvent({ type: 'info', source: 'calls', text: `Cleared ${removed} ended call(s).` });
            if (activeView === 'calls') renderCalls();
        });

        callsTableBody?.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-call-action]');
            if (!btn) return;
            const action = btn.dataset.callAction;
            const callId = btn.dataset.callId;
            if (!action || !callId) return;

            if (action === 'transcript') {
                openCallTranscript(callId);
                return;
            }

            if (action === 'handoff') {
                const call = mockCalls.find(c => c.id === callId);
                if (!call || call.status === 'Ended') return;
                const targets = ['Front Desk', 'Concierge', 'Billing', 'Maintenance', 'Spa Desk'];
                call.handoff_to = call.handoff_to || targets[Math.floor(Math.random() * targets.length)];
                call.status = 'Handoff Pending';
                callsHandoffCount += 1;
                toast(`Handoff requested → ${call.handoff_to}`, { type: 'success' });
                logEvent({ type: 'success', source: 'calls', text: `Handoff requested for ${call.id} to ${call.handoff_to}.` });
                if (activeView === 'calls') renderCalls();
            }
        });

        callTranscriptClose?.addEventListener('click', closeCallTranscript);
        callTranscriptOverlay?.addEventListener('click', closeCallTranscript);

        escalationsSearchInput?.addEventListener('input', () => {
            state.escalationsSearch = escalationsSearchInput.value || '';
            if (activeView === 'escalations') renderEscalations();
        });

        escalationsFilterGroup?.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-filter]');
            if (!btn) return;
            state.escalationsStatus = btn.dataset.filter || 'all';
            setFilterButtonActive(escalationsFilterGroup, btn);
            if (activeView === 'escalations') renderEscalations();
        });

        escalationsList?.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-esc-action]');
            if (!btn) return;
            const action = btn.dataset.escAction;
            const id = btn.dataset.escId;
            if (!action || !id) return;
            updateEscalation(id, action);
        });

        eventLogSearchInput?.addEventListener('input', () => {
            state.eventLogSearch = eventLogSearchInput.value || '';
            if (activeView === 'eventlog') renderEventLog();
        });

        eventLogFilterGroup?.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-type]');
            if (!btn) return;
            state.eventLogType = btn.dataset.type || 'all';
            setFilterButtonActive(eventLogFilterGroup, btn);
            if (activeView === 'eventlog') renderEventLog();
        });

        eventLogBtnClear?.addEventListener('click', () => {
            mockEventLog.splice(0, mockEventLog.length);
            toast('Event log cleared.', { type: 'info' });
            if (activeView === 'eventlog') renderEventLog();
        });

        eventLogBtnExport?.addEventListener('click', exportEventLog);

        staffSearchInput?.addEventListener('input', () => {
            state.staffSearch = staffSearchInput.value || '';
            if (activeView === 'staff') renderStaff();
        });

        staffFilterGroup?.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-filter]');
            if (!btn) return;
            state.staffStatus = btn.dataset.filter || 'all';
            setFilterButtonActive(staffFilterGroup, btn);
            if (activeView === 'staff') renderStaff();
        });
    }

    // 9. Optional "Live" feel - mutate calls & write to event log
    function startCallsSimulation() {
        function tick() {
            if (!mockCalls.length) {
                setTimeout(tick, 4500);
                return;
            }

            const roll = Math.random();
            let callsChanged = false;

            // ~20%: new call comes in
            if (roll < 0.2) {
                simulateNewCall({ showToast: false, render: false, source: 'calls' });
                callsChanged = true;
            } else {
                const call = mockCalls[Math.floor(Math.random() * mockCalls.length)];
                if (!call) {
                    setTimeout(tick, 4500);
                    return;
                }
                callsChanged = true;

                // mutate latency
                const delta = Math.floor(Math.random() * 180 - 90);
                call.latency_ms = Math.max(120, (call.latency_ms || 200) + delta);

                // progress state machine lightly
                if (call.status === 'Ringing' && Math.random() < 0.55) {
                    call.status = 'Active';
                    logEvent({ type: 'info', source: 'calls', text: `${call.id} connected (${call.intent}).` });
                } else if (call.status === 'Active' && Math.random() < 0.15) {
                    call.status = 'Ended';
                    logEvent({ type: 'info', source: 'calls', text: `${call.id} ended.` });
                } else if (call.status === 'Handoff Pending' && Math.random() < 0.3) {
                    call.status = 'Ended';
                    logEvent({ type: 'success', source: 'calls', text: `${call.id} handed off to ${call.handoff_to}.` });
                }

                if (call.status !== 'Ended' && call.latency_ms >= 900) {
                    logEvent({ type: 'warn', source: 'calls', text: `High latency on ${call.id}: ${call.latency_ms}ms.` });
                }
            }

            if (callsChanged && activeView === 'calls') renderCalls();

            const nextTick = Math.floor(Math.random() * (6000 - 3000 + 1) + 3000);
            setTimeout(tick, nextTick);
        }

        setTimeout(tick, 3800);
    }

    // 8. Tabs / Views
    function setActiveView(view, options = {}) {
        const updateHash = options.updateHash !== false;
        if (!panels.length || !navLinks.length) {
            warn('missing tab panels or nav links');
            return;
        }
        const knownViews = navLinks.map(link => link.dataset.view).filter(Boolean);
        if (!knownViews.includes(view)) {
            warn('unknown view requested', view);
            return;
        }

        panels.forEach(panel => {
            const isActive = panel.dataset.panel === view;
            panel.classList.toggle('hidden', !isActive);
        });

        navLinks.forEach(link => {
            const isActive = link.dataset.view === view;
            link.classList.toggle('bg-slate-800', isActive);
            link.classList.toggle('text-white', isActive);
            link.classList.toggle('border-accent', isActive);

            link.classList.toggle('text-slate-400', !isActive);
            link.classList.toggle('border-transparent', !isActive);
            link.classList.toggle('hover:text-white', !isActive);
            link.classList.toggle('hover:bg-slate-800/50', !isActive);

            if (isActive) {
                link.classList.remove('border-transparent', 'hover:text-white', 'hover:bg-slate-800/50');
                link.setAttribute('aria-current', 'page');
            } else {
                link.removeAttribute('aria-current');
            }
        });

        if (updateHash && window.location.hash !== `#${view}`) {
            history.replaceState(null, '', `#${view}`);
        }

        activeView = view;
        if (view === 'calls') renderCalls();
        if (view === 'escalations') renderEscalations();
        if (view === 'eventlog') renderEventLog();
        if (view === 'staff') renderStaff();
    }

    function bindTabs() {
        if (!navLinks.length || !panels.length) {
            warn('missing tab panels or nav links');
            return;
        }

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const view = link.dataset.view;
                if (view) setActiveView(view);
            });

            link.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const view = link.dataset.view;
                    if (view) setActiveView(view);
                }
            });
        });

        const knownViews = navLinks.map(link => link.dataset.view).filter(Boolean);
        const hashView = window.location.hash.replace('#', '');
        const defaultView = knownViews.includes(hashView)
            ? hashView
            : (knownViews.includes('queue') ? 'queue' : knownViews[0]);

        if (defaultView) {
            setActiveView(defaultView);
        }

        window.addEventListener('hashchange', () => {
            const nextView = window.location.hash.replace('#', '');
            if (knownViews.includes(nextView)) {
                setActiveView(nextView, { updateHash: false });
            }
        });
    }

    // 9. Init
    if (tbody) {
        renderTable();
    } else {
        warn('ticket table body missing; skipping render');
    }

    bindFilters();
    startStreamSimulation();
    bindSearchAndFilters();
    startCallsSimulation();
    bindTabs();

    // Bind Event Listeners
    overlay?.addEventListener('click', closeDrawer);
    btnCloseDrawer?.addEventListener('click', closeDrawer);
    btnResolve?.addEventListener('click', closeDrawer);
    btnAssign?.addEventListener('click', () => alert('Ticket assigned to your queue.'));
    btnEscalate?.addEventListener('click', () => alert('Ticket escalated to Level 2 Support.'));

    // Delegate row clicks to tbody (avoids manual rebinding on re-render)
    tbody?.addEventListener('click', (e) => {
        const row = e.target.closest('tr[data-ticket-id]');
        if (row) openDrawer(row.dataset.ticketId);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeDrawer();
            closeCallTranscript();
        }
    });
});
