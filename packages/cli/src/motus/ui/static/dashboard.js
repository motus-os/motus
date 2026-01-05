/**
 * Motus Dashboard - Command Center for AI Agents
 */

// State management
let ws;
let selectedSession = null;
let events = [];
let contexts = {};
let agentStacks = {};  // Track active agents per session
const maxEvents = 50;
let lastHeartbeatTime = null;  // Track last successful heartbeat

// Pagination state for "Load More"
let loadedOffset = 0;  // How many events we've loaded
let hasMoreEvents = false;  // Whether there are more events to load
let isLoadingMore = false;  // Prevent duplicate load_more requests
let isLoadingSession = false;  // Prevent duplicate session selection requests
let sessionHistoryTimeout = null;  // Timeout handle for session history response
const SESSION_HISTORY_TIMEOUT_MS = 5000;

// SPAWN event data storage for expand/copy
let spawnEventData = {};  // Map of spawn-id -> { prompt, context, model, agentType }

// Session filter: 'active' or 'all'
let sessionFilter = 'active';

// Filter state
let filters = {
    searchText: '',
    tools: new Set(),
    riskLevel: 'all'
};

// Persisted to localStorage
let lastSessions = [];
let selectedProject = null;

// Working Memory state (persisted to localStorage)
let workingMemoryEnabled = localStorage.getItem('motus_wm_enabled') !== 'false';
let workingMemoryCollapsed = localStorage.getItem('motus_wm_collapsed') === 'true';

// Reconnection handling
let reconnectAttempts = 0;
const maxReconnectDelay = 30000;

// ============================================================================
// Session Filter
// ============================================================================

function setSessionFilter(filter) {
    sessionFilter = filter;
    document.querySelectorAll('.filter-toggle').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === filter);
    });
    renderSessions(lastSessions);
}

// ============================================================================
// Working Memory (Agent Health Panel)
// ============================================================================

function initWorkingMemory() {
    const wm = document.getElementById('working-memory');
    if (!workingMemoryEnabled) {
        wm.classList.add('disabled');
        wm.querySelector('.working-memory-toggle').textContent = 'Enable';
    }
    if (workingMemoryCollapsed) {
        wm.classList.add('collapsed');
    }
}

function toggleWorkingMemory() {
    const wm = document.getElementById('working-memory');
    if (wm.classList.contains('disabled')) return;
    workingMemoryCollapsed = !workingMemoryCollapsed;
    wm.classList.toggle('collapsed');
    localStorage.setItem('motus_wm_collapsed', workingMemoryCollapsed);
}

function disableWorkingMemory() {
    const wm = document.getElementById('working-memory');
    const btn = wm.querySelector('.working-memory-toggle');
    workingMemoryEnabled = !workingMemoryEnabled;
    wm.classList.toggle('disabled');
    btn.textContent = workingMemoryEnabled ? 'Disable' : 'Enable';
    localStorage.setItem('motus_wm_enabled', workingMemoryEnabled);
}


function updateWorkingMemory(ctx) {
    if (!workingMemoryEnabled || !ctx) return;

    // Calculate health from context
    const health = calculateHealth(ctx);

    // Update circular progress ring
    const ringProgress = document.getElementById('health-ring-progress');
    const ringText = document.getElementById('health-ring-text');
    const wmContent = document.getElementById('wm-content');

    if (ringProgress && ringText) {
        // Calculate stroke-dashoffset based on health percentage
        // Circle circumference = 2 * π * r = 2 * π * 20 = 125.6
        const circumference = 125.6;
        const offset = circumference - (health.health / 100) * circumference;

        ringProgress.style.strokeDashoffset = offset;
        ringText.textContent = health.health + '%';

        // Add low-health pulse animation if health < 50%
        if (health.health < 50) {
            ringProgress.classList.add('low-health');
        } else {
            ringProgress.classList.remove('low-health');
        }
    }

    // Update health class for colors
    wmContent.className = `working-memory-content health-${health.status}`;

    // Update status icon and text
    const healthIcon = document.getElementById('health-status-icon');
    const healthText = document.getElementById('health-status-text');

    // Status icon and text
    const statusConfig = {
        'on_track': { icon: '🟢', text: 'On Track' },
        'exploring': { icon: '🟡', text: 'Exploring' },
        'working_through_it': { icon: '🔧', text: 'Working Through It' },
        'needs_attention': { icon: '🔴', text: 'Needs Attention' },
        'waiting': { icon: '⏳', text: 'Waiting...' }
    };
    const config = statusConfig[health.status] || statusConfig.waiting;
    if (healthIcon) healthIcon.textContent = config.icon;
    if (healthText) healthText.textContent = config.text;

    // Update goal from first decision
    const goalEl = document.getElementById('wm-goal');
    if (ctx.decisions && ctx.decisions.length > 0) {
        goalEl.textContent = ctx.decisions[ctx.decisions.length - 1];
    } else {
        goalEl.textContent = 'Waiting for task...';
    }

    // Update focus from modified files + agents
    const focusEl = document.getElementById('wm-focus');
    let focusItems = [];
    if (ctx.files_modified && ctx.files_modified.length > 0) {
        focusItems = ctx.files_modified.slice(-3).map(f => `📝 ${f}`);
    }
    if (ctx.agent_tree && ctx.agent_tree.length > 0) {
        const latestAgent = ctx.agent_tree[ctx.agent_tree.length - 1];
        focusItems.push(`🤖 ${latestAgent.type}`);
    }
    if (focusItems.length === 0 && ctx.files_read && ctx.files_read.length > 0) {
        focusItems = ctx.files_read.slice(-2).map(f => `📖 ${f}`);
    }
    if (focusItems.length === 0) {
        focusEl.innerHTML = '<span class="wm-focus-item">—</span>';
    } else {
        focusEl.innerHTML = focusItems.map(f =>
            `<span class="wm-focus-item">${escapeHtml(f)}</span>`
        ).join('');
    }
}

// Pure JavaScript health calculation (mirrors Python backend)
function calculateHealth(ctx) {
    if (!ctx) return { health: 50, status: 'waiting', metrics: {} };

    // Friction score (gentler - friction is normal)
    const frictionCount = ctx.friction_count || 0;
    const frictionScore = Math.max(0, 100 - (frictionCount * 15));

    // Activity score
    const tools = ctx.tool_count || {};
    const totalTools = Object.values(tools).reduce((a, b) => a + b, 0);
    const productive = (tools['Edit'] || 0) + (tools['Write'] || 0);
    const readHeavy = (tools['Read'] || 0) + (tools['Glob'] || 0) + (tools['Grep'] || 0);

    let activityScore = 50;
    if (totalTools === 0) {
        activityScore = 50;
    } else if (productive > 0) {
        activityScore = Math.min(100, 60 + (productive * 8));
    } else if (readHeavy > 5) {
        activityScore = 70;
    }

    // Progress score
    const filesModified = (ctx.files_modified || []).length;
    const progressScore = Math.min(100, 40 + (filesModified * 15));

    // Decision score
    const decisions = ctx.decisions || [];
    const decisionScore = Math.min(100, 50 + (decisions.length * 10));

    // Weighted health (friction matters less - it's normal)
    let health = Math.round(
        frictionScore * 0.20 +
        activityScore * 0.30 +
        progressScore * 0.30 +
        decisionScore * 0.20
    );
    health = Math.max(10, Math.min(95, health));

    // Status - use gentler language
    let status = 'waiting';
    if (frictionCount > 3) {
        status = 'working_through_it';
    } else if (health >= 75) {
        status = 'on_track';
    } else if (health >= 50) {
        status = 'exploring';
    } else {
        status = 'needs_attention';
    }

    return { health, status, metrics: { frictionScore, activityScore, progressScore, decisionScore } };
}

// ============================================================================
// Event Filters
// ============================================================================

function toggleToolFilter(tool) {
    if (filters.tools.has(tool)) {
        filters.tools.delete(tool);
        document.querySelector(`[data-tool="${tool}"]`).classList.remove('active');
    } else {
        filters.tools.add(tool);
        document.querySelector(`[data-tool="${tool}"]`).classList.add('active');
    }
    applyFilters();
}

function setRiskFilter(level) {
    filters.riskLevel = level;
    // Update UI
    document.querySelectorAll('[data-risk]').forEach(chip => {
        chip.classList.remove('active');
    });
    document.querySelector(`[data-risk="${level}"]`).classList.add('active');
    applyFilters();
}

function clearAllFilters() {
    filters.searchText = '';
    filters.tools.clear();
    filters.riskLevel = 'all';
    // Update UI
    document.getElementById('search-filter').value = '';
    document.querySelectorAll('[data-tool]').forEach(chip => {
        chip.classList.remove('active');
    });
    document.querySelectorAll('[data-risk]').forEach(chip => {
        chip.classList.remove('active');
    });
    document.querySelector('[data-risk="all"]').classList.add('active');
    applyFilters();
}

function applyFilters() {
    // Update search text from input
    filters.searchText = document.getElementById('search-filter').value.toLowerCase();
    renderFeed();
}

function eventPassesFilters(e) {
    // Session filter - when a session is selected, only show its events
    if (selectedSession && e.session_id !== selectedSession) {
        return false;
    }

    // Text search filter
    if (filters.searchText) {
        const content = (e.content || '').toLowerCase();
        const toolName = (e.tool_name || '').toLowerCase();
        const searchMatch = content.includes(filters.searchText) ||
                          toolName.includes(filters.searchText);
        if (!searchMatch) return false;
    }

    // Tool filter
    if (filters.tools.size > 0) {
        let eventTool = e.tool_name || '';
        if (e.event_type === 'thinking') eventTool = 'THINK';
        if (e.event_type === 'spawn') eventTool = 'SPAWN';

        if (!filters.tools.has(eventTool)) return false;
    }

    // Risk level filter
    if (filters.riskLevel !== 'all') {
        const riskLevel = e.risk_level || 'safe';
        if (filters.riskLevel === 'safe' && riskLevel !== 'safe') return false;
        if (filters.riskLevel === 'medium' && riskLevel !== 'medium') return false;
        if (filters.riskLevel === 'high' && !['high', 'critical'].includes(riskLevel)) return false;
    }

    return true;
}

// ============================================================================
// WebSocket Connection
// ============================================================================

function connect() {
    const port = window.location.port || '8765';
    ws = new WebSocket(`ws://localhost:${port}/ws`);

    ws.onopen = () => {
        document.getElementById('status-dot').classList.remove('disconnected');
        lastHeartbeatTime = Date.now();
        updateConnectionStatus();
        reconnectAttempts = 0;
        // Clear events on reconnect to avoid duplicates, then request fresh backfill
        events = [];
        contexts = {};
        spawnEventData = {};  // Clear spawn data on reconnect to prevent memory leak
        ws.send(JSON.stringify({ type: 'request_backfill', limit: 30 }));
    };

    ws.onclose = () => {
        document.getElementById('status-dot').classList.add('disconnected');
        lastHeartbeatTime = null;
        reconnectAttempts++;
        if (sessionHistoryTimeout) {
            clearTimeout(sessionHistoryTimeout);
            sessionHistoryTimeout = null;
        }
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay);
        if (reconnectAttempts > 5) {
            document.getElementById('status-text').textContent = 'Server offline. Run: motus web';
        } else {
            document.getElementById('status-text').textContent = `Reconnecting in ${Math.round(delay/1000)}s...`;
        }
        setTimeout(connect, delay);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (reconnectAttempts > 3) {
            document.getElementById('status-text').textContent = 'Server offline. Run: motus web';
        } else {
            document.getElementById('status-text').textContent = 'Connection error';
        }
    };

    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        handleMessage(data);
    };
}

function handleMessage(data) {
    // Update heartbeat time on any message
    lastHeartbeatTime = Date.now();

    if (data.type === 'sessions') {
        lastSessions = data.sessions;  // Store sessions for persistence
        renderSessions(data.sessions);
    } else if (data.type === 'backfill') {
        // Load historical events on connect/refresh
        if (data.events && data.events.length > 0) {
            events = data.events.concat(events);
            events = events.slice(0, maxEvents); // Keep within limit
            renderFeed();
            document.getElementById('status-text').textContent = 'Connected (backfilled)';
        }
    } else if (data.type === 'session_history') {
        if (sessionHistoryTimeout) {
            clearTimeout(sessionHistoryTimeout);
            sessionHistoryTimeout = null;
        }
        // Session history loaded (initial load or "load more")
        const newEvents = data.events || [];
        const offset = data.offset || 0;
        hasMoreEvents = data.has_more || false;
        isLoadingMore = false;
        isLoadingSession = false;  // Clear loading state

        if (offset > 0) {
            // "Load more" response - prepend older events to the beginning
            // events array is newest-first; older events should append to the end
            events = [...events, ...newEvents];
        } else {
            // Initial load - replace events array
            events = newEvents;
        }

        // Update loaded offset for next "load more"
        loadedOffset = events.length;

        renderFeed();

        // Scroll behavior depends on whether this is initial load or "load more"
        // Use requestAnimationFrame to ensure scroll happens AFTER browser paint
        const feedContainer = document.getElementById('feed').parentElement;
        if (feedContainer && offset === 0) {
            // Initial load: scroll to TOP to show newest events first
            // Defer until after DOM reflow/paint to avoid jittery scroll
            requestAnimationFrame(() => {
                feedContainer.scrollTop = 0;
            });
        }
        // For "load more" (offset > 0): don't scroll - user is browsing history

        // Update status text
        if (events.length > 0) {
            const totalText = hasMoreEvents
                ? `Loaded ${events.length} events (more available)`
                : `Loaded ${events.length} events`;
            document.getElementById('status-text').textContent = totalText;
        } else {
            document.getElementById('status-text').textContent = 'No events in session';
        }
    } else if (data.type === 'batch_events') {
        // Handle batched events (performance optimization)
        if (data.events && data.events.length > 0) {
            data.events.forEach(event => addEvent(event));
        }
    } else if (data.type === 'event') {
        addEvent(data.event);
    } else if (data.type === 'context') {
        contexts[data.session_id] = data.context;
        if (selectedSession === data.session_id || !selectedSession) {
            renderContext(data.context);
            updateWorkingMemory(data.context);
        }
    } else if (data.type === 'error') {
        // Handle server-side errors
        console.error('Server error:', data.message);
        document.getElementById('status-text').textContent = `Error: ${data.message}`;
        // Clear loading states
        isLoadingSession = false;
        isLoadingMore = false;
        // Clear loading state if we were waiting for this session
        if (selectedSession === data.session_id) {
            const container = document.getElementById('feed');
            container.innerHTML = `<div class="empty-state">${data.message}</div>`;
        }
    }
}

// ============================================================================
// Session Management
// ============================================================================

function renderSessions(sessions) {
    const container = document.getElementById('sessions');

    // Filter sessions based on toggle
    // "active" filter shows active + open + crashed (excludes orphaned)
    let filteredSessions = sessions;
    if (sessionFilter === 'active') {
        filteredSessions = sessions.filter(s =>
            s.status === 'active' || s.status === 'open' || s.status === 'crashed'
        );
    }

    // Store session timestamps for live updates (using parseTimestamp for NaN safety)
    filteredSessions.forEach(s => {
        if (s.last_event_time) {
            s._lastEventTimestamp = parseTimestamp(s.last_event_time);
        }
    });

    // Add "All Sessions" option at top
    let html = `
        <div class="all-sessions ${!selectedSession ? 'active' : ''}"
             onclick="selectAllSessions()">
            📡 All Sessions (${filteredSessions.length})
        </div>
    `;

    // Session list with status indicator
    html += filteredSessions.map(s => {
        // Map status to CSS class
        const statusClass = 'status-' + (s.status || 'orphaned');
        // Status label and last active time
        let statusLabel = '';
        if (s.status === 'open') statusLabel = '<div class="session-age">open</div>';
        else if (s.status === 'crashed') statusLabel = '<div class="session-age" style="color:#ef4444">crashed</div>';
        else if (s.status === 'orphaned') statusLabel = '<div class="session-age">ended</div>';

        // Add last active time
        let lastActiveLabel = '';
        if (s._lastEventTimestamp) {
            const elapsed = formatTimeAgo(s._lastEventTimestamp);
            lastActiveLabel = `<div class="session-last-active" data-timestamp="${s._lastEventTimestamp}">active ${elapsed}</div>`;
        }

        // Source badge (CLU=Claude, COD=Codex, GEM=Gemini, SDK=SDK)
        const source = s.source || 'claude';
        const sourceColors = {
            claude: '#a855f7',  // purple
            codex: '#22c55e',   // green
            gemini: '#3b82f6',  // blue
            sdk: '#eab308',     // yellow
        };
        const sourceColor = sourceColors[source] || '#6b7280';
        const sourceBadge = `<span class="source-badge" style="color:${sourceColor}">${escapeHtml(source.slice(0, 3).toUpperCase())}</span>`;

        return `
            <div class="session-item ${selectedSession === s.session_id ? 'active' : ''}"
                 onclick="selectSession('${escapeHtml(s.session_id)}', '${escapeHtml(s.project_path)}')">
                <span class="session-status ${statusClass}"></span>
                ${sourceBadge}
                <span class="session-id">${escapeHtml(s.session_id.slice(0, 8))}</span>
                <div class="session-project">${escapeHtml(s.project_path.split('/').pop())}</div>
                ${statusLabel}
                ${lastActiveLabel}
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

function selectSession(id, projectPath) {
    // Prevent duplicate requests while loading
    if (isLoadingSession) {
        return;
    }

    selectedSession = id;
    selectedProject = projectPath;

    // Reset pagination state for new session
    loadedOffset = 0;
    hasMoreEvents = false;
    isLoadingMore = false;
    isLoadingSession = true;

    // Clear spawn event data to prevent memory leak (can grow to 150MB+)
    spawnEventData = {};

    renderSessions(lastSessions);
    updateBreadcrumbs();
    updateExportButton();

    // Show loading state while fetching session history
    const container = document.getElementById('feed');
    container.innerHTML = '<div class="empty-state">Loading session history...</div>';
    document.getElementById('status-text').textContent = 'Loading...';

    if (contexts[id]) renderContext(contexts[id]);

    // Request full session history - renderFeed will be called when data arrives
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'select_session', session_id: id }));
        if (sessionHistoryTimeout) {
            clearTimeout(sessionHistoryTimeout);
        }
        sessionHistoryTimeout = setTimeout(() => {
            if (!isLoadingSession) {
                return;
            }
            isLoadingSession = false;
            isLoadingMore = false;
            container.innerHTML = '<div class="empty-state">Session history unavailable. Run "motus doctor" for diagnostics.</div>';
            document.getElementById('status-text').textContent = 'Session history unavailable';
        }, SESSION_HISTORY_TIMEOUT_MS);
    } else {
        // WebSocket not ready - clear loading state
        isLoadingSession = false;
        container.innerHTML = '<div class="empty-state">WebSocket disconnected. Reconnecting...</div>';
    }
}

function selectAllSessions() {
    selectedSession = null;
    selectedProject = null;

    // Clear spawn event data to prevent memory leak
    spawnEventData = {};

    renderSessions(lastSessions);
    updateBreadcrumbs();
    updateExportButton();
    renderFeed();  // Re-render feed to show all sessions
    renderContext(null);
}

function updateBreadcrumbs() {
    const container = document.getElementById('breadcrumbs');
    if (!selectedSession) {
        container.innerHTML = '<span class="breadcrumb active">All Sessions</span>';
    } else {
        const projectName = selectedProject ? selectedProject.split('/').pop() : 'Unknown';
        container.innerHTML = `
            <span class="breadcrumb" onclick="selectAllSessions()" style="cursor:pointer">All Sessions</span>
            <span class="breadcrumb-sep">›</span>
            <span class="breadcrumb-project">${escapeHtml(projectName)}</span>
            <span class="breadcrumb-sep">›</span>
            <span class="breadcrumb-session">${selectedSession.slice(0, 8)}</span>
        `;
    }
}

// ============================================================================
// Event Feed
// ============================================================================

function addEvent(event) {
    // Store timestamp for relative time display (using parseTimestamp for NaN safety)
    if (event.timestamp) {
        event._timestamp = parseTimestamp(event.timestamp);
    }

    // Mark new high-risk events for flash animation
    if (event.risk_level === 'high' || event.risk_level === 'critical') {
        event._isNew = true;
    }

    events.unshift(event);
    if (events.length > maxEvents) events.pop();

    // Auto-scroll if user is near the top (within 200px)
    const feedContainer = document.getElementById('feed').parentElement;
    const shouldScroll = feedContainer && feedContainer.scrollTop < 200;

    renderFeed();

    // Smooth scroll to top if near the top
    if (shouldScroll && feedContainer) {
        feedContainer.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function renderFeed() {
    const container = document.getElementById('feed');
    const resultsCounter = document.getElementById('results-count');

    if (events.length === 0) {
        container.innerHTML = '<div class="empty-state">Waiting for events...</div>';
        resultsCounter.innerHTML = '';
        return;
    }

    // Apply filters
    const filteredEvents = events.filter(eventPassesFilters);

    // Get previous count for animation
    const countEl = resultsCounter?.querySelector('.count');
    const previousCount = countEl ? parseInt(countEl.textContent) || 0 : 0;
    const currentCount = filteredEvents.length;

    // Update results count
    const activeFiltersCount = filters.tools.size + (filters.searchText ? 1 : 0) + (filters.riskLevel !== 'all' ? 1 : 0);
    if (activeFiltersCount > 0) {
        resultsCounter.innerHTML = `<span class="count">${filteredEvents.length}</span> of ${events.length} events`;
    } else {
        resultsCounter.innerHTML = `<span class="count">${filteredEvents.length}</span> events`;
    }

    // Animate count change
    if (currentCount !== previousCount) {
        const newCountEl = resultsCounter?.querySelector('.count');
        if (newCountEl) {
            newCountEl.classList.add('count-updated');
            setTimeout(() => newCountEl.classList.remove('count-updated'), 300);
        }
    }

    if (filteredEvents.length === 0) {
        container.innerHTML = '<div class="empty-state">No events match the current filters</div>';
        return;
    }

    // Group events by sub-agent sessions
    const groupedEvents = groupEventsBySubAgent(filteredEvents);

    // Build HTML with optional "Load More" button at the top
    let html = '';
    if (hasMoreEvents && selectedSession && !isLoadingMore) {
        html += `
            <div class="load-more-container">
                <button class="load-more-btn" onclick="loadMoreEvents()">
                    Load Older Events
                </button>
            </div>
        `;
    } else if (isLoadingMore) {
        html += `
            <div class="load-more-container">
                <span class="load-more-loading">Loading...</span>
            </div>
        `;
    }

    html += renderEventGroups(groupedEvents);
    container.innerHTML = html;

    // Remove new-event class after animation completes
    setTimeout(() => {
        events.forEach(e => {
            if (e._isNew) {
                delete e._isNew;
            }
        });
    }, 1500);
}

// Load more historical events for pagination
function loadMoreEvents() {
    if (!selectedSession || !hasMoreEvents || isLoadingMore) return;

    isLoadingMore = true;
    renderFeed();  // Show loading state

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'load_more',
            session_id: selectedSession,
            offset: loadedOffset
        }));
    }
}

// Group events into sub-agent sessions
function groupEventsBySubAgent(events) {
    const groups = [];
    let currentGroup = null;

    for (let i = 0; i < events.length; i++) {
        const e = events[i];
        const depth = e.agent_depth || 0;

        if (e.event_type === 'spawn' && depth === 1) {
            // Start new sub-agent group
            if (currentGroup) {
                groups.push(currentGroup);
            }
            currentGroup = {
                type: 'subagent',
                spawnEvent: e,
                events: [],
                agentType: e.agent_type,
                collapsed: false
            };
        } else if (currentGroup && depth > 0) {
            // Add event to current sub-agent group
            currentGroup.events.push(e);
        } else {
            // Main agent event - close any open group and add as standalone
            if (currentGroup) {
                groups.push(currentGroup);
                currentGroup = null;
            }
            groups.push({ type: 'standalone', event: e });
        }
    }

    // Close any remaining group
    if (currentGroup) {
        groups.push(currentGroup);
    }

    return groups;
}

// Render tool result event
function renderToolResult(e, idx) {
    const content = e.content || e.tool_output || '';
    const fullContent = e.raw_data?.full_content || content;
    const toolUseId = e.raw_data?.tool_use_id || '';
    const eventId = String(e.event_id || idx).replace(/[^a-zA-Z0-9_-]/g, '');

    const hasMore = fullContent.length > 500;
    const preview = hasMore ? escapeHtml(content.substring(0, 500)) + '...' : escapeHtml(content);

    // Store timestamp for live updates (using parseTimestamp for NaN safety)
    const timestampMs = e._timestamp || parseTimestamp(e.timestamp);
    const relativeTime = formatTimeAgo(timestampMs);

    // Source badge for events (Claude/Codex/Gemini/SDK)
    let sourceBadge = '';
    if (e.source) {
        const sourceColors = {
            claude: '#a855f7',  // purple
            codex: '#22c55e',   // green
            gemini: '#3b82f6',  // blue
            sdk: '#eab308',     // yellow
        };
        const sourceColor = sourceColors[e.source] || '#6b7280';
        const sourceLabel = e.source.slice(0, 3).toUpperCase();
        sourceBadge = `<span class="event-source-badge" style="color:${sourceColor};font-size:10px;font-weight:600;opacity:0.8;">${escapeHtml(sourceLabel)}</span>`;
    }

    return `
        <div class="event tool-result" data-tool-use-id="${escapeHtml(toolUseId)}" data-idx="${idx}">
            <div class="event-header">
                <span class="event-time" data-timestamp="${timestampMs}">${relativeTime}</span>
                ${sourceBadge}
                <span class="event-badge badge-result">📤 RESULT</span>
                <span class="result-size">${fullContent.length} chars</span>
                <span class="session-id">${escapeHtml((e.session_id || '').slice(0, 6))}</span>
            </div>
            <div class="event-content">
                <pre class="tool-output" id="result-preview-${eventId}">${preview}</pre>
                ${hasMore ? `
                    <pre class="tool-output-full" id="result-full-${eventId}" style="display:none">${escapeHtml(fullContent)}</pre>
                    <button class="expand-btn" onclick="event.stopPropagation(); toggleToolResult('${eventId}')">
                        Show full output
                    </button>
                ` : ''}
            </div>
        </div>
    `;
}

function toggleToolResult(eventId) {
    const preview = document.getElementById('result-preview-' + eventId);
    const full = document.getElementById('result-full-' + eventId);
    const btn = event.target;

    if (full && preview && btn) {
        if (full.style.display === 'none') {
            preview.style.display = 'none';
            full.style.display = 'block';
            btn.textContent = 'Show preview';
        } else {
            preview.style.display = 'block';
            full.style.display = 'none';
            btn.textContent = 'Show full output';
        }
    }
}

// Render grouped events
function renderEventGroups(groups) {
    return groups.map((group, groupIdx) => {
        if (group.type === 'standalone') {
            return renderEvent(group.event, groupIdx, false);
        } else {
            // Render sub-agent group with collapsible container
            const agentType = group.agentType || 'Agent';
            const lowerType = agentType.toLowerCase();
            let icon = '⚡';
            let typeClass = 'agent-general';
            if (lowerType.includes('explore')) {
                icon = '🔍';
                typeClass = 'agent-explore';
            } else if (lowerType.includes('plan')) {
                icon = '📋';
                typeClass = 'agent-plan';
            }

            const eventCount = group.events.length;
            const thinkCount = group.events.filter(e => e.event_type === 'thinking').length;
            const toolCount = group.events.filter(e => e.tool_name && e.event_type !== 'thinking').length;

            return `
                <div class="subagent-group ${typeClass}" data-group="${groupIdx}">
                    <div class="subagent-header" onclick="toggleSubagentGroup(${groupIdx})">
                        <span class="collapse-icon">▼</span>
                        <span class="subagent-badge">${icon} ${escapeHtml(agentType)}</span>
                        <span class="subagent-desc">${escapeHtml(group.spawnEvent.content || '')}</span>
                        <span class="subagent-count">${eventCount} events (${thinkCount} thoughts, ${toolCount} actions)</span>
                    </div>
                    <div class="subagent-events">
                        ${renderEvent(group.spawnEvent, groupIdx + '-spawn', true)}
                        ${group.events.map((e, idx) => renderEvent(e, `${groupIdx}-${idx}`, true)).join('')}
                    </div>
                </div>
            `;
        }
    }).join('');
}

// Render individual event
function renderEvent(e, idx, isInGroup) {
    // Handle tool_result events
    if (e.event_type === 'tool_result') {
        return renderToolResult(e, idx);
    }

    let badgeClass = 'badge-tool';
    let badge = e.tool_name || 'EVENT';
    let eventTypeClass = 'event-tool';
    let depthClass = '';
    let threadClass = '';
    let agentTypeClass = '';

    // Determine event type and color
    if (e.event_type === 'thinking') {
        badgeClass = 'badge-think';
        badge = 'THINK';
        eventTypeClass = 'event-think';
    } else if (e.event_type === 'spawn') {
        badgeClass = 'badge-spawn';
        badge = 'SPAWN';
        eventTypeClass = 'event-spawn';
    } else if (e.risk_level === 'high' || e.risk_level === 'critical') {
        badgeClass = 'badge-high';
        eventTypeClass = 'event-high';
    } else if (e.tool_name === 'Read' || e.tool_name === 'Glob' || e.tool_name === 'Grep') {
        eventTypeClass = 'event-read';
    } else if (e.tool_name === 'Write' || e.tool_name === 'Edit') {
        eventTypeClass = 'event-write';
    } else if (e.tool_name === 'Bash') {
        eventTypeClass = 'event-bash';
    }

    // Apply depth for sub-agents (only when NOT in group, as group provides structure)
    const depth = e.agent_depth || 0;
    if (depth > 0 && !isInGroup) {
        depthClass = 'depth-' + Math.min(depth, 3);
        threadClass = 'event-thread';
    }

    // Agent type specific styling
    if (e.agent_type) {
        const lowerType = e.agent_type.toLowerCase();
        if (lowerType.includes('explore')) {
            agentTypeClass = 'agent-explore';
        } else if (lowerType.includes('plan')) {
            agentTypeClass = 'agent-plan';
        } else {
            agentTypeClass = 'agent-general';
        }
    }

    // Agent badge with icon (only for sub-agents when NOT in group)
    let agentBadge = '';
    if (depth > 0 && e.agent_type && !isInGroup) {
        const lowerType = e.agent_type.toLowerCase();
        let icon = '⚡';
        if (lowerType.includes('explore')) icon = '🔍';
        else if (lowerType.includes('plan')) icon = '📋';
        agentBadge = `<span class="event-badge badge-spawn" style="font-size:10px;padding:1px 6px;">${icon} ${escapeHtml(e.agent_type)}</span>`;
    }

    // Error highlighting
    let errorClass = '';
    let errorBadge = '';
    if (e.has_error) {
        errorClass = 'event-error';
        errorBadge = '<span class="event-badge badge-high" style="font-size:10px;padding:1px 6px;">⚠ ERROR</span>';
    }

    // Source badge for events (Claude/Codex/Gemini/SDK)
    let sourceBadge = '';
    if (e.source) {
        const sourceColors = {
            claude: '#a855f7',  // purple
            codex: '#22c55e',   // green
            gemini: '#3b82f6',  // blue
            sdk: '#eab308',     // yellow
        };
        const sourceColor = sourceColors[e.source] || '#6b7280';
        const sourceLabel = e.source.slice(0, 3).toUpperCase();
        sourceBadge = `<span class="event-source-badge" style="color:${sourceColor};font-size:10px;font-weight:600;opacity:0.8;">${escapeHtml(sourceLabel)}</span>`;
    }

    // Model badge for SPAWN events
    let modelBadge = '';
    if (e.event_type === 'spawn' && e.model) {
        const modelLabel = e.model.includes('haiku') ? 'haiku' : e.model.includes('sonnet') ? 'sonnet' : e.model.includes('opus') ? 'opus' : e.model.slice(0, 8);
        modelBadge = `<span class="event-model-badge" style="font-size:9px;padding:1px 5px;background:rgba(171,69,192,0.2);border-radius:3px;color:#d1d5db;">${escapeHtml(modelLabel)}</span>`;
    }

    // Highlight THINK events in sub-agents
    let thinkHighlight = '';
    if (e.event_type === 'thinking' && depth > 0 && isInGroup) {
        thinkHighlight = 'subagent-think';
    }

    // Build expandable detail section for all event types
    let detailRows = [];
    if (e.file_path) detailRows.push(`<div class="detail-row"><span class="detail-label">Path:</span><span class="detail-value">${escapeHtml(e.file_path)}</span></div>`);
    if (e.tool_name) detailRows.push(`<div class="detail-row"><span class="detail-label">Tool:</span><span class="detail-value">${escapeHtml(e.tool_name)}</span></div>`);
    if (e.risk_level && e.risk_level !== 'safe') detailRows.push(`<div class="detail-row"><span class="detail-label">Risk:</span><span class="detail-value">${escapeHtml(e.risk_level)}</span></div>`);
    if (e.agent_type) detailRows.push(`<div class="detail-row"><span class="detail-label">Agent:</span><span class="detail-value">${escapeHtml(e.agent_type)} (depth ${depth})</span></div>`);
    if (e.event_type === 'spawn' && e.description) detailRows.push(`<div class="detail-row"><span class="detail-label">Task:</span><span class="detail-value">${escapeHtml(e.description)}</span></div>`);
    if (e.event_type === 'spawn' && e.model) detailRows.push(`<div class="detail-row"><span class="detail-label">Model:</span><span class="detail-value">${escapeHtml(e.model)}</span></div>`);

    // SPAWN events: generate unique ID and store data for expand/copy
    let spawnId = null;
    if (e.event_type === 'spawn') {
        // Generate a safe ID (strip anything except alnum, dash, underscore)
        const rawSpawnId = `spawn-${e.session_id?.slice(0,8) || 'x'}-${e.timestamp?.replace(/[^0-9]/g, '') || Date.now()}-${idx}`;
        spawnId = rawSpawnId.replace(/[^a-zA-Z0-9_-]/g, '');
        spawnEventData[spawnId] = {
            prompt: e.prompt || '',
            context: e.context || '',
            model: e.model || '',
            agentType: e.agent_type || '',
            description: e.description || ''
        };
    }

    // SPAWN events: add full prompt with expand/copy
    if (e.event_type === 'spawn' && e.prompt) {
        const promptPreview = escapeHtml(e.prompt.substring(0, 100));
        const hasMore = e.prompt.length > 100;
        detailRows.push(`
            <div class="detail-row spawn-prompt-row">
                <span class="detail-label">Prompt:</span>
                <div class="spawn-prompt-container">
                    <div class="spawn-prompt-preview" id="prompt-${spawnId}">${promptPreview}${hasMore ? '...' : ''}</div>
                    <div class="spawn-prompt-actions">
                        ${hasMore ? `<button class="spawn-expand-btn" onclick="event.stopPropagation(); toggleSpawnPrompt('${spawnId}')">Show Full</button>` : ''}
                        <button class="spawn-copy-btn" onclick="event.stopPropagation(); copySpawnText('${spawnId}', 'prompt')">Copy</button>
                    </div>
                </div>
            </div>
        `);
    }

    // SPAWN events: add full context with expand/copy (if available)
    if (e.event_type === 'spawn' && e.context) {
        const contextPreview = escapeHtml(e.context.substring(0, 100));
        const hasMore = e.context.length > 100;
        detailRows.push(`
            <div class="detail-row spawn-context-row">
                <span class="detail-label">Context:</span>
                <div class="spawn-context-container">
                    <div class="spawn-context-preview" id="context-${spawnId}">${contextPreview}${hasMore ? '...' : ''}</div>
                    <div class="spawn-context-actions">
                        ${hasMore ? `<button class="spawn-expand-btn" onclick="event.stopPropagation(); toggleSpawnContext('${spawnId}')">Show Full</button>` : ''}
                        <button class="spawn-copy-btn" onclick="event.stopPropagation(); copySpawnText('${spawnId}', 'context')">Copy</button>
                    </div>
                </div>
            </div>
        `);
    }

    detailRows.push(`<div class="detail-row"><span class="detail-label">Session:</span><span class="detail-value">${escapeHtml(e.session_id || 'unknown')}</span></div>`);

    let detailSection = detailRows.length > 1 ? `<div class="event-detail">${detailRows.join('')}</div>` : '';
    let hasDetails = detailSection !== '';

    // Store timestamp for live updates (using parseTimestamp for NaN safety)
    const timestampMs = e._timestamp || parseTimestamp(e.timestamp);
    const relativeTime = formatTimeAgo(timestampMs);

    // Add new-event class for risk flash animation
    const newEventClass = e._isNew ? 'new-event' : '';

    // Render expandable content with collapse/expand functionality
    let contentSection = '';
    const safeEventId = `event-${e.event_id.replace(/[^a-zA-Z0-9_-]/g, '')}`;

    if (e.full_content && e.full_content.length > 0) {
        // Has expandable content
        const preview = e.content || '';
        const fullContent = e.full_content;
        const charCount = fullContent.length;

        contentSection = `
            <div class="event-content expandable-content">
                <div class="content-preview" id="content-preview-${safeEventId}">${escapeHtml(preview)}</div>
                <div class="content-full" id="content-full-${safeEventId}" style="display:none;">${escapeHtml(fullContent)}</div>
                <button class="expand-btn" id="content-btn-${safeEventId}" onclick="event.stopPropagation(); toggleContentExpand('${safeEventId}')">
                    <span class="expand-icon">▶</span> Show full (${charCount} chars)
                </button>
            </div>
        `;
    } else {
        // Regular content (no expansion needed)
        contentSection = `<div class="event-content">${escapeHtml(e.content || '')}</div>`;
    }

    return `
        <div class="event ${hasDetails ? 'event-expandable' : ''} ${eventTypeClass} ${depthClass} ${threadClass} ${agentTypeClass} ${errorClass} ${thinkHighlight} ${newEventClass}" ${hasDetails ? 'onclick="toggleEventExpand(this)"' : ''} data-idx="${idx}">
            <div class="event-header">
                <span class="event-time" data-timestamp="${timestampMs}">${relativeTime}</span>
                ${sourceBadge}
                ${agentBadge}
                ${errorBadge}
                <span class="event-badge ${badgeClass}">${escapeHtml(badge)}</span>
                ${modelBadge}
                <span class="session-id">${escapeHtml((e.session_id || '').slice(0, 6))}</span>
                ${hasDetails ? '<span class="expand-icon">▶</span>' : ''}
            </div>
            ${contentSection}
            ${detailSection}
        </div>
    `;
}

// ============================================================================
// Context Panel
// ============================================================================

function renderContext(ctx) {
    const container = document.getElementById('context');
    if (!ctx) {
        container.innerHTML = '<div class="empty-state">No context yet</div>';
        return;
    }
    let html = '';

    // FRICTION COUNT AT TOP (if any - but it's normal)
    if (ctx.friction_count && ctx.friction_count > 0) {
        html += `<div class="context-section">
            <div class="context-label" style="color:#f59e0b;">🔧 Friction (${ctx.friction_count})</div>
            <div class="context-item" style="border-left: 3px solid #f59e0b; background: rgba(245,158,11,0.1);">
                Working through ${ctx.friction_count} challenge${ctx.friction_count > 1 ? 's' : ''}
            </div>
        </div>`;
    }

    // TOOLS SECOND (most useful for understanding agent behavior)
    if (ctx.tool_count && Object.keys(ctx.tool_count).length) {
        const maxCount = Math.max(...Object.values(ctx.tool_count));
        const totalTools = Object.values(ctx.tool_count).reduce((a, b) => a + b, 0);
        html += `<div class="context-section">
            <div class="context-label">📊 Tools (${totalTools} calls)</div>
            ${Object.entries(ctx.tool_count).sort((a,b) => b[1] - a[1]).slice(0, 8).map(([tool, count]) => `
                <div class="context-item tool-stat">
                    <span>${escapeHtml(tool)}</span>
                    <div style="display:flex;align-items:center">
                        <div class="tool-bar" style="width:${(count/maxCount)*60}px"></div>
                        <span style="margin-left:8px;color:#6b7280">${count}</span>
                    </div>
                </div>
            `).join('')}
        </div>`;
    }

    // Decisions (AI reasoning trail)
    if (ctx.decisions && ctx.decisions.length) {
        html += `<div class="context-section">
            <div class="context-label">💡 Decisions</div>
            ${ctx.decisions.map(d => `<div class="context-item" style="border-left: 2px solid #f59e0b;">→ ${escapeHtml(d)}</div>`).join('')}
        </div>`;
    }

    // Agent Tree Visualization
    if (ctx.agent_tree && ctx.agent_tree.length) {
        html += `<div class="context-section">
            <div class="context-label">🤖 Agent Tree (${ctx.agent_tree.length})</div>
            <div class="agent-tree-container">
                ${renderAgentTree(ctx.agent_tree)}
            </div>
        </div>`;
    }

    // Files Modified (important changes)
    if (ctx.files_modified && ctx.files_modified.length) {
        html += `<div class="context-section">
            <div class="context-label">✏️ Modified (${ctx.files_modified.length})</div>
            ${ctx.files_modified.map(f => `<div class="context-item file-modified">${escapeHtml(f)}</div>`).join('')}
        </div>`;
    }

    // Files Read (context gathering)
    if (ctx.files_read && ctx.files_read.length) {
        html += `<div class="context-section">
            <div class="context-label">📖 Files Read (${ctx.files_read.length})</div>
            ${ctx.files_read.slice(0, 8).map(f => `<div class="context-item file-read">${escapeHtml(f)}</div>`).join('')}
            ${ctx.files_read.length > 8 ? `<div class="context-item" style="opacity:0.6">+${ctx.files_read.length - 8} more</div>` : ''}
        </div>`;
    }

    container.innerHTML = html || '<div class="empty-state">Collecting context...</div>';
}

function renderAgentTree(agentTree) {
    if (!agentTree || agentTree.length === 0) return '';

    // Determine agent type class and icon
    function getAgentStyle(type) {
        const lowerType = (type || '').toLowerCase();
        if (lowerType.includes('explore')) {
            return { class: 'agent-node-type-explore', icon: '🔍', color: 'Explore' };
        } else if (lowerType.includes('plan')) {
            return { class: 'agent-node-type-plan', icon: '📋', color: 'Plan' };
        } else {
            return { class: 'agent-node-type-general', icon: '⚡', color: 'Agent' };
        }
    }

    return agentTree.map((agent, idx) => {
        const style = getAgentStyle(agent.type);
        const isActive = idx === agentTree.length - 1;
        const statusClass = isActive ? 'active' : 'completed';
        const statusBadge = isActive ?
            '<span class="agent-status-badge agent-status-active">Active</span>' :
            '<span class="agent-status-badge agent-status-completed">Completed</span>';

        return `
            <div class="agent-node ${style.class} ${statusClass}">
                <div class="agent-node-label">
                    ${style.icon} ${agent.type}
                    ${statusBadge}
                </div>
                <div class="agent-node-desc">${escapeHtml(agent.desc)}</div>
                ${agent.prompt ? `<div class="agent-node-desc" style="margin-top:4px;opacity:0.7">${escapeHtml(agent.prompt.slice(0, 80))}...</div>` : ''}
            </div>
        `;
    }).join('');
}

// ============================================================================
// Utilities
// ============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleEventExpand(element) {
    element.classList.toggle('expanded');
}

// Toggle content expansion for long content
function toggleContentExpand(eventId) {
    const preview = document.getElementById(`content-preview-${eventId}`);
    const full = document.getElementById(`content-full-${eventId}`);
    const btn = document.getElementById(`content-btn-${eventId}`);

    if (!preview || !full || !btn) return;

    if (full.style.display === 'none') {
        preview.style.display = 'none';
        full.style.display = 'block';
        btn.innerHTML = '<span class="expand-icon">▼</span> Collapse';
    } else {
        preview.style.display = 'block';
        full.style.display = 'none';
        btn.innerHTML = `<span class="expand-icon">▶</span> Show full`;
    }
}

function toggleSubagentGroup(groupIdx) {
    const group = document.querySelector(`[data-group="${groupIdx}"]`);
    if (group) {
        group.classList.toggle('collapsed');
    }
}

// ============================================================================
// SPAWN Prompt/Context Expand and Copy
// ============================================================================

function toggleSpawnPrompt(spawnId) {
    const el = document.getElementById(`prompt-${spawnId}`);
    const btn = el?.parentElement?.querySelector('.spawn-expand-btn');

    if (!el || !btn) return;

    // Get the stored data
    const eventData = spawnEventData[spawnId];
    if (!eventData || !eventData.prompt) return;

    // Toggle between preview and full
    if (el.classList.contains('expanded')) {
        const promptPreview = escapeHtml(eventData.prompt.substring(0, 100));
        el.textContent = promptPreview + (eventData.prompt.length > 100 ? '...' : '');
        el.classList.remove('expanded');
        btn.textContent = 'Show Full';
    } else {
        el.textContent = escapeHtml(eventData.prompt);
        el.classList.add('expanded');
        btn.textContent = 'Show Less';
    }
}

function toggleSpawnContext(spawnId) {
    const el = document.getElementById(`context-${spawnId}`);
    const btn = el?.parentElement?.querySelector('.spawn-expand-btn');

    if (!el || !btn) return;

    // Get the stored data
    const eventData = spawnEventData[spawnId];
    if (!eventData || !eventData.context) return;

    // Toggle between preview and full
    if (el.classList.contains('expanded')) {
        const contextPreview = escapeHtml(eventData.context.substring(0, 100));
        el.textContent = contextPreview + (eventData.context.length > 100 ? '...' : '');
        el.classList.remove('expanded');
        btn.textContent = 'Show Full';
    } else {
        el.textContent = escapeHtml(eventData.context);
        el.classList.add('expanded');
        btn.textContent = 'Show Less';
    }
}

async function copySpawnText(spawnId, type) {
    // Get the stored data
    const eventData = spawnEventData[spawnId];
    if (!eventData) return;

    const textToCopy = type === 'prompt' ? eventData.prompt : eventData.context;
    if (!textToCopy) return;

    try {
        await navigator.clipboard.writeText(textToCopy);

        // Visual feedback - find the button near the element
        const containerId = type === 'prompt' ? `prompt-${spawnId}` : `context-${spawnId}`;
        const btn = document.getElementById(containerId)?.parentElement?.querySelector('.spawn-copy-btn');
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            btn.style.background = 'rgba(102, 255, 222, 0.3)';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        }
    } catch (err) {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard. Please try again.');
    }
}

// ============================================================================
// Export Summary
// ============================================================================

async function exportSummary() {
    if (!selectedSession) {
        alert('Please select a session first');
        return;
    }

    const btn = document.getElementById('export-btn');
    const originalText = btn.textContent;
    btn.textContent = '⏳ Exporting...';
    btn.disabled = true;

    try {
        // Use relative URL to avoid port issues
        const response = await fetch(`/api/summary/${selectedSession}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.summary) {
            // Copy to clipboard
            await navigator.clipboard.writeText(data.summary);

            // Show success feedback
            btn.textContent = '✅ Copied!';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.disabled = false;
            }, 2000);
        } else {
            throw new Error('No summary in response');
        }
    } catch (error) {
        console.error('Export failed:', error);
        btn.textContent = '❌ Failed';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        }, 2000);
    }
}

function updateExportButton() {
    const btn = document.getElementById('export-btn');
    if (btn) {
        btn.disabled = !selectedSession;
        btn.title = selectedSession ? 'Copy session summary to clipboard' : 'Select a session to export';
    }
}

// ============================================================================
// Live Updates - Relative Timestamps & Connection Status
// ============================================================================

/**
 * Parse timestamp string to milliseconds.
 * Handles both ISO format ("2025-12-04T18:30:45") and HH:MM:SS format ("18:30:45").
 * Returns NaN-safe fallback to current time if parsing fails.
 */
function parseTimestamp(timestamp) {
    if (!timestamp) return Date.now();

    // If already a number (milliseconds), return as-is
    if (typeof timestamp === 'number') {
        return isNaN(timestamp) ? Date.now() : timestamp;
    }

    // Try ISO format first
    let ms = new Date(timestamp).getTime();
    if (!isNaN(ms)) return ms;

    // Handle HH:MM:SS format (backend sends this)
    if (typeof timestamp === 'string' && /^\d{2}:\d{2}:\d{2}$/.test(timestamp)) {
        // Create date for today with the given time
        const today = new Date();
        const [h, m, s] = timestamp.split(':').map(Number);
        today.setHours(h, m, s, 0);
        return today.getTime();
    }

    // Fallback to current time
    return Date.now();
}

function formatTimeAgo(timestamp) {
    const now = Date.now();
    // Handle NaN and invalid timestamps
    const ts = (typeof timestamp === 'number' && !isNaN(timestamp)) ? timestamp : now;
    const diff = now - ts;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 0) return 'just now';  // Future time (clock skew)
    if (seconds < 10) return 'just now';
    if (seconds < 60) return `${seconds}s ago`;
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
}

function updateRelativeTimestamps() {
    const now = Date.now();

    // Update event timestamps (only for events less than 1 hour old)
    document.querySelectorAll('.event-time[data-timestamp]').forEach(el => {
        const timestamp = parseInt(el.dataset.timestamp);
        const age = now - timestamp;

        // Only update timestamps less than 1 hour old
        if (age < 3600000) {
            const oldText = el.textContent;
            const newText = formatTimeAgo(timestamp);

            if (oldText !== newText) {
                el.textContent = newText;
                // Add pulse animation to show it updated
                el.classList.add('just-updated');
                setTimeout(() => el.classList.remove('just-updated'), 500);
            }
        }
    });

    // Update session last active times
    document.querySelectorAll('.session-last-active[data-timestamp]').forEach(el => {
        const timestamp = parseInt(el.dataset.timestamp);
        const newText = `active ${formatTimeAgo(timestamp)}`;
        if (el.textContent !== newText) {
            el.textContent = newText;
        }
    });
}

function updateConnectionStatus() {
    const statusText = document.getElementById('status-text');
    if (!lastHeartbeatTime) {
        statusText.textContent = 'Disconnected';
        return;
    }

    const elapsed = Math.floor((Date.now() - lastHeartbeatTime) / 1000);
    if (elapsed < 60) {
        statusText.textContent = `Connected (${elapsed}s ago)`;
    } else {
        const minutes = Math.floor(elapsed / 60);
        statusText.textContent = `Connected (${minutes}m ago)`;
    }
}

// ============================================================================
// Theme Management
// ============================================================================

function getSystemTheme() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        return 'light';
    }
    return 'dark';
}

function loadTheme() {
    const stored = localStorage.getItem('motus_theme');
    const theme = stored || getSystemTheme();
    applyTheme(theme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.textContent = theme === 'light' ? '☀️' : '🌙';
    }
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem('motus_theme', newTheme);
    applyTheme(newTheme);
}

// Listen for system theme changes
if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
        // Only apply if user hasn't set a preference
        if (!localStorage.getItem('motus_theme')) {
            applyTheme(e.matches ? 'light' : 'dark');
        }
    });
}

// ============================================================================
// Initialization
// ============================================================================

// Initialize theme first (before any rendering)
loadTheme();

// Initialize on load
initWorkingMemory();
connect();

// Track intervals for cleanup on page unload
const intervalIds = [];

// Heartbeat to keep connection alive
intervalIds.push(setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'heartbeat' }));
    }
}, 30000));

// Update relative timestamps every 5 seconds (was 1s - reduced for efficiency)
// Human perception doesn't need sub-5s precision for "2m ago" style timestamps
intervalIds.push(setInterval(updateRelativeTimestamps, 5000));

// Update connection status every 5 seconds (was 1s - reduced for efficiency)
intervalIds.push(setInterval(updateConnectionStatus, 5000));

// Cleanup on page unload to prevent memory leaks
window.addEventListener('beforeunload', () => {
    // Clear all intervals
    intervalIds.forEach(id => clearInterval(id));
    // Close WebSocket cleanly
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
    }
    // Clear large data structures
    spawnEventData = {};
    events = [];
    contexts = {};
});

// ============================================================================
// Keyboard Navigation
// ============================================================================

let highlightedSessionIndex = -1; // -1 = "All Sessions", 0+ = session items
let visibleSessions = []; // Track visible sessions for keyboard navigation

// Update visible sessions when sessions are rendered
function updateVisibleSessions() {
    const allSessionsEl = document.querySelector('.all-sessions');
    const sessionElements = document.querySelectorAll('.session-item');

    visibleSessions = [];
    if (allSessionsEl) {
        visibleSessions.push({ type: 'all', element: allSessionsEl });
    }
    sessionElements.forEach(el => {
        visibleSessions.push({ type: 'session', element: el });
    });
}

// Apply highlight to current index
function applySessionHighlight() {
    // Remove all highlights
    document.querySelectorAll('.all-sessions, .session-item').forEach(el => {
        el.classList.remove('highlighted');
    });

    // Apply new highlight
    if (highlightedSessionIndex >= 0 && highlightedSessionIndex < visibleSessions.length) {
        visibleSessions[highlightedSessionIndex].element.classList.add('highlighted');

        // Scroll into view
        const element = visibleSessions[highlightedSessionIndex].element;
        element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// Navigate to next session
function navigateSessionDown() {
    updateVisibleSessions();
    if (visibleSessions.length === 0) return;

    highlightedSessionIndex = Math.min(highlightedSessionIndex + 1, visibleSessions.length - 1);
    applySessionHighlight();
}

// Navigate to previous session
function navigateSessionUp() {
    updateVisibleSessions();
    if (visibleSessions.length === 0) return;

    highlightedSessionIndex = Math.max(highlightedSessionIndex - 1, 0);
    applySessionHighlight();
}

// Confirm selection (Enter key)
function confirmSessionSelection() {
    if (highlightedSessionIndex < 0 || highlightedSessionIndex >= visibleSessions.length) return;

    const session = visibleSessions[highlightedSessionIndex];
    session.element.click();
}

// Quick select session by number (1-9)
function quickSelectSession(num) {
    updateVisibleSessions();

    // num 1 = index 0, num 2 = index 1, etc.
    const targetIndex = num;

    if (targetIndex >= 0 && targetIndex < visibleSessions.length) {
        highlightedSessionIndex = targetIndex;
        applySessionHighlight();
        confirmSessionSelection();
    }
}

// Deselect session (Escape)
function deselectSession() {
    highlightedSessionIndex = -1;
    applySessionHighlight();

    // If a session is selected, go back to "All Sessions"
    if (selectedSession) {
        selectAllSessions();
    }
}

// Toggle shortcuts help overlay
function toggleShortcutsHelp() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (overlay) {
        overlay.classList.toggle('active');
    }
}

// Close shortcuts help overlay
function closeShortcutsHelp() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// Refresh sessions (r key)
function refreshSessions() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        // Request fresh sessions list
        ws.send(JSON.stringify({ type: 'request_sessions' }));

        // Visual feedback
        const statusText = document.getElementById('status-text');
        const originalText = statusText.textContent;
        statusText.textContent = 'Refreshing...';
        setTimeout(() => {
            statusText.textContent = originalText;
        }, 1000);
    }
}

// Global keyboard event handler
document.addEventListener('keydown', (e) => {
    // Don't intercept keys when user is typing in an input field
    const activeElement = document.activeElement;
    const isTyping = activeElement.tagName === 'INPUT' ||
                     activeElement.tagName === 'TEXTAREA' ||
                     activeElement.isContentEditable;

    // Special case: Allow Escape even when typing (to blur input)
    if (e.key === 'Escape') {
        if (isTyping) {
            // Blur the input and clear it if it's the search filter
            activeElement.blur();
            if (activeElement.id === 'search-filter') {
                activeElement.value = '';
                applyFilters();
            }
        } else {
            // Close shortcuts help or deselect session
            const shortcutsOverlay = document.getElementById('shortcuts-overlay');
            if (shortcutsOverlay && shortcutsOverlay.classList.contains('active')) {
                closeShortcutsHelp();
            } else {
                deselectSession();
            }
        }
        e.preventDefault();
        return;
    }

    // Don't intercept other keys when typing
    if (isTyping) return;

    // Session navigation
    if (e.key === 'j' || e.key === 'ArrowDown') {
        navigateSessionDown();
        e.preventDefault();
    } else if (e.key === 'k' || e.key === 'ArrowUp') {
        navigateSessionUp();
        e.preventDefault();
    } else if (e.key === 'Enter') {
        confirmSessionSelection();
        e.preventDefault();
    }

    // Quick select (1-9)
    else if (e.key >= '1' && e.key <= '9') {
        const num = parseInt(e.key);
        quickSelectSession(num - 1); // Convert to 0-indexed
        e.preventDefault();
    }

    // Filter focus
    else if (e.key === '/') {
        const searchInput = document.getElementById('search-filter');
        if (searchInput) {
            searchInput.focus();
            e.preventDefault();
        }
    }

    // Shortcuts help
    else if (e.key === '?' || e.key === 'h') {
        toggleShortcutsHelp();
        e.preventDefault();
    }

    // Refresh
    else if (e.key === 'r') {
        refreshSessions();
        e.preventDefault();
    }

    // Export
    else if (e.key === 'e') {
        const exportBtn = document.getElementById('export-btn');
        if (exportBtn && !exportBtn.disabled) {
            exportSummary();
        }
        e.preventDefault();
    }
});

// Click outside shortcuts modal to close
document.addEventListener('click', (e) => {
    const overlay = document.getElementById('shortcuts-overlay');
    if (overlay && overlay.classList.contains('active')) {
        if (e.target === overlay) {
            closeShortcutsHelp();
        }
    }
});
