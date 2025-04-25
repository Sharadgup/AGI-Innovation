/**
 * AI Note Taker - COMBINED Frontend Script
 * Handles Report Generation/Chat and General Dashboard Chat
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM Content Loaded - Initializing combined script...");

    // --- Element References (Report Section) ---
    const generateBtn = document.getElementById('generateBtn');
    const inputText = document.getElementById('inputText');
    const reportContainer = document.getElementById('reportContainer');
    const reportOutput = document.getElementById('reportOutput');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const loadingText = document.getElementById('loadingText');
    const errorMessageDiv = document.getElementById('errorMessage'); // General error display
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');
    const keywordChartContainer = document.getElementById('keywordChartContainer');
    const sentimentChartContainer = document.getElementById('sentimentChartContainer');
    const keywordChartCanvas = document.getElementById('keywordChart')?.getContext('2d');
    const sentimentChartCanvas = document.getElementById('sentimentChart')?.getContext('2d');
    const noChartsMessage = document.getElementById('noChartsMessage');
    // Report-specific chat elements
    const reportChatContainer = document.getElementById('chatContainer'); // Renamed variable for clarity
    const reportChatMessages = document.getElementById('chatMessages');
    const reportChatInput = document.getElementById('chatInput');
    const reportSendChatBtn = document.getElementById('sendChatBtn');
    const reportTypingIndicator = document.getElementById('typingIndicator');

    // --- Element References (Dashboard Chat Section - might be null if user not logged in) ---
    const dashboardChatMessages = document.getElementById('dashboardChatMessages');
    const dashboardChatInput = document.getElementById('dashboardChatInput');
    const dashboardSendChatBtn = document.getElementById('sendDashboardChatBtn');
    const dashboardTypingIndicator = document.getElementById('dashboardTypingIndicator');
    const dashboardChatErrorDiv = document.getElementById('chatError'); // Using the same error div for now, might need separation

    // --- State Variables ---
    let keywordChartInstance = null;
    let sentimentChartInstance = null;
    let currentDocumentationId = null; // ID for the current report's chat

    // --- Initialize Socket.IO Connections ---
    let reportSocket; // For default namespace '/'
    let dashboardSocket; // For '/dashboard_chat' namespace

    // Initialize Report Chat Socket (Always needed on this page)
    try {
        console.log("[Report Socket Init] Attempting...");
        if (typeof io === 'undefined') throw new Error("Socket.IO client library (io) not found.");
        reportSocket = io('/'); // Connect to default namespace
        console.log("[Report Socket Init] Object created.");
        setupReportSocketListeners();
        disableReportChatInput(true, "Generate a report to enable chat...");
    } catch (e) {
        console.error("[Report Socket Init] CRITICAL:", e);
        showError("Could not initialize report chat connection.", true);
        disableReportChatInput(true, "Chat unavailable (init failed).");
    }

    // Initialize Dashboard Chat Socket ONLY IF the elements exist (meaning user is logged in)
    if (dashboardChatMessages && dashboardChatInput && dashboardSendChatBtn) {
        try {
            console.log("[Dashboard Socket Init] Attempting...");
            // No need to check io again if report socket succeeded
            dashboardSocket = io('/dashboard_chat'); // Connect to dashboard namespace
            console.log("[Dashboard Socket Init] Object created.");
            setupDashboardSocketListeners();
            disableDashboardChatInput(true, "Connecting to general chat...");
        } catch (e) {
            console.error("[Dashboard Socket Init] CRITICAL:", e);
            showChatError("Could not connect to general chat service."); // Use specific error display?
            disableDashboardChatInput(true, "General chat unavailable.");
        }
    } else {
        console.log("[Dashboard Socket Init] Dashboard chat elements not found. Skipping initialization.");
    }


    // --- SocketIO Event Listeners Setup (Report Chat - Default Namespace) ---
    function setupReportSocketListeners() {
        if (!reportSocket) { console.error("[Report Socket Setup] Error: reportSocket is not initialized."); return; }
        console.log("[Report Socket Setup] Setting up Report Chat listeners...");

        reportSocket.on('connect', () => {
            console.log('[Report Socket Event] connect: Connected. SID:', reportSocket.id);
            // Use general hideError or a specific one if needed
            hideError();
            if (reportChatContainer && reportChatContainer.style.display !== 'none' && currentDocumentationId) {
                console.log('[Report Socket Event] connect: Reconnected with active Doc ID. Enabling input.');
                disableReportChatInput(false);
            } else {
                console.log('[Report Socket Event] connect: No active report/chat or chat hidden.');
            }
        });

        reportSocket.on('disconnect', (reason) => {
            console.log(`[Report Socket Event] disconnect: Reason: ${reason}`);
            if (reason !== 'io client disconnect') {
                 showError("Report chat connection lost. Trying to reconnect...", false);
                 disableReportChatInput(true, "Chat disconnected. Reconnecting...");
            } else {
                 disableReportChatInput(true, "Chat disconnected.");
            }
        });

        reportSocket.on('connect_error', (err) => {
            console.error(`[Report Socket Event] connect_error: ${err.message}`);
            showError(`Report chat connection failed: ${err.message}.`, true);
            disableReportChatInput(true, "Chat connection failed.");
        });

        reportSocket.on('receive_message', (data) => { // Event for report chat
            console.log('[Report Socket Event] receive_message: Data received:', data);
            if (data && data.user && typeof data.text === 'string') {
                appendReportMessage(data.user, data.text); // Use specific append
            } else {
                console.warn("[Report Socket Event] receive_message: Malformed data:", data);
                appendReportMessage('System', '[Received incomplete message from server]', true);
            }
        });

        reportSocket.on('error', (data) => { // General errors on default namespace
            console.error('[Report Socket Event] error: Server emitted error:', data.message);
            appendReportMessage('System', `Chat Server Error: ${data.message || 'Unknown error'}`, true);
        });

        reportSocket.on('typing_indicator', (data) => { // Typing for report chat
            console.log('[Report Socket Event] typing_indicator:', data);
            if (reportTypingIndicator) {
                reportTypingIndicator.style.display = data.isTyping ? 'flex' : 'none';
                if (data.isTyping) { scrollToBottom(reportChatMessages); }
            } else { console.warn("Report typing indicator element not found.") }
        });
        console.log("[Report Socket Setup] Listeners attached.");
    } // --- End setupReportSocketListeners ---


    // --- SocketIO Event Listeners Setup (Dashboard Chat - /dashboard_chat Namespace) ---
    function setupDashboardSocketListeners() {
        if (!dashboardSocket) { console.error("[Dashboard Socket Setup] Error: dashboardSocket is not initialized."); return; }
        console.log("[Dashboard Socket Setup] Setting up Dashboard Chat listeners...");

        dashboardSocket.on('connect', () => {
            console.log('[Dashboard Socket Event] connect: Connected.', dashboardSocket.id);
            hideChatError(); // Use specific error hide?
            disableDashboardChatInput(false, "Ask a general question...");
            // Clear placeholder only if it exists
            const placeholder = dashboardChatMessages?.querySelector('.message.system');
            if(placeholder && placeholder.textContent.includes('Connecting')) placeholder.remove();
            // appendDashboardMessage('System', 'Connected to general chat.');
        });

        dashboardSocket.on('disconnect', (reason) => {
            console.log(`[Dashboard Socket Event] disconnect: Reason: ${reason}`);
            if (reason !== 'io client disconnect') {
                 showChatError("General chat connection lost. Reconnecting...");
                 disableDashboardChatInput(true, "Reconnecting...");
            } else {
                 disableDashboardChatInput(true, "Chat disconnected.");
            }
        });

        dashboardSocket.on('connect_error', (err) => {
            console.error(`[Dashboard Socket Event] connect_error: ${err.message}`);
            showChatError(`General chat connection failed: ${err.message}`);
            disableDashboardChatInput(true, "Connection failed.");
        });

        // Receive message from SERVER on this namespace
        dashboardSocket.on('receive_dashboard_message', (data) => {
            console.log('[Dashboard Socket Event] receive_dashboard_message: Data received:', data);
            if (data && data.user && typeof data.text === 'string') {
                appendDashboardMessage(data.user, data.text); // Use specific append
            } else {
                console.warn("[Dashboard Socket Event] receive_dashboard_message: Malformed data:", data);
                appendDashboardMessage('System', '[Received incomplete message]', true);
            }
        });

         // Receive error from SERVER on this namespace
        dashboardSocket.on('error', (data) => {
             console.error('[Dashboard Socket Event] error: Server emitted error:', data.message);
             showChatError(`Server error: ${data.message || 'Unknown'}`);
        });

        // Typing indicator from SERVER (assuming server uses same event name for both namespaces)
        dashboardSocket.on('typing_indicator', (data) => {
             console.log('[Dashboard Socket Event] typing_indicator:', data);
            if (dashboardTypingIndicator) {
                dashboardTypingIndicator.style.display = data.isTyping ? 'flex' : 'none';
                if (data.isTyping) { scrollToBottom(dashboardChatMessages); }
            } else { console.warn("Dashboard typing indicator element not found.") }
        });
         console.log("[Dashboard Socket Setup] Listeners attached.");
    } // --- End setupDashboardSocketListeners ---


    // --- Event Listeners ---
    if (generateBtn) { generateBtn.addEventListener('click', handleGenerateReport); }
    else { console.error("Could not attach listener: generateBtn not found."); }

    // Attach listener for Report Chat send button
    if (reportSendChatBtn) { reportSendChatBtn.addEventListener('click', sendReportMessage); }
    else { console.error("Could not attach listener: Report sendChatBtn not found."); }

    // Attach listener for Report Chat input (Enter key)
    if (reportChatInput) { reportChatInput.addEventListener('keypress', (event) => { if (event.key === 'Enter' && !event.shiftKey && !reportChatInput.disabled) { event.preventDefault(); sendReportMessage(); } }); }
    else { console.error("Could not attach listener: Report chatInput not found."); }

    // Attach listener for Dashboard Chat send button (if it exists)
    if (dashboardSendChatBtn) { dashboardSendChatBtn.addEventListener('click', sendDashboardMessage); }
    else { console.log("Dashboard send button not found (user might not be logged in)."); } // Log instead of error

    // Attach listener for Dashboard Chat input (Enter key) (if it exists)
    if (dashboardChatInput) { dashboardChatInput.addEventListener('keypress', (event) => { if (event.key === 'Enter' && !event.shiftKey && !dashboardChatInput.disabled) { event.preventDefault(); sendDashboardMessage(); } }); }
    else { console.log("Dashboard chat input not found (user might not be logged in)."); }

    // PDF Download Button
    if (downloadPdfBtn) { downloadPdfBtn.addEventListener('click', handleDownloadPdf); }
    else { console.warn("Download PDF button not found."); }


    // --- Core Functions ---

    async function handleGenerateReport() {
        console.log("[handleGenerateReport] Function called.");
        const text = inputText.value.trim();
        if (!text) { showError("Please enter some text.", true); return; }
        setLoadingState(true, "Generating report...");
        hideError();
        if(reportContainer) reportContainer.style.display = 'none';
        if(reportChatContainer) reportChatContainer.style.display = 'none'; // Use correct variable
        clearReportChatMessages(); // Use specific clear
        destroyCharts();
        currentDocumentationId = null; // Reset Doc ID
        disableReportChatInput(true, "Generating report..."); // Use specific disable

        let response;
        try {
            console.log("[handleGenerateReport] Sending request to /generate_report");
            response = await fetch('/generate_report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text }) });
            console.log(`[handleGenerateReport] Received response status: ${response.status}`);
            if (!response.ok) { let errorMsg = `Server error! Status: ${response.status}`; try { const errorData = await response.json(); errorMsg = errorData.error || errorMsg; } catch (e) {} throw new Error(errorMsg); }

            const data = await response.json();
            console.log("[handleGenerateReport] Received report data:", data);
            if (!data || typeof data.report_html !== 'string') { throw new Error("Invalid or incomplete report data."); }

            try { // UI Updates
                console.log("[handleGenerateReport] Updating report UI...");
                if (reportOutput) { reportOutput.innerHTML = data.report_html; }
                processChartData(data.chart_data);
                if (reportContainer) reportContainer.style.display = 'block';
                currentDocumentationId = data.documentation_id; // Store the ID
                console.log(`[handleGenerateReport] Stored documentation_id: ${currentDocumentationId}`);

                // Activate Report Chat UI only if ID is valid
                if (currentDocumentationId) {
                    console.log("[handleGenerateReport] Valid documentation_id received. Activating report chat.");
                    if (reportChatContainer) reportChatContainer.style.display = 'flex'; // Show report chat
                    appendReportMessage('System', 'Report generated. Ask questions about this report.', true); // Use specific append
                    if (reportSocket && reportSocket.connected) {
                        console.log("[handleGenerateReport] Report socket connected. Enabling report chat input.");
                        disableReportChatInput(false); // Use specific enable
                    } else {
                        console.warn("[handleGenerateReport] Report socket NOT connected! Chat remains disabled.");
                        showError("Report chat connection is currently down.", false);
                        disableReportChatInput(true, "Chat unavailable.");
                    }
                } else {
                    console.error("[handleGenerateReport] documentation_id MISSING from server response! Report chat remains disabled.");
                    if (reportChatContainer) reportChatContainer.style.display = 'none';
                    showError("Report generated, but failed to initialize chat context (missing ID).", true);
                    disableReportChatInput(true, "Chat unavailable (error).");
                }
             } catch (uiError) { console.error("[handleGenerateReport] Error updating UI:", uiError); showError(`Error displaying report: ${uiError.message}`, true); currentDocumentationId = null; }

        } catch (error) {
            console.error("[handleGenerateReport] Fetch/Process Error:", error);
            showError(`Failed to generate report: ${error.message}`, true);
            currentDocumentationId = null;
            if(reportContainer) reportContainer.style.display = 'none';
            if(reportChatContainer) reportChatContainer.style.display = 'none';
        } finally {
            console.log("[handleGenerateReport] Finished processing.");
            setLoadingState(false);
        }
    } // --- End handleGenerateReport ---

    // --- RENAMED function for Report Chat ---
    function sendReportMessage() {
        console.log("[sendReportMessage] Function called.");
        if (!reportSocket || !reportSocket.connected) { showError("Cannot send: Report chat not connected.", false); disableReportChatInput(true, "Chat disconnected."); return; }
        if (!reportChatInput || reportChatInput.disabled) { console.warn("Report chat input disabled."); return; }
        if (!currentDocumentationId) { console.error("sendReportMessage Error: currentDocumentationId missing!"); showError("Cannot send: No active report context.", false); return; }

        const messageText = reportChatInput.value.trim();
        if (!messageText) return;

        appendReportMessage('User', messageText); // Use specific append
        reportChatInput.value = ''; // Clear specific input

        const payload = { text: messageText, documentation_id: currentDocumentationId };
        console.log("[sendReportMessage] Emitting 'send_message' (default namespace) with payload:", payload);

        try { reportSocket.emit('send_message', payload); } // Use reportSocket
        catch (emitError) { console.error("[sendReportMessage] Error emitting:", emitError); showError("Failed to send message.", false); }
    }

    // --- NEW function for Dashboard Chat ---
    function sendDashboardMessage() {
        console.log("[sendDashboardMessage] Function called.");
        if (!dashboardSocket || !dashboardSocket.connected) { showChatError("Cannot send: General chat not connected."); disableDashboardChatInput(true, "Disconnected."); return; }
        if (!dashboardChatInput || dashboardChatInput.disabled) { console.warn("Dashboard chat input disabled."); return; }

        const messageText = dashboardChatInput.value.trim();
        if (!messageText) return;

        appendDashboardMessage('User', messageText); // Use specific append
        dashboardChatInput.value = ''; // Clear specific input

        const payload = { text: messageText }; // No doc ID needed here
        console.log("[sendDashboardMessage] Emitting 'send_dashboard_message' (/dashboard_chat namespace) with payload:", payload);

        try { dashboardSocket.emit('send_dashboard_message', payload); } // Use dashboardSocket
        catch (emitError) { console.error("[sendDashboardMessage] Error emitting:", emitError); showChatError("Failed to send general message.", false); }
    }


    // --- Helper Functions ---

    // --- RENAMED: Disables/Enables the REPORT chat input and send button ---
    function disableReportChatInput(disabled, placeholderText = "Ask a question about the report...") {
        console.log(`[disableReportChatInput] Setting disabled=${disabled}, placeholder="${placeholderText}"`);
        if (reportChatInput) { reportChatInput.disabled = disabled; reportChatInput.placeholder = placeholderText; }
        else { console.error("[disableReportChatInput] reportChatInput element NOT FOUND!"); }
        if (reportSendChatBtn) { reportSendChatBtn.disabled = disabled; }
        else { console.error("[disableReportChatInput] reportSendChatBtn element NOT FOUND!"); }
    }

    // --- NEW: Disables/Enables the DASHBOARD chat input and send button ---
    function disableDashboardChatInput(disabled, placeholderText = "Ask a general question...") {
        console.log(`[disableDashboardChatInput] Setting disabled=${disabled}, placeholder="${placeholderText}"`);
        if (dashboardChatInput) { dashboardChatInput.disabled = disabled; dashboardChatInput.placeholder = placeholderText; }
        else { console.warn("[disableDashboardChatInput] dashboardChatInput element NOT FOUND (might be expected if not logged in)."); }
        if (dashboardSendChatBtn) { dashboardSendChatBtn.disabled = disabled; }
        else { console.warn("[disableDashboardChatInput] dashboardSendChatBtn element NOT FOUND (might be expected if not logged in)."); }
    }


    function setLoadingState(isLoading, text = "Loading...") {
        // (Remains generic)
         console.log(`[setLoadingState] isLoading=${isLoading}, text="${text}"`);
        if (generateBtn) generateBtn.disabled = isLoading;
        if (loadingIndicator) { if(loadingText) loadingText.textContent = text; loadingIndicator.style.display = isLoading ? 'flex' : 'none'; }
    }

    // --- RENAMED: Appends message to the REPORT chat display ---
    function appendReportMessage(user, text, isSystem = false) {
        if (!reportChatMessages) { console.error("[appendReportMessage] reportChatMessages container not found!"); return; }
        console.log(`[appendReportMessage] User: ${user}, System: ${isSystem}, Text: ${text.substring(0,50)}...`);
        const messageElement = document.createElement('div'); messageElement.classList.add('message'); // Use generic message class
        if (isSystem) { messageElement.classList.add('system'); messageElement.innerHTML = text; }
        else { messageElement.classList.add(user.toLowerCase() === 'ai' ? 'ai' : 'user'); const sanitizedText = text.replace(/</g, "<").replace(/>/g, ">"); messageElement.textContent = sanitizedText; }
        reportChatMessages.appendChild(messageElement);
        scrollToBottom(reportChatMessages); // Scroll specific container
    }

    // --- NEW: Appends message to the DASHBOARD chat display ---
    function appendDashboardMessage(user, text, isSystem = false) {
         if (!dashboardChatMessages) { console.error("[appendDashboardMessage] dashboardChatMessages container not found!"); return; }
         console.log(`[appendDashboardMessage] User: ${user}, System: ${isSystem}, Text: ${text.substring(0,50)}...`);
         const messageElement = document.createElement('div'); messageElement.classList.add('message'); // Use generic message class
         if (isSystem) { messageElement.classList.add('system'); messageElement.innerHTML = text; }
         else { messageElement.classList.add(user.toLowerCase() === 'ai' ? 'ai' : 'user'); const sanitizedText = text.replace(/</g, "<").replace(/>/g, ">"); messageElement.textContent = sanitizedText; }
         dashboardChatMessages.appendChild(messageElement);
         scrollToBottom(dashboardChatMessages); // Scroll specific container
    }


    // --- RENAMED: Clears the REPORT chat message display ---
    function clearReportChatMessages() {
        console.log("[clearReportChatMessages] Clearing report chat messages.");
        if(reportChatMessages) reportChatMessages.innerHTML = ''; else console.error("[clearReportChatMessages] reportChatMessages element not found!");
    }

    // Scrolls an element to its bottom (Generic)
    function scrollToBottom(element) {
        if(element) { element.scrollTop = element.scrollHeight; } else { console.warn("[scrollToBottom] Element not provided.")}
    }

    // Shows error in the main general error div (Generic)
    function showError(message, isFatal = false) {
         console.error(`[showError] Fatal=${isFatal}, Message=${message}`);
         if(errorMessageDiv) { errorMessageDiv.textContent = message; errorMessageDiv.style.display = 'block'; errorMessageDiv.style.backgroundColor = isFatal ? '#dc3545' : '#ffc107'; errorMessageDiv.style.color = isFatal ? 'white' : 'black'; } else { alert(`Error: ${message}`); }
    }
     // --- NEW: Shows error in the DASHBOARD chat error div ---
     function showChatError(message) {
         // Use specific dashboard chat error div if available, otherwise fallback
         const targetErrorDiv = dashboardChatErrorDiv || errorMessageDiv; // Fallback to general error div
         if(targetErrorDiv) { targetErrorDiv.textContent = message; targetErrorDiv.style.display = 'block'; targetErrorDiv.style.backgroundColor = '#ffc107'; targetErrorDiv.style.color = 'black';} // Defaulting to warning style
         else { console.error("Dashboard/General Chat Error Div not found, message:", message); }
     }
    // --- NEW: Hides the DASHBOARD chat error div ---
     function hideChatError() {
        const targetErrorDiv = dashboardChatErrorDiv || errorMessageDiv;
        if(targetErrorDiv) { targetErrorDiv.style.display = 'none'; targetErrorDiv.textContent = ''; }
     }


    // Hides the main general error div (Generic)
    function hideError() {
        console.log("[hideError] Hiding general error message.");
        if(errorMessageDiv) { errorMessageDiv.style.display = 'none'; errorMessageDiv.textContent = ''; }
    }

    function destroyCharts() { /* (Remains the same) */ }
    function processChartData(chartData) { /* (Remains the same) */ }
    function handleDownloadPdf() { /* (Remains the same) */ }

    function initializeUI() {
        // Initializes the state for BOTH sections on the page
        console.log("[initializeUI] Initializing combined UI state...");
        destroyCharts();
        if (reportContainer) reportContainer.style.display = 'none';
        if (reportChatContainer) reportChatContainer.style.display = 'none'; // Hide report chat
        // Hide dashboard chat elements too, if they exist (connect listener enables it)
        if (dashboardChatMessages) {
             const placeholder = dashboardChatMessages.querySelector('.message.system');
             if(!placeholder || !placeholder.textContent.includes('Connecting')) {
                 // Add connecting message if needed (though handled by socket init now)
                 // appendDashboardMessage('System','Connecting to general chat...',true);
             }
        }


        if (loadingIndicator) loadingIndicator.style.display = 'none';
        hideError();
        hideChatError(); // Hide specific chat error too
        disableReportChatInput(true, "Generate a report to enable chat...");
        disableDashboardChatInput(true, "Initializing general chat..."); // Keep dashboard chat disabled initially

        if (!keywordChartCanvas || !sentimentChartCanvas) { console.warn("[initializeUI] Canvas elements missing."); }
     }

    // Call initialization function when the DOM is ready
    initializeUI();

}); // End DOMContentLoaded