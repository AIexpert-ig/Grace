/**
 * GRACE Dashboard - Vanilla JS Logic
 * No build tools, no React, purely operational DOM manipulation.
 */

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
    const lowered = String(type || '').toLowerCase();
    if (lowered === 'warning') return 'warn';
    if (['info', 'warn', 'alert', 'success'].includes(lowered)) return lowered;
    return 'info';
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
    switch (String(severity || '').toLowerCase()) {
        case 'critical': return 'bg-rose-100 text-rose-700 border border-rose-200';
        case 'high': return 'bg-orange-100 text-orange-700 border border-orange-200';
        case 'medium': return 'bg-amber-100 text-amber-700 border border-amber-200';
        case 'low': return 'bg-slate-100 text-slate-600 border border-slate-200';
        default: return 'bg-slate-100 text-slate-600 border border-slate-200';
    }
}

function getStatusStyles(status) {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'resolved') return 'text-emerald-600 bg-emerald-50 border border-emerald-100';
    if (normalized === 'in progress' || normalized === 'in_progress' || normalized === 'in-progress') {
        return 'text-sky-600 bg-sky-50 border border-sky-100';
    }
    return 'text-slate-600 bg-slate-50 border border-slate-200'; // Open / default
}

function getEventTypeStyles(type) {
    const t = normalizeEventType(type);
    if (t === 'alert') return { border: 'border-rose-200', icon: 'text-rose-500', pill: 'bg-rose-100 text-rose-700 border border-rose-200' };
    if (t === 'success') return { border: 'border-emerald-200', icon: 'text-emerald-500', pill: 'bg-emerald-100 text-emerald-700 border border-emerald-200' };
    if (t === 'warn') return { border: 'border-amber-200', icon: 'text-amber-500', pill: 'bg-amber-100 text-amber-700 border border-amber-200' };
    return { border: 'border-slate-200', icon: 'text-slate-400', pill: 'bg-slate-100 text-slate-700 border border-slate-200' };
}

function getCallStatusStyles(status) {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'active') return 'text-emerald-700 bg-emerald-50 border border-emerald-100';
    if (normalized === 'ringing') return 'text-sky-700 bg-sky-50 border border-sky-100';
    if (normalized === 'handoff pending' || normalized === 'handoff_pending') return 'text-amber-700 bg-amber-50 border border-amber-100';
    if (normalized === 'ended') return 'text-slate-600 bg-slate-50 border border-slate-200';
    return 'text-slate-600 bg-slate-50 border border-slate-200';
}

function getStaffStatusStyles(status) {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'on duty' || normalized === 'on_duty') return 'text-emerald-700 bg-emerald-50 border border-emerald-100';
    if (normalized === 'busy') return 'text-amber-700 bg-amber-50 border border-amber-100';
    if (normalized === 'off duty' || normalized === 'off_duty') return 'text-slate-600 bg-slate-50 border border-slate-200';
    return 'text-slate-600 bg-slate-50 border border-slate-200';
}

function getErrorMessage(err) {
    if (!err) return 'Unknown error.';
    if (err.name === 'AbortError') return 'Request timed out.';
    if (typeof err.message === 'string' && err.message.trim()) return err.message.trim();
    return String(err);
}

async function fetchJSON(url, options = {}) {
    const timeoutMs = Number.isFinite(options.timeoutMs) ? options.timeoutMs : 8000;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: { Accept: 'application/json' },
            signal: controller.signal
        });

        const contentType = response.headers.get('content-type') || '';
        const isJson = contentType.includes('application/json');
        const body = isJson ? await response.json().catch(() => null) : await response.text().catch(() => '');

        if (!response.ok) {
            const detail = body && typeof body === 'object'
                ? (body.detail || body.error || JSON.stringify(body))
                : String(body || '');
            const suffix = detail ? ` (${detail})` : '';
            throw new Error(`HTTP ${response.status}${suffix}`);
        }

        return body;
    } finally {
        clearTimeout(timer);
    }
}

function downloadJSON(fileName, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener('DOMContentLoaded', () => {
    const navLinks = Array.from(document.querySelectorAll('[data-view]'));
    const panels = Array.from(document.querySelectorAll('[data-panel]'));

    const warn = (message, detail) => {
        console.warn(`[dashboard] ${message}`, detail || '');
    };

    const knownViews = navLinks.map(link => link.dataset.view).filter(Boolean);
    console.log('[dashboard] boot ok', { views: knownViews, ts: Date.now() });

    // Queue / Tickets
    const tbody = document.getElementById('ticket-table-body');
    const filterGroup = document.getElementById('filter-group');
    const streamContainer = document.getElementById('event-stream-container');
    const kpiOpen = document.getElementById('kpi-open-tickets');
    const kpiCritical = document.getElementById('kpi-critical');
    const kpiActiveCallsQueue = document.getElementById('kpi-active-calls');
    const navEscalationsBadge = document.getElementById('nav-escalations-badge');

    // Drawer (Incident Queue)
    const drawer = document.getElementById('ticket-drawer');
    const overlay = document.getElementById('drawer-overlay');
    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    const btnAssign = document.getElementById('btn-assign');
    const btnEscalate = document.getElementById('btn-escalate');
    const btnResolve = document.getElementById('btn-resolve');

    // Calls
    const callsTableBody = document.getElementById('calls-table-body');
    const callsSearchInput = document.getElementById('calls-search');
    const callsCountBadge = document.getElementById('calls-count-badge');
    const callsKpiActive = document.getElementById('calls-kpi-active');
    const callsKpiAvgLatency = document.getElementById('calls-kpi-avg-latency');
    const callsKpiHandoffs = document.getElementById('calls-kpi-handoffs');
    const callsKpiIntent = document.getElementById('calls-kpi-intent');
    const callsBtnRefresh = document.getElementById('calls-btn-refresh');

    const callTranscriptOverlay = document.getElementById('call-transcript-overlay');
    const callTranscriptModal = document.getElementById('call-transcript-modal');
    const callTranscriptClose = document.getElementById('call-transcript-close');
    const callTranscriptMeta = document.getElementById('call-transcript-meta');
    const callTranscriptTitle = document.getElementById('call-transcript-title');
    const callTranscriptTags = document.getElementById('call-transcript-tags');
    const callTranscriptBody = document.getElementById('call-transcript-body');

    // Escalations (derived from tickets)
    const escalationsList = document.getElementById('escalations-list');
    const escalationsCount = document.getElementById('escalations-count');
    const escalationsSearchInput = document.getElementById('escalations-search');
    const escalationsFilterGroup = document.getElementById('escalations-filter-group');

    // Event Log
    const eventLogList = document.getElementById('eventlog-list');
    const eventLogSearchInput = document.getElementById('eventlog-search');
    const eventLogFilterGroup = document.getElementById('eventlog-filter-group');
    const eventLogBtnExport = document.getElementById('eventlog-btn-export');
    const eventLogBtnRefresh = document.getElementById('eventlog-btn-refresh');

    // Staff
    const staffTableBody = document.getElementById('staff-table-body');
    const staffCountBadge = document.getElementById('staff-count-badge');
    const staffSearchInput = document.getElementById('staff-search');
    const staffFilterGroup = document.getElementById('staff-filter-group');

    const cache = {
        tickets: { data: [], ts: 0, loading: false, promise: null },
        events: { data: [], ts: 0, loading: false, promise: null },
        calls: { data: [], ts: 0, loading: false, promise: null },
        staff: { data: [], ts: 0, loading: false, promise: null }
    };

    const state = {
        activeView: null,
        ticketFilter: 'all',
        callsSearch: '',
        escalationsStatus: 'all',
        escalationsSearch: '',
        eventLogType: 'all',
        eventLogSearch: '',
        staffStatus: 'all',
        staffSearch: ''
    };

    const ticketsById = new Map();
    const callsById = new Map();

    function setPanelError(view, message) {
        const banner = document.getElementById(`${view}-error-banner`);
        const text = document.getElementById(`${view}-error-text`);
        if (!banner || !text) return;
        text.textContent = message;
        banner.classList.remove('hidden');
    }

    function clearPanelError(view) {
        const banner = document.getElementById(`${view}-error-banner`);
        if (!banner) return;
        banner.classList.add('hidden');
    }

    function setTableMessage(targetTbody, message, colspan) {
        if (!targetTbody) return;
        targetTbody.innerHTML = '';
        const tr = document.createElement('tr');
        tr.innerHTML = `<td class="px-4 md:px-6 py-6 text-sm text-slate-500" colspan="${colspan}">${escapeHtml(message)}</td>`;
        targetTbody.appendChild(tr);
    }

    function normalizeTicket(raw) {
        const severity = String(raw?.severity || 'low').toLowerCase();
        const normalizedSeverity = ['critical', 'high', 'medium', 'low'].includes(severity) ? severity : 'low';
        const status = String(raw?.status || 'Open');
        const createdAt = raw?.created_at || null;
        const updatedAt = raw?.updated_at || createdAt || null;

        return {
            id: String(raw?.id || ''),
            customer: String(raw?.customer || 'Unknown'),
            source: String(raw?.source || 'System'),
            subject: String(raw?.subject || ''),
            severity: normalizedSeverity,
            status,
            notes: String(raw?.notes || raw?.subject || ''),
            created_at: createdAt,
            updated_at: updatedAt
        };
    }

    function normalizeEvent(raw) {
        return {
            at: raw?.at || null,
            type: normalizeEventType(raw?.type),
            source: String(raw?.source || 'system'),
            text: String(raw?.text || '')
        };
    }

    function normalizeCall(raw) {
        return {
            id: String(raw?.id || ''),
            from: String(raw?.from || 'Unknown'),
            status: String(raw?.status || 'Active'),
            intent: String(raw?.intent || ''),
            latency_ms: Number.isFinite(raw?.latency_ms) ? raw.latency_ms : null,
            started_at: raw?.started_at || null,
            transcript_snippet: String(raw?.transcript_snippet || '')
        };
    }

    function normalizeStaff(raw) {
        const languages = Array.isArray(raw?.languages) ? raw.languages : [];
        return {
            id: String(raw?.id || ''),
            name: String(raw?.name || ''),
            role: String(raw?.role || ''),
            shift: String(raw?.shift || ''),
            phone: String(raw?.phone || ''),
            status: String(raw?.status || ''),
            languages: languages.map(String)
        };
    }

    function updateTicketKPIs(tickets) {
        const openTickets = tickets.filter(t => String(t.status || '').toLowerCase() !== 'resolved').length;
        const criticalTickets = tickets.filter(t => t.severity === 'critical' && String(t.status || '').toLowerCase() !== 'resolved').length;

        if (kpiOpen) kpiOpen.innerText = String(openTickets);
        if (kpiCritical) kpiCritical.innerText = String(criticalTickets);

        if (navEscalationsBadge) {
            if (cache.tickets.loading && !tickets.length) {
                navEscalationsBadge.innerText = '--';
                navEscalationsBadge.classList.remove('hidden');
            } else {
                const escalations = tickets.filter(t => {
                    const unresolved = String(t.status || '').toLowerCase() !== 'resolved';
                    return unresolved && (t.severity === 'critical' || t.severity === 'high');
                }).length;
                navEscalationsBadge.innerText = String(escalations);
                navEscalationsBadge.classList.toggle('hidden', escalations === 0);
            }
        }
    }

    function renderTickets() {
        if (!tbody) return;
        const tickets = cache.tickets.data;
        updateTicketKPIs(tickets);

        const filtered = state.ticketFilter === 'all'
            ? tickets
            : tickets.filter(t => t.severity === state.ticketFilter);

        ticketsById.clear();
        tickets.forEach(t => ticketsById.set(t.id, t));

        if (cache.tickets.loading && !tickets.length) {
            setTableMessage(tbody, 'Loading tickets…', 5);
            return;
        }

        if (!filtered.length) {
            const msg = tickets.length ? 'No tickets match your filter.' : 'No tickets yet.';
            setTableMessage(tbody, msg, 5);
            return;
        }

        tbody.innerHTML = '';
        filtered.forEach(ticket => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 cursor-pointer transition-colors group';
            tr.dataset.ticketId = ticket.id;
            tr.innerHTML = `
                <td class="px-4 md:px-6 py-4 font-mono text-xs font-semibold text-slate-500 group-hover:text-accent transition-colors">${escapeHtml(ticket.id)}</td>
                <td class="px-4 md:px-6 py-4 font-medium text-graphite">${escapeHtml(ticket.customer)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600 truncate max-w-[150px] sm:max-w-xs md:max-w-sm lg:max-w-md" title="${escapeHtml(ticket.subject)}">${escapeHtml(ticket.subject)}</td>
                <td class="px-4 md:px-6 py-4">
                    <span class="status-badge ${getSeverityStyles(ticket.severity)}">${escapeHtml(ticket.severity)}</span>
                </td>
                <td class="px-4 md:px-6 py-4">
                    <span class="status-badge ${getStatusStyles(ticket.status)}">${escapeHtml(ticket.status)}</span>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function openDrawer(ticketId) {
        if (!drawer || !overlay) return;
        const ticket = ticketsById.get(ticketId);
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
        drawerTicketSubject.innerText = ticket.subject || 'Ticket Details';
        drawerCustomerName.innerText = ticket.customer || 'Unknown';
        drawerCustomerMeta.innerText = `Source: ${ticket.source || 'System'}`;
        drawerCustomerAvatar.innerText = (ticket.customer || 'U').charAt(0).toUpperCase();
        drawerTicketNotes.innerText = ticket.notes || ticket.subject || '';

        drawerTags.innerHTML = `
            <span class="status-badge ${getSeverityStyles(ticket.severity)}">${escapeHtml(ticket.severity)}</span>
            <span class="status-badge ${getStatusStyles(ticket.status)}">${escapeHtml(ticket.status)}</span>
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

    function renderEventStream() {
        if (!streamContainer) return;
        const events = cache.events.data;

        if (cache.events.loading && !events.length) {
            streamContainer.innerHTML = `<div class="p-3 text-xs text-slate-500">Loading events…</div>`;
            return;
        }

        if (!events.length) {
            streamContainer.innerHTML = `<div class="p-3 text-xs text-slate-500">No events yet.</div>`;
            return;
        }

        streamContainer.innerHTML = '';
        events.slice(0, 12).forEach(evt => {
            const styles = getEventTypeStyles(evt.type);
            const time = evt.at ? new Date(evt.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '--';
            const div = document.createElement('div');
            div.className = `event-card-new p-3 bg-white border ${styles.border} rounded-md shadow-sm`;
            div.innerHTML = `
                <div class="flex items-center gap-2 mb-1">
                    <svg class="w-3 h-3 ${styles.icon}" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"></circle></svg>
                    <span class="text-[10px] text-slate-400 font-mono tracking-wider uppercase">${escapeHtml(time)}</span>
                    <span class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-slate-200 text-slate-700 uppercase tracking-wider">${escapeHtml(evt.source)}</span>
                </div>
                <p class="text-xs text-slate-700 leading-relaxed">${escapeHtml(evt.text)}</p>
            `;
            streamContainer.appendChild(div);
        });
    }

    function renderEventLog() {
        if (!eventLogList) return;
        const term = state.eventLogSearch.trim().toLowerCase();
        const type = state.eventLogType;

        let items = cache.events.data;
        if (type !== 'all') items = items.filter(e => e.type === type);
        if (term) {
            items = items.filter(e => {
                const hay = `${e.at} ${e.type} ${e.source} ${e.text}`.toLowerCase();
                return hay.includes(term);
            });
        }

        if (cache.events.loading && !cache.events.data.length) {
            eventLogList.innerHTML = `<div class="p-4 text-sm text-slate-500 bg-white border border-slate-200 rounded-md">Loading events…</div>`;
            return;
        }

        eventLogList.innerHTML = '';
        if (!items.length) {
            const msg = cache.events.data.length ? 'No events match your filters.' : 'No events yet.';
            eventLogList.innerHTML = `<div class="p-4 text-sm text-slate-500 bg-white border border-slate-200 rounded-md">${escapeHtml(msg)}</div>`;
            return;
        }

        items.slice(0, 120).forEach(evt => {
            const styles = getEventTypeStyles(evt.type);
            const time = evt.at ? new Date(evt.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '--';
            const card = document.createElement('div');
            card.className = `event-card-new p-3 bg-white border ${styles.border} rounded-md shadow-sm`;
            card.innerHTML = `
                <div class="flex items-center justify-between gap-3">
                    <div class="flex items-center gap-2 min-w-0">
                        <svg class="w-3 h-3 ${styles.icon}" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"></circle></svg>
                        <span class="text-[10px] text-slate-400 font-mono tracking-wider uppercase">${escapeHtml(time)}</span>
                        <span class="status-badge ${styles.pill}">${escapeHtml(evt.type)}</span>
                        <span class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-slate-200 text-slate-700 uppercase tracking-wider">${escapeHtml(evt.source)}</span>
                    </div>
                </div>
                <p class="text-sm text-slate-700 leading-relaxed mt-2">${escapeHtml(evt.text)}</p>
            `;
            eventLogList.appendChild(card);
        });
    }

    function renderCalls() {
        if (!callsTableBody) return;
        const term = state.callsSearch.trim().toLowerCase();

        let calls = cache.calls.data;
        if (term) {
            calls = calls.filter(c => {
                const hay = `${c.id} ${c.from} ${c.status} ${c.intent}`.toLowerCase();
                return hay.includes(term);
            });
        }

        callsById.clear();
        cache.calls.data.forEach(c => callsById.set(c.id, c));

        const activeCalls = cache.calls.data.filter(c => String(c.status || '').toLowerCase() !== 'ended');
        const latencyValues = activeCalls.map(c => c.latency_ms).filter(v => Number.isFinite(v));
        const avgLatency = latencyValues.length ? Math.round(latencyValues.reduce((a, b) => a + b, 0) / latencyValues.length) : null;

        if (callsKpiActive) callsKpiActive.innerText = String(activeCalls.length);
        if (kpiActiveCallsQueue) kpiActiveCallsQueue.innerText = String(activeCalls.length);
        if (callsKpiAvgLatency) callsKpiAvgLatency.innerText = avgLatency === null ? '--' : String(avgLatency);
        if (callsKpiHandoffs) callsKpiHandoffs.innerText = '--';

        if (callsKpiIntent) {
            const counts = new Map();
            activeCalls.forEach(c => {
                if (!c.intent) return;
                counts.set(c.intent, (counts.get(c.intent) || 0) + 1);
            });
            let top = '--';
            let topCount = 0;
            counts.forEach((count, intent) => {
                if (count > topCount) {
                    topCount = count;
                    top = intent;
                }
            });
            callsKpiIntent.innerText = top;
        }

        if (callsCountBadge) callsCountBadge.innerText = String(calls.length);

        if (cache.calls.loading && !cache.calls.data.length) {
            setTableMessage(callsTableBody, 'Loading calls…', 7);
            return;
        }

        callsTableBody.innerHTML = '';
        if (!calls.length) {
            const msg = cache.calls.data.length ? 'No calls match your search.' : 'No calls yet.';
            setTableMessage(callsTableBody, msg, 7);
            return;
        }

        calls.forEach(call => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 transition-colors';
            tr.dataset.callId = call.id;

            const started = call.started_at ? formatRelativeTime(call.started_at) : '--';
            const latencyText = Number.isFinite(call.latency_ms) ? `${call.latency_ms}ms` : '--';

            tr.innerHTML = `
                <td class="px-4 md:px-6 py-4 font-medium text-graphite">${escapeHtml(call.from)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(call.id)}</td>
                <td class="px-4 md:px-6 py-4"><span class="status-badge ${getCallStatusStyles(call.status)}">${escapeHtml(call.status)}</span></td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(call.intent || '--')}</td>
                <td class="px-4 md:px-6 py-4 font-mono text-xs text-slate-500">${escapeHtml(latencyText)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-500">${escapeHtml(started)}</td>
                <td class="px-4 md:px-6 py-4 text-right">
                    <button data-call-action="transcript" data-call-id="${escapeHtml(call.id)}"
                        class="px-2.5 py-1.5 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                        Transcript
                    </button>
                </td>
            `;
            callsTableBody.appendChild(tr);
        });
    }

    function openCallTranscript(callId) {
        if (!callTranscriptOverlay || !callTranscriptModal) return;
        const call = callsById.get(callId);
        if (!call) return;

        if (callTranscriptMeta) {
            const started = call.started_at ? `started ${formatRelativeTime(call.started_at)} ago` : 'start time unknown';
            callTranscriptMeta.innerText = `${call.id} • ${started}`;
        }
        if (callTranscriptTitle) callTranscriptTitle.innerText = `From ${call.from}`;

        if (callTranscriptTags) {
            const latency = Number.isFinite(call.latency_ms) ? `${call.latency_ms}ms` : '--';
            callTranscriptTags.innerHTML = `
                <span class="status-badge ${getCallStatusStyles(call.status)}">${escapeHtml(call.status)}</span>
                <span class="status-badge bg-slate-100 text-slate-700 border border-slate-200">${escapeHtml(call.intent || '—')}</span>
                <span class="status-badge bg-slate-100 text-slate-700 border border-slate-200">${escapeHtml(latency)}</span>
            `;
        }

        if (callTranscriptBody) {
            const snippet = call.transcript_snippet ? call.transcript_snippet : 'No transcript snippet available.';
            callTranscriptBody.innerText = snippet;
        }

        callTranscriptOverlay.classList.remove('hidden');
        callTranscriptModal.classList.remove('hidden');
    }

    function closeCallTranscript() {
        callTranscriptOverlay?.classList.add('hidden');
        callTranscriptModal?.classList.add('hidden');
    }

    function renderStaff() {
        if (!staffTableBody) return;
        const term = state.staffSearch.trim().toLowerCase();
        const status = state.staffStatus;

        let items = cache.staff.data;
        if (status !== 'all') {
            items = items.filter(s => String(s.status || '') === status);
        }
        if (term) {
            items = items.filter(s => {
                const languages = Array.isArray(s.languages) ? s.languages.join(' ') : '';
                const hay = `${s.id} ${s.name} ${s.role} ${s.shift} ${s.phone} ${s.status} ${languages}`.toLowerCase();
                return hay.includes(term);
            });
        }

        if (staffCountBadge) staffCountBadge.innerText = String(items.length);

        if (cache.staff.loading && !cache.staff.data.length) {
            setTableMessage(staffTableBody, 'Loading staff…', 6);
            return;
        }

        staffTableBody.innerHTML = '';
        if (!items.length) {
            const msg = cache.staff.data.length ? 'No staff match your search.' : 'No staff yet.';
            setTableMessage(staffTableBody, msg, 6);
            return;
        }

        items.forEach(staff => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 transition-colors';
            const languages = Array.isArray(staff.languages) ? staff.languages.join(', ') : '';
            tr.innerHTML = `
                <td class="px-4 md:px-6 py-4 font-medium text-graphite">${escapeHtml(staff.name)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(staff.role)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(staff.shift)}</td>
                <td class="px-4 md:px-6 py-4 font-mono text-xs text-slate-500">${escapeHtml(staff.phone)}</td>
                <td class="px-4 md:px-6 py-4 text-slate-600">${escapeHtml(languages || '--')}</td>
                <td class="px-4 md:px-6 py-4"><span class="status-badge ${getStaffStatusStyles(staff.status)}">${escapeHtml(staff.status || '--')}</span></td>
            `;
            staffTableBody.appendChild(tr);
        });
    }

    function renderEscalations() {
        if (!escalationsList) return;
        const tickets = cache.tickets.data;

        const term = state.escalationsSearch.trim().toLowerCase();
        const status = state.escalationsStatus;

        let items = tickets.filter(t => t.severity === 'critical' || t.severity === 'high');
        if (status !== 'all') {
            items = items.filter(t => String(t.status || '') === status);
        }
        if (term) {
            items = items.filter(t => {
                const hay = `${t.id} ${t.customer} ${t.source} ${t.subject}`.toLowerCase();
                return hay.includes(term);
            });
        }

        if (escalationsCount) escalationsCount.innerText = String(items.length);

        if (cache.tickets.loading && !cache.tickets.data.length) {
            escalationsList.innerHTML = `<div class="p-6 text-sm text-slate-500">Loading escalations…</div>`;
            return;
        }

        escalationsList.innerHTML = '';
        if (!items.length) {
            const msg = tickets.length ? 'No escalations match your filters.' : 'No escalations yet.';
            escalationsList.innerHTML = `<div class="p-6 text-sm text-slate-500">${escapeHtml(msg)}</div>`;
            return;
        }

        items.forEach(ticket => {
            const card = document.createElement('div');
            card.className = 'p-4 md:p-6 bg-white';
            const created = ticket.created_at ? formatRelativeTime(ticket.created_at) : '--';
            card.innerHTML = `
                <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div class="min-w-0">
                        <div class="flex items-center gap-2 flex-wrap">
                            <span class="text-xs font-mono font-semibold text-slate-500">${escapeHtml(ticket.id)}</span>
                            <span class="status-badge ${getSeverityStyles(ticket.severity)}">${escapeHtml(ticket.severity)}</span>
                            <span class="status-badge ${getStatusStyles(ticket.status)}">${escapeHtml(ticket.status)}</span>
                        </div>
                        <p class="text-sm font-semibold text-graphite mt-2 truncate" title="${escapeHtml(ticket.subject)}">${escapeHtml(ticket.subject)}</p>
                        <p class="text-xs text-slate-500 mt-2">${escapeHtml(ticket.customer)} • ${escapeHtml(ticket.source)} • Created ${escapeHtml(created)} ago</p>
                    </div>
                </div>
            `;
            escalationsList.appendChild(card);
        });
    }

    async function loadTickets(contextView, options = {}) {
        const force = options.force === true;
        const maxAgeMs = options.maxAgeMs || 9000;
        const entry = cache.tickets;

        if (entry.loading) return entry.promise;
        if (!force && entry.ts && (Date.now() - entry.ts) < maxAgeMs) return entry.data;

        entry.loading = true;
        clearPanelError(contextView);
        if (state.activeView === 'queue') renderTickets();
        if (state.activeView === 'escalations') renderEscalations();

        entry.promise = (async () => {
            const raw = await fetchJSON('/api/tickets?limit=50', { timeoutMs: 8000 });
            const list = Array.isArray(raw) ? raw : [];
            entry.data = list.map(normalizeTicket).filter(t => t.id);
            entry.ts = Date.now();
            return entry.data;
        })();

        try {
            await entry.promise;
        } catch (err) {
            setPanelError(contextView, getErrorMessage(err));
        } finally {
            entry.loading = false;
            entry.promise = null;
            if (state.activeView === 'queue') renderTickets();
            if (state.activeView === 'escalations') renderEscalations();
        }

        return entry.data;
    }

    async function loadEvents(contextView, options = {}) {
        const force = options.force === true;
        const maxAgeMs = options.maxAgeMs || 9000;
        const entry = cache.events;

        if (entry.loading) return entry.promise;
        if (!force && entry.ts && (Date.now() - entry.ts) < maxAgeMs) return entry.data;

        entry.loading = true;
        clearPanelError(contextView);
        if (state.activeView === 'queue') renderEventStream();
        if (state.activeView === 'eventlog') renderEventLog();

        entry.promise = (async () => {
            const raw = await fetchJSON('/api/events?limit=100', { timeoutMs: 8000 });
            const list = Array.isArray(raw) ? raw : [];
            entry.data = list.map(normalizeEvent);
            entry.ts = Date.now();
            return entry.data;
        })();

        try {
            await entry.promise;
        } catch (err) {
            setPanelError(contextView, getErrorMessage(err));
        } finally {
            entry.loading = false;
            entry.promise = null;
            if (state.activeView === 'queue') renderEventStream();
            if (state.activeView === 'eventlog') renderEventLog();
        }

        return entry.data;
    }

    async function loadCalls(contextView, options = {}) {
        const force = options.force === true;
        const maxAgeMs = options.maxAgeMs || 9000;
        const entry = cache.calls;

        if (entry.loading) return entry.promise;
        if (!force && entry.ts && (Date.now() - entry.ts) < maxAgeMs) return entry.data;

        entry.loading = true;
        clearPanelError(contextView);
        if (state.activeView === 'calls') renderCalls();

        entry.promise = (async () => {
            const raw = await fetchJSON('/api/calls?limit=50', { timeoutMs: 8000 });
            const list = Array.isArray(raw) ? raw : [];
            entry.data = list.map(normalizeCall).filter(c => c.id);
            entry.ts = Date.now();
            return entry.data;
        })();

        try {
            await entry.promise;
        } catch (err) {
            setPanelError(contextView, getErrorMessage(err));
        } finally {
            entry.loading = false;
            entry.promise = null;
            if (state.activeView === 'calls') renderCalls();
        }

        return entry.data;
    }

    async function loadStaff(contextView, options = {}) {
        const force = options.force === true;
        const maxAgeMs = options.maxAgeMs || 30000;
        const entry = cache.staff;

        if (entry.loading) return entry.promise;
        if (!force && entry.ts && (Date.now() - entry.ts) < maxAgeMs) return entry.data;

        entry.loading = true;
        clearPanelError(contextView);
        if (state.activeView === 'staff') renderStaff();

        entry.promise = (async () => {
            const raw = await fetchJSON('/api/staff?limit=100', { timeoutMs: 8000 });
            const list = Array.isArray(raw) ? raw : [];
            entry.data = list.map(normalizeStaff);
            entry.ts = Date.now();
            return entry.data;
        })();

        try {
            await entry.promise;
        } catch (err) {
            setPanelError(contextView, getErrorMessage(err));
        } finally {
            entry.loading = false;
            entry.promise = null;
            if (state.activeView === 'staff') renderStaff();
        }

        return entry.data;
    }

    async function refreshActiveView(options = {}) {
        const force = options.force === true;
        const view = state.activeView || 'queue';

        if (view === 'queue') {
            await Promise.all([
                loadTickets('queue', { force }),
                loadEvents('queue', { force })
            ]);
            return;
        }

        if (view === 'calls') {
            await loadCalls('calls', { force });
            return;
        }

        if (view === 'escalations') {
            await loadTickets('escalations', { force });
            return;
        }

        if (view === 'eventlog') {
            await loadEvents('eventlog', { force });
            return;
        }

        if (view === 'staff') {
            await loadStaff('staff', { force });
        }
    }

    // Tabs / Views
    function setActiveView(view, options = {}) {
        const updateHash = options.updateHash !== false;
        if (!panels.length || !navLinks.length) {
            warn('missing tab panels or nav links');
            return;
        }
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

        if (view !== 'calls') closeCallTranscript();

        state.activeView = view;
        refreshActiveView().catch((err) => warn('refresh failed', err));
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

    // Ticket filters (Incident Queue)
    if (filterGroup) {
        filterGroup.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-filter]');
            if (!btn) return;
            const filter = btn.dataset.filter || 'all';
            state.ticketFilter = filter;

            const buttons = Array.from(filterGroup.querySelectorAll('button'));
            buttons.forEach(b => {
                b.className = 'px-3 py-1 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition';
            });
            btn.className = 'px-3 py-1 text-xs font-semibold rounded bg-graphite text-white transition';

            renderTickets();
        });
    }

    // Delegated row clicks (Incident Queue)
    tbody?.addEventListener('click', (e) => {
        const row = e.target.closest('tr[data-ticket-id]');
        if (row) openDrawer(row.dataset.ticketId);
    });

    // Calls controls
    callsSearchInput?.addEventListener('input', () => {
        state.callsSearch = callsSearchInput.value || '';
        if (state.activeView === 'calls') renderCalls();
    });

    callsBtnRefresh?.addEventListener('click', () => {
        refreshActiveView({ force: true }).catch((err) => warn('refresh failed', err));
    });

    callsTableBody?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-call-action]');
        if (!btn) return;
        const action = btn.dataset.callAction;
        const callId = btn.dataset.callId;
        if (action === 'transcript' && callId) {
            openCallTranscript(callId);
        }
    });

    callTranscriptClose?.addEventListener('click', closeCallTranscript);
    callTranscriptOverlay?.addEventListener('click', closeCallTranscript);

    // Escalations controls
    escalationsSearchInput?.addEventListener('input', () => {
        state.escalationsSearch = escalationsSearchInput.value || '';
        if (state.activeView === 'escalations') renderEscalations();
    });

    escalationsFilterGroup?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-filter]');
        if (!btn) return;
        state.escalationsStatus = btn.dataset.filter || 'all';

        const buttons = Array.from(escalationsFilterGroup.querySelectorAll('button'));
        buttons.forEach(b => {
            b.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition';
        });
        btn.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-graphite text-white transition';

        if (state.activeView === 'escalations') renderEscalations();
    });

    // Event Log controls
    eventLogSearchInput?.addEventListener('input', () => {
        state.eventLogSearch = eventLogSearchInput.value || '';
        if (state.activeView === 'eventlog') renderEventLog();
    });

    eventLogFilterGroup?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-type]');
        if (!btn) return;
        state.eventLogType = btn.dataset.type || 'all';

        const buttons = Array.from(eventLogFilterGroup.querySelectorAll('button'));
        buttons.forEach(b => {
            b.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition';
        });
        btn.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-graphite text-white transition';

        if (state.activeView === 'eventlog') renderEventLog();
    });

    eventLogBtnExport?.addEventListener('click', () => {
        const fileName = `grace-events-${new Date().toISOString().slice(0, 10)}.json`;
        downloadJSON(fileName, cache.events.data);
    });

    eventLogBtnRefresh?.addEventListener('click', () => {
        loadEvents('eventlog', { force: true }).catch((err) => warn('refresh failed', err));
    });

    // Staff controls
    staffSearchInput?.addEventListener('input', () => {
        state.staffSearch = staffSearchInput.value || '';
        if (state.activeView === 'staff') renderStaff();
    });

    staffFilterGroup?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-filter]');
        if (!btn) return;
        state.staffStatus = btn.dataset.filter || 'all';

        const buttons = Array.from(staffFilterGroup.querySelectorAll('button'));
        buttons.forEach(b => {
            b.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition';
        });
        btn.className = 'px-3 py-1.5 text-xs font-semibold rounded bg-graphite text-white transition';

        if (state.activeView === 'staff') renderStaff();
    });

    // Drawer bindings
    overlay?.addEventListener('click', closeDrawer);
    btnCloseDrawer?.addEventListener('click', closeDrawer);
    btnResolve?.addEventListener('click', closeDrawer);
    btnAssign?.addEventListener('click', () => alert('Assign action not implemented.'));
    btnEscalate?.addEventListener('click', () => alert('Escalate action not implemented.'));

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeDrawer();
            closeCallTranscript();
        }
    });

    // Polling: refresh active view periodically (only when visible)
    setInterval(() => {
        if (document.visibilityState === 'hidden') return;
        if (!state.activeView) return;
        refreshActiveView().catch(() => { });
    }, 8000);

    bindTabs();
});
