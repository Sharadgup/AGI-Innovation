/**
 * Handles interactions for the Construction AI Assistant page.
 * Includes Chart.js rendering.
 */
console.log("[Construction Agent JS] Script loaded.");

document.addEventListener('DOMContentLoaded', () => {
    console.log("[Construction Agent JS] DOM Content Loaded.");

    // --- Construction Agent Elements ---
    const contextInput = document.getElementById('constructionDataContext');
    const queryInput = document.getElementById('constructionQueryInput');
    const submitBtn = document.getElementById('submitConstructionQueryBtn');
    const agentOutput = document.getElementById('constructionAgentOutput');
    const loadingIndicator = document.getElementById('constructionAgentLoading');
    const errorDiv = document.getElementById('constructionAgentError');

    // --- **NEW** Chart Elements ---
    const chartsArea = document.getElementById('constructionChartsArea');
    const budgetChartContainer = document.getElementById('budgetChartContainer');
    const budgetChartCanvas = document.getElementById('budgetChart')?.getContext('2d');
    const timelineChartContainer = document.getElementById('timelineChartContainer');
    const timelineChartCanvas = document.getElementById('timelineChart')?.getContext('2d');
    const salesRegionChartContainer = document.getElementById('salesRegionChartContainer');
    const salesRegionChartCanvas = document.getElementById('salesRegionChart')?.getContext('2d');
    const noChartsMsg = document.getElementById('noConstructionChartsMessage');

    // --- State for Charts ---
    let budgetChartInstance = null;
    let timelineChartInstance = null;
    let salesRegionChartInstance = null;
    // Add more chart instances if needed

    // --- Initial Check ---
    if (!queryInput || !submitBtn || !agentOutput) {
        console.error("[Construction Agent JS] Core UI elements not found.");
        return;
    }
    if (!chartsArea || !budgetChartCanvas || !timelineChartCanvas || !salesRegionChartCanvas) {
         console.warn("[Construction Agent JS] One or more chart canvas elements not found.");
         // Allow script to continue, but charts won't render
    }
    console.log("[Construction Agent JS] UI elements found.");

    // --- Event Listeners ---
    submitBtn.addEventListener('click', handleConstructionQuery);
    // (Keep keypress listener if desired)
    console.log("[Construction Agent JS] Event listeners attached.");

    // --- Construction Agent Query Handler ---
    async function handleConstructionQuery() {
        const query = queryInput.value.trim();
        const context = contextInput.value.trim();
        if (!query) { showAgentError("Please enter query/task."); return; }

        console.log("[Construction Agent JS] Sending query:", query);
        setAgentLoading(true); hideAgentError(); destroyConstructionCharts(); // Destroy old charts
        agentOutput.innerHTML = '<p><i>Analyzing...</i></p>';
        if(chartsArea) chartsArea.style.display = 'none'; // Hide chart area

        try {
            const response = await fetch('/agent/construction/query', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query, context: context })
            });
            console.log(`[Construction Agent JS] Rcvd status: ${response.status}`);
            if (!response.ok) { let eMsg=`Err: ${response.status}`; try{const d=await response.json();eMsg=d.error||eMsg;}catch(e){} throw new Error(eMsg); }

            const data = await response.json();
            console.log("[Construction Agent JS] Rcvd data:", data);
            if (data.error) { throw new Error(data.error); }

            // Display Text Answer
            if (agentOutput && data.answer) {
                const sanitizedAnswer = data.answer.replace(/</g, "<").replace(/>/g, ">");
                agentOutput.innerHTML = `<p>${sanitizedAnswer.replace(/\n/g, '<br>')}</p>`;
            } else if (!data.answer) { throw new Error("Empty text answer received."); }
            else { console.error("Output element missing!"); }

            // *** Process and Render Charts ***
            if (data.chart_data) {
                processConstructionCharts(data.chart_data);
            } else {
                console.log("No chart data received from backend.");
                if(noChartsMsg) noChartsMsg.style.display = 'block'; // Show no charts message
            }

        } catch (error) {
            console.error("[Construction Agent JS] Fetch/Process Error:", error);
            showAgentError(`Failed: ${error.message}`);
            agentOutput.innerHTML = `<p><i>Sorry, error processing request.</i></p>`;
        } finally {
            setAgentLoading(false);
        }
    }
    // ------------------------------------------

    // --- **NEW** Chart Processing Functions ---
    function destroyConstructionCharts() {
        console.log("[Construction Agent JS] Destroying charts...");
        if (budgetChartInstance) { budgetChartInstance.destroy(); budgetChartInstance = null; }
        if (timelineChartInstance) { timelineChartInstance.destroy(); timelineChartInstance = null; }
        if (salesRegionChartInstance) { salesRegionChartInstance.destroy(); salesRegionChartInstance = null; }
        // Destroy other chart instances...

        if(budgetChartContainer) budgetChartContainer.style.display = 'none';
        if(timelineChartContainer) timelineChartContainer.style.display = 'none';
        if(salesRegionChartContainer) salesRegionChartContainer.style.display = 'none';
        // Hide other chart containers...
        if(chartsArea) chartsArea.style.display = 'none'; // Hide the whole area
        if(noChartsMsg) noChartsMsg.style.display = 'none';
    }

    function processConstructionCharts(chartData) {
        destroyConstructionCharts(); // Ensure clean slate
        let chartsGenerated = false;
        if (!chartData || Object.keys(chartData).length === 0) {
             console.log("Chart data object is empty.");
             if(noChartsMsg) noChartsMsg.style.display = 'block';
             return;
        }

        console.log("[Construction Agent JS] Processing chart data:", chartData);

        // 1. Budget Comparison Chart (Example: Grouped Bar)
        if (budgetChartCanvas && chartData.budget_comparison && Object.keys(chartData.budget_comparison).length > 0) {
            try {
                const labels = Object.keys(chartData.budget_comparison);
                const budgetValues = labels.map(label => chartData.budget_comparison[label]?.budget || 0);
                const actualValues = labels.map(label => chartData.budget_comparison[label]?.actual || 0);

                if (labels.length > 0) {
                    if(budgetChartContainer) budgetChartContainer.style.display = 'block';
                    budgetChartInstance = new Chart(budgetChartCanvas, {
                        type: 'bar',
                        data: {
                            labels: labels,
                            datasets: [
                                { label: 'Budget', data: budgetValues, backgroundColor: 'rgba(54, 162, 235, 0.6)', borderColor: 'rgba(54, 162, 235, 1)', borderWidth: 1 },
                                { label: 'Actual', data: actualValues, backgroundColor: 'rgba(255, 99, 132, 0.6)', borderColor: 'rgba(255, 99, 132, 1)', borderWidth: 1 }
                            ]
                        },
                        options: { scales: { y: { beginAtZero: true } }, responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Budget vs Actual Costs' } } }
                    });
                    chartsGenerated = true;
                    console.log("Budget chart created.");
                }
            } catch(e) { console.error("Error creating budget chart:", e); showAgentError("Failed to display budget chart."); if(budgetChartContainer) budgetChartContainer.style.display = 'none';}
        }

        // 2. Timeline Progress Chart (Example: Horizontal Bar)
        if (timelineChartCanvas && chartData.timeline_progress && Object.keys(chartData.timeline_progress).length > 0) {
             try {
                const labels = Object.keys(chartData.timeline_progress);
                // For progress, maybe show % complete vs % remaining (out of 100)
                const percentComplete = labels.map(label => chartData.timeline_progress[label]?.actual_percent_complete || 0);
                const percentRemaining = percentComplete.map(p => 100 - p);

                if (labels.length > 0) {
                    if(timelineChartContainer) timelineChartContainer.style.display = 'block';
                    timelineChartInstance = new Chart(timelineChartCanvas, {
                        type: 'bar',
                        data: {
                            labels: labels,
                            datasets: [
                                { label: '% Complete', data: percentComplete, backgroundColor: 'rgba(75, 192, 192, 0.6)', borderColor: 'rgba(75, 192, 192, 1)', borderWidth: 1 },
                                { label: '% Remaining', data: percentRemaining, backgroundColor: 'rgba(201, 203, 207, 0.6)', borderColor: 'rgba(201, 203, 207, 1)', borderWidth: 1 }
                            ]
                        },
                        options: {
                            indexAxis: 'y', // Horizontal bars
                            scales: { x: { stacked: true, beginAtZero: true, max: 100 }, y: { stacked: true } }, // Stacked bar
                            responsive: true, maintainAspectRatio: false,
                            plugins: { title: { display: true, text: 'Task Progress (%)' }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw}%` } } }
                        }
                    });
                    chartsGenerated = true;
                    console.log("Timeline chart created.");
                }
             } catch(e) { console.error("Error creating timeline chart:", e); showAgentError("Failed to display timeline chart."); if(timelineChartContainer) timelineChartContainer.style.display = 'none';}
        }

        // 3. Sales by Region Chart (Example: Pie/Doughnut)
        if (salesRegionChartCanvas && chartData.sales_by_region && Object.keys(chartData.sales_by_region).length > 0) {
             try {
                 const labels = Object.keys(chartData.sales_by_region);
                 const values = labels.map(label => chartData.sales_by_region[label] || 0);
                 // Simple background colors - can get fancier
                 const bgColors = ['rgba(255, 159, 64, 0.6)', 'rgba(153, 102, 255, 0.6)', 'rgba(255, 205, 86, 0.6)', 'rgba(75, 192, 192, 0.6)', 'rgba(54, 162, 235, 0.6)'];

                 if (labels.length > 0) {
                     if(salesRegionChartContainer) salesRegionChartContainer.style.display = 'block';
                     salesRegionChartInstance = new Chart(salesRegionChartCanvas, {
                         type: 'doughnut',
                         data: {
                             labels: labels,
                             datasets: [{
                                 label: 'Sales by Region',
                                 data: values,
                                 backgroundColor: bgColors.slice(0, labels.length),
                                 hoverOffset: 4
                             }]
                         },
                          options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Sales Distribution by Region' } } }
                     });
                     chartsGenerated = true;
                     console.log("Sales chart created.");
                 }
             } catch(e) { console.error("Error creating sales chart:", e); showAgentError("Failed to display sales chart."); if(salesRegionChartContainer) salesRegionChartContainer.style.display = 'none';}
        }

        // Show chart area if any chart was made, otherwise show 'no charts' message
        if (chartsGenerated) {
            if(chartsArea) chartsArea.style.display = 'block';
            if(noChartsMsg) noChartsMsg.style.display = 'none';
        } else {
             console.log("No relevant chart data found in response to render.");
             if(noChartsMsg) noChartsMsg.style.display = 'block';
             if(chartsArea) chartsArea.style.display = 'none'; // Ensure area hidden if no charts
        }
    }
    // --------------------------------------


    // --- Construction Agent Helper Functions ---
     function setAgentLoading(isLoading) { /* (Keep implementation) */ }
     function showAgentError(message) { /* (Keep implementation) */ }
     function hideAgentError() { /* (Keep implementation) */ }
     // ---------------------------------------------

     // --- Initial UI State ---
     function initializeAgentUI() {
         console.log("[Construction Agent JS] Initializing UI...");
         hideAgentError();
         setAgentLoading(false);
         destroyConstructionCharts(); // Also destroy charts on init
         if (agentOutput) agentOutput.innerHTML = "<p><i>AI insights appear here...</i></p>";
         if (queryInput) queryInput.value = '';
         if (contextInput) contextInput.value = '';
     }
     initializeAgentUI();

}); // End DOMContentLoaded