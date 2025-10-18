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

// Connect to SSE stream (simulated - will connect to real summarizer)
function connectSSE() {
    // In production, this will connect to the actual summarizer
    // For now, we'll simulate with a demo data generator

    // Real connection will be:
    // const eventSource = new EventSource('http://localhost:8080/v1/summarize-json?profile=logs&stream=true');

    // Simulate streaming data for demo
    startDemoStream();
}

// Demo data generator (simulates what SSE will provide)
function startDemoStream() {
    setInterval(() => {
        const demoData = generateDemoData();
        handleSSEMessage(demoData);
    }, 2000);
}

function generateDemoData() {
    const errorCodes = [504, 500, 401, 429, 503];
    const services = ['api', 'auth', 'worker'];

    return {
        phase: 'summary',
        bullet: {
            text: `Generated at ${new Date().toLocaleTimeString()}`,
            evidence: {
                level: {
                    top: [
                        ['error', Math.floor(Math.random() * 50) + 10],
                        ['warn', Math.floor(Math.random() * 30) + 5],
                        ['info', Math.floor(Math.random() * 100) + 50]
                    ]
                },
                service: {
                    top: services.map(s => [s, Math.floor(Math.random() * 40) + 5])
                },
                code: {
                    top: errorCodes.map(c => [c, Math.floor(Math.random() * 30) + 2])
                }
            }
        }
    };
}

// Handle SSE messages
function handleSSEMessage(data) {
    eventCount++;
    document.getElementById('event-counter').textContent = `${eventCount} events`;

    if (data.phase === 'summary' && data.bullet && data.bullet.evidence) {
        updateDashboard(data.bullet.evidence);
        addLogEntry(data.bullet.text);
    }
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

    // Keep last 20 data points
    if (errorChart.data.labels.length > 20) {
        errorChart.data.labels.shift();
        errorChart.data.datasets[0].data.shift();
    }

    errorChart.update();
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
