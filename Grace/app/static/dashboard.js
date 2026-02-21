/**
 * GRACE Dashboard - Vanilla JS Logic
 * No build tools, no React, purely operational DOM manipulation.
 */

// 1. Mock Data Source
const mockTickets = [
    { id: 'TCK-9042', customer: 'Sarah Jenkins', source: 'Telegram', subject: 'Spa booking failed', severity: 'high', status: 'Open', notes: 'System encountered API 404 while booking Spa package. Webhook intercepted.' },
    { id: 'TCK-9041', customer: 'Dr. House', source: 'Voice (Room 211)', subject: 'Water leak in bathroom', severity: 'critical', status: 'Open', notes: 'Transcript: "There is water leaking rapidly from the ceiling in the bathroom, please send maintenance immediately."' },
    { id: 'TCK-9040', customer: 'Mr. Anderson', source: 'Voice (Room 509)', subject: 'Late checkout request', severity: 'low', status: 'Resolved', notes: 'Transcript: "Hi Grace, can I stay until 2 PM?" System approved based on loyalty tier.' },
    { id: 'TCK-9039', customer: 'Emily Chen', source: 'Web Chat', subject: 'Inquiring about suite upgrade', severity: 'medium', status: 'Open', notes: 'User asking about cost delta for upgrading to Presidential Suite for 2 nights.' },
    { id: 'TCK-9038', customer: 'Anonymous', source: 'Voice (Lobby)', subject: 'Lost item inquiry', severity: 'medium', status: 'In Progress', notes: 'Guest left a black leather wallet at the main bar. Agent checking lost and found database.' },
    { id: 'TCK-9037', customer: 'John Doe', source: 'Telegram', subject: 'Cancel reservation', severity: 'high', status: 'Open', notes: 'User triggered /cancel command. Requires manual refund authorization.' },
];

const mockEvents = [
    { text: "AI handled incoming call from +971 50 *** 4567.", type: "info" },
    { text: "Telegram webhook processed `/status` command.", type: "info" },
    { text: "Grace autonomously booked Appointment #882.", type: "success" },
    { text: "PMS Database synchronization complete.", type: "success" },
    { text: "User dropped call during intent classification.", type: "warning" },
    { text: "High latency detected on OpenRouter endpoint.", type: "warning" },
    { text: "New critical ticket generated from Voice interface.", type: "alert" }
];

// 2. DOM Elements
const tbody = document.getElementById('ticket-table-body');
const drawer = document.getElementById('ticket-drawer');
const overlay = document.getElementById('drawer-overlay');
const filterGroup = document.getElementById('filter-group');
const streamContainer = document.getElementById('event-stream-container');

const btnCloseDrawer = document.getElementById('btn-close-drawer');
const btnAssign = document.getElementById('btn-assign');
const btnEscalate = document.getElementById('btn-escalate');
const btnResolve = document.getElementById('btn-resolve');

// 3. Helper Functions
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

function updateKPIs() {
    const openTickets = mockTickets.filter(t => t.status !== 'Resolved').length;
    const criticalTickets = mockTickets.filter(t => t.severity === 'critical' && t.status !== 'Resolved').length;
    document.getElementById('kpi-open-tickets').innerText = openTickets;
    document.getElementById('kpi-critical').innerText = criticalTickets;
}

// 4. Render Table
function renderTable(filter = 'all') {
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

// 5. Drawer Controls
function openDrawer(ticketId) {
    const ticket = mockTickets.find(t => t.id === ticketId);
    if (!ticket) return;

    document.getElementById('drawer-ticket-id').innerText = ticket.id;
    document.getElementById('drawer-ticket-subject').innerText = ticket.subject;
    document.getElementById('drawer-customer-name').innerText = ticket.customer;
    document.getElementById('drawer-customer-meta').innerText = `Source: ${ticket.source}`;
    document.getElementById('drawer-customer-avatar').innerText = ticket.customer.charAt(0).toUpperCase();
    document.getElementById('drawer-ticket-notes').innerText = ticket.notes;

    document.getElementById('drawer-tags').innerHTML = `
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
    drawer.classList.remove('drawer-enter');
    drawer.classList.add('drawer-exit');
    overlay.classList.remove('overlay-fade-in');
    overlay.classList.add('overlay-fade-out');
    setTimeout(() => overlay.classList.add('hidden'), 300);
}

// Bind Event Listeners
overlay.addEventListener('click', closeDrawer);
btnCloseDrawer.addEventListener('click', closeDrawer);
btnResolve.addEventListener('click', closeDrawer);
btnAssign.addEventListener('click', () => alert('Ticket assigned to your queue.'));
btnEscalate.addEventListener('click', () => alert('Ticket escalated to Level 2 Support.'));

// Delegate row clicks to tbody (avoids manual rebinding on re-render)
tbody.addEventListener('click', (e) => {
    const row = e.target.closest('tr[data-ticket-id]');
    if (row) openDrawer(row.dataset.ticketId);
});

// 6. Filtering Logic
filterGroup.addEventListener('click', (e) => {
    if (e.target.tagName !== 'BUTTON') return;

    Array.from(filterGroup.children).forEach(btn => {
        btn.className = 'px-3 py-1 text-xs font-semibold rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition';
    });
    e.target.className = 'px-3 py-1 text-xs font-semibold rounded bg-graphite text-white transition';
    renderTable(e.target.dataset.filter);
});

// 7. Event Stream Simulation
function appendStreamEvent(eventObj) {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    let borderClass = 'border-slate-200', iconColor = 'text-slate-400';
    if (eventObj.type === 'alert') { borderClass = 'border-rose-200'; iconColor = 'text-rose-500'; }
    if (eventObj.type === 'success') { borderClass = 'border-emerald-200'; iconColor = 'text-emerald-500'; }
    if (eventObj.type === 'warning') { borderClass = 'border-amber-200'; iconColor = 'text-amber-500'; }

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
    appendStreamEvent({ text: "GRACE Command Center initialized.", type: "info" });

    function triggerRandom() {
        const randomEvent = mockEvents[Math.floor(Math.random() * mockEvents.length)];
        appendStreamEvent(randomEvent);
        const nextTick = Math.floor(Math.random() * (15000 - 8000 + 1) + 8000);
        setTimeout(triggerRandom, nextTick);
    }
    setTimeout(triggerRandom, 2000);
}

// 8. Init
document.addEventListener('DOMContentLoaded', () => {
    renderTable();
    startStreamSimulation();

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDrawer();
    });
});
