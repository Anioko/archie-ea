let APP_CONFIG = window.__APP_CONFIG__ || {};

let examples = {
  sales: {
    fields: [
      {name: "id", type: "integer", primary: true},
      {name: "customer", type: "string", label: "Customer"},
      {name: "revenue", type: "currency", label: "Revenue"},
      {name: "status", type: "status", values: ["pending", "completed", "refunded"]},
      {name: "sale_date", type: "date", label: "Sale Date"}
    ],
    count: 10,
    dashboard: {
      title: "Sales Dashboard",
      description: "Sales tracking dashboard with 10 records",
      sections: [
        {type: "metrics", fields: [
          {name: "revenue", type: "currency", label: "Revenue"},
          {name: "customer", type: "string", label: "Customer"},
          {name: "status", type: "status", label: "Status"}
        ]},
        {type: "table", "id": "sales_table"}
      ]
    }
  },
  users: {
    fields: [
      {name: "id", type: "integer", primary: true},
      {name: "username", type: "string", label: "Username"},
      {name: "email", type: "email", label: "Email"},
      {name: "role", type: "status", values: ["admin", "user", "guest"]},
      {name: "created_at", type: "date", label: "Joined"}
    ],
    count: 10,
    dashboard: {
      title: "User Management",
      description: "User accounts dashboard with 10 records",
      sections: [
        {type: "metrics", fields: [
          {name: "username", type: "string", label: "Username"},
          {name: "role", type: "status", label: "Role"}
        ]},
        {type: "table", "id": "users_table"}
      ]
    }
  },
  inventory: {
    fields: [
      {name: "id", type: "integer", primary: true},
      {name: "name", type: "string", label: "Product Name"},
      {name: "sku", type: "string", label: "SKU"},
      {name: "stock", type: "number", label: "Stock Level"},
      {name: "price", type: "currency", label: "Price"}
    ],
    count: 10,
    dashboard: {
      title: "Inventory Dashboard",
      description: "Product inventory dashboard with 10 records",
      sections: [
        {type: "metrics", fields: [
          {name: "stock", type: "number", label: "Stock Level"},
          {name: "price", type: "currency", label: "Price"}
        ]},
        {type: "table", "id": "inventory_table"}
      ]
    }
  },
  analytics: {
    fields: [
      {name: "id", type: "integer", primary: true},
      {name: "metric_name", type: "string", label: "Metric"},
      {name: "value", type: "number", label: "Value"},
      {name: "change", type: "percentage", label: "Change %"},
      {name: "recorded_at", type: "date", label: "Timestamp"}
    ],
    count: 10,
    dashboard: {
      title: "Analytics Dashboard",
      description: "Analytics metrics dashboard with 10 records",
      sections: [
        {type: "metrics", fields: [
          {name: "value", type: "number", label: "Value"},
          {name: "change", type: "percentage", label: "Change %"}
        ]},
        {type: "table", "id": "analytics_table"}
      ]
    }
  }
};

// Initialize Lucide icons
if (typeof lucide !== 'undefined') {
  lucide.createIcons();
}

// Schema card click handlers
document.querySelectorAll('.schema-card').forEach(function(card) {
  card.addEventListener('click', function() {
    let schema = card.dataset.schema;
    document.getElementById('schemaInput').value = JSON.stringify(examples[schema], null, 2);
  });
});

// Tab switching functionality
document.querySelectorAll('[data-code-tab]').forEach(function(tab) {
  tab.addEventListener('click', function() {
    let targetTab = tab.dataset.codeTab;

    // Update tab buttons
    document.querySelectorAll('[data-code-tab]').forEach(function(t) { t.classList.remove('active'); });
    tab.classList.add('active');

    // Update content areas
    document.querySelectorAll('.code-tab-content').forEach(function(content) {
      content.style.display = 'none';
    });

    let contentMap = {
      'view': 'viewCode',
      'template': 'templateCode',
      'javascript': 'javascriptCode',
      'rust': 'rustCode',
      'go': 'goCode'
    };

    let targetContent = document.getElementById(contentMap[targetTab]);
    if (targetContent) {
      targetContent.style.display = 'block';
    }
  });
});

// Generate button handler
document.getElementById('generateBtn').addEventListener('click', async function() {
  let schema = document.getElementById('schemaInput').value;
  let previewArea = document.getElementById('previewArea');

  try {
    let parsed = JSON.parse(schema);
    safeHTML(previewArea, '<div class="text-center py-8"><i data-lucide="loader-2" class="w-8 h-8 animate-spin mx-auto"></i><p class="mt-4 text-muted-foreground">Generating dashboard...</p></div>');

    let csrfMeta = document.querySelector('meta[name=csrf-token]');
    let response = await fetch('/code-generation/api/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : ''
      },
      body: JSON.stringify(parsed)
    });

    if (!response.ok) {
      throw new Error('Generation failed: ' + response.statusText);
    }

    let result = await response.json();

    // Render preview in iframe for proper isolation
    if (result.preview) {
      let iframe = document.createElement('iframe');
      iframe.style.width = '100%';
      iframe.style.minHeight = '600px';
      iframe.style.border = 'none';
      iframe.style.borderRadius = '0.375rem';
      safeHTML(previewArea, '');
      previewArea.appendChild(iframe);

      // Write full HTML document to iframe
      iframe.contentDocument.open();
      iframe.contentDocument.write(result.preview);
      iframe.contentDocument.close();

      // Auto-resize iframe to content
      setTimeout(function() {
        iframe.style.height = iframe.contentWindow.document.body.scrollHeight + 'px';
      }, 100);
    }

    // Display generated code in tabs
    if (result.files) {
      document.getElementById('viewCode').textContent = result.files.view_code || result.files.route_code || '# View code generated successfully';
      document.getElementById('templateCode').textContent = result.files.template_html || '<!-- Template code generated successfully -->';
      document.getElementById('javascriptCode').textContent = result.files.script_js || result.files.js_code || '// JavaScript code will be generated based on your interactions';
      document.getElementById('rustCode').textContent = result.files.rust_code || '// Rust code generated successfully';
      document.getElementById('goCode').textContent = result.files.go_code || '// Go code generated successfully';
    } else {
      // Fallback for backward compatibility
      document.getElementById('viewCode').textContent = result.code || '# View code generated successfully';
      document.getElementById('templateCode').textContent = '<!-- Template not available in this version -->';
      document.getElementById('javascriptCode').textContent = '// JavaScript not available in this version';
      document.getElementById('rustCode').textContent = '// Rust not available in this version';
      document.getElementById('goCode').textContent = '// Go not available in this version';
    }

  } catch (e) {
    safeHTML(previewArea, '<div class="text-center py-8"><i data-lucide="alert-circle" class="w-8 h-8 text-destructive mx-auto"></i><p class="mt-4 text-destructive">Error: ' + e.message + '</p></div>');
    console.error('Generation error:', e);
  }
});

// Validate button handler
document.getElementById('validateBtn').addEventListener('click', function() {
  try {
    JSON.parse(document.getElementById('schemaInput').value);
    // Show success message using shadcn toast
    let toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-card border border-border rounded-lg p-4 shadow-lg z-50';
    safeHTML(toast, '<div class="flex items-center gap-2"><i data-lucide="check-circle" class="w-5 h-5 text-emerald-600"></i><span class="text-foreground">Schema is valid JSON!</span></div>');
    document.body.appendChild(toast);
    setTimeout(function() {
      document.body.removeChild(toast);
    }, 3000);
  } catch (e) {
    // Show error message using shadcn toast
    let toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-card border border-border rounded-lg p-4 shadow-lg z-50';
    safeHTML(toast, '<div class="flex items-center gap-2"><i data-lucide="x-circle" class="w-5 h-5 text-destructive"></i><span class="text-destructive">Invalid JSON: ' + e.message + '</span></div>');
    document.body.appendChild(toast);
    setTimeout(function() {
      document.body.removeChild(toast);
    }, 3000);
  }
});

// Copy code button handler
document.getElementById('copyCodeBtn').addEventListener('click', function() {
  let activeCode = document.querySelector('.code-tab-content[style*="display: block"], .code-tab-content.active:not([style*="display: none"])');
  if (activeCode) {
    navigator.clipboard.writeText(activeCode.textContent);
    let activeTabEl = document.querySelector('[data-code-tab].active');
    let activeTab = activeTabEl ? activeTabEl.dataset.codeTab : 'view';

    // Show success toast
    let toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-card border border-border rounded-lg p-4 shadow-lg z-50';
    safeHTML(toast, '<div class="flex items-center gap-2"><i data-lucide="check" class="w-5 h-5 text-emerald-600"></i><span class="text-foreground">' + activeTab + ' code copied to clipboard!</span></div>');
    document.body.appendChild(toast);
    setTimeout(function() {
      document.body.removeChild(toast);
    }, 3000);
  }
});

// Download button handler
document.getElementById('downloadBtn').addEventListener('click', async function() {
  try {
    let schema = JSON.parse(document.getElementById('schemaInput').value);

    let csrfMeta = document.querySelector('meta[name=csrf-token]');
    let response = await fetch('/dashboard/applications/download-template', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : ''
      },
      body: JSON.stringify(schema)
    });

    if (!response.ok) throw new Error('Download failed');

    // Create download link
    let blob = await response.blob();
    let url = window.URL.createObjectURL(blob);
    let a = document.createElement('a');
    a.href = url;
    a.download = (schema.dashboard && schema.dashboard.title ? schema.dashboard.title : 'dashboard') + '_generated.zip';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    // Show success toast
    let toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-card border border-border rounded-lg p-4 shadow-lg z-50';
    safeHTML(toast, '<div class="flex items-center gap-2"><i data-lucide="download" class="w-5 h-5 text-emerald-600"></i><span class="text-foreground">Files downloaded successfully!</span></div>');
    document.body.appendChild(toast);
    setTimeout(function() {
      document.body.removeChild(toast);
    }, 3000);
  } catch (e) {
    // Show error toast
    let toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-card border border-border rounded-lg p-4 shadow-lg z-50';
    safeHTML(toast, '<div class="flex items-center gap-2"><i data-lucide="x-circle" class="w-5 h-5 text-destructive"></i><span class="text-destructive">Download failed: ' + e.message + '</span></div>');
    document.body.appendChild(toast);
    setTimeout(function() {
      document.body.removeChild(toast);
    }, 3000);
  }
});
