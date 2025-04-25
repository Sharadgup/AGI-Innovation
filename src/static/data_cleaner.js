document.addEventListener('DOMContentLoaded', () => {
    console.log("DOMContentLoaded fired for:", window.location.pathname); // Debug: Check DOM ready

    // --- Get Data from HTML ---
    const uploadIdInput = document.getElementById('uploadId');
    const previewDataEl = document.getElementById('previewDataJson');
    const columnInfoEl = document.getElementById('columnInfoJson');

    // --- Element Existence Check (Initial) ---
    if (!uploadIdInput || !previewDataEl || !columnInfoEl) {
        console.error("Data Cleaner Script Error: Missing critical data elements from HTML.");
        console.error("Check for IDs: 'uploadId', 'previewDataJson', 'columnInfoJson'.");
        // Optionally display a static error message if possible
        const body = document.querySelector('body');
        if (body) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger';
            errorDiv.textContent = 'Page Initialization Error: Could not load data. Please go back and try uploading again.';
            body.prepend(errorDiv);
        }
        return; // Stop execution
    }
    console.log("Initial data elements found.");

    const uploadId = uploadIdInput.value;
    let previewData = [];
    let columnInfo = [];

    try {
        previewData = JSON.parse(previewDataEl.textContent);
        columnInfo = JSON.parse(columnInfoEl.textContent);
        console.log("Initial previewData count:", previewData.length);
        console.log("Initial columnInfo count:", columnInfo.length);
    } catch (e) {
        console.error("Data Cleaner Script Error: Failed to parse initial data from HTML.", e);
        // Display error
         const body = document.querySelector('body');
        if (body) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger';
            errorDiv.textContent = 'Page Initialization Error: Failed to parse initial data.';
            body.prepend(errorDiv);
        }
        return; // Stop execution
    }


    // --- DOM Element References ---
    const tableDiv = document.getElementById('data-preview-table');
    const columnInfoListDiv = document.getElementById('column-info-list');
    const selectColumnCleaning = document.getElementById('selectColumnCleaning');
    const selectXAxis = document.getElementById('selectXAxis');
    const selectYAxis = document.getElementById('selectYAxis');
    const selectColor = document.getElementById('selectColor');
    const nullActionMethodSelect = document.getElementById('nullActionMethod');
    const nullCustomValueInput = document.getElementById('nullCustomValue');
    const cleaningFeedbackDiv = document.getElementById('cleaning-feedback');
    const analysisResultsDiv = document.getElementById('analysis-results');
    const plotOutputDiv = document.getElementById('plot-output');
    const insightsOutputDiv = document.getElementById('insights-output');
    const generatePlotBtn = document.getElementById('generatePlotBtn');
    const generateInsightsBtn = document.getElementById('generateInsightsBtn');
    const selectChartType = document.getElementById('selectChartType');
    const vizControlY = document.querySelector('.viz-control-y');
    const vizControlColor = document.querySelector('.viz-control-color');
    const cleaningButtons = document.querySelectorAll('.apply-cleaning-btn'); // NodeList
    const analysisButtons = document.querySelectorAll('.analysis-btn'); // NodeList

    // --- Element Existence Check (UI Controls) ---
    // Add checks for all major UI elements used later
     const criticalElements = { tableDiv, columnInfoListDiv, selectColumnCleaning, selectXAxis, selectYAxis, selectColor, nullActionMethodSelect, nullCustomValueInput, cleaningFeedbackDiv, analysisResultsDiv, plotOutputDiv, insightsOutputDiv, generatePlotBtn, generateInsightsBtn, selectChartType, vizControlY, vizControlColor};
    let missingElements = false;
    for (const key in criticalElements) {
         console.log(`Element check - ${key}:`, criticalElements[key]);
         if (!criticalElements[key]) {
             console.error(`Data Cleaner Script Error: UI Element missing: ${key}`);
             missingElements = true;
         }
    }
     if (cleaningButtons.length === 0) console.warn("No cleaning buttons found with class 'apply-cleaning-btn'.");
     if (analysisButtons.length === 0) console.warn("No analysis buttons found with class 'analysis-btn'.");

     if (missingElements) {
          if (cleaningFeedbackDiv) displayFeedback("Page Initialization Error: Some UI components are missing. Functionality may be limited.", true, false);
         // Decide if you want to return or allow partial functionality
         // return;
     }
    console.log("UI Element check passed.");


    let tabulatorTable = null;

    // --- Helper Functions ---
    function showLoading(elementId, show = true) {
        // console.log(`showLoading called for ${elementId}, show=${show}`); // Debug showLoading
        const indicator = document.getElementById(elementId);
        if (indicator) {
            indicator.style.display = show ? 'flex' : 'none';
             // Optional: Disable relevant controls while loading
             const parentPanel = indicator.closest('.panel');
             if(parentPanel) {
                 const controls = parentPanel.querySelectorAll('button, input, select');
                 controls.forEach(control => control.disabled = show);
             }
        } else {
            // console.warn(`Loading indicator element not found: ${elementId}`);
        }
    }

    function displayFeedback(element, message, isError = false) {
         // console.log(`displayFeedback called for ${element?.id}: msg='${message}', isError=${isError}`); // Debug displayFeedback
         if(element) {
             element.textContent = message;
             element.className = `mt-2 small ${isError ? 'text-danger' : 'text-success'}`;
             element.style.display = 'block'; // Ensure it's visible
         } else {
             console.warn('Attempted to display feedback on a non-existent element.');
         }
    }

     function clearFeedback(element) {
         if (element) {
             element.textContent = '';
             element.style.display = 'none';
         }
     }


    async function fetchApi(url, method = 'GET', body = null) {
        // console.log(`fetchApi: ${method} ${url}`, body); // Debug fetchApi start
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                 // Add CSRF token header if needed
                // 'X-CSRFToken': getCsrfToken(),
            },
        };
        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(url, options);
            const result = await response.json(); // Assume JSON response for simplicity here
            // console.log(`fetchApi response: ${method} ${url}, Status: ${response.status}`, result); // Debug fetchApi response
            return { ok: response.ok, status: response.status, data: result };
        } catch (error) {
            console.error(`API Fetch Error (${url}):`, error); // Debug fetchApi error
            return { ok: false, status: 500, data: { error: `Network error or invalid JSON response: ${error.message}` } };
        }
    }


    // --- Initialization Functions ---
    function initializeTable() {
        console.log("initializeTable called."); // Debug init table
        if (tableDiv && previewData && previewData.length >= 0) { // Allow empty data init
             showLoading('previewLoading', true);
             const tableColumns = columnInfo.map(col => ({
                 title: col.name, field: col.name, headerFilter: "input",
                 minWidth: 100, sorter: inferTabulatorSorter(col.dtype),
                 formatter: "plaintext", tooltip: true,
                 headerTooltip: `Type: ${col.dtype}\nNulls: ${col.null_count}`
             }));
            console.log("Tabulator columns config:", tableColumns); // Debug columns config

            try {
                 tabulatorTable = new Tabulator(tableDiv, {
                     data: previewData,
                     columns: tableColumns,
                     layout: "fitDataStretch", pagination: "local", paginationSize: 10,
                     paginationSizeSelector: [10, 25, 50, 100], movableColumns: true,
                     height: "400px", placeholder: "No Data Available",
                     langs: { "default": { "pagination": { "page_size": "Rows/Page", "first": "First", "first_title": "First Page", "last": "Last", "last_title": "Last Page", "prev": "Prev", "prev_title": "Previous Page", "next": "Next", "next_title": "Next Page" } } },
                     tableBuilt: function(){
                         console.log("Tabulator table built successfully."); // Debug table built
                         showLoading('previewLoading', false);
                     },
                 });
            } catch (tabulatorError) {
                 console.error("Failed to initialize Tabulator:", tabulatorError); // Debug tabulator error
                 tableDiv.innerHTML = '<div class="alert alert-danger">Error initializing data preview table.</div>';
                 showLoading('previewLoading', false);
            }

        } else if (tableDiv) {
             console.warn("initializeTable: No preview data or tableDiv missing."); // Debug no data/div
             tableDiv.innerHTML = '<div class="alert alert-warning">No preview data available.</div>';
             showLoading('previewLoading', false);
        }
    }
     function inferTabulatorSorter(dtype) {
         // ... (same as before)
          if (!dtype) return 'string';
         const lowerDtype = dtype.toLowerCase();
         if (lowerDtype.includes('int') || lowerDtype.includes('float') || lowerDtype.includes('numeric')) return 'number';
         if (lowerDtype.includes('date') || lowerDtype.includes('time')) return 'datetime';
         if (lowerDtype.includes('bool')) return 'boolean';
         return 'string';
     }


    function updateColumnSelectors() {
        console.log("updateColumnSelectors called."); // Debug update selectors
        selectColumnCleaning.innerHTML = '<option value="" selected disabled>-- Select Column --</option>';
        selectXAxis.innerHTML = '<option value="" selected disabled>-- Select Column --</option>';
        selectYAxis.innerHTML = '<option value="" selected disabled>-- Select Column --</option>';
        selectColor.innerHTML = '<option value="">-- None --</option>';

        columnInfo.forEach(col => {
            const option = `<option value="${col.name}">${col.name} (${col.dtype})</option>`;
            selectColumnCleaning.insertAdjacentHTML('beforeend', option);
            selectXAxis.insertAdjacentHTML('beforeend', option);
            selectYAxis.insertAdjacentHTML('beforeend', option);
            selectColor.insertAdjacentHTML('beforeend', option);
        });
         console.log("Column selectors updated."); // Debug update done
    }

    function updateColumnInfoDisplay() {
         console.log("updateColumnInfoDisplay called."); // Debug update info
         if (!columnInfoListDiv) return; // Guard clause
         columnInfoListDiv.innerHTML = '';
         const ul = document.createElement('ul');
         ul.className = 'list-group list-group-flush small';
         if (columnInfo && columnInfo.length > 0) {
             columnInfo.forEach(col => {
                 const li = document.createElement('li');
                 li.className = 'list-group-item d-flex justify-content-between align-items-center';
                 li.innerHTML = `<span>${col.name} <small class="text-muted">(${col.dtype})</small></span><span class="badge bg-${col.null_count > 0 ? 'warning' : 'light text-dark'}">Nulls: ${col.null_count}</span>`;
                 ul.appendChild(li);
             });
         } else {
              const li = document.createElement('li');
              li.className = 'list-group-item';
              li.textContent = 'No column information available.';
              ul.appendChild(li);
         }
         columnInfoListDiv.appendChild(ul);

         const rowCountSpan = document.getElementById('rowCount');
         const colCountSpan = document.getElementById('colCount');
         // Use table row count if available AFTER filtering/cleaning, else use initial count
         const currentDataRowCount = tabulatorTable ? tabulatorTable.getDataCount('active') : (previewData ? previewData.length : 'N/A');
         if (rowCountSpan) rowCountSpan.textContent = currentDataRowCount;
         if (colCountSpan) colCountSpan.textContent = columnInfo ? columnInfo.length : 'N/A';

          console.log("Column info display updated."); // Debug update done
    }


    // --- Event Listener Attachments ---

    // Cleaning Action Buttons
    console.log(`Attaching listeners to ${cleaningButtons.length} cleaning buttons.`); // Debug attach cleaning
    cleaningButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            console.log('Cleaning button clicked. Action:', event.target.dataset.action); // Debug cleaning click
            const action = event.target.dataset.action;
            let selectedColumn = selectColumnCleaning.value;
            let params = {};

            if (action !== 'remove_duplicates' && !selectedColumn) {
                displayFeedback(cleaningFeedbackDiv, 'Please select a column first.', true);
                return;
            }
            if (action === 'remove_duplicates') {
                 selectedColumn = null;
            }

            // Gather params
            if (action === 'handle_nulls') {
                params.method = nullActionMethodSelect.value;
                if (params.method === 'custom') params.custom_value = nullCustomValueInput.value;
            } else if (action === 'convert_type') {
                params.new_type = document.getElementById('convertTypeNew').value;
                if (!params.new_type) { displayFeedback(cleaningFeedbackDiv, 'Please select a target data type.', true); return; }
            }
            // Add other param gathering

            displayFeedback(cleaningFeedbackDiv, `Applying ${action}...`, false);
            clearFeedback(cleaningFeedbackDiv); // Clear previous feedback immediately
            showLoading('cleaningLoading', true);

            const apiUrl = `/apply_cleaning_action/${uploadId}`;
            const payload = { action: action, column: selectedColumn, params: params };

            const result = await fetchApi(apiUrl, 'POST', payload);

            showLoading('cleaningLoading', false);
            if (result.ok) {
                displayFeedback(cleaningFeedbackDiv, result.data.message || 'Action applied successfully.', false);
                // Update state ONLY IF server confirms success
                previewData = result.data.preview_data;
                columnInfo = result.data.column_info;
                if (tabulatorTable) {
                     console.log("Updating Tabulator data after cleaning."); // Debug update table data
                     tabulatorTable.setData(previewData); // Use full dataset if server sends it, else just preview
                } else {
                     console.warn("Tabulator table not initialized, cannot update data.");
                }
                updateColumnSelectors();
                updateColumnInfoDisplay();
            } else {
                displayFeedback(cleaningFeedbackDiv, `Error: ${result.data.error || 'Failed to apply action.'}`, true);
            }
        });
    });

    // Show/Hide Custom Null Input
    if (nullActionMethodSelect) {
        nullActionMethodSelect.addEventListener('change', (event) => {
            if (nullCustomValueInput) {
                 nullCustomValueInput.style.display = (event.target.value === 'custom') ? 'block' : 'none';
            }
        });
         // Initial check in case 'custom' is default
         if (nullCustomValueInput) {
             nullCustomValueInput.style.display = (nullActionMethodSelect.value === 'custom') ? 'block' : 'none';
         }
    }


     // Analysis Buttons
    console.log(`Attaching listeners to ${analysisButtons.length} analysis buttons.`); // Debug attach analysis
     analysisButtons.forEach(button => {
         button.addEventListener('click', async (event) => {
             const analysisType = event.target.dataset.analysisType;
             console.log('Analysis button clicked! Type:', analysisType); // Debug analysis click
             if (analysisResultsDiv) analysisResultsDiv.textContent = `Running ${analysisType}...`;
             showLoading('analysisLoading', true);
             clearFeedback(cleaningFeedbackDiv); // Clear other feedback areas

             const apiUrl = `/run_analysis/${uploadId}/${analysisType}`;
             const result = await fetchApi(apiUrl, 'POST'); // Add payload if needed

             showLoading('analysisLoading', false);
             if (analysisResultsDiv) {
                 if (result.ok) {
                     analysisResultsDiv.textContent = JSON.stringify(result.data.results, null, 2);
                 } else {
                     analysisResultsDiv.textContent = `Error running ${analysisType}: ${result.data.error || 'Failed'}`;
                 }
             }
         });
     });

    // Plotting Controls Logic
    if (selectChartType) {
        selectChartType.addEventListener('change', () => {
             console.log('Chart type changed:', selectChartType.value); // Debug chart type change
             const chartType = selectChartType.value;
             if (vizControlY) vizControlY.style.display = ['histogram', 'heatmap'].includes(chartType) ? 'none' : 'block';
             if (vizControlColor) vizControlColor.style.display = ['heatmap'].includes(chartType) ? 'none' : 'block';
        });
    }


    // Generate Plot Button
    if (generatePlotBtn) {
        console.log('Attaching listener to generatePlotBtn:', generatePlotBtn); // Debug attach plot
        generatePlotBtn.addEventListener('click', async () => {
             console.log('Generate Plot button clicked!'); // Debug plot click
             const plotConfig = {
                 chart_type: selectChartType.value,
                 x: selectXAxis.value,
                 y: selectYAxis.value,
                 color: selectColor.value,
             };

            // --- Input Validation ---
            let validationError = null;
             if (!plotConfig.chart_type) validationError = "Please select Chart Type.";
             else if (!plotConfig.x) validationError = "Please select X-Axis.";
             else if (['scatter', 'bar', 'line'].includes(plotConfig.chart_type) && !plotConfig.y) validationError = `Please select Y-Axis for ${plotConfig.chart_type}.`;

             if (validationError) {
                  alert(validationError); // Simple alert for now
                  return;
             }

            if (plotOutputDiv) plotOutputDiv.innerHTML = '<div class="text-center p-3">Generating plot...</div>';
            showLoading('plotLoading', true);
            clearFeedback(cleaningFeedbackDiv);

            const apiUrl = `/generate_plot/${uploadId}`;
            const result = await fetchApi(apiUrl, 'POST', plotConfig);

            showLoading('plotLoading', false);
             if (plotOutputDiv) {
                 if (result.ok && result.data.plot_json) {
                     try {
                         const plotData = JSON.parse(result.data.plot_json);
                         console.log("Plotly data received:", plotData); // Debug plotly data
                         Plotly.newPlot(plotOutputDiv, plotData.data, plotData.layout, {responsive: true});
                     } catch (e) {
                         console.error("Plotly JSON parsing or rendering error:", e);
                         plotOutputDiv.innerHTML = '<p class="text-danger p-3">Error rendering plot. Invalid data received.</p>';
                     }
                 } else {
                     plotOutputDiv.innerHTML = `<p class="text-danger p-3">Error generating plot: ${result.data.error || 'Failed'}</p>`;
                 }
             }
        });
    } else {
         console.warn("Generate Plot button not found.");
    }


     // Generate Insights Button
     if (generateInsightsBtn) {
         console.log('Attaching listener to generateInsightsBtn:', generateInsightsBtn); // Debug attach insights
         generateInsightsBtn.addEventListener('click', async () => {
             console.log('Generate Insights button clicked!'); // Debug insights click
             if (insightsOutputDiv) insightsOutputDiv.textContent = 'Generating insights...';
             showLoading('insightsLoading', true);
             clearFeedback(cleaningFeedbackDiv);

             const apiUrl = `/generate_insights/${uploadId}`;
             const result = await fetchApi(apiUrl, 'POST');

             showLoading('insightsLoading', false);
             if (insightsOutputDiv) {
                 if (result.ok && result.data.insights) {
                     console.log("Insights received:", result.data.insights); // Debug insights data
                     insightsOutputDiv.innerHTML = ''; // Clear loading message
                     if (result.data.insights.length > 0) {
                         const ul = document.createElement('ul');
                         ul.className = 'list-unstyled';
                         result.data.insights.forEach(insight => {
                             const li = document.createElement('li');
                             li.innerHTML = `<i class="fas fa-check-circle text-success me-2"></i> ${insight}`; // Assumes FontAwesome
                             ul.appendChild(li);
                         });
                         insightsOutputDiv.appendChild(ul);
                     } else {
                          insightsOutputDiv.textContent = 'No insights generated.';
                     }
                 } else {
                     insightsOutputDiv.textContent = `Error generating insights: ${result.data.error || 'Failed'}`;
                 }
             }
         });
     } else {
          console.warn("Generate Insights button not found.");
     }


    // --- Initial Page Load Setup Execution ---
    console.log("Running initial page setup..."); // Debug initial setup start
    initializeTable();
    updateColumnSelectors();
    updateColumnInfoDisplay();
    // Trigger initial show/hide for plot controls if element exists
    if(selectChartType) selectChartType.dispatchEvent(new Event('change'));
    console.log("Initial page setup complete."); // Debug initial setup end


}); // End DOMContentLoaded