/**
 * Raw Log Viewer
 */

const AGGREGATOR_URL = 'http://localhost:9880';
let allLogs = [];
let filteredLogs = [];

// Refresh logs from aggregator
async function refreshLogs() {
    try {
        const response = await fetch(`${AGGREGATOR_URL}/logs/last-5min`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        allLogs = await response.json();
        console.log(`Loaded ${allLogs.length} logs`);

        // Update service filter options
        updateServiceFilter();

        // Apply current filters
        applyFilters();

        // Update count
        document.getElementById('log-count').textContent = `${allLogs.length} logs`;

    } catch (error) {
        console.error('Failed to load logs:', error);
        alert(`Failed to load logs: ${error.message}`);
    }
}

// Update service filter dropdown
function updateServiceFilter() {
    const serviceSelect = document.getElementById('filter-service');
    const services = [...new Set(allLogs.map(log => log.service).filter(Boolean))];

    // Keep current selection
    const currentValue = serviceSelect.value;

    // Rebuild options
    serviceSelect.innerHTML = '<option value="">All</option>' +
        services.map(s => `<option value="${s}">${s}</option>`).join('');

    // Restore selection if it still exists
    if (services.includes(currentValue)) {
        serviceSelect.value = currentValue;
    }
}

// Apply filters
function applyFilters() {
    const levelFilter = document.getElementById('filter-level').value;
    const serviceFilter = document.getElementById('filter-service').value;
    const searchText = document.getElementById('search-text').value.toLowerCase();

    filteredLogs = allLogs.filter(log => {
        // Level filter
        if (levelFilter && log.level !== levelFilter) return false;

        // Service filter
        if (serviceFilter && log.service !== serviceFilter) return false;

        // Search text
        if (searchText) {
            const searchableText = JSON.stringify(log).toLowerCase();
            if (!searchableText.includes(searchText)) return false;
        }

        return true;
    });

    renderLogs();
}

// Render logs to table
function renderLogs() {
    const tbody = document.getElementById('log-table');

    if (filteredLogs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="px-4 py-8 text-center text-gray-500">
                    No logs match the current filters
                </td>
            </tr>
        `;
        return;
    }

    // Sort by timestamp descending (newest first)
    const sorted = [...filteredLogs].sort((a, b) => {
        const timeA = new Date(a.timestamp || a.ingested_at);
        const timeB = new Date(b.timestamp || b.ingested_at);
        return timeB - timeA;
    });

    tbody.innerHTML = sorted.map((log, index) => {
        const levelClass = log.level === 'error' ? 'text-red-400' :
                          log.level === 'warn' ? 'text-yellow-400' :
                          'text-green-400';

        const timestamp = log.timestamp || log.ingested_at || '-';
        const level = log.level || '-';
        const service = log.service || '-';
        const code = log.code || '-';
        const message = log.message || '-';

        return `
            <tr class="hover:bg-gray-700/50 cursor-pointer" onclick="showLogDetail(${index})">
                <td class="px-4 py-2 text-gray-300">${timestamp.substring(11, 19)}</td>
                <td class="px-4 py-2 ${levelClass} font-semibold uppercase">${level}</td>
                <td class="px-4 py-2">${service}</td>
                <td class="px-4 py-2 ${code >= 400 ? 'text-red-400' : 'text-green-400'}">${code}</td>
                <td class="px-4 py-2 text-gray-300 truncate max-w-md">${message}</td>
                <td class="px-4 py-2">
                    <button class="text-blue-400 hover:text-blue-300 text-xs">View JSON</button>
                </td>
            </tr>
        `;
    }).join('');
}

// Show log detail modal
function showLogDetail(index) {
    const log = filteredLogs.sort((a, b) => {
        const timeA = new Date(a.timestamp || a.ingested_at);
        const timeB = new Date(b.timestamp || b.ingested_at);
        return timeB - timeA;
    })[index];

    const content = document.getElementById('log-detail-content');
    content.textContent = JSON.stringify(log, null, 2);

    document.getElementById('log-detail-modal').classList.remove('hidden');
}

// Close detail modal
function closeDetailModal() {
    document.getElementById('log-detail-modal').classList.add('hidden');
}

// Clear display
function clearDisplay() {
    allLogs = [];
    filteredLogs = [];
    document.getElementById('log-count').textContent = '0 logs';
    renderLogs();
}

// Auto-refresh every 5 seconds (optional)
// setInterval(refreshLogs, 5000);
