// Cache busting
window.APP_VERSION = window.__PAGE_CONFIG__.appVersion;

// Global error handler
window.addEventListener('error', function(e) {
  console.error('GLOBAL ERROR:', e.error);
});

const APPLICATION_ID = window.__PAGE_CONFIG__.applicationId;
const CSRF_TOKEN = window.__PAGE_CONFIG__.csrfToken;

// ArchiMate element types by layer
const ELEMENT_TYPES = {
  strategy: ['Resource', 'Capability', 'CourseOfAction', 'ValueStream'],
  motivation: ['Stakeholder', 'Driver', 'Assessment', 'Goal', 'Outcome', 'Principle', 'Requirement', 'Constraint', 'Meaning', 'Value'],
  business: ['BusinessActor', 'BusinessRole', 'BusinessCollaboration', 'BusinessInterface', 'BusinessProcess', 'BusinessFunction', 'BusinessInteraction', 'BusinessEvent', 'BusinessService', 'BusinessObject', 'Contract', 'Representation', 'Product'],
  application: ['ApplicationComponent', 'ApplicationCollaboration', 'ApplicationInterface', 'ApplicationFunction', 'ApplicationProcess', 'ApplicationInteraction', 'ApplicationEvent', 'ApplicationService', 'DataObject'],
  technology: ['Node', 'Device', 'SystemSoftware', 'TechnologyCollaboration', 'TechnologyInterface', 'Path', 'CommunicationNetwork', 'TechnologyFunction', 'TechnologyProcess', 'TechnologyInteraction', 'TechnologyEvent', 'TechnologyService', 'Artifact'],
  physical: ['Equipment', 'Facility', 'DistributionNetwork', 'Material'],
  implementation: ['WorkPackage', 'Deliverable', 'ImplementationEvent', 'Plateau', 'Gap']
};

class ApplicationArchitectureManager {
  constructor(applicationId) {
    this.applicationId = applicationId;
    this.currentLayer = 'strategy';
    this.elements = {};
    this.documents = [];
    this.init();
  }

  async init() {
    await this.loadApplicationDetails();
    await this.loadElements();
    await this.loadDocuments();
    this.setupEventListeners();
    this.renderCurrentLayer();
  }

  async loadApplicationDetails() {
    try {
      const response = await fetch(`/dashboard/api/applications/${this.applicationId}/details`);
      if (!response.ok) throw new Error('Failed to load application details');
      const data = await response.json();
      this.updateHeader(data);
      this.updateLayerCounts(data.element_counts_by_layer);
    } catch (error) {
      console.error('Error loading application details:', error);
    }
  }

  updateHeader(data) {
    document.getElementById('app-name').textContent = data.name;
    document.getElementById('app-description').textContent = data.description || 'No description available';
    const statusEl = document.getElementById('app-status');
    statusEl.textContent = data.status;
    statusEl.className = 'status-badge ' + (data.status || 'development').toLowerCase();
  }

  updateLayerCounts(counts) {
    let total = 0;
    for (const [layer, count] of Object.entries(counts)) {
      const countEl = document.querySelector(`.layer-count[data-layer="${layer}"]`);
      if (countEl) {
        countEl.textContent = count;
      }
      total += count;
    }
    document.querySelector('.total-elements').textContent = total;
  }

  async loadElements() {
    try {
      const response = await fetch(`/dashboard/api/applications/${this.applicationId}/architecture/elements`);
      if (!response.ok) throw new Error('Failed to load elements');
      const data = await response.json();
      
      // Group elements by layer
      this.elements = {};
      for (const elem of data.elements) {
        const layer = elem.layer || 'application';
        if (!this.elements[layer]) this.elements[layer] = [];
        this.elements[layer].push(elem);
      }
    } catch (error) {
      console.error('Error loading elements:', error);
    }
  }

  async loadDocuments() {
    try {
      const response = await fetch(`/dashboard/api/applications/${this.applicationId}/architecture/documents`);
      if (!response.ok) throw new Error('Failed to load documents');
      const data = await response.json();
      this.documents = data.documents;
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  }

  setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.arch-tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        const layer = e.currentTarget.dataset.layer;
        this.switchLayer(layer);
      });
    });

    // Create element buttons
    document.querySelectorAll('.create-element-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const layer = this.currentLayer;
        this.openCreateModal(layer);
      });
    });

    // Create element form
    document.getElementById('create-element-form').addEventListener('submit', (e) => {
      e.preventDefault();
      this.createElement();
    });

    // Close modal
    document.querySelectorAll('.close-modal-btn').forEach(btn => {
      btn.addEventListener('click', () => this.closeModal());
    });

    // Modal overlay click
    document.getElementById('create-element-modal').addEventListener('click', (e) => {
      if (e.target.id === 'create-element-modal') {
        this.closeModal();
      }
    });

    // Search
    document.querySelectorAll('.layer-search').forEach(input => {
      input.addEventListener('input', (e) => {
        this.filterElements(e.target.value);
      });
    });

    // Export CSV
    document.getElementById('export-csv-btn').addEventListener('click', () => {
      this.exportCSV();
    });

    // Export JSON
    document.getElementById('export-json-btn').addEventListener('click', () => {
      this.exportJSON();
    });

    // Generate AI
    document.getElementById('generate-ai-btn').addEventListener('click', () => {
      this.generateWithAI();
    });

    // Upload document
    document.getElementById('upload-document-btn').addEventListener('click', () => {
      document.getElementById('document-upload').click();
    });

    document.getElementById('document-upload').addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        this.uploadDocument(e.target.files[0]);
      }
    });
  }

  switchLayer(layer) {
    this.currentLayer = layer;
    
    // Update tab styles
    document.querySelectorAll('.arch-tab').forEach(tab => {
      if (tab.dataset.layer === layer) {
        tab.classList.add('active');
        tab.style.color = 'var(--foreground)';
        tab.style.borderBottomColor = 'var(--primary)';
      } else {
        tab.classList.remove('active');
        tab.style.color = 'var(--muted-foreground)';
        tab.style.borderBottomColor = 'transparent';
      }
    });

    // Show/hide content
    if (layer === 'documents') {
      document.querySelector('.layer-content[data-layer="strategy"]').style.display = 'none';
      document.querySelector('.layer-content[data-layer="documents"]').style.display = 'block';
      // Re-initialize Lucide icons for the document analyzer component
      if (typeof lucide !== 'undefined') {
        lucide.createIcons();
      }
      this.renderDocuments();
    } else {
      document.querySelector('.layer-content[data-layer="strategy"]').style.display = 'block';
      document.querySelector('.layer-content[data-layer="documents"]').style.display = 'none';
      this.renderCurrentLayer();
    }
  }

  renderCurrentLayer() {
    const layer = this.currentLayer;
    if (layer === 'documents') {
      this.renderDocuments();
      return;
    }

    const elements = this.elements[layer] || [];
    const tbody = document.querySelector('.elements-tbody');

    if (elements.length === 0) {
      tbody.innerHTML = `
        <tr class="empty-state">
          <td colspan="5" style="text-align: center; padding: 3rem 1rem; color: var(--muted-foreground);">
            No elements in this layer. Click "Create Element" to add one.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = elements.map(el => {
      // Check if this is a vendor-deployed element
      const isVendorElement = el.template_element_id || el.source_product_id;
      const vendorBadge = isVendorElement ? `
        <span style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; padding: 0.125rem 0.375rem; border-radius: 9999px; font-size: 0.625rem; font-weight: 600; margin-left: 0.25rem;" title="Deployed from vendor template">
          VENDOR
        </span>
      ` : '';
      
      return `
      <tr data-element-id="${el.id}" data-model-type="${el.model_type || 'domain'}" style="${isVendorElement ? 'background: linear-gradient(90deg, rgba(59, 130, 246, 0.05) 0%, transparent 100%);' : ''}">
        <td class="editable" data-field="name" style="padding: 0.75rem 1rem; border-top: 1px solid var(--border); cursor: text;">
          ${this.escapeHtml(el.name)}${vendorBadge}
        </td>
        <td style="padding: 0.75rem 1rem; border-top: 1px solid var(--border);">
          <span style="background: ${isVendorElement ? 'linear-gradient(135deg, #3b82f6, #1d4ed8); color: white;' : 'var(--muted)'}; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">${el.archimate_type}</span>
        </td>
        <td style="padding: 0.75rem 1rem; border-top: 1px solid var(--border);">${el.framework || '-'}</td>
        <td class="editable" data-field="description" style="padding: 0.75rem 1rem; border-top: 1px solid var(--border); cursor: text; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${this.escapeHtml(el.description || '-')}</td>
        <td style="padding: 0.75rem 1rem; border-top: 1px solid var(--border); text-align: center;">
          <button class="edit-element-btn" data-element-id="${el.id}" style="background: none; border: none; cursor: pointer; color: var(--primary); padding: 0.25rem; margin-right: 0.5rem;" title="Edit">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
          </button>
          <button class="delete-element-btn" data-element-id="${el.id}" style="background: none; border: none; cursor: pointer; color: var(--destructive); padding: 0.25rem;" title="Delete">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </td>
      </tr>
    `;
    }).join('');

    // Attach event listeners
    this.attachInlineEditHandlers();
    this.attachDeleteHandlers();
    this.attachEditHandlers();
  }

  attachInlineEditHandlers() {
    document.querySelectorAll('.editable').forEach(cell => {
      cell.addEventListener('click', (e) => {
        this.enableInlineEdit(e.target);
      });
    });
  }

  enableInlineEdit(cell) {
    if (cell.querySelector('input, textarea')) return;

    const originalValue = cell.textContent.trim();
    const field = cell.dataset.field;
    const row = cell.closest('tr');
    const elementId = row.dataset.elementId;
    const modelType = row.dataset.modelType;

    // Only allow editing archimate elements for now
    if (modelType !== 'archimate') {
      this.showNotification('Inline editing is only available for ArchiMate elements', 'info');
      return;
    }

    const input = document.createElement('input');
    input.type = 'text';
    input.value = originalValue === '-' ? '' : originalValue;
    input.style.cssText = 'width: 100%; padding: 0.25rem; font-size: inherit; border: 1px solid var(--primary); border-radius: 4px;';
    
    cell.innerHTML = '';
    cell.appendChild(input);
    input.focus();

    const saveEdit = async () => {
      const newValue = input.value.trim();
      cell.textContent = newValue || '-';
      
      if (newValue !== originalValue && newValue !== '') {
        await this.updateElement(elementId, { [field]: newValue });
      }
    };

    input.addEventListener('blur', saveEdit);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        input.blur();
      } else if (e.key === 'Escape') {
        cell.textContent = originalValue;
      }
    });
  }

  attachDeleteHandlers() {
    document.querySelectorAll('.delete-element-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const elementId = e.currentTarget.dataset.elementId;
        await this.deleteElement(elementId);
      });
    });
  }

  attachEditHandlers() {
    document.querySelectorAll('.edit-element-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const elementId = e.currentTarget.dataset.elementId;
        await this.editElement(elementId);
      });
    });
  }

  async updateElement(elementId, updates) {
    try {
      const response = await fetch(
        `/dashboard/api/applications/${this.applicationId}/architecture/elements/${elementId}`,
        {
          method: 'PUT',
          headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN
          },
          body: JSON.stringify(updates)
        }
      );

      if (!response.ok) throw new Error('Update failed');

      const updatedElement = await response.json();
      
      // Update local cache
      const layer = updatedElement.layer;
      if (this.elements[layer]) {
        const index = this.elements[layer].findIndex(el => el.id == elementId);
        if (index !== -1) {
          this.elements[layer][index] = updatedElement;
        }
      }

      this.showNotification('Element updated successfully', 'success');
    } catch (error) {
      this.showNotification('Failed to update element', 'error');
      this.renderCurrentLayer();
    }
  }

  async deleteElement(elementId) {
    if (!confirm('Delete this element? This will also remove all its relationships.')) {
      return;
    }

    try {
      const response = await fetch(
        `/dashboard/api/applications/${this.applicationId}/architecture/elements/${elementId}`,
        { 
          method: 'DELETE',
          headers: { 'X-CSRFToken': CSRF_TOKEN }
        }
      );

      if (!response.ok) throw new Error('Delete failed');

      // Remove from cache
      for (const layer in this.elements) {
        this.elements[layer] = this.elements[layer].filter(el => el.id != elementId);
      }

      this.renderCurrentLayer();
      await this.loadApplicationDetails();
      this.showNotification('Element deleted', 'success');
    } catch (error) {
      this.showNotification('Failed to delete element', 'error');
    }
  }

  async editElement(elementId) {
    // Find the element in cache
    let element = null;
    for (const layer in this.elements) {
      const found = this.elements[layer].find(el => el.id == elementId);
      if (found) {
        element = found;
        break;
      }
    }

    if (!element) {
      this.showNotification('Element not found', 'error');
      return;
    }

    // Open edit modal
    this.openEditModal(element);
  }

  openEditModal(element) {
    // Create edit modal dynamically
    const modalHtml = `
      <div id="edit-element-modal" role="dialog" aria-modal="true" aria-labelledby="edit-element-title" class="fixed inset-0 bg-black/80 flex items-center justify-center opacity-0 invisible transition-opacity duration-200" style="z-index: 1000;">
        <div class="rounded-lg border bg-card text-card-foreground shadow-sm w-full max-w-2xl p-6 m-4 max-h-[90vh] overflow-y-auto">
          <h2 id="edit-element-title" class="m-0 mb-4 text-xl font-semibold">Edit Element</h2>
          <form id="edit-element-form">
            <input type="hidden" id="edit-element-id" value="${element.id}">
            <div class="flex flex-col gap-4">
              <div>
                <label class="block text-sm font-medium mb-2">Name *</label>
                <input type="text" id="edit-element-name" required class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" value="${this.escapeHtml(element.name)}">
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">Type *</label>
                <select id="edit-element-type" required class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                  <option value="${element.archimate_type}" selected>${element.archimate_type}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">Description</label>
                <textarea id="edit-element-description" rows="3" class="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">${this.escapeHtml(element.description || '')}</textarea>
              </div>
            </div>
            <div class="flex justify-end gap-2 mt-4">
              <button type="button" class="close-edit-modal-btn inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2" aria-label="Action">Cancel</button>
              <button type="submit" class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2" aria-label="Submit">Save Changes</button>
            </div>
          </form>
        </div>
      </div>
    `;

    // Add modal to page
    const modalContainer = document.createElement('div');
    modalContainer.innerHTML = modalHtml;
    document.body.appendChild(modalContainer);

    // Populate type options based on layer
    const typeSelect = document.getElementById('edit-element-type');
    const layerTypes = ELEMENT_TYPES[element.layer] || [];
    typeSelect.innerHTML = layerTypes.map(type => 
      `<option value="${type}" ${type === element.archimate_type ? 'selected' : ''}>${type}</option>`
    ).join('');

    // Attach event handlers
    document.getElementById('edit-element-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.saveEditedElement();
    });

    document.querySelector('.close-edit-modal-btn').addEventListener('click', () => {
      this.closeEditModal();
    });

    // Close on backdrop click
    document.getElementById('edit-element-modal').addEventListener('click', (e) => {
      if (e.target.id === 'edit-element-modal') {
        this.closeEditModal();
      }
    });

    // Show modal
    document.body.classList.add('overflow-hidden');
    setTimeout(() => {
      document.getElementById('edit-element-modal').classList.remove('opacity-0', 'invisible');
      document.getElementById('edit-element-modal').classList.add('opacity-100', 'visible');
    }, 10);
  }

  closeEditModal() {
    const modal = document.getElementById('edit-element-modal');
    if (modal) {
      document.body.classList.remove('overflow-hidden');
      modal.remove();
    }
  }

  async saveEditedElement() {
    const elementId = document.getElementById('edit-element-id').value;
    const name = document.getElementById('edit-element-name').value.trim();
    const archimateType = document.getElementById('edit-element-type').value;
    const description = document.getElementById('edit-element-description').value.trim();

    if (!name) {
      this.showNotification('Name is required', 'error');
      return;
    }

    try {
      const response = await fetch(
        `/dashboard/api/applications/${this.applicationId}/architecture/elements/${elementId}`,
        {
          method: 'PUT',
          headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN
          },
          body: JSON.stringify({
            name: name,
            archimate_type: archimateType,
            description: description
          })
        }
      );

      if (!response.ok) throw new Error('Update failed');

      const updatedElement = await response.json();
      
      // Update local cache
      const layer = updatedElement.layer;
      if (this.elements[layer]) {
        const index = this.elements[layer].findIndex(el => el.id == elementId);
        if (index !== -1) {
          this.elements[layer][index] = updatedElement;
        }
      }

      this.renderCurrentLayer();
      this.closeEditModal();
      this.showNotification('Element updated successfully', 'success');
    } catch (error) {
      this.showNotification('Failed to update element', 'error');
    }
  }

  openCreateModal(layer) {
    document.getElementById('element-layer').value = layer;
    document.getElementById('element-name').value = '';
    document.getElementById('element-description').value = '';
    document.getElementById('selected-template-id').value = '';
    
    // Reset framework dropdowns
    const frameworkSelect = document.getElementById('element-framework');
    const levelSelect = document.getElementById('element-level');
    const templateSelect = document.getElementById('element-template');
    
    levelSelect.innerHTML = '<option value="">-- Select Level --</option>';
    levelSelect.disabled = true;
    templateSelect.innerHTML = '<option value="">-- Select Template --</option>';
    templateSelect.disabled = true;
    
    // Load frameworks
    this.loadFrameworks();
    
    // Populate type dropdown
    const typeSelect = document.getElementById('element-type');
    typeSelect.innerHTML = '<option value="">Select type...</option>';
    const types = ELEMENT_TYPES[layer] || [];
    types.forEach(type => {
      const option = document.createElement('option');
      option.value = type;
      option.textContent = type;
      typeSelect.appendChild(option);
    });

    // Setup framework dropdown event listeners (once)
    if (!frameworkSelect.dataset.initialized) {
      frameworkSelect.addEventListener('change', (e) => this.onFrameworkChange(e.target.value));
      levelSelect.addEventListener('change', (e) => this.onLevelChange(e.target.value));
      templateSelect.addEventListener('change', (e) => this.onTemplateChange(e.target.value));
      frameworkSelect.dataset.initialized = 'true';
    }

    const modal = document.getElementById('create-element-modal');
    modal.removeAttribute('hidden');
    modal.setAttribute('aria-hidden', 'false');
    modal.style.display = 'flex';
    document.body.classList.add('overflow-hidden');
  }

  async loadFrameworks() {
    try {
      const response = await fetch('/dashboard/api/templates/frameworks');
      if (!response.ok) throw new Error('Failed to load frameworks');
      const frameworks = await response.json();
      
      const select = document.getElementById('element-framework');
      select.innerHTML = '<option value="">-- Select Framework --</option>';
      
      if (Array.isArray(frameworks)) {
        frameworks.forEach(fw => {
          const option = document.createElement('option');
          option.value = fw;
          option.textContent = fw;
          select.appendChild(option);
        });
      }
    } catch (error) {
      console.error('Error loading frameworks:', error);
    }
  }

  async onFrameworkChange(framework) {
    const levelSelect = document.getElementById('element-level');
    const templateSelect = document.getElementById('element-template');
    
    // Reset downstream dropdowns
    levelSelect.innerHTML = '<option value="">-- Select Level --</option>';
    templateSelect.innerHTML = '<option value="">-- Select Template --</option>';
    templateSelect.disabled = true;
    
    if (!framework) {
      levelSelect.disabled = true;
      return;
    }
    
    try {
      const response = await fetch(`/dashboard/api/templates/decomposition/levels?framework=${encodeURIComponent(framework)}`);
      if (!response.ok) throw new Error('Failed to load levels');
      const data = await response.json();
      
      levelSelect.disabled = false;
      if (data.levels && data.levels.length > 0) {
        data.levels.forEach(lvl => {
          const option = document.createElement('option');
          option.value = lvl.level;
          option.textContent = `${lvl.name} (${lvl.count})`;
          levelSelect.appendChild(option);
        });
      }
    } catch (error) {
      console.error('Error loading levels:', error);
      levelSelect.disabled = true;
    }
  }

  async onLevelChange(level) {
    const templateSelect = document.getElementById('element-template');
    const framework = document.getElementById('element-framework').value;
    
    templateSelect.innerHTML = '<option value="">-- Select Template --</option>';
    
    if (!level || !framework) {
      templateSelect.disabled = true;
      return;
    }
    
    try {
      const response = await fetch(`/dashboard/api/templates/by-level?framework=${encodeURIComponent(framework)}&level=${level}&limit=200`);
      if (!response.ok) throw new Error('Failed to load templates');
      const data = await response.json();
      
      templateSelect.disabled = false;
      if (data.templates && data.templates.length > 0) {
        data.templates.forEach(tpl => {
          const option = document.createElement('option');
          option.value = tpl.id;
          option.textContent = tpl.code ? `${tpl.code} - ${tpl.name}` : tpl.name;
          option.dataset.name = tpl.name;
          option.dataset.description = tpl.description || '';
          option.dataset.elementType = tpl.element_type;
          templateSelect.appendChild(option);
        });
      } else {
        templateSelect.innerHTML = '<option value="">No templates at this level</option>';
        templateSelect.disabled = true;
      }
    } catch (error) {
      console.error('Error loading templates:', error);
      templateSelect.disabled = true;
    }
  }

  onTemplateChange(templateId) {
    const templateSelect = document.getElementById('element-template');
    const selectedOption = templateSelect.options[templateSelect.selectedIndex];
    
    if (!templateId || !selectedOption) {
      document.getElementById('selected-template-id').value = '';
      return;
    }
    
    // Auto-populate fields from selected template
    const name = selectedOption.dataset.name || '';
    const description = selectedOption.dataset.description || '';
    const elementType = selectedOption.dataset.elementType || '';
    
    document.getElementById('element-name').value = name;
    document.getElementById('element-description').value = description;
    document.getElementById('selected-template-id').value = templateId;
    
    // Try to select the matching element type
    const typeSelect = document.getElementById('element-type');
    for (let i = 0; i < typeSelect.options.length; i++) {
      if (typeSelect.options[i].value === elementType) {
        typeSelect.selectedIndex = i;
        break;
      }
    }
  }

  closeModal() {
    const modal = document.getElementById('create-element-modal');
    modal.setAttribute('hidden', '');
    modal.setAttribute('aria-hidden', 'true');
    modal.style.display = '';
    document.body.classList.remove('overflow-hidden');
  }

  async createElement() {
    const form = document.getElementById('create-element-form');
    const formData = new FormData(form);
    const data = {
      name: formData.get('name'),
      archimate_type: formData.get('archimate_type'),
      layer: formData.get('layer'),
      description: formData.get('description')
    };

    try {
      const response = await fetch(
        `/dashboard/api/applications/${this.applicationId}/architecture/elements`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN
          },
          body: JSON.stringify(data)
        }
      );

      if (!response.ok) {
        const text = await response.text();
        console.error('Response text:', text);
        let error;
        try {
          error = JSON.parse(text);
        } catch (e) {
          error = { error: text };
        }
        throw new Error(error.error || 'Create failed');
      }

      const newElement = await response.json();
      
      // Add to cache
      const layer = newElement.layer;
      if (!this.elements[layer]) this.elements[layer] = [];
      this.elements[layer].push(newElement);

      this.closeModal();
      this.renderCurrentLayer();
      await this.loadApplicationDetails();
      this.showNotification('Element created successfully', 'success');
    } catch (error) {
      this.showNotification(error.message || 'Failed to create element', 'error');
    }
  }

  filterElements(searchTerm) {
    const layer = this.currentLayer;
    const allElements = this.elements[layer] || [];
    
    if (!searchTerm) {
      this.renderCurrentLayer();
      return;
    }

    const filtered = allElements.filter(el => 
      (el.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (el.description || '').toLowerCase().includes(searchTerm.toLowerCase())
    );

    const tbody = document.querySelector('.elements-tbody');
    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr class="empty-state">
          <td colspan="5" style="text-align: center; padding: 3rem 1rem; color: var(--muted-foreground);">
            No elements match your search.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = filtered.map(el => `
      <tr data-element-id="${el.id}" data-model-type="${el.model_type || 'domain'}">
        <td class="editable" data-field="name" style="padding: 0.75rem 1rem; border-top: 1px solid var(--border); cursor: text;">${this.escapeHtml(el.name)}</td>
        <td style="padding: 0.75rem 1rem; border-top: 1px solid var(--border);">
          <span style="background: var(--muted); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">${el.archimate_type}</span>
        </td>
        <td style="padding: 0.75rem 1rem; border-top: 1px solid var(--border);">${el.framework || '-'}</td>
        <td class="editable" data-field="description" style="padding: 0.75rem 1rem; border-top: 1px solid var(--border); cursor: text;">${this.escapeHtml(el.description || '-')}</td>
        <td style="padding: 0.75rem 1rem; border-top: 1px solid var(--border); text-align: center;">
          <button class="delete-element-btn" data-element-id="${el.id}" style="background: none; border: none; cursor: pointer; color: var(--destructive); padding: 0.25rem;" aria-label="Action">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </td>
      </tr>
    `).join('');

    this.attachInlineEditHandlers();
    this.attachDeleteHandlers();
  }

  renderDocuments() {
    // Re-initialize Lucide icons when documents tab is rendered
    if (typeof lucide !== 'undefined') {
      setTimeout(() => lucide.createIcons(), 100);
    }
    
    const grid = document.getElementById('documents-grid');
    
    if (this.documents.length === 0) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; text-align: center; padding: 3rem 1rem; color: var(--muted-foreground);">
          No documents uploaded yet. Click "Upload Document" to add one.
        </div>
      `;
      return;
    }

    grid.innerHTML = this.documents.map(doc => `
      <div class="rounded-lg border bg-card text-card-foreground shadow-sm p-4 flex gap-4 items-start" data-doc-id="${doc.id}">
        <div class="text-5xl w-12 h-12 flex items-center justify-center bg-muted rounded-lg">
          ${this.getDocIcon(doc.mime_type)}
        </div>
        <div class="flex-1 min-w-0">
          <h4 class="m-0 mb-2 text-sm font-semibold overflow-hidden text-overflow-ellipsis whitespace-nowrap">${this.escapeHtml(doc.filename)}</h4>
          <p class="m-0 text-xs text-muted-foreground">${doc.document_type} - v${doc.version || '1.0'}</p>
          <p class="m-0 text-xs text-muted-foreground">${this.formatFileSize(doc.file_size)} • ${this.formatDate(doc.created_at)}</p>
        </div>
        <div class="flex flex-col gap-1">
          <button class="download-doc-btn inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-2 py-1" data-doc-id="${doc.id}" aria-label="Action">Download</button>
          <button class="delete-doc-btn inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-2 py-1 text-destructive" data-doc-id="${doc.id}" aria-label="Action">Delete</button>
        </div>
      </div>
    `).join('');

    // Attach document event handlers
    document.querySelectorAll('.download-doc-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const docId = e.currentTarget.dataset.docId;
        window.location.href = `/dashboard/api/applications/${this.applicationId}/architecture/documents/${docId}`;
      });
    });

    document.querySelectorAll('.delete-doc-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const docId = e.currentTarget.dataset.docId;
        await this.deleteDocument(docId);
      });
    });
  }

  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', 'Architecture Diagram');
    formData.append('version', '1.0');

    try {
      const response = await fetch(
        `/dashboard/api/applications/${this.applicationId}/architecture/documents`,
        {
          method: 'POST',
          headers: { 'X-CSRFToken': CSRF_TOKEN },
          body: formData
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Upload failed');
      }

      const newDoc = await response.json();
      this.documents.unshift(newDoc);
      this.renderDocuments();
      this.showNotification('Document uploaded successfully', 'success');
    } catch (error) {
      this.showNotification(error.message || 'Failed to upload document', 'error');
    }

    document.getElementById('document-upload').value = '';
  }

  async deleteDocument(docId) {
    if (!confirm('Delete this document?')) return;

    try {
      const response = await fetch(
        `/dashboard/api/applications/${this.applicationId}/architecture/documents/${docId}`,
        { 
          method: 'DELETE',
          headers: { 'X-CSRFToken': CSRF_TOKEN }
        }
      );

      if (!response.ok) throw new Error('Delete failed');

      this.documents = this.documents.filter(d => d.id != docId);
      this.renderDocuments();
      this.showNotification('Document deleted', 'success');
    } catch (error) {
      this.showNotification('Failed to delete document', 'error');
    }
  }

  async generateWithAI() {
    if (!confirm('Generate ArchiMate elements using AI? This may take 30-60 seconds.')) {
      return;
    }

    const btn = document.getElementById('generate-ai-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generating...';

    try {
      const response = await fetch(
        `/dashboard/api/applications/${this.applicationId}/generate-architecture`,
        { 
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN
          },
          body: JSON.stringify({
            layers: ['strategy', 'motivation', 'business', 'application', 'technology', 'physical', 'implementation'],
            description: 'Generate comprehensive ArchiMate elements for this application'
          })
        }
      );

      if (!response.ok) throw new Error('AI generation failed');

      await this.loadElements();
      await this.loadApplicationDetails();
      this.renderCurrentLayer();
      this.showNotification('AI elements generated successfully', 'success');
    } catch (error) {
      this.showNotification('AI generation failed', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg><span style="margin-left: 0.25rem;">Generate with AI</span>';
    }
  }

  exportCSV() {
    window.location.href = `/dashboard/api/applications/${this.applicationId}/architecture/export-csv`;
  }

  exportJSON() {
    fetch(`/dashboard/api/applications/${this.applicationId}/architecture/export-json`)
      .then(response => response.json())
      .then(data => {
        // Create a blob from the JSON data
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        // Generate filename with timestamp
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        a.download = `application_${this.applicationId}_architecture_${timestamp}.json`;
        
        // Trigger download
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      })
      .catch(error => {
        console.error('Error exporting JSON:', error);
        alert('Failed to export JSON. Please try again.');
      });
  }

  showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 1rem;
      right: 1rem;
      padding: 1rem 1.5rem;
      border-radius: 8px;
      font-size: 0.875rem;
      z-index: 9999;
      animation: slideIn 0.3s ease;
      ${type === 'success' ? 'background: #10b981; color: white;' : ''}
      ${type === 'error' ? 'background: #ef4444; color: white;' : ''}
      ${type === 'info' ? 'background: #3b82f6; color: white;' : ''}
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
  }

  escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  getDocIcon(mimeType) {
    const icons = {
      'application/pdf': '📄',
      'application/msword': '📝',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📝',
      'image/png': '🖼️',
      'image/jpeg': '🖼️',
      'application/vnd.ms-excel': '📊',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '📊',
      'application/vnd.visio': '📐',
      'application/vnd.ms-visio.drawing': '📐',
    };
    return icons[mimeType] || '📁';
  }

  formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    return new Date(dateStr).toLocaleDateString('en-US', { 
      year: 'numeric', month: 'short', day: 'numeric' 
    });
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  try {
    window.archManager = new ApplicationArchitectureManager(APPLICATION_ID);
  } catch (error) {
    console.error('Error creating manager:', error);
  }
});
