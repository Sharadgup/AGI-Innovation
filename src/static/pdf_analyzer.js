/**
 * Frontend Script for PDF Analyzer Page
 * Handles PDF Upload, Text Preview, and PDF-Specific Chat
 */
console.log("[PDF Analyzer JS] Script loaded.");

document.addEventListener('DOMContentLoaded', () => {
    console.log("[PDF Analyzer JS] DOM Content Loaded.");

    // --- Elements ---
    const uploadForm = document.getElementById('pdfUploadForm');
    const pdfFileInput = document.getElementById('pdfFile');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadProgressBar = uploadProgress?.querySelector('.progress-bar');
    const uploadStatus = document.getElementById('uploadStatus');
    const uploadError = document.getElementById('uploadError');
    const analysisSection = document.getElementById('analysisSection');
    const textPreview = document.getElementById('textPreview');
    // PDF Chat Elements
    const pdfChatContainer = document.getElementById('pdfChatContainer'); // Optional check later
    const pdfChatMessages = document.getElementById('pdfChatMessages');
    const pdfChatInput = document.getElementById('pdfChatInput');
    const sendPdfChatBtn = document.getElementById('sendPdfChatBtn');
    const pdfChatTypingIndicator = document.getElementById('pdfChatTypingIndicator');
    const pdfChatError = document.getElementById('pdfChatError');
    const currentAnalysisIdInput = document.getElementById('currentAnalysisId'); // Hidden input

    // --- State ---
    let pdfChatSocket; // Variable for the PDF chat socket connection

    // --- Initial Check for Upload Elements ---
    if (!uploadForm || !pdfFileInput || !uploadBtn) {
        console.error("[PDF Analyzer JS] Critical upload elements (form, input, button) not found! Upload functionality disabled.");
        // Optionally display a more user-friendly error message on the page
        const body = document.querySelector('body');
        if(body) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message'; // Use your error style
            errorDiv.textContent = 'Page Error: Upload elements missing. Please contact support.';
            errorDiv.style.display = 'block';
            body.prepend(errorDiv); // Add error at the top
        }
        return; // Stop if core upload elements are missing
    }

    // --- Event Listeners ---
    uploadForm.addEventListener('submit', handlePdfUpload);
    console.log("[PDF Analyzer JS] Upload form listener attached.");

    // Attach chat listeners only if chat elements exist
    if (sendPdfChatBtn && pdfChatInput) {
        sendPdfChatBtn.addEventListener('click', sendPdfChatMessage);
        pdfChatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !pdfChatInput.disabled) {
                e.preventDefault();
                sendPdfChatMessage();
            }
        });
         console.log("[PDF Analyzer JS] PDF Chat listeners attached.");
    } else {
        console.warn("[PDF Analyzer JS] PDF Chat input/button elements not found. Chat listener not attached.");
    }


    // --- Upload Functions ---

    function showUploadError(message) {
        console.error("[PDF Upload Error]", message);
        if(uploadError) { uploadError.textContent = message; uploadError.style.display = 'block';}
        if(uploadStatus) uploadStatus.textContent = '';
        if(uploadProgress) uploadProgress.style.display = 'none';
        if(uploadBtn) uploadBtn.disabled = false; // Re-enable button on error
    }
    function hideUploadError() {
        if(uploadError) { uploadError.style.display = 'none'; uploadError.textContent = ''; }
    }
    function setUploadProgress(percent) {
        // Ensure elements exist before trying to update
        if(uploadProgress && uploadProgressBar && uploadStatus) {
            uploadProgress.style.display = 'block';
            uploadProgressBar.style.width = percent + '%';
            uploadProgressBar.setAttribute('aria-valuenow', percent);
            uploadStatus.textContent = percent < 100 ? `Uploading (${percent}%)...` : `Processing...`; // Change text at 100%
            uploadStatus.style.color = '#6c757d'; // Neutral color during progress
        }
    }
    function setUploadStatus(message, isSuccess = true) {
         if(uploadStatus) {
             uploadStatus.textContent = message;
             uploadStatus.style.color = isSuccess ? 'green' : 'red'; // Indicate success/failure
         }
         if(uploadProgress) uploadProgress.style.display = 'none'; // Hide progress bar on completion/error
         if(uploadBtn) uploadBtn.disabled = false; // Re-enable button
    }

    async function handlePdfUpload(event) {
        event.preventDefault();
        console.log("[handlePdfUpload] Initiating...");
        hideUploadError(); // Clear previous errors

        if (!pdfFileInput.files || pdfFileInput.files.length === 0) { showUploadError("Please select a PDF file."); return; }
        const file = pdfFileInput.files[0];
        if (file.type !== "application/pdf") { showUploadError("Invalid file type. Only PDF allowed."); return; }
        if (file.size > 10 * 1024 * 1024) { // Example: 10MB limit
             showUploadError("File is too large (Max 10MB)."); return;
        }


        setUploadProgress(0); // Show progress bar starting at 0%
        if(uploadBtn) uploadBtn.disabled = true; // Disable button during upload
        uploadStatus.textContent = "Starting upload...";
        if(analysisSection) analysisSection.style.display = 'none'; // Hide old results
        if(pdfChatSocket?.connected) pdfChatSocket.disconnect(); // Disconnect old chat if exists

        const formData = new FormData();
        formData.append('pdfFile', file);

        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/pdf/upload', true); 

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) { setUploadProgress(Math.round((event.loaded / event.total) * 100)); }
            };

            xhr.onload = function() {
                if(uploadBtn) uploadBtn.disabled = false; // Re-enable button once loaded
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        console.log("Upload successful, response:", data);
                        setUploadStatus(`Processed: ${data.filename || 'file'}`, true);

                        // Display Text Preview
                        if (textPreview && data.text_preview) {
                            const sanitizedPreview = data.text_preview.replace(/</g, "<").replace(/>/g, ">");
                            textPreview.innerHTML = `<pre>${sanitizedPreview}</pre>`;
                        } else if (textPreview) { textPreview.innerHTML = `<p><i>Text preview unavailable or empty.</i></p>`; }

                        // Setup Chat if ID received
                        if (data.analysis_id) {
                            currentAnalysisIdInput.value = data.analysis_id;
                            if (analysisSection) analysisSection.style.display = 'block';
                            initializePdfChat(data.analysis_id); // Connect PDF chat socket
                        } else {
                            showUploadError("Processing ok, but no analysis ID received.");
                            if (analysisSection) analysisSection.style.display = 'none';
                        }
                    } catch (e) { console.error("Error parsing server response:", e, xhr.responseText); showUploadError("Invalid response from server."); if (analysisSection) analysisSection.style.display = 'none'; }
                } else { // Handle HTTP errors
                    let errorMsg = `Upload failed (Status: ${xhr.status})`;
                     try { const errData = JSON.parse(xhr.responseText); errorMsg = errData.error || errorMsg; } catch(e){}
                     console.error("Upload failed:", errorMsg); showUploadError(errorMsg); if (analysisSection) analysisSection.style.display = 'none';
                }
            };

            xhr.onerror = function() { console.error("Network error during upload."); showUploadError('Network error during upload.'); if (analysisSection) analysisSection.style.display = 'none'; if(uploadBtn) uploadBtn.disabled = false; };
            xhr.send(formData);

        } catch (error) { console.error("Error setting up upload:", error); showUploadError('Could not initiate upload.'); if (analysisSection) analysisSection.style.display = 'none'; if(uploadBtn) uploadBtn.disabled = false; }
    } // End handlePdfUpload


    // --- PDF Chat Functions ---
    function initializePdfChat(analysisId) {
        if (!analysisId) { console.error("Cannot initialize PDF chat without analysis ID."); return; }
        if(pdfChatSocket?.connected) { console.log("Disconnecting existing PDF chat socket."); pdfChatSocket.disconnect(); }

        console.log(`[PDF Chat Init] Initializing for analysis ID: ${analysisId}`);
        if (typeof io === 'undefined') { showPdfChatError("Chat library error."); return; }
        // Check if chat elements exist before trying to connect
        if (!pdfChatMessages || !pdfChatInput || !sendPdfChatBtn) {
             console.warn("[PDF Chat Init] PDF chat UI elements missing. Cannot initialize chat.");
             return;
        }

        try {
             pdfChatSocket = io('/pdf_chat', { // Ensure namespace is correct
                 reconnectionAttempts: 3 // Example: Limit reconnection attempts
             });
             setupPdfChatSocketListeners(analysisId); // Pass ID for context
             disablePdfChatInput(true, "Connecting to PDF chat...");
             pdfChatMessages.innerHTML = ''; // Clear previous chat messages
             appendPdfMessage("System", "Connected. Ask about the PDF content.", true);
        } catch(e) {
            console.error("[PDF Chat Init] Error:", e);
            showPdfChatError("Could not connect to PDF chat service.");
            disablePdfChatInput(true, "Chat unavailable.");
        }
    }

    function setupPdfChatSocketListeners(analysisId) { // analysisId passed for context, though not used in handlers here
         if (!pdfChatSocket) return;
         console.log("[PDF Chat Setup] Attaching listeners...");

         pdfChatSocket.on('connect', () => { console.log('[PDF Chat Event] connect: SID:', pdfChatSocket.id); hidePdfChatError(); disablePdfChatInput(false, "Ask about the PDF content..."); });
         pdfChatSocket.on('disconnect', (reason) => { console.log(`[PDF Chat Event] disconnect: ${reason}`); if (reason !== 'io client disconnect') { showPdfChatError("PDF chat lost. Reconnecting..."); disablePdfChatInput(true, "Reconnecting...");} else { disablePdfChatInput(true, "Chat disconnected."); } });
        pdfChatSocket.on('connect_error', (err) => { console.error(`[PDF Chat Event] connect_error: ${err.message}`); showPdfChatError(`PDF chat conn failed: ${err.message}`); disablePdfChatInput(true, "Connection failed."); });
        pdfChatSocket.on('receive_pdf_chat_message', (data) => { console.log('[PDF Chat Event] receive_pdf_chat_message:', data); if (data?.user && data.text) { appendPdfMessage(data.user, data.text); } else { appendPdfMessage('System', '[Invalid msg]', true); } });
        pdfChatSocket.on('error', (data) => { console.error('[PDF Chat Event] error:', data.message); showPdfChatError(`Server error: ${data.message || 'Unknown'}`); });
        pdfChatSocket.on('typing_indicator', (data) => { if (pdfChatTypingIndicator) { pdfChatTypingIndicator.style.display = data.isTyping ? 'flex' : 'none'; if (data.isTyping) scrollToBottom(pdfChatMessages); } });
    }

    function sendPdfChatMessage() {
        const currentId = currentAnalysisIdInput?.value; // Use optional chaining
        if (!currentId) { showPdfChatError("Error: Analysis ID missing."); console.error("Cannot send PDF chat message: Analysis ID input or value missing."); return; }
        if (!pdfChatSocket?.connected) { showPdfChatError("Not connected."); disablePdfChatInput(true, "Disconnected."); return; }
        if (!pdfChatInput || pdfChatInput.disabled) return;

        const messageText = pdfChatInput.value.trim(); if (!messageText) return;

        appendPdfMessage('User', messageText); pdfChatInput.value = '';
        console.log(`[PDF Chat Send] Emitting 'send_pdf_chat_message' for analysis ${currentId}`);
        try { pdfChatSocket.emit('send_pdf_chat_message', { text: messageText, analysis_id: currentId }); }
        catch(e) { console.error("PDF Chat Emit error:", e); showPdfChatError("Failed to send message."); }
    }

    function appendPdfMessage(user, text, isSystem = false) {
         if (!pdfChatMessages) return; const el = document.createElement('div'); el.classList.add('message'); if(isSystem){el.classList.add('system'); el.innerHTML=text;} else {el.classList.add(user.toLowerCase()==='ai'?'ai':'user'); const sText=text.replace(/</g,"<").replace(/>/g,">"); el.textContent=sText;} pdfChatMessages.appendChild(el); scrollToBottom(pdfChatMessages);
     }

    function disablePdfChatInput(disabled, placeholderText = "Ask about the PDF...") {
         if (pdfChatInput) { pdfChatInput.disabled = disabled; pdfChatInput.placeholder = placeholderText; }
         if (sendPdfChatBtn) { sendPdfChatBtn.disabled = disabled; }
    }

     function showPdfChatError(message) {
         if(pdfChatError) { pdfChatError.textContent = message; pdfChatError.style.display = 'block';}
         else { console.error("PDF Chat Error Div not found, msg:", message); }
     }
     function hidePdfChatError() { if(pdfChatError) { pdfChatError.style.display = 'none'; pdfChatError.textContent = ''; } }
     function scrollToBottom(element) { if(element) { element.scrollTop = element.scrollHeight; } }

     // --- Initial UI ---
     function initializePageUI() {
        console.log("[PDF Analyzer JS] Initializing Page UI...");
        if (analysisSection) analysisSection.style.display = 'none'; // Hide analysis at first
        hideUploadError();
        hidePdfChatError(); // Hide chat error too
        // Button enabled state handled by upload flow
     }
     initializePageUI();

}); // End DOMContentLoaded