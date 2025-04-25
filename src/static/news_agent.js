/**
 * news_agent.js
 * Frontend logic for the News AI Agent page.
 * Handles fetching news, displaying articles and notifications,
 * theme switching, summarization via backend API, and Text-to-Speech.
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOMContentLoaded fired for:", window.location.pathname); // Debug: Check DOM ready

    // --- DOM Element References ---
    const mainNewsContentDiv = document.getElementById('main-news-content');
    const notificationPanelDiv = document.getElementById('notification-panel');
    const statusUpdateSpan = document.getElementById('status-update');
    const liveHeadlinesSpan = document.getElementById('live-headlines');
    const summarizeReadBtn = document.getElementById('summarize-read-btn');
    const stopReadingBtn = document.getElementById('stop-reading-btn');
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const notificationTemplate = document.getElementById('notification-template');
    const mainNewsControlsDiv = document.querySelector('.main-news-controls');

    // --- Element Existence Check (Initial & Critical) ---
    // Checks if essential HTML elements were found. Logs errors if not.
    console.log("--- Running Initial Element Checks ---");
    const criticalElements = {
        mainNewsContentDiv, notificationPanelDiv, statusUpdateSpan,
        liveHeadlinesSpan, summarizeReadBtn, stopReadingBtn,
        themeToggleBtn, notificationTemplate, mainNewsControlsDiv
        // Add any other elements your script critically relies on
    };
    let allElementsFound = true;
    for (const key in criticalElements) {
        console.log(`Element check - ${key}:`, criticalElements[key]); // Log element reference or null
        if (!criticalElements[key]) {
            console.error(`News Agent Script Error: UI Element missing: #${key}. Check HTML ID.`);
            allElementsFound = false;
        }
    }
     if (!allElementsFound) {
          console.error("News Agent Script Error: Essential page elements are missing. Aborting initial setup. Check HTML IDs match JS getElementById calls.");
          // Provide user feedback if possible
          if (statusUpdateSpan) statusUpdateSpan.textContent = "Status: Page Error!";
          if (mainNewsContentDiv) mainNewsContentDiv.innerHTML = "<p class='text-danger'>Page failed to initialize correctly due to missing elements.</p>";
          return; // Stop script execution if essential elements are missing
     }
     console.log("--- Initial Element Checks Passed (All essential elements found) ---");


    // --- State Variables ---
    let currentMainArticle = null; // Stores the full article object currently in the main view
    let lastFetchTime = 0;         // Timestamp of the last successfully PROCESSED fetch to avoid race conditions
    let knownNotificationUrls = new Set(); // Tracks URLs already shown in notifications to prevent duplicates
    let isReading = false;          // Flag for Text-to-Speech (TTS) state
    let pollingIntervalId = null;   // To store the interval ID for potential clearing later
    const POLLING_INTERVAL = 30000; // Fetch news every 30 seconds (30000 ms). Adjust as needed.

    // --- Helper Functions ---

    /**
     * Shows/hides a loading indicator element and disables controls in its parent panel.
     * @param {string} elementId - The ID of the loading indicator element.
     * @param {boolean} show - True to show loading, false to hide.
     */
    function showLoading(elementId, show = true) {
        // console.log(`showLoading called for ${elementId}, show=${show}`); // Optional detailed log
        const indicator = document.getElementById(elementId);
        if (indicator) {
            indicator.style.display = show ? 'flex' : 'none'; // Use flex for centering content usually
            // Disable controls within the relevant panel while loading
            const parentPanel = indicator.closest('.panel, .main-news-display-area');
            if (parentPanel) {
                const controls = parentPanel.querySelectorAll('button, input, select');
                controls.forEach(control => control.disabled = show);
            }
        } else {
            // Log a warning if the specified loading indicator doesn't exist in the HTML
            // console.warn(`Loading indicator element not found: ${elementId}`);
        }
    }

    /**
     * Updates the status text message displayed in the bottom bar.
     * @param {string} message - The message to display.
     * @param {boolean} isError - True if the message indicates an error (styles differently).
     */
    function updateStatus(message, isError = false) {
        console.log(`updateStatus called: msg='${message}', isError=${isError}`); // Debug status update
        if (statusUpdateSpan) {
            statusUpdateSpan.textContent = `Status: ${message}`;
            // Use CSS variables for theme compatibility. Add/remove an error class.
            statusUpdateSpan.style.color = isError ? 'var(--status-text-light)' : 'inherit'; // Inherit default text color
            statusUpdateSpan.classList.toggle('status-error', isError); // Assumes a .status-error class in CSS for red color
        } else {
             console.error("statusUpdateSpan element not found! Cannot update status.");
        }
    }

    /**
     * Updates the live headlines text in the bottom bar. Usually shows a generic message or clears.
     * @param {string} text - The text to display (e.g., "Live headlines showing.").
     */
    function updateLiveHeadlines(text = "") {
         console.log(`updateLiveHeadlines called: text='${text}'`); // Debug headline update
         if (liveHeadlinesSpan) {
             // Wrap text in <strong> if present for emphasis
             liveHeadlinesSpan.innerHTML = text ? `<strong>${text}</strong>` : '';
         } else {
              console.warn("liveHeadlinesSpan element not found! Cannot update headlines.");
         }
    }

    /**
     * Formats an ISO date string into a relative time string (e.g., "5m ago", "2h ago") or a formatted date.
     * @param {string} dateString - The ISO 8601 date string.
     * @returns {string} Formatted date/time string.
     */
    function formatTimeAgo(dateString) {
        if (!dateString) return '';
        try {
            const date = new Date(dateString);
            const now = new Date();
            const secondsPast = (now.getTime() - date.getTime()) / 1000;

            if (isNaN(secondsPast) || secondsPast < 0) return 'in future'; // Handle invalid or future dates
            if (secondsPast < 60) return `${Math.round(secondsPast)}s ago`;
            if (secondsPast < 3600) return `${Math.round(secondsPast / 60)}m ago`;
            if (secondsPast <= 86400 * 2) return `${Math.round(secondsPast / 3600)}h ago`; // Show hours up to 2 days

            // Format older dates simply (e.g., "Apr 23, 2025")
            const options = { year: 'numeric', month: 'short', day: 'numeric' };
            return date.toLocaleDateString(undefined, options); // Use browser's locale default

        } catch (e) {
            console.error("Error parsing date:", dateString, e);
            return dateString; // Return original string if parsing fails
        }
    }

    // --- News Fetching & Display Logic ---

    /** Fetches news from the backend '/fetch_live_news' endpoint and initiates processing. */
    async function fetchNews() {
        console.log("--- fetchNews initiated ---");
        console.log("Checking NEWS_API_AVAILABLE flag:", window.NEWS_API_AVAILABLE);

        // Stop immediately if the API key wasn't available when the page loaded
        if (!window.NEWS_API_AVAILABLE) {
            updateStatus("News API Key missing on server", true);
            showLoading('mainNewsLoading', false); // Hide loading indicator if it was shown
            if (mainNewsContentDiv) mainNewsContentDiv.innerHTML = '<p class="placeholder-text text-danger">News Agent Disabled: API Key Missing.</p>';
            console.log("fetchNews aborted: API key not available (checked via window.NEWS_API_AVAILABLE).");
            // Stop polling if the key is missing
            if (pollingIntervalId) {
                clearInterval(pollingIntervalId);
                pollingIntervalId = null;
                console.log("Polling stopped due to missing API key.");
            }
            return; // Exit the function
        }

        updateStatus("Fetching live news...");
        showLoading('mainNewsLoading', true); // Show loading indicator for the main news area

        try {
            console.log("Sending request to /fetch_live_news");
            const response = await fetch('/fetch_live_news'); // Use GET by default
            console.log("Fetch response received. Status:", response.status);

            // Get raw text first for detailed debugging in case of non-JSON response
            const responseText = await response.text();
            console.log("Raw response text (first 500 chars):", responseText.substring(0, 500) + (responseText.length > 500 ? '...' : ''));

            let data;
            try {
                data = JSON.parse(responseText); // Attempt to parse the raw text as JSON
                console.log("Parsed response data:", data);
            } catch (jsonError) {
                console.error("Failed to parse server response as JSON:", jsonError);
                // Construct a more informative error message including status and response preview
                throw new Error(`Server returned non-JSON response (Status: ${response.status}). Response starts with: "${responseText.substring(0, 100)}..."`);
            }

            // Check both the HTTP status code and the 'status' field in the parsed JSON data
            if (!response.ok || data.status !== 'ok') {
                // Prioritize error message from the JSON data if available
                const errorMessage = data.error || data.message || `Unknown API error (Status: ${response.status})`;
                console.error("Fetch error response from server:", data);
                throw new Error(errorMessage); // Throw the error to be caught by the outer catch block
            }

            // --- Success Path ---
            if (data.articles && Array.isArray(data.articles)) {
                const fetchTimestamp = Date.now(); // Timestamp for this batch of articles
                console.log(`Fetched ${data.articles.length} articles. Processing...`);
                processNews(data.articles, fetchTimestamp); // Process the valid articles
                updateStatus("News updated successfully.", false); // Update status bar
                updateLiveHeadlines("Live headlines showing."); // Update headline indicator
            } else {
                console.log("No 'articles' array found or it's empty in the response.");
                updateStatus("No new articles found in this update.", false);
                // Don't clear headlines if previous ones were showing, maybe just indicate no *new* ones?
                // updateLiveHeadlines(""); // Optional: Clear headlines if no articles
            }

        } catch (error) {
            // Catch errors from fetch itself (network) or thrown errors from response handling
            console.error("Error during fetchNews operation:", error);
            updateStatus(`Error fetching news: ${error.message || error}`, true); // Display error
            updateLiveHeadlines(""); // Clear headlines on error
        } finally {
            // This block always executes, regardless of success or error
            console.log("--- fetchNews finally block ---");
            showLoading('mainNewsLoading', false); // Ensure loading indicator is hidden
        }
    }

    /**
     * Processes an array of fetched articles. Updates the main display with the latest
     * article if it's new, and adds new, unseen articles to the notification panel.
     * @param {Array} articles - Array of article objects from the API.
     * @param {number} fetchTimestamp - The timestamp when this batch was fetched.
     */
    function processNews(articles, fetchTimestamp) {
         console.log(`processNews called. Articles: ${articles.length}, FetchTime: ${fetchTimestamp}, Last Processed Time: ${lastFetchTime}`);
        // Prevent processing older data if fetches overlap or arrive out of order
        if (fetchTimestamp <= lastFetchTime) {
            console.log("Skipping processNews: fetched data timestamp is not newer than last processed.");
            return;
        }

        // 1. Update Main Display Area
        const latestArticle = articles.length > 0 ? articles[0] : null;
        // Update main display only if there's a new latest article (based on URL)
        // or if nothing is currently displayed
        if (latestArticle && latestArticle.url && latestArticle.url !== currentMainArticle?.url) {
            console.log("New latest article found, updating main display:", latestArticle.title);
            displayMainArticle(latestArticle);
        } else if (!currentMainArticle && latestArticle && latestArticle.url) {
            // If main display is empty, show the first valid article from the fetch
            console.log("No current main article, displaying first fetched article:", latestArticle.title);
            displayMainArticle(latestArticle);
        } else {
             console.log("Main article content not updated (latest article unchanged or no valid articles).");
        }

        // 2. Update Notification Panel
        let newNotifications = 0;
        // Clear the initial "Waiting..." message if it exists and we have articles
        const waitingMessage = notificationPanelDiv?.querySelector('.text-muted.small.p-2');
        if (articles.length > 0 && waitingMessage) {
             console.log("Clearing 'Waiting...' message from notifications panel.");
             notificationPanelDiv.innerHTML = '';
        }

        if (notificationPanelDiv) {
            // Iterate backwards through the fetched articles to prepend newest notifications first
            for (let i = articles.length - 1; i >= 0; i--) {
                 const article = articles[i];
                 // Add notification only if article has a URL and title, and we haven't seen the URL before
                 if (article && article.url && article.title && !knownNotificationUrls.has(article.url)) {
                     addNotification(article);         // Create and prepend the notification element
                     knownNotificationUrls.add(article.url); // Add URL to the set of seen URLs
                     newNotifications++;
                 }
             }
             // Optional: Limit the total number of notifications displayed
             const maxNotifications = 50;
             while (notificationPanelDiv.children.length > maxNotifications) {
                 const oldestNotification = notificationPanelDiv.lastElementChild; // Get the oldest item (at the bottom)
                 if (oldestNotification) {
                     const urlToRemove = oldestNotification.dataset.url; // Get URL from data attribute
                     if (urlToRemove) {
                         knownNotificationUrls.delete(urlToRemove); // Remove from seen set
                     }
                     notificationPanelDiv.removeChild(oldestNotification); // Remove from DOM
                 } else {
                     break; // Should not happen if children exist
                 }
             }
        } else {
             console.warn("Notification panel div not found, cannot add notifications.");
        }

         console.log(`Processed news. Added ${newNotifications} new notifications. Total known URLs in set: ${knownNotificationUrls.size}`);
         lastFetchTime = fetchTimestamp; // IMPORTANT: Update timestamp ONLY after successful processing
    }

    /**
     * Renders a single article's details in the main display area.
     * @param {object} article - The article object (with mapped fields).
     */
    function displayMainArticle(article) {
        console.log("Attempting to display main article:", article?.title);
        if (!article || !article.url) { // Require at least URL and implicitly title for display
            console.warn("Attempted to display invalid or incomplete article data:", article);
            return;
        }
        // Update the state
        currentMainArticle = article;

        if (!mainNewsContentDiv || !mainNewsControlsDiv) {
            console.error("Cannot display main article, essential DOM elements missing.");
            return;
        }

        // Build HTML content safely
        let contentHtml = '';
        // Add image with lazy loading and basic error handling
        if (article.urlToImage) {
            contentHtml += `<img src="${article.urlToImage}" alt="Image for ${article.title || 'article'}" class="img-fluid mb-3" loading="lazy" style="max-height: 300px; object-fit: cover;" onerror="this.style.display='none'; console.warn('Image failed to load: ${article.urlToImage}');">`;
        }
        contentHtml += `<h3>${article.title}</h3>`; // Title is required by this point
        // Add source and time if available
        if (article.source?.name || article.publishedAt) {
             contentHtml += `<p class="text-muted small mb-2">`;
             if(article.source?.name) contentHtml += `Source: ${article.source.name}`;
             if(article.source?.name && article.publishedAt) contentHtml += ` | `;
             if(article.publishedAt) contentHtml += `Published: ${formatTimeAgo(article.publishedAt)}`;
             contentHtml += `</p>`;
        }
        // Get text content (mapped from 'text' field in backend)
        const articleText = article.content || article.description || ''; // Backend maps 'text' to both
        contentHtml += `<p>${articleText || '<em class="text-muted">No text content available for this article.</em>'}</p>`;

        // Link to original source
        contentHtml += `<a href="${article.url}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-secondary btn-sm">Read Full Story <i class="fas fa-external-link-alt fa-xs"></i></a>`;

        // Update the DOM
        mainNewsContentDiv.innerHTML = contentHtml;
        mainNewsContentDiv.classList.remove('wavy-background'); // Remove placeholder style
        mainNewsControlsDiv.style.display = 'block'; // Show controls (Summarize/Read)

        // Enable summarize button only if there's actual text content
        summarizeReadBtn.disabled = !articleText;

        // Stop any previous TTS when a new article is displayed
        stopReading();
        console.log("Main article display updated.");
    }

    /**
     * Creates a notification item from an article object and prepends it to the notification panel.
     * @param {object} article - The article object (with mapped fields).
     */
    function addNotification(article) {
         // console.log("Adding notification for:", article?.title); // Optional log
         if (!notificationTemplate || !notificationPanelDiv) {
             console.warn("Cannot add notification, template or panel missing.");
             return;
         }
         // Ensure necessary data exists
         if (!article || !article.url || !article.title) {
              console.warn("Skipping notification for incomplete article data:", article);
              return;
         }

         try {
             // Clone the template content
             const notificationClone = notificationTemplate.content.cloneNode(true);
             const itemDiv = notificationClone.querySelector('.notification-item');
             if (!itemDiv) { console.error("Notification template structure error: missing .notification-item"); return; }

             // Store URL for potential removal later
             itemDiv.dataset.url = article.url;

             // Find elements within the cloned template
             const sourceEl = itemDiv.querySelector('.notification-source');
             const titleEl = itemDiv.querySelector('.notification-title');
             const timeEl = itemDiv.querySelector('.notification-time');

             // Populate the elements, handling potentially missing data
             if (sourceEl) sourceEl.textContent = article.source?.name || 'Unknown Source';
             if (titleEl) titleEl.textContent = article.title;
             if (timeEl) timeEl.textContent = formatTimeAgo(article.publishedAt);

             // Add click listener to load this article into the main view
             itemDiv.addEventListener('click', (e) => {
                 e.preventDefault();
                 console.log("Notification clicked:", article.title);
                 displayMainArticle(article); // Update main display with this article
                 if (mainNewsContentDiv) mainNewsContentDiv.scrollTop = 0; // Scroll main view up
             });

             // Prepend the new notification to the top of the panel
             notificationPanelDiv.prepend(notificationClone);

         } catch(e) {
              // Log errors during element creation/population
              console.error("Error creating notification element:", e);
         }
    }

    // --- Summarization and Text-to-Speech (TTS) ---

    /** Handles the click event for the 'Summarize & Read' button. */
    async function handleSummarizeAndRead() {
        console.log("handleSummarizeAndRead initiated.");
        // Check if there's an article loaded and TTS isn't already active
        if (!currentMainArticle || isReading) {
             console.warn("Summarize aborted: No current article selected or TTS already active.");
             return;
        }

        // Get the text content to summarize (prioritize 'content', fallback to 'description')
        const content = currentMainArticle.content || currentMainArticle.description;
        const title = currentMainArticle.title || 'Article'; // Use title for context

        if (!content) {
            console.warn("No content available in the current article to summarize.");
            alert("No text content available in this article to summarize.");
            return;
        }

        // Update UI state: disable button, show loading, update status
        summarizeReadBtn.disabled = true;
        if(stopReadingBtn) stopReadingBtn.style.display = 'none';
        showLoading('summaryLoading', true);
        updateStatus("Summarizing article...");
        console.log(`Sending content (title: ${title}) for summarization (first 80 chars):`, content.substring(0, 80) + "...");

        try {
            const apiUrl = '/summarize_news';
            const payload = { content: content, title: title };
            console.log("Calling fetchApi for summarization:", apiUrl, payload);
            const result = await fetchApi(apiUrl, 'POST', payload); // Use helper for fetch
            console.log("Summarization API result:", result);

            showLoading('summaryLoading', false); // Hide loading indicator

            // Check if the API call was successful and returned a valid summary
            if (result.ok && result.data.summary && !result.data.summary.startsWith("[AI")) {
                console.log("Summary received, calling speakText:", result.data.summary);
                updateStatus("Summary complete. Reading aloud...", false);
                speakText(result.data.summary); // Initiate TTS with the summary
            } else {
                 // Handle errors reported by the backend or invalid summaries
                 throw new Error(result.data.error || result.data.summary || "Failed to get valid summary from server.");
            }
        } catch (error) {
             // Handle fetch errors or errors thrown from response check
             console.error("Error in handleSummarizeAndRead:", error);
             updateStatus(`Summarization Error: ${error.message}`, true);
             showLoading('summaryLoading', false);
             // Re-enable the button only if there's content to allow retry
             summarizeReadBtn.disabled = !content;
        }
    }

    /**
     * Uses the browser's SpeechSynthesis API to read the provided text aloud.
     * @param {string} text - The text to be spoken.
     */
    function speakText(text) {
         console.log("speakText called with text (first 80 chars):", text.substring(0, 80) + "...");
        // Check for browser support
        if (!('speechSynthesis' in window)) {
            console.error("TTS not supported by this browser.");
            alert("Sorry, your browser doesn't support Text-to-Speech.");
            updateStatus("TTS not supported by browser.", true);
            // Re-enable button if applicable
            if(summarizeReadBtn) summarizeReadBtn.disabled = !(currentMainArticle?.content || currentMainArticle?.description);
            return;
        }

        // Stop any speech that might be ongoing from a previous action
        stopReading();

        // Create the utterance object
        const utterance = new SpeechSynthesisUtterance(text);

        // Optional: Configure voice, rate, pitch, language
        // utterance.lang = 'en-US'; // Set language if needed (helps select appropriate voice)
        // utterance.rate = 1; // Speed (0.1 to 10)
        // utterance.pitch = 1; // Pitch (0 to 2)
        // Choose a specific voice (requires waiting for voices):
        // window.speechSynthesis.onvoiceschanged = () => {
        //     const voices = window.speechSynthesis.getVoices();
        //     utterance.voice = voices.find(voice => voice.lang === 'en-US'); // Find a specific voice
        // };

        // --- Event Handlers for the Utterance ---
        utterance.onstart = () => {
             console.log("TTS playback started.");
             isReading = true;
             if(summarizeReadBtn) summarizeReadBtn.disabled = true; // Keep disabled while reading
             if(stopReadingBtn) stopReadingBtn.style.display = 'inline-block'; // Show the stop button
             updateStatus("Reading summary aloud...", false);
        };

        utterance.onend = () => {
            console.log("TTS playback finished naturally.");
            isReading = false;
            // Re-enable summarize button ONLY if there is content in the currently displayed article
            if(summarizeReadBtn) summarizeReadBtn.disabled = !(currentMainArticle?.content || currentMainArticle?.description);
            if(stopReadingBtn) stopReadingBtn.style.display = 'none'; // Hide stop button
            updateStatus("Finished reading summary.", false);
        };

        utterance.onerror = (event) => {
             console.error("TTS error occurred:", event.error, event);
             isReading = false; // Reset state on error
             if(summarizeReadBtn) summarizeReadBtn.disabled = !(currentMainArticle?.content || currentMainArticle?.description);
             if(stopReadingBtn) stopReadingBtn.style.display = 'none';
             updateStatus(`TTS Error: ${event.error}`, true); // Display error status
        };

        // --- Initiate Speech ---
        // Use a small timeout; browsers sometimes need a moment before speaking
        setTimeout(() => {
            console.log("Issuing speechSynthesis.speak command.");
            window.speechSynthesis.speak(utterance);
        }, 100); // 100ms delay

    }

    /** Stops any currently active or pending speech synthesis. */
    function stopReading() {
        // Check if speech synthesis is available and currently speaking
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
            console.log("Stopping TTS playback via cancel().");
            window.speechSynthesis.cancel(); // Cancels current and pending utterances

            // Reset state immediately as 'onend' might not fire reliably after cancel
            isReading = false;
            if(summarizeReadBtn) summarizeReadBtn.disabled = !(currentMainArticle?.content || currentMainArticle?.description);
            if(stopReadingBtn) stopReadingBtn.style.display = 'none';
            updateStatus("Reading stopped.", false); // Optionally update status
        } else if (window.speechSynthesis && window.speechSynthesis.pending) {
             console.log("Cancelling pending TTS utterances.");
             window.speechSynthesis.cancel(); // Also cancel if just pending
        } else {
             // console.log("stopReading called but nothing was speaking or pending."); // Optional log
        }
    }


    // --- Theme Toggle Logic ---

    /** Applies the 'dark-theme' class to the body element based on the provided theme name. */
    function applyTheme(theme) {
        console.log("Applying theme:", theme);
        if (theme === 'dark') {
            document.body.classList.add('dark-theme');
        } else {
            // Default to light theme if theme is not 'dark' or is invalid
            document.body.classList.remove('dark-theme');
        }
    }

    /** Attaches the event listener to the theme toggle button if it exists. */
    if (themeToggleBtn) {
         console.log('Attaching click listener to themeToggleBtn.');
        themeToggleBtn.addEventListener('click', () => {
            // Toggle the class and determine the new theme state
            const isDark = document.body.classList.toggle('dark-theme');
            const newTheme = isDark ? 'dark' : 'light';
            try {
                 // Save the user's preference to localStorage
                 localStorage.setItem('newsAgentTheme', newTheme);
                 console.log("Theme toggled and saved to localStorage:", newTheme);
            } catch (e) {
                 // Handle potential localStorage errors (e.g., storage full, private mode)
                 console.warn("Could not save theme preference to localStorage:", e);
            }
        });
    } else {
         console.warn("Theme toggle button (#theme-toggle-btn) not found.");
    }


    // --- Initial Page Setup Execution ---
    console.log("--- Running Initial Page Setup ---");

    // 1. Load saved theme preference from localStorage or default to 'light'
    let savedTheme = 'light'; // Default theme
    try {
        savedTheme = localStorage.getItem('newsAgentTheme') || 'light';
    } catch (e) {
        console.warn("Could not read theme preference from localStorage:", e);
    }
    applyTheme(savedTheme); // Apply the loaded or default theme

    // 2. Attach event listeners to the control buttons if they exist
    if (summarizeReadBtn) {
         console.log('Attaching click listener to summarizeReadBtn.');
         summarizeReadBtn.addEventListener('click', handleSummarizeAndRead);
    }
    if (stopReadingBtn) {
         console.log('Attaching click listener to stopReadingBtn.');
         stopReadingBtn.addEventListener('click', stopReading);
    }

    // 3. Set initial status message after elements are confirmed to exist
    updateStatus("Ready.", false);

    // 4. Fetch initial news data immediately on load
    console.log("Calling initial fetchNews() on page load.");
    fetchNews();

    // 5. Start polling for new news at the defined interval, but ONLY if the API key is available
    if (window.NEWS_API_AVAILABLE) {
        console.log(`Starting news polling interval (${POLLING_INTERVAL}ms).`);
        if(pollingIntervalId) clearInterval(pollingIntervalId); // Clear any previous interval (safety net)
        pollingIntervalId = setInterval(fetchNews, POLLING_INTERVAL);
    } else {
        // Log clearly that polling won't start due to the missing key flag
        console.warn("News polling not started because window.NEWS_API_AVAILABLE is false.");
    }

    // 6. Add cleanup for polling when the window unloads (optional but good practice)
    window.addEventListener('beforeunload', () => {
         if (pollingIntervalId) {
             clearInterval(pollingIntervalId);
             console.log("Cleared news polling interval on page unload.");
         }
         stopReading(); // Also ensure TTS stops if user navigates away
    });


    console.log("--- Initial Page Setup Complete ---");


}); // End DOMContentLoaded