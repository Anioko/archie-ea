// Permissions Management JavaScript
document.addEventListener('DOMContentLoaded', function() {
    function escapeHtml(str) {
        if (str == null) return '';
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }
    let permissions = [];
    let users = [];
    let roles = [];
    let selectedPermissions = new Set();
    let selectedUsers = new Set();
    let selectedRoles = new Set();
    let validationResults = null;

    // DOM Elements
    const permissionTree = document.getElementById('permission-tree');
    const permissionFilter = document.getElementById('permission-filter');
    const userSelector = document.getElementById('user-selector');
    const roleSelector = document.getElementById('role-selector');
    const userPermissions = document.getElementById('user-permissions');
    const rolePermissions = document.getElementById('role-permissions');
    const bulkAssignment = document.getElementById('bulk-assignment');
    const conflictResolution = document.getElementById('conflict-resolution');
    const validationResultsDiv = document.getElementById('validation-results');
    const validationList = document.getElementById('validation-list');
    const conflictList = document.getElementById('conflict-list');
    const auditEntries = document.getElementById('audit-entries');

    // Modal Elements
    const permissionModal = document.getElementById('permission-modal');
    const deleteModal = document.getElementById('permission-delete-modal');
    const permissionForm = document.getElementById('permission-form');

    // Initialize
    loadPermissions();
    loadUsersAndRoles();

    // Event Listeners
    permissionFilter.addEventListener('change', filterPermissions);
    userSelector.addEventListener('change', loadUserPermissions);
    roleSelector.addEventListener('change', loadRolePermissions);

    // Modal Events
    document.getElementById('btn-create-permission').addEventListener('click', () => openPermissionModal());
    document.getElementById('btn-close-permission-modal').addEventListener('click', closePermissionModal);
    document.getElementById('btn-cancel-permission-modal').addEventListener('click', closePermissionModal);
    document.getElementById('btn-cancel-delete').addEventListener('click', closeDeleteModal);
    document.getElementById('btn-confirm-delete').addEventListener('click', confirmDelete);

    // Form Events
    permissionForm.addEventListener('submit', savePermission);

    // Tree Actions
    document.getElementById('btn-expand-tree').addEventListener('click', expandTree);
    document.getElementById('btn-collapse-tree').addEventListener('click', collapseTree);

    // Validation and Testing
    document.getElementById('btn-test-permissions').addEventListener('click', testPermissions);
    document.getElementById('btn-validate-permissions').addEventListener('click', validatePermissions);
    document.getElementById('btn-close-validation').addEventListener('click', () => validationResultsDiv.style.display = 'none');

    // Bulk Actions
    document.getElementById('btn-close-bulk').addEventListener('click', () => bulkAssignment.style.display = 'none');
    document.getElementById('btn-assign-permissions').addEventListener('click', assignBulkPermissions);
    document.getElementById('btn-revoke-permissions').addEventListener('click', revokeBulkPermissions);

    // Conflict Resolution
    document.getElementById('btn-resolve-conflicts').addEventListener('click', resolveConflicts);

    async function loadPermissions() {
        try {
            const response = await fetch('/admin/api/enterprise-roles');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'Failed to load permissions');
            permissions = data.permissions;
            renderPermissions();
        } catch (error) {
            console.error('Failed to load permissions:', error);
            showError('Failed to load permissions: ' + error.message);
        }
    }

    async function loadUsersAndRoles() {
        try {
            const [usersResp, rolesResp] = await Promise.all([
                fetch('/admin/api/enterprise-roles/users'),
                fetch('/admin/api/roles')
            ]);
            const usersData = usersResp.ok ? await usersResp.json() : { users: [] };
            const rolesData = rolesResp.ok ? await rolesResp.json() : { roles: [] };

            users = (usersData.users || []).map(u => ({
                id: u.id,
                name: u.name || u.email,
                email: u.email,
                enterprise_role: u.enterprise_role
            }));
            roles = rolesData.roles || [];

            userSelector.innerHTML = '<option value="">Choose a user...</option>' + /* safe-html: escapeHtml() applied to all dynamic values */
                users.map(user => `<option value="${escapeHtml(user.id)}">${escapeHtml(user.name)} (${escapeHtml(user.email)})</option>`).join('');

            roleSelector.innerHTML = '<option value="">Choose a role...</option>' + /* safe-html: escapeHtml() applied to all dynamic values */
                roles.map(role => `<option value="${escapeHtml(role.id)}">${escapeHtml(role.name)}</option>`).join('');
        } catch (error) {
            console.error('Failed to load users and roles:', error);
        }
    }

    function renderPermissions() {
        const filteredPermissions = getFilteredPermissions();

        if (filteredPermissions.length === 0) {
            permissionTree.innerHTML = ` /* safe-html */
                <div class="text-center py-12">
                    <svg class="mx-auto h-12 w-12 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"/>
                    </svg>
                    <h3 class="mt-2 text-sm font-medium text-foreground">No permissions found</h3>
                    <p class="mt-1 text-sm text-muted-foreground">Try adjusting your filter.</p>
                </div>
            `;
            return;
        }

        // Group by hierarchy
        const rootPermissions = filteredPermissions.filter(p => !p.parent_id);
        const childPermissions = filteredPermissions.filter(p => p.parent_id);

        permissionTree.innerHTML = '';

        rootPermissions.forEach(perm => {
            renderPermissionNode(perm, childPermissions);
        });

        attachCheckboxListeners();
    }

    function renderPermissionNode(permission, allChildren, level = 1) {
        const children = allChildren.filter(child => child.parent_id === permission.id);
        const hasChildren = children.length > 0;

        const nodeHtml = `
            <div class="permission-node permission-level-${level}" data-permission-id="${permission.id}" data-testid="permission-node-${permission.id}">
                <div class="permission-info">
                    <input type="checkbox" class="permission-checkbox" data-permission-id="${permission.id}" data-testid="checkbox-${permission.id}">
                    ${hasChildren ? `<button class="expand-btn mr-2 text-muted-foreground hover:text-muted-foreground" data-permission-id="${permission.id}" data-testid="expand-btn-${permission.id}" aria-label="Action">▶</button>` : '<span class="mr-2 w-4"></span>'}
                    <div>
                        <span class="permission-type type-${permission.type}" data-testid="permission-type-${permission.id}">${permission.type.charAt(0).toUpperCase() + permission.type.slice(1)}</span>
                        <h4 class="font-semibold text-foreground" data-testid="permission-name-${permission.id}">${permission.name}</h4>
                        <p class="text-sm text-muted-foreground" data-testid="permission-description-${permission.id}">${permission.description}</p>
                    </div>
                </div>
                <div class="permission-actions">
                    <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-9 px-3 text-sm bg-secondary text-secondary-foreground hover:bg-secondary/80" @click="editPermission(${permission.id})" data-testid="btn-edit-permission-${permission.id}" aria-label="Action">Edit</button>
                    <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-9 px-3 text-sm bg-destructive text-destructive-foreground hover:bg-destructive/90" @click="deletePermission(${permission.id})" data-testid="btn-delete-permission-${permission.id}" aria-label="Action">Delete</button>
                </div>
            </div>
            <div class="permission-children ml-6 hidden" data-parent-id="${permission.id}" data-testid="permission-children-${permission.id}">
                ${children.map(child => renderPermissionNode(child, allChildren, level + 1)).join('')}
            </div>
        `;

        permissionTree.insertAdjacentHTML('beforeend', nodeHtml);

        // Attach expand/collapse listeners
        if (hasChildren) {
            const expandBtn = permissionTree.querySelector(`[data-permission-id="${permission.id}"].expand-btn`);
            expandBtn.addEventListener('click', function() {
                const childrenContainer = permissionTree.querySelector(`[data-parent-id="${permission.id}"].permission-children`);
                const isExpanded = childrenContainer.style.display !== 'none';
                childrenContainer.style.display = isExpanded ? 'none' : 'block';
                this.textContent = isExpanded ? '▶' : '▼';
            });
        }
    }

    function getFilteredPermissions() {
        const filterValue = permissionFilter.value;

        return permissions.filter(permission => {
            if (!filterValue) return true;
            return permission.type === filterValue;
        });
    }

    function filterPermissions() {
        renderPermissions();
    }

    function attachCheckboxListeners() {
        document.querySelectorAll('.permission-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const permissionId = parseInt(this.dataset.permissionId);
                if (this.checked) {
                    selectedPermissions.add(permissionId);
                } else {
                    selectedPermissions.delete(permissionId);
                }
                updateBulkActions();
            });
        });
    }

    function updateBulkActions() {
        if (selectedPermissions.size > 0 || selectedUsers.size > 0 || selectedRoles.size > 0) {
            bulkAssignment.style.display = 'block';
            updateBulkAssignmentDetails();
        } else {
            bulkAssignment.style.display = 'none';
        }
    }

    function updateBulkAssignmentDetails() {
        // This would be updated when users/roles are selected
        document.getElementById('selected-users').textContent = selectedUsers.size > 0 ? `${selectedUsers.size} user${selectedUsers.size === 1 ? '' : 's'} selected` : 'No users selected';
        document.getElementById('selected-roles').textContent = selectedRoles.size > 0 ? `${selectedRoles.size} role${selectedRoles.size === 1 ? '' : 's'} selected` : 'No roles selected';
    }

    function openPermissionModal(permission = null) {
        if (permission) {
            document.getElementById('permission-modal-title').textContent = 'Edit Permission';
            document.getElementById('permission-id').value = permission.id;
            document.getElementById('permission-parent-id').value = permission.parent_id || '';
            document.getElementById('permission-name').value = permission.name;
            document.getElementById('permission-type').value = permission.type;
            document.getElementById('permission-resource').value = permission.resource;
            document.getElementById('permission-action').value = permission.action;
            document.getElementById('permission-scope').value = permission.scope;
            document.getElementById('permission-description').value = permission.description;
        } else {
            document.getElementById('permission-modal-title').textContent = 'Create Permission';
            permissionForm.reset();
        }
        permissionModal.classList.remove('hidden');
    }

    function closePermissionModal() {
        permissionModal.classList.add('hidden');
        permissionForm.reset();
    }

    function closeDeleteModal() {
        deleteModal.classList.add('hidden');
    }

    async function savePermission(e) {
        e.preventDefault();

        const formData = new FormData(permissionForm);
        const permissionData = Object.fromEntries(formData);

        try {
            // Mock API call - replace with actual API
            if (permissionData.id) {
                // Update existing permission
                const index = permissions.findIndex(p => p.id == permissionData.id);
                if (index !== -1) {
                    permissions[index] = { ...permissions[index], ...permissionData };
                }
            } else {
                // Create new permission
                const newPermission = {
                    id: Math.max(...permissions.map(p => p.id)) + 1,
                    ...permissionData,
                    level: permissionData.parent_id ? 2 : 1,
                    children: []
                };
                permissions.push(newPermission);
            }

            renderPermissions();
            closePermissionModal();
            addAuditEntry(`Permission "${permissionData.name}" ${permissionData.id ? 'updated' : 'created'}`);
            showSuccess('Permission saved successfully');
        } catch (error) {
            console.error('Failed to save permission:', error);
            showError('Failed to save permission');
        }
    }

    function deletePermission(permissionId) {
        const permission = permissions.find(p => p.id === permissionId);
        if (!permission) return;

        document.getElementById('delete-message').textContent = `Are you sure you want to delete the permission "${permission.name}"? This will affect all users and roles that have this permission.`;
        deleteModal.classList.remove('hidden');
        deleteModal.dataset.permissionId = permissionId;
    }

    async function confirmDelete() {
        const permissionId = parseInt(deleteModal.dataset.permissionId);

        try {
            // Mock API call - replace with actual API
            permissions = permissions.filter(p => p.id !== permissionId);
            selectedPermissions.delete(permissionId);
            renderPermissions();
            closeDeleteModal();
            addAuditEntry(`Permission deleted: ID ${permissionId}`);
            showSuccess('Permission deleted successfully');
        } catch (error) {
            console.error('Failed to delete permission:', error);
            showError('Failed to delete permission');
        }
    }

    function expandTree() {
        document.querySelectorAll('.permission-children').forEach(container => {
            container.style.display = 'block';
        });
        document.querySelectorAll('.expand-btn').forEach(btn => {
            btn.textContent = '▼';
        });
    }

    function collapseTree() {
        document.querySelectorAll('.permission-children').forEach(container => {
            container.style.display = 'none';
        });
        document.querySelectorAll('.expand-btn').forEach(btn => {
            btn.textContent = '▶';
        });
    }

    async function testPermissions() {
        try {
            addAuditEntry('Permission testing initiated');

            // Mock test results
            const testResults = [
                { permission: 'app.view', status: 'valid', message: 'Permission correctly defined' },
                { permission: 'user.manage', status: 'valid', message: 'Permission correctly defined' },
                { permission: 'admin.settings', status: 'warning', message: 'Permission may conflict with role hierarchy' },
                { permission: 'invalid.perm', status: 'invalid', message: 'Permission references non-existent resource' }
            ];

            displayValidationResults(testResults);
            showSuccess('Permission testing completed');
        } catch (error) {
            console.error('Failed to test permissions:', error);
            showError('Failed to test permissions');
        }
    }

    async function validatePermissions() {
        try {
            addAuditEntry('Permission validation initiated');

            // Mock validation results
            const validationResults = [
                { rule: 'Hierarchy Consistency', status: 'valid', message: 'All permissions properly nested' },
                { rule: 'Resource References', status: 'valid', message: 'All resource references are valid' },
                { rule: 'Action Conflicts', status: 'warning', message: 'Potential conflicts in edit/delete actions' },
                { rule: 'Scope Boundaries', status: 'valid', message: 'All scopes properly defined' },
                { rule: 'Circular Dependencies', status: 'invalid', message: 'Circular dependency detected in permission tree' }
            ];

            displayValidationResults(validationResults);
            checkForConflicts(validationResults);
            showSuccess('Permission validation completed');
        } catch (error) {
            console.error('Failed to validate permissions:', error);
            showError('Failed to validate permissions');
        }
    }

    function displayValidationResults(results) {
        validationList.innerHTML = results.map(result => ` /* safe-html: internal mock data, all values escaped */
            <div class="validation-item">
                <div class="flex items-center gap-3">
                    <span class="validation-status status-${escapeHtml(result.status)}">
                        ${getStatusIcon(result.status)}
                        ${escapeHtml(result.status.charAt(0).toUpperCase() + result.status.slice(1))}
                    </span>
                    <span class="font-medium">${escapeHtml(result.rule || result.permission)}</span>
                </div>
                <span class="text-sm text-muted-foreground">${escapeHtml(result.message)}</span>
            </div>
        `).join('');

        validationResultsDiv.style.display = 'block';
    }

    function checkForConflicts(results) {
        const conflicts = results.filter(r => r.status === 'invalid' || r.status === 'warning');

        if (conflicts.length > 0) {
            conflictList.innerHTML = conflicts.map(conflict => ` /* safe-html: internal mock data, all values escaped */
                <div class="conflict-item">
                    <div>
                        <span class="font-medium">${escapeHtml(conflict.rule || conflict.permission)}</span>
                        <p class="text-sm text-muted-foreground">${escapeHtml(conflict.message)}</p>
                    </div>
                    <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-9 px-3 text-sm bg-secondary text-secondary-foreground hover:bg-secondary/80" @click="resolveConflict('${escapeHtml(conflict.rule || conflict.permission)}')" aria-label="Action">Resolve</button>
                </div>
            `).join('');
            conflictResolution.style.display = 'block';
        } else {
            conflictResolution.style.display = 'none';
        }
    }

    function getStatusIcon(status) {
        const icons = {
            valid: '<svg class="w-4 h-4 text-success" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l8 8a1 1 0 01.414 1.414z" clip-rule="evenodd"/></svg>',
            invalid: '<svg class="w-4 h-4 text-destructive" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>',
            warning: '<svg class="w-4 h-4 text-warning" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>'
        };
        return icons[status] || icons.valid;
    }

    async function assignBulkPermissions() {
        if (selectedPermissions.size === 0) return;

        try {
            // Mock bulk assignment
            addAuditEntry(`Bulk permission assignment: ${selectedPermissions.size} permissions to ${selectedUsers.size} users and ${selectedRoles.size} roles`);
            showSuccess('Permissions assigned successfully');
            bulkAssignment.style.display = 'none';
            selectedUsers.clear();
            selectedRoles.clear();
        } catch (error) {
            console.error('Failed to assign permissions:', error);
            showError('Failed to assign permissions');
        }
    }

    async function revokeBulkPermissions() {
        if (selectedPermissions.size === 0) return;

        try {
            // Mock bulk revocation
            addAuditEntry(`Bulk permission revocation: ${selectedPermissions.size} permissions from ${selectedUsers.size} users and ${selectedRoles.size} roles`);
            showSuccess('Permissions revoked successfully');
            bulkAssignment.style.display = 'none';
            selectedUsers.clear();
            selectedRoles.clear();
        } catch (error) {
            console.error('Failed to revoke permissions:', error);
            showError('Failed to revoke permissions');
        }
    }

    function resolveConflicts() {
        // Mock conflict resolution
        conflictResolution.style.display = 'none';
        addAuditEntry('Permission conflicts auto-resolved');
        showSuccess('Conflicts resolved successfully');
    }

    function loadUserPermissions() {
        const userId = userSelector.value;
        if (!userId) {
            userPermissions.innerHTML = '<p class="text-muted-foreground text-sm">Select a user to view permissions</p>'; /* safe-html */
            return;
        }

        // Mock user permissions
        const userPerms = [
            { name: 'View Applications', granted: true },
            { name: 'Create Applications', granted: false },
            { name: 'Edit Applications', granted: true },
            { name: 'View Users', granted: true },
            { name: 'Manage Users', granted: false }
        ];

        userPermissions.innerHTML = userPerms.map(perm => ` /* safe-html: hardcoded mock data, values escaped */
            <div class="user-permission-status">
                <span class="font-medium">${escapeHtml(perm.name)}</span>
                <label class="permission-toggle">
                    <input type="checkbox" ${perm.granted ? 'checked' : ''} @change="toggleUserPermission('${escapeHtml(perm.name)}', this.checked)" aria-label="Checkbox field">
                    <span class="permission-slider"></span>
                </label>
            </div>
        `).join('');
    }

    function loadRolePermissions() {
        const roleId = roleSelector.value;
        if (!roleId) {
            rolePermissions.innerHTML = '<p class="text-muted-foreground text-sm">Select a role to view permissions</p>'; /* safe-html */
            return;
        }

        // Mock role permissions
        const rolePerms = [
            { name: 'View Applications', granted: true },
            { name: 'Create Applications', granted: true },
            { name: 'Edit Applications', granted: true },
            { name: 'View Users', granted: true },
            { name: 'Manage Users', granted: false }
        ];

        rolePermissions.innerHTML = rolePerms.map(perm => ` /* safe-html: hardcoded mock data, values escaped */
            <div class="user-permission-status">
                <span class="font-medium">${escapeHtml(perm.name)}</span>
                <label class="permission-toggle">
                    <input type="checkbox" ${perm.granted ? 'checked' : ''} @change="toggleRolePermission('${escapeHtml(perm.name)}', this.checked)" aria-label="Checkbox field">
                    <span class="permission-slider"></span>
                </label>
            </div>
        `).join('');
    }

    function addAuditEntry(action) {
        const auditEntry = document.createElement('div');
        auditEntry.className = 'audit-entry';
        auditEntry.innerHTML = ` /* safe-html: action is internal string from code, escaped for safety */
            <div class="audit-action">${escapeHtml(action)}</div>
            <div class="audit-user">by Current User</div>
            <div class="audit-timestamp">just now</div>
        `;
        auditEntries.insertBefore(auditEntry, auditEntries.firstChild);
    }

    // Global functions for inline onclick handlers
    window.editPermission = function(permissionId) {
        const permission = permissions.find(p => p.id === permissionId);
        if (permission) {
            openPermissionModal(permission);
        }
    };

    window.deletePermission = deletePermission;

    window.toggleUserPermission = function(permissionName, granted) {
        addAuditEntry(`User permission "${permissionName}" ${granted ? 'granted' : 'revoked'}`);
    };

    window.toggleRolePermission = function(permissionName, granted) {
        addAuditEntry(`Role permission "${permissionName}" ${granted ? 'granted' : 'revoked'}`);
    };

    window.resolveConflict = function(conflictId) {
        addAuditEntry(`Conflict resolved: ${conflictId}`);
    };

    // Utility functions
    function showSuccess(message) {
        console.log('SUCCESS:', message);
    }

    function showError(message) {
        console.error('ERROR:', message);
    }

    function showInfo(message) {
        console.log('INFO:', message);
    }
});
