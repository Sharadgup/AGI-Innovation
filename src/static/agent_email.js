/**
 * agent_email.js
 * Frontend logic for the Autonomous Email Agent page.
 * Handles auth initiation, config saving, status display, logs, draft reviews.
 * NOTE: This is conceptual and assumes backend endpoints or ADK/MCP methods exist.
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("[Email Agent JS] DOM Loaded.");

    // --- Elements ---
    const statusEl = document.getElementById('agentStatus');
    const statusIndicatorEl = document.getElementById('agentStatusIndicator');
    const connectBtn = document.getElementById('connectGmailBtn');
    const startBtn = document.getElementById('startAgentBtn');
    const stopBtn = document.getElementById('stopAgentBtn');
    const controlErrorEl = document.getElementById('agentControlError');

    const configForm = document.getElementById('agentConfigForm');
    const monitorLabelInput = document.getElementById('monitorLabel');
    const rulesTextarea = document.getElementById('processingRules');
    const approvalCheckbox = document.getElementById('requireApproval');
    const configStatusEl = document.getElementById('configSaveStatus');

    const draftReviewArea = document.getElementById('draftReviewArea');
    const draftCountSpan = document.getElementById('draftCount');
    const refreshDraftsBtn = document.getElementById('refreshDraftsBtn');

    const activityLogEl = document.getElementById('activityLog');
    const refreshLogsBtn = document.getElementById('refreshLogsBtn');

    // --- Check Essential Elements ---
    if (!statusEl || !startBtn || !stopBtn || !activityLogEl || !draftReviewArea) {
        console.error("Email Agent essential elements missing. Aborting.");
        if(statusEl) statusEl.textContent = "Page Load Error";
        return;
    }

    // --- State ---
    let agentState = { // Example state structure
        connected: false, // Is Gmail connected?
        monitoring: false, // Is the agent actively monitoring?
        statusText: "Initializing...",
        statusClass: "status-idle"
    };

    // --- Initialization ---
    updateUIState(); // Set initial button states etc.
    getAgentStatus(); // Fetch initial status from backend/MCP
    fetchLogs();      // Fetch initial logs
    fetchDrafts();    // Fetch initial drafts

    // --- Event Listeners ---
    if (connectBtn) {
        connectBtn.addEventListener('click', handleConnectGmail);
    }
    startBtn.addEventListener('click', handleStartAgent);
    stopBtn.addEventListener('click', handleStopAgent);
    if (configForm) {
        configForm.addEventListener('submit', handleSaveConfig);
    }
    if (refreshLogsBtn) {
        refreshLogsBtn.addEventListener('click', fetchLogs);
    }
     if (refreshDraftsBtn) {
        refreshDraftsBtn.addEventListener('click', fetchDrafts);
    }
     // Add event delegation for dynamically added approve/reject buttons
     draftReviewArea.addEventListener('click', handleDraftAction);


    // --- Functions ---

    /** Updates the UI based on the agentState object */
    function updateUIState() {
        statusEl.textContent = agentState.statusText;
        statusIndicatorEl.className = `status-indicator ${agentState.statusClass}`; // Update class

        if (connectBtn) {
            connectBtn.style.display = agentState.connected ? 'none' : 'inline-block';
        }
        startBtn.disabled = !agentState.connected || agentState.monitoring;
        stopBtn.disabled = !agentState.connected || !agentState.monitoring;

        // Update config form based on fetched config later if needed
    }

    /** Clears and potentially shows a control error */
    function showControlError(message = '') {
         if (controlErrorEl) {
            controlErrorEl.textContent = message;
            controlErrorEl.style.display = message ? 'block' : 'none';
        }
    }

    /** Fetch current status from backend/MCP */
    async function getAgentStatus() {
        updateStatusIndicator("connecting", "Connecting..."); // Visual cue
        // Replace with your ADK/MCP method or fetch call
        // CONCEPTUAL: const result = await adk.getStatus('emailAgent');
        const result = await fetchApi('/agent/email/status'); // Example Flask route

        if (result.ok && result.data) {
            agentState.connected = result.data.gmail_connected || false;
            agentState.monitoring = result.data.is_monitoring || false;
            agentState.statusText = result.data.status_message || (agentState.monitoring ? 'Monitoring Inbox' : 'Idle');
            agentState.statusClass = agentState.monitoring ? 'status-running' : (agentState.connected ? 'status-idle' : 'status-error');
            if (!agentState.connected) agentState.statusText = "Gmail Not Connected";
        } else {
            agentState = { connected: false, monitoring: false, statusText: "Error fetching status", statusClass: "status-error" };
            showControlError(result.error || "Could not get agent status.");
        }
        updateUIState();
    }

     /** Update status indicator visual */
     function updateStatusIndicator(statusClass = 'status-idle', text = 'Idle') {
         agentState.statusClass = statusClass;
         agentState.statusText = text;
         updateUIState();
     }

    /** Initiate Gmail OAuth Connection */
    async function handleConnectGmail() {
        showControlError();
        updateStatusIndicator("connecting", "Redirecting to Google...");
        // This typically involves redirecting the user to a backend route
        // that initiates the Flask-Dance OAuth flow.
        window.location.href = '/agent/email/authorize'; // Example backend route to start OAuth
        // The backend will handle the redirect to Google and the callback.
        // After callback success, the backend should ideally notify frontend (e.g., via SocketIO)
        // or the user might need to refresh this page.
    }

    /** Send command to start monitoring */
    async function handleStartAgent() {
        showControlError();
        updateStatusIndicator("running", "Starting agent...");
        // CONCEPTUAL: const result = await adk.sendCommand('emailAgent', 'start_monitoring');
        const result = await fetchApi('/agent/email/start', 'POST'); // Example Flask route
        if (!result.ok) { showControlError(result.error || "Failed to start agent."); }
        getAgentStatus(); // Refresh status after command
    }

    /** Send command to stop monitoring */
    async function handleStopAgent() {
         showControlError();
         updateStatusIndicator("idle", "Stopping agent...");
         // CONCEPTUAL: const result = await adk.sendCommand('emailAgent', 'stop_monitoring');
         const result = await fetchApi('/agent/email/stop', 'POST'); // Example Flask route
         if (!result.ok) { showControlError(result.error || "Failed to stop agent."); }
         getAgentStatus(); // Refresh status after command
    }

    /** Save configuration */
    async function handleSaveConfig(event) {
        event.preventDefault();
        showControlError();
        if(configStatusEl) configStatusEl.textContent = 'Saving...';

        const configData = {
            monitor_label: monitorLabelInput.value.trim(),
            processing_rules: rulesTextarea.value.trim(),
            require_approval: approvalCheckbox.checked
        };
        console.log("Saving config:", configData);

        // CONCEPTUAL: const result = await adk.setConfig('emailAgent', configData);
        const result = await fetchApi('/agent/email/config', 'POST', configData); // Example Flask route

         if(configStatusEl) {
             configStatusEl.textContent = result.ok ? 'Configuration Saved!' : `Error: ${result.error}`;
             configStatusEl.className = result.ok ? 'text-success small mt-2' : 'text-danger small mt-2';
             setTimeout(() => { configStatusEl.textContent = ''; }, 4000); // Clear after 4s
         }
    }

    /** Fetch recent activity logs */
    async function fetchLogs() {
         showControlError();
         activityLogEl.innerHTML = '<p class="text-muted small"><i>Loading logs...</i></p>';
         // CONCEPTUAL: const result = await adk.getLogs('emailAgent', { limit: 20 });
         const result = await fetchApi('/agent/email/logs?limit=20'); // Example Flask route

         if (result.ok && result.data?.logs) {
             renderLogs(result.data.logs);
         } else {
              activityLogEl.innerHTML = `<p class="text-danger small"><i>Error loading logs: ${result.error || 'Unknown error'}</i></p>`;
         }
    }

    /** Render activity logs */
    function renderLogs(logs) {
        if (!logs || logs.length === 0) {
            activityLogEl.innerHTML = '<p class="text-muted small"><i>No recent activity found.</i></p>';
            return;
        }
        activityLogEl.innerHTML = ''; // Clear placeholder/old logs
        logs.forEach(log => {
            const entryDiv = document.createElement('div');
            entryDiv.className = 'log-entry';
            // Format timestamp
            const timestamp = log.timestamp ? new Date(log.timestamp.$date || log.timestamp).toLocaleString() : 'N/A'; // Handle BSON date
            const statusClass = log.status === 'success' ? 'log-status-success' : (log.status === 'failed' ? 'log-status-failed' : '');
            // Simple display (customize as needed)
            entryDiv.innerHTML = `
                <small>${timestamp}</small>
                <span class="log-details">
                    <strong>${log.action || 'Action'}:</strong>
                    ${log.email_details?.subject ? `Subj: '${log.email_details.subject.substring(0,30)}...'` : ''}
                    ${log.email_details?.to ? `To: ${log.email_details.to}` : ''}
                    ${log.error ? `<span class="text-danger">(${log.error.substring(0,50)}...)</span>` : ''}
                </span>
                <span class="log-status ${statusClass}">${log.status || ''}</span>
            `;
            activityLogEl.appendChild(entryDiv);
        });
    }

    /** Fetch drafts needing approval */
    async function fetchDrafts() {
         showControlError();
         draftReviewArea.innerHTML = '<p class="text-muted small"><i>Loading drafts...</i></p>';
         // CONCEPTUAL: const result = await adk.getPendingActions('emailAgent', { type: 'draft_approval' });
         const result = await fetchApi('/agent/email/drafts'); // Example Flask route

          if (result.ok && result.data?.drafts) {
             renderDrafts(result.data.drafts);
             if (draftCountSpan) draftCountSpan.textContent = result.data.drafts.length;
         } else {
              draftReviewArea.innerHTML = `<p class="text-danger small"><i>Error loading drafts: ${result.error || 'Unknown error'}</i></p>`;
              if (draftCountSpan) draftCountSpan.textContent = '0';
         }
    }

    /** Render drafts needing approval */
    function renderDrafts(drafts) {
         if (!drafts || drafts.length === 0) {
            draftReviewArea.innerHTML = '<p class="text-muted small"><i>No drafts currently awaiting approval.</i></p>';
            return;
        }
        draftReviewArea.innerHTML = ''; // Clear placeholder
        drafts.forEach(draft => {
             // Ensure draft has needed info
            if (!draft.draft_id || !draft.email_details) return;

            const draftDiv = document.createElement('div');
            draftDiv.className = 'draft-review';
            draftDiv.dataset.draftId = draft.draft_id; // Store ID for actions

            draftDiv.innerHTML = `
                <div class="draft-header">
                    <strong>To:</strong> ${draft.email_details.to || 'N/A'}<br>
                    <strong>Subject:</strong> ${draft.email_details.subject || 'N/A'}
                </div>
                <div class="draft-body">${(draft.email_details.body || '').replace(/\n/g, '<br>')}</div>
                <div class="draft-actions mt-2">
                    <button class="btn btn-success btn-sm draft-approve-btn"><i class="fas fa-check"></i> Approve & Send</button>
                    <button class="btn btn-danger btn-sm draft-reject-btn"><i class="fas fa-times"></i> Reject Draft</button>
                    {# Add Edit button later? #}
                </div>
                <div class="draft-feedback text-danger small mt-1"></div>
            `;
            draftReviewArea.appendChild(draftDiv);
        });
    }

    /** Handle Approve/Reject clicks using event delegation */
    async function handleDraftAction(event) {
        const target = event.target;
        const draftDiv = target.closest('.draft-review');
        if (!draftDiv) return; // Click wasn't inside a draft review area

        const draftId = draftDiv.dataset.draftId;
        const feedbackEl = draftDiv.querySelector('.draft-feedback');
        if (!draftId) { console.error("Draft ID missing from element."); return; }

        let action = null;
        if (target.classList.contains('draft-approve-btn')) action = 'approve';
        else if (target.classList.contains('draft-reject-btn')) action = 'reject';
        else return; // Click wasn't on an action button

        console.log(`Performing action '${action}' on draft ID: ${draftId}`);
        if(feedbackEl) feedbackEl.textContent = 'Processing...';
        target.disabled = true; // Disable button during action
        const otherButton = draftDiv.querySelector(action === 'approve' ? '.draft-reject-btn' : '.draft-approve-btn');
        if(otherButton) otherButton.disabled = true;

        // CONCEPTUAL: const result = await adk.performAction('emailAgent', action, { draft_id: draftId });
        const result = await fetchApi(`/agent/email/drafts/${draftId}/action`, 'POST', { action: action }); // Example

        if (result.ok) {
             console.log(`Draft ${draftId} action ${action} successful.`);
             // Remove the draft visually after success
             draftDiv.style.opacity = '0.5';
             draftDiv.style.transition = 'opacity 0.5s ease';
             setTimeout(() => { draftDiv.remove(); fetchDrafts(); /* Refresh count/list */ }, 500);
        } else {
             console.error(`Failed to ${action} draft ${draftId}:`, result.error);
             if(feedbackEl) feedbackEl.textContent = `Error: ${result.error || 'Action failed'}`;
             target.disabled = false; // Re-enable button on error
             if(otherButton) otherButton.disabled = false;
        }
    }


    // --- Initial Load & Setup ---
    console.log("[Email Agent JS] Running initial setup...");
    if (NEWS_API_AVAILABLE) { // Check if the *news* key flag exists - adapt if needed
        // Allow agent interaction only if system seems generally configured
        // Add more robust check if possible based on backend status endpoint
    } else {
         updateStatusIndicator("error", "Dependent Service Unavailable");
         console.warn("Disabling Email Agent controls as a dependent service might be offline (based on NEWS_API_AVAILABLE flag).");
         // Optionally disable all buttons
         // startBtn.disabled = true; stopBtn.disabled = true; // ... etc.
    }
    // --- End Initial Load ---

}); // End DOMContentLoaded