/**
 * Handles interactions for the Healthcare AI Assistant page.
 */
console.log("[Healthcare Agent JS] Script loaded.");

document.addEventListener('DOMContentLoaded', () => {
    console.log("[Healthcare Agent JS] DOM Content Loaded.");

    // --- Healthcare Agent Elements ---
    const queryInput = document.getElementById('healthcareQueryInput');
    const submitBtn = document.getElementById('submitHealthcareQueryBtn');
    const agentOutput = document.getElementById('healthcareAgentOutput');
    const loadingIndicator = document.getElementById('healthcareAgentLoading');
    const errorDiv = document.getElementById('healthcareAgentError');

    // --- Initial Check ---
    if (!queryInput || !submitBtn || !agentOutput) {
        console.error("[Healthcare Agent JS] Core UI elements (input, button, or output) not found. Functionality disabled.");
        if(loadingIndicator) loadingIndicator.style.display = 'none';
        if(errorDiv) errorDiv.style.display = 'none';
        return; // Stop if essential elements are missing
    }
    console.log("[Healthcare Agent JS] UI elements found.");

    // --- Event Listeners ---
    submitBtn.addEventListener('click', handleHealthcareQuery);
    queryInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !event.shiftKey && !submitBtn.disabled) {
            event.preventDefault();
            handleHealthcareQuery();
        }
    });
    console.log("[Healthcare Agent JS] Event listeners attached.");

    // --- Healthcare Agent Query Handler ---
    async function handleHealthcareQuery() {
        const query = queryInput.value.trim();
        if (!query) {
            showAgentError("Please enter a health-related question.");
            return;
        }

        console.log("[Healthcare Agent JS] Sending query:", query);
        setAgentLoading(true); // Show loading
        hideAgentError();      // Hide previous errors
        agentOutput.innerHTML = '<p><i>Processing your health query...</i></p>'; // Indicate processing

        try {
            // Fetch request to the dedicated Flask endpoint
            const response = await fetch('/agent/healthcare/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });
            console.log(`[Healthcare Agent JS] Rcvd status: ${response.status}`);

            if (!response.ok) {
                let errorMsg = `Error: ${response.status}`;
                try { const errData = await response.json(); errorMsg = errData.error || errorMsg; } catch(e) {}
                if(response.status === 401) { errorMsg = "Authentication required."; }
                throw new Error(errorMsg);
            }

            const data = await response.json();
            console.log("[Healthcare Agent JS] Rcvd data:", data);

            if (data.error) { throw new Error(data.error); }

            if (data.answer) {
                // Basic sanitization
                const sanitizedAnswer = data.answer.replace(/</g, "<").replace(/>/g, ">");
                agentOutput.innerHTML = `<p>${sanitizedAnswer.replace(/\n/g, '<br>')}</p>`; // Display formatted answer
            } else { throw new Error("Received an empty answer."); }

        } catch (error) {
            console.error("[Healthcare Agent JS] Fetch/Process Error:", error);
            showAgentError(`Failed: ${error.message}`);
            agentOutput.innerHTML = `<p><i>Sorry, could not process the health query. Remember to consult a medical professional for advice.</i></p>`;
        } finally {
            setAgentLoading(false); // Hide loading
        }
    }
    // ------------------------------------------

    // --- Healthcare Agent Helper Functions ---
     function setAgentLoading(isLoading) {
         if (loadingIndicator) { loadingIndicator.style.display = isLoading ? 'flex' : 'none'; }
         if (submitBtn) { submitBtn.disabled = isLoading; }
         if (queryInput) { queryInput.disabled = isLoading; }
     }
     function showAgentError(message) {
         console.error("[Healthcare Agent JS] Error:", message);
         if (errorDiv) { errorDiv.textContent = message; errorDiv.style.display = 'block'; }
         else { alert("Healthcare Agent Error: " + message); } // Fallback
     }
     function hideAgentError() { if (errorDiv) { errorDiv.style.display = 'none'; errorDiv.textContent = ''; } }
     // ---------------------------------------------

     // --- Initial UI State for Healthcare Agent ---
     function initializeAgentUI() {
         console.log("[Healthcare Agent JS] Initializing UI state...");
         hideAgentError();
         setAgentLoading(false); // Ensure loading is off
         if (agentOutput) agentOutput.innerHTML = "<p><i>The AI's informational response will appear here. Remember to consult a professional for medical advice.</i></p>";
         if (queryInput) queryInput.value = '';
     }
     initializeAgentUI(); // Run initial setup

}); // End DOMContentLoaded