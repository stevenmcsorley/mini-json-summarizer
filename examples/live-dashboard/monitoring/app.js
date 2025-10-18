/**
 * Monitoring Dashboard - Simple, No Polling, Manual Refresh
 */

const AGGREGATOR_URL = 'http://localhost:9880';
const SUMMARIZER_URL = 'http://localhost:8080';

let allLogs = [];

// Manual refresh
async function refreshDashboard() {
    console.log('Refreshing dashboard...');

    try {
        // Step 1: Fetch logs from aggregator
        const logsResponse = await fetch(`${AGGREGATOR_URL}/logs/last-5min`);
        if (!logsResponse.ok) {
            throw new Error(`Aggregator error: ${logsResponse.status}`);
        }

        allLogs = await logsResponse.json();
        console.log(`Fetched ${allLogs.length} logs`);

        if (allLogs.length === 0) {
            updateStats(0, 0, 100, '-');
            document.getElementById('error-codes').innerHTML = '<p class="text-center text-gray-400 py-8">No logs found</p>';
            document.getElementById('error-types').innerHTML = '<p class="text-center text-gray-400 py-8">No logs found</p>';
            document.getElementById('summary-text').innerHTML = '<p class="italic">No data to summarize</p>';
            updateLastUpdate();
            return;
        }

        // Step 2: Calculate basic stats
        const errors = allLogs.filter(log => log.level === 'error');
        const successRate = ((allLogs.length - errors.length) / allLogs.length * 100).toFixed(1);

        // Count error codes
        const errorCodes = {};
        const errorTypes = {};
        errors.forEach(log => {
            if (log.code) {
                errorCodes[log.code] = (errorCodes[log.code] || 0) + 1;
            }
            if (log.error_type) {
                errorTypes[log.error_type] = (errorTypes[log.error_type] || 0) + 1;
            }
        });

        const topErrorCode = Object.keys(errorCodes).length > 0 ?
            Object.entries(errorCodes).sort((a, b) => b[1] - a[1])[0][0] : '-';

        updateStats(allLogs.length, errors.length, successRate, topErrorCode);

        // Display error codes
        displayTopItems('error-codes', errorCodes, (code) => getErrorName(code));

        // Display error types
        displayTopItems('error-types', errorTypes, (type) => type.replace('_', ' '));

        // Display recent logs
        displayRecentLogs();

        // Step 3: Get AI summary from summarizer
        await getSummary();

        updateLastUpdate();

    } catch (error) {
        console.error('Dashboard refresh failed:', error);
        alert(`Failed to refresh: ${error.message}`);
    }
}

// Update stats
function updateStats(total, errors, successRate, topError) {
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-errors').textContent = errors;
    document.getElementById('stat-success-rate').textContent = `${successRate}%`;
    document.getElementById('stat-top-error').textContent = topError;
}

// Display top items
function displayTopItems(elementId, items, labelFormatter) {
    const container = document.getElementById(elementId);

    if (Object.keys(items).length === 0) {
        container.innerHTML = '<p class="text-center text-gray-400 py-4">No errors</p>';
        return;
    }

    const sorted = Object.entries(items).sort((a, b) => b[1] - a[1]).slice(0, 5);

    container.innerHTML = sorted.map(([key, count]) => {
        const percentage = (count / allLogs.length * 100).toFixed(1);
        return `
            <div class="bg-white/5 rounded-lg p-3">
                <div class="flex justify-between items-center mb-2">
                    <span class="font-semibold">${labelFormatter(key)}</span>
                    <span class="text-2xl font-bold">${count}</span>
                </div>
                <div class="w-full bg-gray-700 rounded-full h-2">
                    <div class="bg-purple-500 h-2 rounded-full" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

// Display recent logs
function displayRecentLogs() {
    const container = document.getElementById('recent-logs');
    const recent = allLogs.slice(-20).reverse();

    container.innerHTML = recent.map(log => {
        const levelColor = log.level === 'error' ? 'text-red-400' :
                          log.level === 'warn' ? 'text-yellow-400' : 'text-green-400';
        return `<div class="${levelColor}">[${log.timestamp}] ${log.level.toUpperCase()}: ${log.message}</div>`;
    }).join('');
}

// Get AI summary
async function getSummary() {
    try {
        const response = await fetch(`${SUMMARIZER_URL}/v1/summarize-json`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                json: allLogs,
                profile: 'logs',
                stream: false
            })
        });

        if (!response.ok) {
            throw new Error(`Summarizer error: ${response.status}`);
        }

        const summary = await response.json();
        console.log('Summary received:', summary);

        if (summary.bullets && summary.bullets.length > 0) {
            const summaryText = summary.bullets.map(bullet => `• ${bullet.text}`).join('<br>');
            document.getElementById('summary-text').innerHTML = summaryText;
        } else {
            document.getElementById('summary-text').innerHTML = '<p class="italic">No insights generated</p>';
        }

    } catch (error) {
        console.error('Summary generation failed:', error);
        document.getElementById('summary-text').innerHTML = `<p class="text-red-400">Failed to generate summary: ${error.message}</p>`;
    }
}

// Clear logs
function clearLogs() {
    allLogs = [];
    updateStats(0, 0, 100, '-');
    document.getElementById('error-codes').innerHTML = '<p class="text-center text-gray-400 py-8">No logs</p>';
    document.getElementById('error-types').innerHTML = '<p class="text-center text-gray-400 py-8">No logs</p>';
    document.getElementById('recent-logs').innerHTML = '<div class="text-center text-gray-400 py-8">No logs</div>';
    document.getElementById('summary-text').innerHTML = '<p class="italic">No data to summarize</p>';
}

// Update last update time
function updateLastUpdate() {
    const now = new Date().toLocaleTimeString();
    document.getElementById('last-update').textContent = `Last updated: ${now}`;
}

// Helper: Get error name
function getErrorName(code) {
    const names = {
        '200': 'OK',
        '400': 'Bad Request',
        '401': 'Unauthorized',
        '402': 'Payment Required',
        '403': 'Forbidden',
        '409': 'Conflict',
        '500': 'Internal Server Error',
        '503': 'Service Unavailable',
        '504': 'Gateway Timeout'
    };
    return names[code] || `HTTP ${code}`;
}
