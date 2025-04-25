/**
 * news_agent.js
 * Frontend logic for the News AI Agent page.
 * Handles fetching news (initial load, search, polling), displaying articles
 * and notifications, theme switching, summarization via backend API, and Text-to-Speech.
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("[News Agent JS] DOM Content Loaded.");

    // --- DOM Element References ---
    // Main display area
    const mainNewsContentDiv = document.getElementById('main-news-content');
    const mainNewsControlsDiv = document.querySelector('.main-news-controls'); // Controls below main article

    // Notifications
    const notificationPanelDiv = document.getElementById('notification-panel');
    const notificationTemplate = document.getElementById('notification-template'); // Assumes <template id="notification-template"> exists

    // Status/Bottom Bar
    const statusUpdateSpan = document.getElementById('status-update');
    const liveHeadlinesSpan = document.getElementById('live-headlines');

    // Controls
    const summarizeReadBtn = document.getElementById('summarize-read-btn');
    const stopReadingBtn = document.getElementById('stop-reading-btn');
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const newsSearchQueryInput = document.getElementById('newsSearchQuery');
    const newsSourceCountrySelect = document.getElementById('newsSourceCountry');
    const searchNewsBtn = document.getElementById('searchNewsBtn');

    // Indicators/Feedback
    const newsLoadingIndicator = document.getElementById('newsLoadingIndicator'); // For article list
    const newsErrorDiv = document.getElementById('newsError');             // For article list errors
    const newsArticleContainer = document.getElementById('newsArticleContainer'); // Where articles are appended/displayed
    const summaryLoadingIndicator = document.getElementById('summaryLoading'); // Separate loader maybe near summarize btn
    const newsSearchFeedback = document.getElementById('news-search-feedback'); // Small text for search input errors


    // --- Element Existence Check ---
    console.log("--- Running Initial Element Checks ---");
    const criticalElements = { // List elements essential for basic operation
        mainNewsContentDiv, notificationPanelDiv, statusUpdateSpan, newsSearchQueryInput,
        newsSourceCountrySelect, searchNewsBtn, newsLoadingIndicator, newsErrorDiv, newsArticleContainer
        // Add others if they are absolutely required for the page to function at all
    };
    let allElementsFound = true;
    for (const key in criticalElements) {
        console.log(`Element check - ${key}:`, criticalElements[key] ? 'Found' : 'MISSING!');
        if (!criticalElements[key]) {
            console.error(`News Agent Script Error: Essential UI Element missing: #${key}. Check HTML.`);
            allElementsFound = false;
        }
    }
     if (!allElementsFound) {
          console.error("News Agent Script Error: Aborting setup due to missing essential elements.");
          if (statusUpdateSpan) statusUpdateSpan.textContent = "Status: Page Error!";
          if (mainNewsContentDiv) mainNewsContentDiv.innerHTML = "<p class='text-danger'>Page failed to initialize correctly (missing HTML elements).</p>";
          return; // Stop script
     }
     // Check optional elements needed for specific features
     if (!summarizeReadBtn || !stopReadingBtn) console.warn("Summarize/Stop Reading buttons not found. TTS functionality limited.");
     if (!themeToggleBtn) console.warn("Theme toggle button not found.");
     if (!notificationTemplate) console.warn("Notification template not found. Notifications disabled.");
     if (!mainNewsControlsDiv) console.warn("Main news controls div not found. Summarize/Read buttons might not show.");
     if (!summaryLoadingIndicator) console.warn("Summary loading indicator not found.");
     if (!newsSearchFeedback) console.warn("News search feedback element not found.");

     console.log("--- Initial Element Checks Passed ---");


    // --- State Variables ---
    let currentMainArticle = null; // Full article object in main view
    let lastFetchTime = 0;         // Avoid race conditions with polling/search
    let knownNotificationUrls = new Set(); // Prevent duplicate notifications
    let isReading = false;          // TTS state flag
    let pollingIntervalId = null;   // Polling interval reference
    const POLLING_INTERVAL = 60000; // Fetch every 60 seconds
    // Read the flag set by the backend template rendering
    // Ensure this variable name matches what's passed in news_agent.html
    const NEWS_API_AVAILABLE = typeof news_api_available !== 'undefined' ? news_api_available : false;
    // Optional: Make it global for easier debugging access in console
    window.NEWS_API_AVAILABLE = NEWS_API_AVAILABLE;


    // --- Helper Functions ---

    /** Shows/hides loading indicator and optionally disables controls in parent */
    function showLoading(elementId, show = true, disableControls = true) {
        const indicator = document.getElementById(elementId);
        if (!indicator) return; // Exit if indicator element doesn't exist
        indicator.style.display = show ? 'flex' : 'none';

        if (disableControls) {
            // Try to find the relevant control container more specifically
            let controlContainer = null;
            if (elementId === 'newsLoadingIndicator') controlContainer = document.querySelector('.news-controls .card-body'); // Search controls
            else if (elementId === 'summaryLoading') controlContainer = mainNewsControlsDiv; // Main controls
            // Add other cases if needed

            if (controlContainer) {
                const controls = controlContainer.querySelectorAll('button, input, select');
                controls.forEach(control => { if(control) control.disabled = show; });
            }
        }
    }

    /** Updates the status text */
    function updateStatus(message, isError = false) {
        if (!statusUpdateSpan) return;
        statusUpdateSpan.textContent = `Status: ${message}`;
        statusUpdateSpan.classList.toggle('status-error', isError);
        statusUpdateSpan.style.color = isError ? 'var(--bs-danger)' : '';
    }

     /** Updates live headlines text */
    function updateLiveHeadlines(text = "") {
         if (liveHeadlinesSpan) liveHeadlinesSpan.innerHTML = text ? `<strong>${text}</strong>` : '';
    }

    /** Formats date string */
    function formatTimeAgo(dateString) {
         if (!dateString) return 'N/A'; // Handle null/empty dates
         try {
             const date = new Date(dateString); const now = new Date();
             const secondsPast = (now.getTime() - date.getTime()) / 1000;
             if (isNaN(secondsPast)) return 'Invalid Date'; // Check for invalid parsing
             if (secondsPast < 0) return 'Future Date';
             if (secondsPast < 5) return 'just now';
             if (secondsPast < 60) return `${Math.round(secondsPast)}s ago`;
             if (secondsPast < 3600) return `${Math.round(secondsPast / 60)}m ago`;
             if (secondsPast <= 86400 * 2) return `${Math.round(secondsPast / 3600)}h ago`;
             const options = { year: 'numeric', month: 'short', day: 'numeric' };
             return date.toLocaleDateString(undefined, options);
         } catch (e) { console.error("Error parsing date:", dateString, e); return 'Date Error'; }
    }

    /** Generic API Fetch Helper with Error Handling */
    async function fetchApi(url, method = 'GET', body = null) {
        console.log(`fetchApi: ${method} ${url}`, body ? 'with body:' : '', body ? body : ''); // Log body too
        const options = { method: method };
        if (body) { // Only add body/headers if sending data
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }
        // Add credentials include if needed for session authentication on API routes
        // options.credentials = 'include';

        try {
            const response = await fetch(url, options);
            // Get raw text regardless of status for better debugging
            const responseText = await response.text();
            let data = null;
            let jsonError = null;
            let responseError = null; // Specific error extracted from JSON

            if (!response.ok) { // Handle HTTP errors first
                 console.warn(`fetchApi: HTTP error ${response.status} for ${url}`);
            }

            try { // Attempt to parse JSON even on HTTP error, backend might send error details
                 data = JSON.parse(responseText);
                 responseError = data?.error || data?.message; // Try to get specific error message
            } catch (e) {
                 jsonError = e; // Store JSON parsing error
                 console.warn(`fetchApi: Response for ${url} not valid JSON. Status: ${response.status}. Text: ${responseText.substring(0, 200)}...`);
            }

            // Determine overall success/error message
            const ok = response.ok && !responseError && !jsonError; // OK only if HTTP is ok AND no app error/JSON error
            const error = !ok
                ? (responseError || // Prioritize backend app error
                   (jsonError ? `Invalid JSON response (Status: ${response.status})` : null) || // Then JSON error
                   `HTTP Error ${response.status}: ${response.statusText}`) // Then generic HTTP error
                : null; // No error if ok

            return { ok, status: response.status, statusText: response.statusText, data, error, rawText };

        } catch (networkError) { // Catch network errors (fetch fails entirely)
            console.error(`fetchApi Network Error for ${url}:`, networkError);
            return { ok: false, status: 0, statusText: networkError.message, data: null, error: `Network Error: ${networkError.message}.` };
        }
    }


    // --- News Fetching & Display Logic ---

    /** Fetches news based on current search/filter criteria */
    async function fetchNews(isSearch = false) {
        console.log(`--- fetchNews called (isSearch: ${isSearch}) ---`);
        if (!NEWS_API_AVAILABLE) {
             console.warn("fetchNews aborted: NEWS_API_AVAILABLE is false.");
             updateStatus("News API unavailable (check server config).", true);
             if(isSearch) showNewsError("Cannot search: News API key is missing on the server.");
             return;
        }

        showLoading('newsLoadingIndicator', true);
        hideNewsError();
        if(newsSearchFeedback) newsSearchFeedback.textContent = ''; // Clear search feedback

        const queryParams = new URLSearchParams();
        const searchTerm = newsSearchQueryInput.value.trim();
        const country = newsSourceCountrySelect.value;

        // Add parameters based on context
        if (isSearch && searchTerm) queryParams.append('text', searchTerm);
        else if (!isSearch && !searchTerm) queryParams.append('text', 'latest technology business AI'); // Default for polling if search is empty
        else if (searchTerm) queryParams.append('text', searchTerm); // Use term even for polling if user entered one

        if (country) queryParams.append('source-countries', country);
        queryParams.append('number', 30); // Number of articles to fetch

        // --- Construct Correct URL for the /news/fetch endpoint ---
        const fetchUrl = `/news/fetch?${queryParams.toString()}`;
        console.log("Sending GET request to:", fetchUrl);
        updateStatus("Fetching news articles...");

        const result = await fetchApi(fetchUrl); // Use API helper

        if (!result.ok) {
            console.error("Error fetching news:", result.error);
            showNewsError(`Failed to fetch news: ${result.error}`);
            updateStatus(`Error fetching news`, true);
        } else if (result.data?.articles && Array.isArray(result.data.articles)) {
            const articles = result.data.articles;
            const fetchTimestamp = Date.now();
            console.log(`Fetched ${articles.length} articles successfully.`);
            if (articles.length === 0) {
                 // Handle no results found specifically for searches
                 if (isSearch) {
                      newsArticleContainer.innerHTML = `<p class="text-center text-muted mt-3">No articles found matching '${searchTerm || 'your criteria'}'.</p>`;
                      updateStatus("No matching articles found.", false);
                 } else {
                      updateStatus("No new articles in latest update.", false); // Polling found nothing new
                 }
            } else {
                 processNews(articles, fetchTimestamp); // Process the received articles
                 updateStatus("News updated successfully.", false);
                 updateLiveHeadlines("Live headlines displayed.");
            }
        } else {
             // Handle cases where response is OK but data format is wrong
             console.error("Received OK response but 'articles' array is missing or invalid:", result.data);
             showNewsError("Received unexpected data format from the server.");
             updateStatus("Error processing news data.", true);
        }
        showLoading('newsLoadingIndicator', false); // Hide loading indicator
    }

    /** Processes articles, updates main view and notifications */
    function processNews(articles, fetchTimestamp) {
        // ... (Keep processNews function as previously defined) ...
        // Check timestamp, update main display if needed, add new notifications
        if (fetchTimestamp <= lastFetchTime) { console.log("Skipping processNews: stale data."); return; }
        const latest = articles.length > 0 ? articles[0] : null;
        if (latest?.url && (!currentMainArticle || latest.url !== currentMainArticle.url)) displayMainArticle(latest);
        else if (!currentMainArticle && latest?.url) displayMainArticle(latest);
        let newCount = 0;
        const waitingMsg = notificationPanelDiv?.querySelector('.placeholder-text');
        if (articles.length > 0 && waitingMsg) notificationPanelDiv.innerHTML = '';
        if (notificationPanelDiv) {
            for (let i = articles.length - 1; i >= 0; i--) {
                 const article = articles[i];
                 if (article?.url && article.title && !knownNotificationUrls.has(article.url)) { addNotification(article); knownNotificationUrls.add(article.url); newCount++; }
            }
            const maxN = 50; // Limit notifications shown
            while (notificationPanelDiv.children.length > maxN) { /* remove oldest */ const old = notificationPanelDiv.lastElementChild; if (old?.dataset?.url) knownNotificationUrls.delete(old.dataset.url); if (old) notificationPanelDiv.removeChild(old); else break; }
        }
        console.log(`Processed news. Added ${newCount} new notifications.`);
        lastFetchTime = fetchTimestamp;
    }

    /** Renders an article in the main display */
    function displayMainArticle(article) {
        // ... (Keep displayMainArticle function as previously defined) ...
         if (!article?.url || !mainNewsContentDiv || !mainNewsControlsDiv) return;
         console.log("Displaying main article:", article.title);
         currentMainArticle = article;
         let html = ''; if (article.urlToImage) html += `<img src="${article.urlToImage}" alt="${article.title || 'article'}" class="img-fluid mb-3 news-main-image" loading="lazy" onerror="this.style.display='none';">`; html += `<h3>${article.title || 'Untitled'}</h3>`; if (article.source?.name || article.publishedAt) { html += `<p class="text-muted small mb-2">`; if(article.source?.name) html += `Source: ${article.source.name}`; if(article.source?.name && article.publishedAt) html += ` | `; if(article.publishedAt) html += `Published: ${formatTimeAgo(article.publishedAt)}`; html += `</p>`; } const text = article.content || article.description || ''; html += `<div class="news-article-content">${text ? text.replace(/\n/g, '<br>') : '<em class="text-muted">No content.</em>'}</div>`; html += `<a href="${article.url}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-secondary btn-sm mt-3">Read Full Story <i class="fas fa-external-link-alt fa-xs ms-1"></i></a>`;
         mainNewsContentDiv.innerHTML = html; mainNewsControlsDiv.style.display = 'block'; if(summarizeReadBtn) summarizeReadBtn.disabled = !text; stopReading();
    }

    /** Adds a notification item */
    function addNotification(article) {
        // ... (Keep addNotification function as previously defined) ...
         if (!notificationTemplate || !notificationPanelDiv || !article?.url || !article.title) return;
         try { const clone = notificationTemplate.content.cloneNode(true); const item = clone.querySelector('.notification-item'); if (!item) return; item.dataset.url = article.url; item.querySelector('.notification-source').textContent = article.source?.name || 'Unknown'; item.querySelector('.notification-title').textContent = article.title; item.querySelector('.notification-time').textContent = formatTimeAgo(article.publishedAt); item.addEventListener('click', (e) => { e.preventDefault(); displayMainArticle(article); if (mainNewsContentDiv) mainNewsContentDiv.scrollTop = 0; }); notificationPanelDiv.prepend(clone); } catch(e) { console.error("Error creating notification:", e); }
    }

    // --- Error Display for News List ---
    function showNewsError(message) {
        if (newsErrorDiv) { newsErrorDiv.textContent = message; newsErrorDiv.style.display = 'block'; newsArticleContainer.innerHTML = ''; }
        else { console.error("News error display element missing:", message); }
    }
    function hideNewsError() { if (newsErrorDiv) newsErrorDiv.style.display = 'none'; }

    // --- Summarization and Text-to-Speech (TTS) ---
    /** Handles Summarize & Read button click */
    async function handleSummarizeAndRead() {
        if (!currentMainArticle || isReading) return;
        const content = currentMainArticle.content || currentMainArticle.description;
        const title = currentMainArticle.title || 'Article';
        if (!content) { alert("No text content to summarize."); return; }

        if(summarizeReadBtn) summarizeReadBtn.disabled = true;
        if(stopReadingBtn) stopReadingBtn.style.display = 'none';
        showLoading('summaryLoading', true, false);
        updateStatus("Summarizing article...");
        console.log("Requesting summary...");

        // --- Construct Correct URL ---
        const result = await fetchApi('/news/summarize', 'POST', { content: content, title: title }); // Use helper and CORRECT URL

        showLoading('summaryLoading', false);

        if (result.ok && result.data?.summary && !result.data.summary.startsWith("[AI")) {
            console.log("Summary received, speaking...");
            updateStatus("Reading summary aloud...", false);
            speakText(result.data.summary);
        } else {
             const errorMsg = result.error || result.data?.summary || "Failed to get valid summary.";
             console.error("Summarization Error:", errorMsg);
             updateStatus(`Summarization Error: ${errorMsg}`, true);
             if(summarizeReadBtn) summarizeReadBtn.disabled = !content; // Re-enable if content exists
        }
    }

    /** Speaks text using browser TTS */
    function speakText(text) {
        // ... (Keep speakText function as previously defined) ...
        if (!('speechSynthesis' in window)) { alert("TTS not supported."); updateStatus("TTS not supported.", true); return; }
        stopReading(); const utterance = new SpeechSynthesisUtterance(text);
        utterance.onstart = () => { isReading = true; if(stopReadingBtn) stopReadingBtn.style.display = 'inline-block'; updateStatus("Reading summary...", false); };
        utterance.onend = () => { isReading = false; if(stopReadingBtn) stopReadingBtn.style.display = 'none'; updateStatus("Finished reading.", false); if(summarizeReadBtn) summarizeReadBtn.disabled = !(currentMainArticle?.content);};
        utterance.onerror = (e) => { console.error("TTS error:", e.error); isReading = false; if(stopReadingBtn) stopReadingBtn.style.display = 'none'; updateStatus(`TTS Error: ${e.error}`, true); if(summarizeReadBtn) summarizeReadBtn.disabled = !(currentMainArticle?.content);};
        setTimeout(() => { window.speechSynthesis.speak(utterance); }, 100);
    }

    /** Stops TTS */
    function stopReading() {
        // ... (Keep stopReading function as previously defined) ...
        if (window.speechSynthesis?.speaking || window.speechSynthesis?.pending) {
             window.speechSynthesis.cancel(); isReading = false; if(stopReadingBtn) stopReadingBtn.style.display = 'none'; updateStatus("Reading stopped.", false); if(summarizeReadBtn) summarizeReadBtn.disabled = !(currentMainArticle?.content);
        }
    }

    // --- Theme Toggle Logic ---
    function applyTheme(theme) { /* ... keep as before ... */ document.body.classList.toggle('dark-theme', theme === 'dark'); }
    if (themeToggleBtn) themeToggleBtn.addEventListener('click', () => { const isDark = document.body.classList.toggle('dark-theme'); try { localStorage.setItem('newsAgentTheme', isDark ? 'dark' : 'light'); } catch (e) {} });

    // --- Search Event Listeners ---
    if (searchNewsBtn && newsSearchQueryInput && newsSourceCountrySelect) {
        searchNewsBtn.addEventListener('click', () => {
            console.log("Search button clicked"); // Confirm click registered
            fetchNews(true); // Pass true to indicate manual search
        });
        newsSearchQueryInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                console.log("Enter key pressed in search input"); // Confirm Enter registered
                event.preventDefault(); // Prevent potential form submission
                fetchNews(true); // Trigger search
            }
        });
         console.log("[News Agent JS] Search event listeners attached.");
    } else {
         console.error("[News Agent JS] Search UI elements (button, input, or select) missing. Search disabled.");
    }

    // --- Initial Page Setup ---
    console.log("--- Running Initial Page Setup ---");
    let savedTheme = 'light'; try { savedTheme = localStorage.getItem('newsAgentTheme') || 'light'; } catch (e) {} applyTheme(savedTheme);
    if (summarizeReadBtn) summarizeReadBtn.addEventListener('click', handleSummarizeAndRead);
    if (stopReadingBtn) stopReadingBtn.addEventListener('click', stopReading);
    updateStatus("Initializing...", false);
    if (NEWS_API_AVAILABLE) { // Fetch initial only if API key is okay
        fetchNews(); // Initial fetch (uses defaults)
        if(pollingIntervalId) clearInterval(pollingIntervalId);
        pollingIntervalId = setInterval(fetchNews, POLLING_INTERVAL); // Start polling
        console.log(`News polling started (${POLLING_INTERVAL}ms).`);
    } else {
        console.warn("Initial fetch and polling skipped (API key missing).");
        updateStatus("News Agent Disabled: API Key Missing.", true); // Show disabled status
        if (mainNewsContentDiv) mainNewsContentDiv.innerHTML = "<p class='text-center text-muted mt-4'>News functionality requires a valid API key configured on the server.</p>";
        if (notificationPanelDiv) notificationPanelDiv.innerHTML = "<p class='text-center text-muted small p-2'>Notifications unavailable.</p>";
    }
    window.addEventListener('beforeunload', () => { if (pollingIntervalId) clearInterval(pollingIntervalId); stopReading(); }); // Cleanup
    console.log("--- Initial Page Setup Complete ---");

}); // End DOMContentLoaded