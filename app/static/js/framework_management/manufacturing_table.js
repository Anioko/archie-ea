/**
 * Manufacturing Excellence Framework Data Table — extracted from
 * framework_management/manufacturing_table.html (UIUX-023)
 *
 * Requires DOM elements: searchInput, categoryFilter, maturityFilter,
 * statusFilter, selectAll, dataTableBody
 */
(function() {
'use strict';

let currentPage = 1;
let sortColumn = 'name';
let sortDirection = 'asc';
let tableData = [];

function setupEventListeners() {
    document.getElementById('searchInput').addEventListener('input', filterTable);
    document.getElementById('categoryFilter').addEventListener('change', filterTable);
    document.getElementById('maturityFilter').addEventListener('change', filterTable);
    document.getElementById('statusFilter').addEventListener('change', filterTable);
    document.getElementById('selectAll').addEventListener('change', toggleSelectAll);
}

function loadTableData() {
    tableData = [];
    fetch('/framework-management/api/manufacturing/instances')
        .then(function(r) { return r.json(); })
        .then(function(res) {
            tableData = res.data || [];
            renderTable();
        })
        .catch(function() {
            tableData = [];
            renderTable();
        });
}

function renderTable() {
    let tbody = document.getElementById('dataTableBody');
    if (typeof safeHTML === 'function') {
        safeHTML(tbody, '');
    } else {
        tbody.innerHTML = '';
    }

    let filteredData = getFilteredData();
    let sortedData = sortData(filteredData);
    let paginatedData = getPaginatedData(sortedData);

    let total = filteredData.length;
    let start = total === 0 ? 0 : (currentPage - 1) * 10 + 1;
    let end = Math.min(currentPage * 10, total);
    let paginationInfo = document.getElementById('paginationInfo');
    if (paginationInfo) {
        let startEl = document.getElementById('paginationStart');
        let endEl = document.getElementById('paginationEnd');
        let totalEl = document.getElementById('paginationTotal');
        if (startEl) startEl.textContent = start;
        if (endEl) endEl.textContent = end;
        if (totalEl) totalEl.textContent = total;
    }

    paginatedData.forEach(function(row) {
        let tr = document.createElement('tr');
        tr.className = 'hover:bg-muted';
        let setHTML = typeof safeHTML === 'function' ? safeHTML : function(el, html) { el.innerHTML = html; };
        setHTML(tr,
            '<td class="px-4 py-3"><input type="checkbox" class="rounded border-border" data-id="' + row.id + '"></td>' +
            '<td class="px-4 py-3 font-medium text-foreground">' + row.name + '</td>' +
            '<td class="px-4 py-3"><span class="px-2 py-1 text-xs rounded-full bg-primary/10 text-primary/90">' + row.category + '</span></td>' +
            '<td class="px-4 py-3"><div class="flex items-center"><span class="text-foreground">Level ' + row.maturity + '</span>' +
            '<div class="ml-2 w-16 bg-muted rounded-full h-2"><div class="bg-primary h-2 rounded-full" style="width: ' + ((row.maturity / 5) * 100) + '%"></div></div></div></td>' +
            '<td class="px-4 py-3"><div class="flex items-center"><span class="text-foreground">' + (row.performance != null ? row.performance + '%' : '—') + '</span>' +
            '<i class="fas fa-arrow-up text-emerald-500 text-xs ml-1"></i></div></td>' +
            '<td class="px-4 py-3"><span class="px-2 py-1 text-xs rounded-full ' + getStatusColor(row.status) + '">' + row.status + '</span></td>' +
            '<td class="px-4 py-3 text-muted-foreground">' + row.owner + '</td>' +
            '<td class="px-4 py-3 text-muted-foreground">' + row.lastUpdated + '</td>' +
            '<td class="px-4 py-3"><div class="flex space-x-2">' +
            '<button data-action="editCapability" data-id="' + row.id + '" class="text-primary hover:text-primary/90"><i class="fas fa-edit"></i></button>' +
            '<button data-action="viewCapability" data-id="' + row.id + '" class="text-emerald-600 hover:text-green-800"><i class="fas fa-eye"></i></button>' +
            '<button data-action="deleteCapability" data-id="' + row.id + '" class="text-destructive hover:text-red-800"><i class="fas fa-trash"></i></button>' +
            '</div></td>');
        tbody.appendChild(tr);
    });
}

function getFilteredData() {
    let searchTerm = document.getElementById('searchInput').value.toLowerCase();
    let categoryFilter = document.getElementById('categoryFilter').value;
    let maturityFilter = document.getElementById('maturityFilter').value;
    let statusFilter = document.getElementById('statusFilter').value;

    return tableData.filter(function(row) {
        let name = (row.name || '').toLowerCase();
        let owner = (row.owner || '').toLowerCase();
        let matchesSearch = name.includes(searchTerm) || owner.includes(searchTerm);
        let matchesCategory = !categoryFilter || row.category === categoryFilter;
        let matchesMaturity = !maturityFilter || row.maturity.toString() === maturityFilter;
        let matchesStatus = !statusFilter || row.status === statusFilter;
        return matchesSearch && matchesCategory && matchesMaturity && matchesStatus;
    });
}

function sortData(data) {
    return data.sort(function(a, b) {
        let aVal = a[sortColumn];
        let bVal = b[sortColumn];
        if (typeof aVal === 'string') { aVal = aVal.toLowerCase(); bVal = bVal.toLowerCase(); }
        if (sortDirection === 'asc') { return aVal > bVal ? 1 : -1; }
        return aVal < bVal ? 1 : -1;
    });
}

function getPaginatedData(data) {
    let start = (currentPage - 1) * 10;
    return data.slice(start, start + 10);
}

function getStatusColor(status) {
    let colors = {
        'active': 'bg-emerald-500/10 text-green-800',
        'implementing': 'bg-amber-500/10 text-yellow-800',
        'planned': 'bg-primary/10 text-primary/90',
        'deprecated': 'bg-destructive/10 text-red-800'
    };
    return colors[status] || 'bg-muted text-foreground';
}

function filterTable() {
    currentPage = 1;
    renderTable();
}

function toggleSelectAll() {
    let selectAll = document.getElementById('selectAll');
    let checkboxes = document.querySelectorAll('#dataTableBody input[type="checkbox"]');
    checkboxes.forEach(function(cb) { cb.checked = selectAll.checked; });
}

window.sortTable = function(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'asc';
    }
    renderTable();
};

window.editCapability = function(id) {};
window.viewCapability = function(id) {};

window.deleteCapability = async function(id) {
    if ((await Platform.modal.confirm('Are you sure you want to delete this capability?'))) {
        loadTableData();
    }
};

window.exportData = function() {
    window.open('/framework-management/manufacturing/export/csv', '_blank');
};

window.refreshData = function() {
    loadTableData();
};

window.previousPage = function() {
    if (currentPage > 1) { currentPage--; renderTable(); }
};

window.nextPage = function() {
    let totalPages = Math.ceil(getFilteredData().length / 10);
    if (currentPage < totalPages) { currentPage++; renderTable(); }
};

document.addEventListener('DOMContentLoaded', function() {
    loadTableData();
    setupEventListeners();
});

})();
