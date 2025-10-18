/**
 * Live Error Monitoring Dashboard
 * Powered by Mini JSON Summarizer SSE streaming
 */

let eventCount = 0;
let errorChart = null;
let errorData = new Map();
let serviceHealth = new Map();

// Initialize Chart.js
function initChart() {
    const ctx = document.getElementById('error-chart').getContext('2d');
    errorChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Error Count',
                data: [],
                borderColor: 'rgb(239, 68, 68)',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.7)'
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.7)'
                    }
                }
            }
        }
    });
}

// Connect to REAL SSE stream from Mini JSON Summarizer
function connectSSE() {
    console.log('Starting streaming summarization polling...');
    updateConnectionStatus('connected');

    // Poll the summarizer every 10 seconds (reduced to prevent PC slowdown)
    pollSummarizer();
    setInterval(pollSummarizer, 10000);
}

async function pollSummarizer() {
    try {
        const response = await fetch('http://localhost:8080/v1/summarize-json', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                json_url: 'http://log-aggregator:9880/logs/last-5min',
                profile: 'logs',
                stream: true,
                focus: ['level', 'service', 'code']
            })
        });

        if (!response.ok) {
            console.error('Summarizer error:', response.status, response.statusText);
            updateConnectionStatus('error');
            return;
        }

        // Read SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE messages
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep incomplete message in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        if (data.phase === 'summary') {
                            handleSSEMessage(data);
                        }
                    } catch (error) {
                        console.error('Error parsing SSE data:', error);
                    }
                }
            }
        }

        updateConnectionStatus('connected');
    } catch (error) {
        console.error('Polling error:', error);
        updateConnectionStatus('error');
    }
}

// Update connection status indicator
function updateConnectionStatus(status) {
    const indicator = document.getElementById('connection-status');
    if (indicator) {
        indicator.textContent = status === 'connected' ? '🟢 Live' : '🔴 Disconnected';
        indicator.className = status === 'connected' ? 'text-green-400' : 'text-red-400';
    }
}

// Handle SSE messages from Mini JSON Summarizer
function handleSSEMessage(data) {
    eventCount++;
    document.getElementById('event-counter').textContent = `${eventCount} events`;

    // Real summarizer sends bullets with extractors in the format:
    // { phase: 'summary', bullet: { text: '...', extractors: [...] } }
    if (data.phase === 'summary' && data.bullet) {
        const bullet = data.bullet;

        // Extract evidence from extractors
        const evidence = extractEvidenceFromBullet(bullet);

        if (evidence) {
            updateDashboard(evidence);
        }

        // Add bullet text to log stream
        if (bullet.text) {
            addLogEntry(bullet.text);
        }
    }
}

// Extract evidence from bullet extractors
function extractEvidenceFromBullet(bullet) {
    const evidence = {
        code: null,
        service: null,
        level: null
    };

    // Extractors are in format: { name: 'categorical:code', top: [...] }
    if (bullet.extractors && Array.isArray(bullet.extractors)) {
        bullet.extractors.forEach(extractor => {
            if (extractor.name && extractor.name.startsWith('categorical:')) {
                const field = extractor.name.split(':')[1];

                if (field === 'code' && extractor.top) {
                    evidence.code = { top: extractor.top };
                } else if (field === 'service' && extractor.top) {
                    evidence.service = { top: extractor.top };
                } else if (field === 'level' && extractor.top) {
                    evidence.level = { top: extractor.top };
                }
            }
        });
    }

    return evidence;
}

// Update dashboard panels
function updateDashboard(evidence) {
    if (evidence.code && evidence.code.top) {
        updateTopErrors(evidence.code.top);
    }

    if (evidence.service && evidence.service.top) {
        updateServiceHealth(evidence.service.top);
    }

    if (evidence.level && evidence.level.top) {
        updateErrorChart(evidence.level.top);
    }
}

// Update Top Errors panel
function updateTopErrors(errorCodes) {
    const container = document.getElementById('top-errors');
    container.innerHTML = errorCodes.map(([code, count]) => {
        const severity = code >= 500 ? 'error' : code >= 400 ? 'warning' : 'info';
        const bgColor = severity === 'error' ? 'bg-red-500/20' :
                       severity === 'warning' ? 'bg-yellow-500/20' : 'bg-blue-500/20';
        const icon = severity === 'error' ? '🔴' : severity === 'warning' ? '🟡' : '🔵';

        return `
            <div class="${bgColor} rounded-lg p-3 flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <span class="text-xl">${icon}</span>
                    <div>
                        <div class="font-semibold">${getErrorName(code)}</div>
                        <div class="text-sm text-gray-400">HTTP ${code}</div>
                    </div>
                </div>
                <div class="text-2xl font-bold">${count}</div>
            </div>
        `;
    }).join('');
}

// Update Service Health panel
function updateServiceHealth(services) {
    const container = document.getElementById('service-health');
    container.innerHTML = services.map(([service, errorCount]) => {
        const status = errorCount > 30 ? 'critical' : errorCount > 10 ? 'degraded' : 'healthy';
        const statusColor = status === 'critical' ? 'text-red-400' :
                           status === 'degraded' ? 'text-yellow-400' : 'text-green-400';
        const icon = status === 'critical' ? '🔴' : status === 'degraded' ? '🟡' : '🟢';
        const statusText = status.toUpperCase();

        return `
            <div class="bg-white/5 rounded-lg p-3 flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <span class="text-xl">${icon}</span>
                    <div>
                        <div class="font-semibold">${service}-service</div>
                        <div class="text-sm text-gray-400">${errorCount} errors</div>
                    </div>
                </div>
                <div class="${statusColor} font-semibold">${statusText}</div>
            </div>
        `;
    }).join('');
}

// Update error chart
function updateErrorChart(levels) {
    const now = new Date().toLocaleTimeString();
    const errorCount = levels.find(([level]) => level === 'error')?.[1] || 0;

    errorChart.data.labels.push(now);
    errorChart.data.datasets[0].data.push(errorCount);

    // Keep last 20 data points (not infinite)
    if (errorChart.data.labels.length > 20) {
        errorChart.data.labels.shift();
        errorChart.data.datasets[0].data.shift();
    }

    // Use 'none' mode to prevent animations that cause performance issues
    errorChart.update('none');
}

// Add log entry to stream
function addLogEntry(text) {
    const logStream = document.getElementById('log-stream');
    const timestamp = new Date().toISOString();

    const entry = document.createElement('div');
    entry.className = 'text-green-400';
    entry.textContent = `[${timestamp}] ${text}`;

    logStream.insertBefore(entry, logStream.firstChild);

    // Keep last 100 entries
    while (logStream.children.length > 100) {
        logStream.removeChild(logStream.lastChild);
    }
}

// Clear logs
function clearLogs() {
    document.getElementById('log-stream').innerHTML = '';
    eventCount = 0;
    document.getElementById('event-counter').textContent = '0 events';
}

// Trigger errors on a specific service
async function triggerError(service, count = 10) {
    const ports = { api: 8081, auth: 8082, worker: 8083 };
    const port = ports[service];

    if (!port) {
        console.error('Unknown service:', service);
        return;
    }

    console.log(`Triggering ${count} requests to ${service} service...`);

    // Make parallel requests to trigger errors
    const promises = [];
    for (let i = 0; i < count; i++) {
        const endpoint = service === 'api' ? '/api/users' :
                        service === 'auth' ? '/auth/login' :
                        '/jobs/process';

        promises.push(
            fetch(`http://localhost:${port}${endpoint}`, {
                method: service === 'api' ? 'GET' : 'POST'
            }).catch(err => console.log(`Request ${i} failed (expected)`))
        );
    }

    await Promise.all(promises);
    console.log(`✅ Triggered ${count} requests to ${service} service`);
}

// Trigger error storm across all services
async function triggerStorm() {
    console.log('🔥 Triggering error storm...');
    await Promise.all([
        triggerError('api', 20),
        triggerError('auth', 20),
        triggerError('worker', 20)
    ]);
    console.log('✅ Error storm complete');
}

// Trigger 504 spike
async function triggerSpike() {
    console.log('⚡ Triggering 504 spike...');
    await triggerError('api', 50);
    console.log('✅ 504 spike complete');
}

// Helper: Get error name from code
function getErrorName(code) {
    const names = {
        504: 'Gateway Timeout',
        500: 'Internal Error',
        503: 'Service Unavailable',
        401: 'Unauthorized',
        403: 'Forbidden',
        429: 'Rate Limited'
    };
    return names[code] || `HTTP ${code}`;
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    initChart();
    connectSSE();
});
