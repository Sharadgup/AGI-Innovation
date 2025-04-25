// script.js (Combined & Corrected - Includes sendTranscript Debugging)

// Ensure the Socket.IO client library is included in your HTML:
// <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>

document.addEventListener('DOMContentLoaded', () => {
    // --- Get DOM Elements ---
    const micButton = document.getElementById('mic-button');
    const micIcon = document.getElementById('mic-icon');
    const statusMessage = document.getElementById('status-message');
    const userChatArea = document.getElementById('user-chat-area');
    const agentChatArea = document.getElementById('agent-chat-area');
    const exitButton = document.getElementById('exit-button');
    const dashboardButton = document.getElementById('dashboard-button');

    // *** VERIFY ALL ELEMENTS EXIST ***
    if (!micButton || !micIcon || !statusMessage || !userChatArea || !agentChatArea || !exitButton || !dashboardButton) {
        console.error("FATAL ERROR: One or more required DOM elements (mic-button, mic-icon, status-message, user-chat-area, agent-chat-area, exit-button, dashboard-button) were not found. Please check your HTML IDs.");
        if (statusMessage) statusMessage.textContent = "UI Error: Elements missing.";
        return; // Stop script execution
    }
    console.log("All required DOM elements found.");

    // --- Web Speech API Setup (with prefix check) ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const SpeechSynthesis = window.speechSynthesis;

    // --- Check for browser support ---
    if (!SpeechRecognition) {
        console.error("Web Speech API (SpeechRecognition/webkitSpeechRecognition) not supported.");
        statusMessage.textContent = "Voice input not supported by browser.";
        micButton.disabled = true; micButton.style.cursor = 'not-allowed'; micButton.title = "Voice input not supported"; micButton.style.backgroundColor = '#ccc';
        return;
    } else { console.log("SpeechRecognition API supported."); }
    if (!SpeechSynthesis) { console.warn("Speech Synthesis API not supported."); }
    else { console.log("SpeechSynthesis API supported."); }

    // --- Socket.IO Connection ---
    console.log("Attempting to connect to /voice_chat namespace...");
    // const socket = io('http://127.0.0.1:5001/voice_chat'); // Use full URL if needed
    const socket = io('/voice_chat');

    // --- Socket.IO Event Listeners ---
    socket.on('connect', () => {
        console.log('Socket connected to /voice_chat! SID:', socket.id);
        statusMessage.textContent = "Connected. Click mic.";
        micButton.disabled = false; micButton.style.cursor = 'pointer';
    });
    socket.on('connect_error', (err) => {
        console.error('Socket Connection Error to /voice_chat:', err.message);
        statusMessage.textContent = "Connection Error.";
        micButton.disabled = true; micButton.style.cursor = 'not-allowed';
    });
    socket.on('disconnect', (reason) => {
        console.log('Socket disconnected from /voice_chat:', reason);
        statusMessage.textContent = "Disconnected.";
        micButton.disabled = true; micButton.style.cursor = 'not-allowed';
    });
    socket.on('connection_ack', (data) => { console.log('Backend ACK:', data.message); });

    socket.on('receive_ai_voice_text', (data) => {
        console.log("Received 'receive_ai_voice_text':", data);
        if (!interactionActive) { console.warn("Interaction inactive, ignoring received message."); return; }
        try {
            if (data && data.text) {
                 displayMessage(data.text, 'agent');
                 speakText(data.text, data.lang);
            } else {
                 console.warn("Received voice response event, but data lacks text:", data);
                 displayMessage("[Received empty/invalid AI response]", 'agent');
            }
        } catch (error) { console.error("Error processing received AI message:", error); statusMessage.textContent = "Error displaying response.";}
        finally {
            // Re-enable mic only if interaction is still active
            if (interactionActive) {
                micButton.classList.remove('processing');
                micButton.disabled = false;
                statusMessage.textContent = "Click mic to speak";
                console.log("Mic button state after processing response: disabled=", micButton.disabled);
            }
        }
    });

    socket.on('error', (data) => {
        console.error('Received error event from backend:', data.message);
        statusMessage.textContent = `Error: ${data.message}`;
        if (interactionActive) { micButton.classList.remove('processing'); micButton.disabled = false; }
    });

    // --- Web Speech API Variables ---
    let recognition;
    let isRecording = false;
    let finalTranscript = '';
    let interactionActive = true;

    // --- Initialize Recognition Function ---
    const initializeRecognition = () => {
        console.log("Initializing SpeechRecognition...");
        if (recognition) { try { recognition.stop(); } catch (e) {console.warn("Error stopping previous recog:", e);} }
        try {
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onstart = () => {
                console.log(">>> EVENT: recognition.onstart fired <<<");
                isRecording = true; finalTranscript = '';
                micButton.classList.add('recording'); micIcon.classList.remove('fa-microphone'); micIcon.classList.add('fa-stop');
                statusMessage.textContent = "Listening...";
                clearPlaceholders();
            };

            recognition.onresult = (event) => {
                if (!interactionActive) return;
                let interimTranscript = '';
                finalTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    const transcriptPart = event.results[i][0].transcript;
                    if (event.results[i].isFinal) { finalTranscript += transcriptPart + ' '; }
                    else { interimTranscript += transcriptPart; }
                }
            };

            recognition.onspeechend = () => { console.log(">>> EVENT: recognition.onspeechend fired <<<"); };
            recognition.onaudioend = () => { console.log(">>> EVENT: recognition.onaudioend fired <<<"); };

            recognition.onend = () => {
                console.log(">>>> EVENT: recognition.onend FIRED! <<<<");
                const wasRecording = isRecording;
                isRecording = false;
                console.log(`onend: finalTranscript = "${finalTranscript}"`);
                console.log(`onend: interactionActive = ${interactionActive}`);
                micButton.classList.remove('recording');
                micIcon.classList.remove('fa-stop'); micIcon.classList.add('fa-microphone');

                if (!interactionActive) { statusMessage.textContent = "Interaction stopped."; micButton.disabled = false; return; }

                finalTranscript = finalTranscript.trim();
                if (finalTranscript) {
                    console.log("onend: finalTranscript has value, proceeding to 'Processing...'");
                    statusMessage.textContent = "Processing...";
                    micButton.classList.add('processing'); micButton.disabled = true;
                    displayMessage(finalTranscript, 'user');
                    sendTranscriptToBackendViaSocket(finalTranscript, recognition.lang);
                } else {
                    console.log("onend: finalTranscript is EMPTY.");
                    if (!statusMessage.textContent.includes("Error") && !statusMessage.textContent.includes("stopped")) { statusMessage.textContent = "No speech detected."; }
                    micButton.disabled = false; console.log("Mic button RE-ENABLED in onend (no final transcript).");
                }
            };

            recognition.onerror = (event) => {
                 console.error(">>> EVENT: recognition.onerror fired <<< Error Type:", event.error, "Msg:", event.message);
                 let userFriendlyError = `Voice input error: ${event.error}.`; // Simplified error message
                 if (event.error === 'no-speech') {userFriendlyError = "No speech detected.";}
                 else if (event.error === 'audio-capture') {userFriendlyError = "Microphone error.";}
                 else if (event.error === 'not-allowed') {userFriendlyError = "Permission denied.";}
                 else if (event.error === 'aborted') {userFriendlyError = "Listening stopped.";}

                 if (interactionActive) statusMessage.textContent = userFriendlyError;
                 isRecording = false;
                 micButton.classList.remove('recording', 'processing');
                 micIcon.classList.remove('fa-stop'); micIcon.classList.add('fa-microphone');
                 if (interactionActive) { micButton.disabled = false; console.log("Mic button RE-ENABLED on error."); }
            };
            console.log("SpeechRecognition initialized successfully.");
        } catch (initError) {
             console.error("FATAL: Error initializing SpeechRecognition instance:", initError);
             statusMessage.textContent = "Error initializing voice input.";
             if(micButton) micButton.disabled = true;
        }
    }

    // --- Initialize on Load ---
    initializeRecognition();

    // --- UI Event Listeners ---
    micButton.addEventListener('click', () => {
        console.log("Mic button CLICKED.");
        if (micButton.disabled) { console.warn("Mic button is disabled, click ignored."); return; }
        if (!socket.connected) { statusMessage.textContent = "Connecting..."; console.warn("Mic clicked but socket not connected."); return; }
        if (!interactionActive) { interactionActive = true; hideExitMessage(); }

        if (isRecording) {
            try { console.log("CLICK HANDLER: Attempting to STOP recognition..."); recognition.stop(); statusMessage.textContent = "Stopping..."; }
            catch(e) { console.error("CLICK HANDLER: Error calling recognition.stop():", e); /* Manual reset? */ }
        } else {
            if (SpeechSynthesis && SpeechSynthesis.speaking) { SpeechSynthesis.cancel(); }
            try { console.log("CLICK HANDLER: Attempting to START recognition..."); recognition.start(); }
            catch (error) {
                console.error("CLICK HANDLER: Error calling recognition.start():", error);
                if (error.name === 'InvalidStateError') { console.warn("Recognition in invalid state. Re-initializing..."); initializeRecognition(); statusMessage.textContent = "Voice input reset. Try again."; }
                else if (error.name === 'NotAllowedError') { statusMessage.textContent = "Permission denied. Allow microphone access."; micButton.disabled = false; return; }
                 else { statusMessage.textContent = "Could not start."; }
                 micButton.disabled = false; // Ensure usable if start fails
            }
        }
    });

    exitButton.addEventListener('click', () => {
        console.log("Exit clicked");
        interactionActive = false;
        if (isRecording) { recognition.abort(); }
        if (SpeechSynthesis && SpeechSynthesis.speaking) { SpeechSynthesis.cancel(); }
        statusMessage.textContent = "Interaction stopped. Click mic to restart.";
        micButton.classList.remove('recording', 'processing');
        micIcon.classList.remove('fa-stop'); micIcon.classList.add('fa-microphone');
        micButton.disabled = false; isRecording = false;
        // clearChatAreas(); // Optional
    });

    dashboardButton.addEventListener('click', () => {
        console.log("Back to Dashboard clicked - Implement navigation");
        alert("Dashboard navigation not implemented in this example.");
        // window.location.href = '/dashboard'; // Example redirect
    });

    // --- Helper Functions ---

    // ***** Function with Enhanced Logging *****
    function sendTranscriptToBackendViaSocket(transcript, language) {
        // DEBUG 1: Confirm function call
        console.log(">>> sendTranscriptToBackendViaSocket called <<<");
        console.log(`  Transcript: "${transcript.substring(0,50)}..."`);
        console.log(`  Language: ${language}`);

        // DEBUG 2: Check socket connection *immediately* before emit
        if (!socket || !socket.connected) {
             console.error("SOCKET NOT CONNECTED at the moment of sending! Aborting emit.");
             statusMessage.textContent = "Connection lost before sending.";
             // Reset button state fully
             micButton.classList.remove('processing');
             micButton.disabled = false;
             isRecording = false;
             micIcon.classList.remove('fa-stop');
             micIcon.classList.add('fa-microphone');
             return;
        }

        const payload = {
            text: transcript,
            lang: language || 'en-US'
        };
        console.log("Attempting to emit 'send_voice_text' via SocketIO with payload:", payload);

        try {
            // DEBUG 3: The actual emit call
            socket.emit('send_voice_text', payload);
            console.log("'send_voice_text' event emitted successfully.");
            // Status remains "Processing..." until response is received
        } catch (emitError) {
             // DEBUG 4: Catch errors during emit
             console.error("Error occurred during socket.emit('send_voice_text'):", emitError);
             statusMessage.textContent = "Error sending data.";
             // Reset button state fully if emit fails
             micButton.classList.remove('processing');
             micButton.disabled = false;
             isRecording = false;
             micIcon.classList.remove('fa-stop');
             micIcon.classList.add('fa-microphone');
        }
    }
    // ***** End of Enhanced Function *****

    function displayMessage(text, sender) {
        if (!text || !interactionActive) return;
        const chatArea = (sender === 'user') ? userChatArea : agentChatArea;
        const messageClass = (sender === 'user') ? 'user-message' : 'agent-message';
        const placeholder = chatArea.querySelector('.placeholder-text');
        if (placeholder && placeholder.style.display !== 'none') { placeholder.style.display = 'none'; }

        const messageBubble = document.createElement('div');
        messageBubble.classList.add('message-bubble', messageClass);
        messageBubble.textContent = text;
        chatArea.appendChild(messageBubble);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function speakText(text, lang = 'en-US') {
         if (!SpeechSynthesis || !text || !interactionActive) { console.log("Skipping speech synthesis."); return; }
         if (SpeechSynthesis.speaking || SpeechSynthesis.pending) { SpeechSynthesis.cancel(); }

         const utterance = new SpeechSynthesisUtterance(text);
         utterance.lang = lang; // Set language
         utterance.onerror = (event) => console.error("Speech synthesis error:", event.error);
         utterance.onend = () => console.log("Finished speaking response.");

         setTimeout(() => { if (interactionActive) SpeechSynthesis.speak(utterance); }, 100);
    }

    function clearPlaceholders() {
        const placeholders = document.querySelectorAll('.placeholder-text');
        placeholders.forEach(p => p.style.display = 'none');
    }
    function hideExitMessage() {
         if (statusMessage.textContent.includes("Interaction stopped")) { statusMessage.textContent = "Click mic to start"; }
    }
    function clearChatAreas() {
         userChatArea.innerHTML = '<p class="placeholder-text" style="display: block;">User chat cleared.</p>';
         agentChatArea.innerHTML = '<p class="placeholder-text" style="display: block;">Agent chat cleared.</p>';
    }

}); // End DOMContentLoaded