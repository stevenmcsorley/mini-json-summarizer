/**
 * Monitoring Dashboard - Uses ONLY Mini JSON Summarizer
 * No manual calculations - everything from the summarizer's extractors
 */

const AGGREGATOR_URL = 'http://localhost:9880';
const SUMMARIZER_URL = 'http://localhost:8080';

// Manual refresh - get summary from Mini JSON Summarizer
async function refreshDashboard() {
    console.log('Refreshing dashboard...');

    try {
        // Step 1: Fetch logs from aggregator
        const logsResponse = await fetch(`${AGGREGATOR_URL}/logs/last-5min`);
        if (!logsResponse.ok) {
            throw new Error(`Aggregator error: ${logsResponse.status}`);
        }

        const logs = await logsResponse.json();
        console.log(`Fetched ${logs.length} logs`);

        if (logs.length === 0) {
            showEmptyState();
            updateLastUpdate();
            return;
        }

        // Step 2: Send to Mini JSON Summarizer with logs profile
        const summaryResponse = await fetch(`${SUMMARIZER_URL}/v1/summarize-json`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                json: logs,
                profile: 'logs',
                stream: false
            })
        });

        if (!summaryResponse.ok) {
            throw new Error(`Summarizer error: ${summaryResponse.status}`);
        }

        const summary = await summaryResponse.json();
        console.log('Summary received:', summary);

        // Step 3: Extract data from bullets
        if (summary.bullets && summary.bullets.length > 0) {
            processSummaryBullets(summary.bullets, logs.length);
        } else {
            showEmptyState();
        }

        updateLastUpdate();

    } catch (error) {
        console.error('Dashboard refresh failed:', error);
        alert(`Failed to refresh: ${error.message}`);
    }
}

// Process bullets from Mini JSON Summarizer
function processSummaryBullets(bullets, totalLogs) {
    console.log('Processing bullets:', bullets);

    // Find specific extractors by name
    let levelExtractor = null;
    let serviceExtractor = null;
    let codeExtractor = null;
    let timebucketExtractor = null;

    // Scan all bullets for extractors
    bullets.forEach(bullet => {
        if (bullet.extractors && Array.isArray(bullet.extractors)) {
            bullet.extractors.forEach(ext => {
                if (ext.name.startsWith('categorical:level')) levelExtractor = ext;
                else if (ext.name.startsWith('categorical:service')) serviceExtractor = ext;
                else if (ext.name.startsWith('categorical:code')) codeExtractor = ext;
                else if (ext.name.startsWith('timebucket:')) timebucketExtractor = ext;
            });
        }
    });

    // Update stats from extractors
    updateStats(totalLogs, levelExtractor, serviceExtractor, timebucketExtractor);

    // Display error codes
    if (codeExtractor && codeExtractor.top) {
        displayErrorCodes(codeExtractor.top, totalLogs);
    }

    // Display services
    if (serviceExtractor && serviceExtractor.top) {
        displayServices(serviceExtractor.top, totalLogs);
    }

    // Display log levels
    if (levelExtractor && levelExtractor.top) {
        displayLogLevels(levelExtractor.top, totalLogs);
    }

    // Display time buckets
    if (timebucketExtractor && timebucketExtractor.top) {
        displayTimeBuckets(timebucketExtractor.top);
    }

    // Display full summary text
    displayFullSummary(bullets);
}

// Update top stats
function updateStats(totalLogs, levelExtractor, serviceExtractor, timebucketExtractor) {
    // Total events
    document.getElementById('stat-total').textContent = totalLogs;

    // Error rate (from level extractor)
    if (levelExtractor && levelExtractor.top) {
        const errorItem = levelExtractor.top.find(([level]) => level === 'error');
        const errorCount = errorItem ? errorItem[1] : 0;
        const errorRate = ((errorCount / totalLogs) * 100).toFixed(1);
        document.getElementById('stat-error-rate').textContent = `${errorRate}%`;
    } else {
        document.getElementById('stat-error-rate').textContent = '0%';
    }

    // Services count
    if (serviceExtractor && serviceExtractor.top) {
        document.getElementById('stat-services').textContent = serviceExtractor.top.length;
    } else {
        document.getElementById('stat-services').textContent = '0';
    }

    // Time range (from timebucket extractor)
    if (timebucketExtractor && timebucketExtractor.top) {
        document.getElementById('stat-timerange').textContent = timebucketExtractor.top.length;
    } else {
        document.getElementById('stat-timerange').textContent = '0';
    }
}

// Display error codes from categorical:code extractor
function displayErrorCodes(topCodes, totalLogs) {
    const container = document.getElementById('error-codes');

    if (topCodes.length === 0) {
        container.innerHTML = '<p class="text-center text-muted py-4 text-sm">No error codes found</p>';
        return;
    }

    container.innerHTML = topCodes.map(([code, count]) => {
        const percentage = ((count / totalLogs) * 100).toFixed(1);
        const isError = parseInt(code) >= 400;
        const fillClass = isError ? 'error' : '';

        return `
            <div>
                <div class="flex items-center justify-between mb-1">
                    <div class="flex items-center space-x-2">
                        <span class="text-sm font-medium ${isError ? 'text-red-400' : 'text-green-400'}">${code}</span>
                        <span class="text-xs text-muted">${getErrorName(code)}</span>
                    </div>
                    <div class="flex items-center space-x-3">
                        <span class="text-xs text-muted">${percentage}%</span>
                        <span class="text-sm font-semibold text-white">${count}</span>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill ${fillClass}" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

// Display services from categorical:service extractor
function displayServices(topServices, totalLogs) {
    const container = document.getElementById('services');

    container.innerHTML = topServices.map(([service, count]) => {
        const percentage = ((count / totalLogs) * 100).toFixed(1);

        return `
            <div>
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm font-medium text-white">${service}</span>
                    <div class="flex items-center space-x-3">
                        <span class="text-xs text-muted">${percentage}%</span>
                        <span class="text-sm font-semibold text-white">${count}</span>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

// Display log levels from categorical:level extractor
function displayLogLevels(topLevels, totalLogs) {
    const container = document.getElementById('log-levels');

    container.innerHTML = topLevels.map(([level, count]) => {
        const percentage = ((count / totalLogs) * 100).toFixed(1);
        const levelColors = {
            'error': 'text-red-400',
            'warn': 'text-yellow-400',
            'info': 'text-blue-400',
            'debug': 'text-gray-400'
        };
        const fillClasses = {
            'error': 'error',
            'warn': 'warning',
            'info': '',
            'debug': ''
        };

        return `
            <div>
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm font-medium ${levelColors[level] || 'text-white'} uppercase">${level}</span>
                    <div class="flex items-center space-x-3">
                        <span class="text-xs text-muted">${percentage}%</span>
                        <span class="text-sm font-semibold text-white">${count}</span>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill ${fillClasses[level] || ''}" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

// Display time buckets from timebucket extractor
function displayTimeBuckets(topBuckets) {
    const container = document.getElementById('time-buckets');

    const maxCount = Math.max(...topBuckets.map(([, count]) => count));

    container.innerHTML = topBuckets.map(([bucket, count]) => {
        const percentage = ((count / maxCount) * 100).toFixed(1);
        const timeLabel = bucket.substring(11, 16); // Extract HH:MM

        return `
            <div>
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm font-medium text-white">${timeLabel}</span>
                    <span class="text-sm font-semibold text-white">${count}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

// Display full summary text
function displayFullSummary(bullets) {
    const container = document.getElementById('full-summary');

    const summaryHtml = bullets.map(bullet => {
        return `<p class="text-sm text-white leading-relaxed">• ${bullet.text}</p>`;
    }).join('');

    container.innerHTML = summaryHtml;
}

// Show empty state
function showEmptyState() {
    document.getElementById('stat-total').textContent = '0';
    document.getElementById('stat-error-rate').textContent = '0%';
    document.getElementById('stat-services').textContent = '0';
    document.getElementById('stat-timerange').textContent = '0';

    const emptyMsg = '<p class="text-center text-muted py-4 text-sm">No data available</p>';
    document.getElementById('error-codes').innerHTML = emptyMsg;
    document.getElementById('services').innerHTML = emptyMsg;
    document.getElementById('log-levels').innerHTML = emptyMsg;
    document.getElementById('time-buckets').innerHTML = emptyMsg;
    document.getElementById('full-summary').innerHTML = '<p class="text-sm text-muted italic">No logs to analyze</p>';
}

// Update last update time
function updateLastUpdate() {
    const now = new Date().toLocaleTimeString();
    document.getElementById('last-update').textContent = `Updated: ${now}`;
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
