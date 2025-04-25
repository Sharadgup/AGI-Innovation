/**
 * Handles interactions for the Education AI Assistant panel.
 * Assumes the necessary HTML elements exist with the specified IDs
 * on the page where this script is loaded (e.g., education_agent.html or dashboard.html).
 */

// Log immediately to confirm script loading
console.log("[Education Agent] Script loaded.");

// Wait for the DOM to be fully loaded before accessing elements
document.addEventListener('DOMContentLoaded', () => {
    console.log("[Education Agent] DOM Content Loaded. Initializing...");

    // --- Get References to Education Agent UI Elements ---
    const educationQueryInput = document.getElementById('educationQueryInput'); // Textarea for user input
    const submitEducationQueryBtn = document.getElementById('submitEducationQueryBtn'); // Button to send query
    const educationAgentOutput = document.getElementById('educationAgentOutput');   // Div to display chat messages/output
    const educationAgentLoading = document.getElementById('educationAgentLoading'); // Loading indicator element (e.g., a spinner div)
    const educationAgentError = document.getElementById('educationAgentError');     // Div to display specific errors for this agent

    // --- Initial Check & Graceful Degradation ---
    // If essential elements aren't found, log a warning and disable functionality
    // to prevent errors later in the script.
    if (!educationQueryInput || !submitEducationQueryBtn || !educationAgentOutput) {
        console.warn("[Education Agent] Core UI elements ('educationQueryInput', 'submitEducationQueryBtn', or 'educationAgentOutput') not found. Agent functionality disabled for this page.");
        // Attempt to hide related elements if they exist partially
        if(educationAgentLoading) educationAgentLoading.style.display = 'none';
        if(educationAgentError) educationAgentError.style.display = 'none';
        // Optionally disable the input/button if they were found but output wasn't
        if(educationQueryInput) educationQueryInput.disabled = true;
        if(submitEducationQueryBtn) submitEducationQueryBtn.disabled = true;
        return; // Stop script execution for this agent
    }
    console.log("[Education Agent] Required UI elements found.");

    // --- Attach Event Listeners ---
    // Handle button click
    submitEducationQueryBtn.addEventListener('click', handleEducationQuery);

    // Handle Enter key press in the textarea (ignore Shift+Enter)
    educationQueryInput.addEventListener('keypress', (event) => {
        // Check if Enter was pressed without the Shift key and the button isn't disabled
        if (event.key === 'Enter' && !event.shiftKey && !submitEducationQueryBtn.disabled) {
            event.preventDefault(); // Prevent default behavior (usually adding a newline)
            handleEducationQuery(); // Trigger the query submission
        }
    });
    console.log("[Education Agent] Event listeners attached.");

    // --- Main Query Handling Function ---
    async function handleEducationQuery() {
        const query = educationQueryInput.value.trim(); // Get text and remove leading/trailing whitespace

        // Basic validation: ensure query is not empty
        if (!query) {
            showEducationError("Please enter an education-related question.");
            // Optionally briefly highlight the input field
            // educationQueryInput.focus();
            // educationQueryInput.classList.add('input-error'); // Assuming you have CSS for this
            // setTimeout(() => educationQueryInput.classList.remove('input-error'), 1500);
            return; // Stop if query is empty
        }

        console.log("[Education Agent] Sending query:", query);
        setEducationLoading(true); // Show loading indicator, disable input/button
        hideEducationError();      // Clear any previous error messages
        // Clear previous output or show a placeholder message
        // educationAgentOutput.innerHTML = '<p><i>Fetching answer... Please wait.</i></p>';
        // Append user message to chat output immediately for better UX
        appendMessageToOutput('User', query);


        try {
            // --- API Call using Fetch ---
            // Ensure the URL includes the correct blueprint prefix ('/agent')
            const response = await fetch('/agent/education/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // Add other headers if needed (e.g., CSRF token)
                    // 'X-CSRFToken': getCookie('csrftoken') // Example CSRF
                },
                body: JSON.stringify({ query: query }) // Send the query in the request body
            });
            console.log(`[Education Agent] Received response status: ${response.status}`);

            // --- Handle HTTP Errors ---
            if (!response.ok) {
                let errorMsg = `Server Error: ${response.status}`; // Default error
                try {
                    // Attempt to parse JSON error response from Flask
                    const errData = await response.json();
                    // Use the specific error message from the backend if available
                    errorMsg = errData.error || errorMsg;
                } catch (e) {
                    // If response wasn't JSON, use the status text
                    errorMsg = `Server Error ${response.status}: ${response.statusText}`;
                    console.warn("[Education Agent] Response was not valid JSON:", await response.text()); // Log non-JSON response for debugging
                }
                 // Provide more user-friendly messages for common statuses
                 if(response.status === 401) { errorMsg = "Authentication required. Please ensure you are logged in."; }
                 else if(response.status === 404) { errorMsg = "Could not reach the agent endpoint (404 Not Found). Please check configuration."; } // More specific 404
                 else if(response.status === 503) { errorMsg = "The AI model service appears to be temporarily unavailable. Please try again later."; }
                 else if (response.status >= 500) {errorMsg = "An unexpected server error occurred. Please try again later."; }

                // Throw an error to be caught by the catch block
                throw new Error(errorMsg);
            }

            // --- Process Successful Response ---
            const data = await response.json(); // Parse the JSON payload
            console.log("[Education Agent] Received data:", data);

            // Check for application-level errors within the JSON (e.g., { "error": "..." })
            if (data.error) {
                 throw new Error(data.error);
            }

            // Display the AI's answer
            if (data.answer) {
                // Simple sanitization to prevent basic HTML injection - VERY basic.
                // For production, use a proper sanitization library (like DOMPurify).
                // const sanitizedAnswer = data.answer
                //                         .replace(/</g, "<")
                //                         .replace(/>/g, ">");

                // Append AI message to chat output
                appendMessageToOutput('AI', data.answer); // Pass raw answer for formatting in append function
                educationQueryInput.value = ''; // Clear input on success
            } else {
                 // Handle case where server responded 200 OK but no answer was provided
                 console.warn("[Education Agent] Received 200 OK but no 'answer' field in response data:", data);
                 throw new Error("Received an empty or incomplete answer from the agent.");
            }

        // --- Catch Block for Errors ---
        } catch (error) {
            console.error("[Education Agent] Fetch/Process Error:", error);
            // Display the error message to the user
            showEducationError(`Failed to get answer: ${error.message}`);
            // Optionally display error in chat output too
            appendMessageToOutput('Error', `Sorry, an error occurred: ${error.message}`);
        } finally {
            // --- Cleanup ---
            setEducationLoading(false); // Hide loading indicator and re-enable input/button
        }
    }
    // --- End handleEducationQuery ---

    // --- Helper Function to Append Messages to Output ---
    function appendMessageToOutput(sender, text) {
        if (!educationAgentOutput) return; // Guard clause

        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender.toLowerCase()); // e.g., 'message user', 'message ai', 'message error'

        const senderSpan = document.createElement('strong');
        senderSpan.textContent = `${sender}: `;

        const textNode = document.createElement('span');
        // Basic Markdown-like formatting for display (bold, italics, newlines)
        // Replace **bold** with <strong>
        let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Replace *italic* with <em> (use _italic_ or *italic* consistently)
        formattedText = formattedText.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // Replace newlines with <br> tags
        formattedText = formattedText.replace(/\n/g, '<br>');
        // IMPORTANT: Assigning to innerHTML requires careful consideration of sanitization
        // if the text comes from potentially untrusted sources (even AI output).
        // The basic sanitization above is minimal. Use a library like DOMPurify if needed.
        textNode.innerHTML = formattedText;

        messageDiv.appendChild(senderSpan);
        messageDiv.appendChild(textNode);

        // Clear initial placeholder if it exists
        const placeholder = educationAgentOutput.querySelector('p > i');
        if (placeholder && placeholder.textContent.includes('appear here')) {
            educationAgentOutput.innerHTML = '';
        }

        educationAgentOutput.appendChild(messageDiv);

        // Auto-scroll to the bottom
        educationAgentOutput.scrollTop = educationAgentOutput.scrollHeight;
    }

    // --- Helper Function to Manage Loading State ---
     function setEducationLoading(isLoading) {
         // Show/hide loading indicator element
         if (educationAgentLoading) {
             educationAgentLoading.style.display = isLoading ? 'flex' : 'none'; // Use flex or block as appropriate
         } else { console.warn("Education loading indicator element not found."); }

         // Disable/enable button
         if (submitEducationQueryBtn) {
             submitEducationQueryBtn.disabled = isLoading;
             submitEducationQueryBtn.textContent = isLoading ? 'Sending...' : 'Send Query'; // Update button text
         } else { console.warn("Education submit button not found."); }

          // Disable/enable input textarea
          if (educationQueryInput) {
             educationQueryInput.disabled = isLoading;
             educationQueryInput.placeholder = isLoading ? 'Waiting for response...' : 'Ask an education question...';
         }
     }

     // --- Helper Function to Show Errors ---
     function showEducationError(message) {
         console.error("[Education Agent] Error:", message);
         if (educationAgentError) {
             educationAgentError.textContent = message;
             educationAgentError.style.display = 'block'; // Make error visible
             // Optional: auto-hide error after a delay
             // setTimeout(hideEducationError, 5000); // Hide after 5 seconds
         } else {
             // Fallback if specific error div isn't found
             console.error("Education error div not found. Using alert.");
             alert("Education Agent Error: " + message);
         }
     }

     // --- Helper Function to Hide Errors ---
     function hideEducationError() {
          if (educationAgentError) {
             educationAgentError.style.display = 'none'; // Hide error element
             educationAgentError.textContent = ''; // Clear text content
         }
     }
     // --- End Helper Functions ---

     // --- Initialize the UI State on Load ---
     function initializeEducationAgentUI() {
         console.log("[Education Agent] Initializing Agent UI state...");
         hideEducationError();       // Ensure no errors are shown initially
         setEducationLoading(false); // Ensure loading indicator is off, button/input enabled
         if (educationAgentOutput) { // Set initial placeholder text
            educationAgentOutput.innerHTML = "<p><i>Ask the Education AI Assistant a question. The answer will appear here.</i></p>";
         }
         if (educationQueryInput) {
             educationQueryInput.value = ''; // Clear any leftover input
             educationQueryInput.focus();    // Focus the input field for immediate typing
         }
     }
     initializeEducationAgentUI(); // Call the initialization function

    console.log("[Education Agent] Initialization complete.");

}); // End DOMContentLoaded Listener