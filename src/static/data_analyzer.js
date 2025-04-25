/**
 * Frontend Script for Data Analyzer Upload Page (e.g., data_analyzer.html)
 * Handles file selection, validation, upload, and redirect to the cleaner page.
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("[Data Analyzer Upload] DOM Content Loaded for:", window.location.pathname);

    // --- Element Selection ---
    const fileInput = document.getElementById('analysisFile');
    const uploadButton = document.getElementById('uploadButton'); // Make sure button ID matches HTML
    const feedbackDiv = document.getElementById('upload-feedback'); // Feedback area
    const loadingIndicator = document.getElementById('loadingIndicator'); // Loading spinner/message

    // --- Element Existence Check ---
    // Essential elements for this script to function
    if (!fileInput || !uploadButton || !feedbackDiv || !loadingIndicator) {
        console.error("[Data Analyzer Upload] Script Error: One or more required HTML elements (analysisFile, uploadButton, upload-feedback, loadingIndicator) are missing on this page.");
        // Optionally display a user-facing error if elements are missing
        if(feedbackDiv) displayFeedback("Page setup error: Required elements missing.", true, false);
        return; // Stop execution if critical elements aren't found
    }
    console.log("[Data Analyzer Upload] All required elements found.");

    // --- Initial State ---
    // Disable upload button until a valid file is selected
    uploadButton.disabled = true;
    showLoading(false); // Ensure loading indicator is hidden initially
    clearFeedback();    // Clear any stale feedback

    // --- Event Listeners ---
    // Validate file and enable button on file selection
    fileInput.addEventListener('change', handleFileSelection);
    console.log("[Data Analyzer Upload] File input listener attached.");

    // Trigger upload on button click
    uploadButton.addEventListener('click', handleUpload);
    console.log("[Data Analyzer Upload] Upload button listener attached.");

    // --- File Selection and Validation ---
    function handleFileSelection() {
        if (fileInput.files && fileInput.files.length > 0) {
            const file = fileInput.files[0];
            console.log("[Data Analyzer Upload] File selected:", file.name, file.type, file.size);
            const validationError = validateFile(file); // Validate type and size
            if (validationError) {
                displayFeedback(validationError, true); // Show validation error
                uploadButton.disabled = true;       // Keep button disabled
                fileInput.value = '';               // Clear the invalid selection
            } else {
                // File is valid
                uploadButton.disabled = false; // Enable upload button
                clearFeedback();               // Clear any previous errors
                displayFeedback(`Selected: ${file.name}`, false, false); // Show selected file name
            }
        } else {
            // No file selected (e.g., user cancelled)
            uploadButton.disabled = true; // Disable button
            clearFeedback();              // Clear feedback
        }
    }

    // --- File Validation Logic ---
    function validateFile(file) {
        if (!file) return "No file selected.";

        // Check file type (adjust allowed types as needed)
        const allowedTypes = ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
        const allowedExtensions = ['.csv', '.xlsx']; // Check extension as fallback
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();

        if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
             console.warn(`Invalid file type detected. Type: ${file.type}, Extension: ${fileExtension}`);
             return `Invalid file type. Please select a CSV or XLSX file. Detected type: ${file.type || 'unknown'}`;
        }

        // Check file size (e.g., 50MB limit)
        const maxSizeMB = 50;
        const maxSize = maxSizeMB * 1024 * 1024;
        if (file.size > maxSize) {
            return `File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum size is ${maxSizeMB} MB.`;
        }
        if (file.size === 0) {
             return `File appears to be empty. Please select a valid file.`;
        }

        return null; // No validation errors
    }

    // --- Core Upload Logic ---
    async function handleUpload() {
        console.log('[Data Analyzer Upload] handleUpload initiated.');

        // Final checks before uploading
        if (!fileInput.files || fileInput.files.length === 0) {
             displayFeedback('Please select a file first.', true);
             uploadButton.disabled = true;
             return;
        }
        const file = fileInput.files[0];
        const validationError = validateFile(file);
        if (validationError) {
             displayFeedback(validationError, true);
             uploadButton.disabled = true;
             return;
        }

        // Prepare form data for sending the file
        const formData = new FormData();
        formData.append('analysisFile', file); // Key must match Flask request.files key

        // Update UI for upload state
        showLoading(true); // Show spinner
        uploadButton.disabled = true; // Disable button during upload
        displayFeedback('Uploading and processing, please wait...', false, false); // Indicate activity
        console.log('[Data Analyzer Upload] Sending fetch request to /data/analyzer/upload'); // Log correct endpoint

        try {
            // --- Perform the fetch request ---
            // Use the CORRECT endpoint including the blueprint prefix '/data'
            const response = await fetch('/data/analyzer/upload', {
                method: 'POST',
                body: formData,
                // Headers are typically set automatically by fetch for FormData
            });
            console.log('[Data Analyzer Upload] Received fetch response. Status:', response.status);

            // Process the server's response (handles JSON parsing, errors, redirect)
            await processUploadResponse(response, file.name);

        } catch (error) {
            // Catch network errors or other client-side issues during fetch
            console.error("[Data Analyzer Upload] Network or client-side upload error:", error);
            displayFeedback('Upload Error: Could not connect to the server. Please check your network connection and try again.', true);
            showLoading(false); // Hide loading on error
            uploadButton.disabled = false; // Re-enable button on error
        }
    } // --- End handleUpload ---


    // --- Process Server Response (Handles redirect on success) ---
    async function processUploadResponse(response, originalFileName) {
        let resultJson = null; // Initialize resultJson

        try {
            // Attempt to read the response body as text first for debugging
            const responseText = await response.text();
            console.log('[Data Analyzer Upload] Raw server response text:', responseText.substring(0, 500) + '...'); // Log start of text

            // Attempt to parse the response text as JSON
            resultJson = JSON.parse(responseText);
            console.log('[Data Analyzer Upload] Parsed JSON response:', resultJson);

        } catch (jsonError) {
            // Handle cases where the response is not valid JSON
            console.error("[Data Analyzer Upload] Failed to parse server response as JSON:", jsonError);
            const errorMsg = `Server Error: Received an unexpected response (Status: ${response.status}). Please check server logs.`;
            displayFeedback(errorMsg, true);
            showLoading(false);
            uploadButton.disabled = false; // Re-enable button
            return; // Stop processing
        }

        // --- Handle Response based on Status and Content ---
        if (response.ok && resultJson && resultJson.upload_id) {
            // --- SUCCESS CASE ---
            console.log('[Data Analyzer Upload] Upload successful. Preparing redirect...');
            const redirectId = resultJson.upload_id;
            const redirectUrl = `/data/cleaner/${redirectId}`; // CORRECT Redirect URL with '/data' prefix

            console.log(`[Data Analyzer Upload] Redirecting to: ${redirectUrl}`);

            // Provide success feedback before redirecting
            const successMsg = `Success! File '${resultJson.filename || originalFileName}' uploaded (${resultJson.rows} rows, ${resultJson.columns} columns). Redirecting to cleaner...`;
            displayFeedback(successMsg, false, false); // Show non-error, non-dismissing message

            // Delay redirect slightly so user can see success message (optional)
            setTimeout(() => {
                window.location.href = redirectUrl; // Perform the redirect
            }, 1500); // 1.5 second delay

        } else {
            // --- ERROR CASE (HTTP error or JSON missing expected fields) ---
            const errorMessage = resultJson?.error || // Prefer specific error from JSON
                                 `Upload failed (Status: ${response.status}). Please try again.`;
            console.error("[Data Analyzer Upload] Upload failed:", errorMessage, resultJson);
            displayFeedback(`Error: ${errorMessage}`, true); // Display error message
            showLoading(false); // Hide loading
            uploadButton.disabled = false; // Re-enable upload button
            fileInput.value = ''; // Clear file input on failed upload
        }
    } // --- End processUploadResponse ---


    // --- Helper UI Functions (Defined INSIDE DOMContentLoaded) ---

    /** Displays loading indicator and disables button */
    function showLoading(isLoading) {
        if (loadingIndicator) {
            loadingIndicator.style.display = isLoading ? 'block' : 'none';
        } else { console.warn("loadingIndicator element not found"); }
        // Keep button disabled while loading is explicitly shown
        if (uploadButton) uploadButton.disabled = isLoading;

    }

    /** Displays feedback messages to the user */
    function displayFeedback(message, isError = false, autoDismiss = true) {
        if (!feedbackDiv) {
            console.error("Feedback DIV not found, message:", message);
            alert(message); // Fallback
            return;
        }
        feedbackDiv.textContent = message;
        feedbackDiv.className = 'upload-feedback'; // Reset classes
        feedbackDiv.classList.add(isError ? 'error' : 'success');
        feedbackDiv.style.display = 'block'; // Make it visible

        // Clear message after a delay if not an error or instructed not to
        if (!isError && autoDismiss) {
            setTimeout(clearFeedbackAnimated, 3000); // Clear success messages after 3s
        }
        // Errors persist until the next action or explicit clear
    }

    /** Clears the feedback area */
    function clearFeedback() {
        if (feedbackDiv) {
            feedbackDiv.textContent = '';
            feedbackDiv.style.display = 'none';
            feedbackDiv.className = 'upload-feedback'; // Reset classes
        }
    }

    /** Clears feedback with a fade-out effect (optional) */
    function clearFeedbackAnimated() {
         if (feedbackDiv) {
             feedbackDiv.classList.add('fade-out');
             // Remove the element after the animation finishes
             setTimeout(() => {
                 clearFeedback();
                 feedbackDiv.classList.remove('fade-out'); // Clean up class
             }, 500); // Match animation duration in CSS
         }
    }
    // --- End Helper Functions ---

    console.log("[Data Analyzer Upload] Script initialization complete.");

}); // End DOMContentLoaded Event Listener