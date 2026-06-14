// Role Management JavaScript
document.addEventListener('DOMContentLoaded', function() {
    function escapeHtml(str) {
        if (str == null) return '';
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }
    let roles = [];
    let selectedRoles = new Set();
    let selectedRole = null;

    // DOM Elements
    const roleGrid = document.getElementById('role-grid');
    const roleFilter = document.getElementById('role-filter');
    const bulkActions = document.getElementById('bulk-actions');
    const selectedCount = document.getElementById('selected-count');
    const permissionMatrix = document.getElementById('permission-matrix');
    const roleDetails = document.getElementById('role-details');

    // Modal Elements
    const roleModal = document.getElementById('role-modal');
    const permissionModal = document.getElementById('role-permission-modal');
    const deleteModal = document.getElementById('role-delete-modal');
    const roleForm = document.getElementById('role-form');

    // Initialize
    loadRoles();

    // Event Listeners
    roleFilter.addEventListener('change', filterRoles);

    // Modal Events
    document.getElementById('btn-create-role').addEventListener('click', () => openRoleModal());
    document.getElementById('btn-empty-create').addEventListener('click', () => openRoleModal());
    document.getElementById('btn-close-role-modal').addEventListener('click', closeRoleModal);
    document.getElementById('btn-cancel-role-modal').addEventListener('click', closeRoleModal);
    document.getElementById('btn-cancel-delete').addEventListener('click', closeDeleteModal);
    document.getElementById('btn-confirm-delete').addEventListener('click', confirmDelete);

    // Permission Modal Events
    document.getElementById('btn-close-role-permission-modal').addEventListener('click', closePermissionModal);
    document.getElementById('btn-cancel-permissions').addEventListener('click', closePermissionModal);
    document.getElementById('btn-save-permissions').addEventListener('click', savePermissions);

    // Form Events
    roleForm.addEventListener('submit', saveRole);

    // Bulk Actions
    document.getElementById('btn-bulk-clone').addEventListener('click', bulkClone);
    document.getElementById('btn-bulk-activate').addEventListener('click', () => bulkAction('activate'));
    document.getElementById('btn-bulk-deactivate').addEventListener('click', () => bulkAction('deactivate'));
    document.getElementById('btn-bulk-delete').addEventListener('click', () => bulkAction('delete'));

    async function loadRoles() {
        try {
            const response = await fetch('/admin/api/roles');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'Failed to load roles');
            roles = data.roles;
            renderRoles();
        } catch (error) {
            console.error('Failed to load roles:', error);
            showError('Failed to load roles: ' + error.message);
        }
    }

    function renderRoles() {
        const filteredRoles = getFilteredRoles();

        if (filteredRoles.length === 0) {
            roleGrid.innerHTML = ` /* safe-html */
                <div class="col-span-full text-center py-12">
                    <svg class="mx-auto h-12 w-12 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"/>
                    </svg>
                    <h3 class="mt-2 text-sm font-medium text-foreground">No roles found</h3>
                    <p class="mt-1 text-sm text-muted-foreground">Try adjusting your filter.</p>
                </div>
            `;
            return;
        }

        roleGrid.innerHTML = filteredRoles.map(role => ` /* safe-html: all dynamic values escaped via escapeHtml() */
            <div class="role-card" data-role-id="${escapeHtml(role.id)}" data-testid="role-card-${escapeHtml(role.id)}">
                <div class="role-header">
                    <div class="flex items-start gap-3">
                        <input type="checkbox" class="role-checkbox" data-role-id="${escapeHtml(role.id)}" data-testid="checkbox-${escapeHtml(role.id)}">
                        <div class="flex-1">
                            <h3 class="text-lg font-semibold text-foreground" data-testid="role-name-${escapeHtml(role.id)}">${escapeHtml(role.name)}</h3>
                            <p class="text-sm text-muted-foreground mt-1" data-testid="role-description-${escapeHtml(role.id)}">${escapeHtml(role.description)}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="role-badge badge-${escapeHtml(role.type)}" data-testid="role-badge-${escapeHtml(role.id)}">${escapeHtml(role.type.charAt(0).toUpperCase() + role.type.slice(1))}</span>
                    </div>
                </div>

                <div class="permission-matrix">
                    ${renderPermissionSummary(role.permissions)}
                </div>

                <div class="user-assignment">
                    <div class="text-sm font-medium text-foreground/80 mb-2">${escapeHtml(role.userCount)} users assigned</div>
                    <div class="user-list">
                        ${role.users.slice(0, 3).map(user => `<span class="user-tag">${escapeHtml(user.split('@')[0])}</span>`).join('')}
                        ${role.users.length > 3 ? `<span class="user-tag">+${role.users.length - 3} more</span>` : ''}
                    </div>
                </div>

                <div class="flex justify-between items-center mt-4">
                    <span class="text-xs text-muted-foreground">Modified ${new Date(role.lastModified).toLocaleDateString()}</span>
                    <div class="flex gap-1">
                        <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 text-xs" @click="editPermissions(${role.id})" data-testid="btn-edit-permissions-${escapeHtml(role.id)}" aria-label="Action">Permissions</button>
                        <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 text-xs" @click="editRole(${role.id})" data-testid="btn-edit-role-${escapeHtml(role.id)}" aria-label="Action">Edit</button>
                        <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 bg-destructive text-destructive-foreground hover:bg-destructive/90 text-xs" @click="deleteRole(${role.id})" data-testid="btn-delete-role-${escapeHtml(role.id)}" aria-label="Action">Delete</button>
                    </div>
                </div>
            </div>
        `).join('');

        attachCheckboxListeners();
        updateBulkActions();
    }

    function renderPermissionSummary(permissions) {
        const categories = {
            applications: ['app-view', 'app-create', 'app-edit', 'app-delete'],
            capabilities: ['cap-view', 'cap-create', 'cap-edit', 'cap-mapping'],
            users: ['user-view', 'user-manage'],
            admin: ['admin-settings', 'admin-logs', 'admin-backup', 'admin-integrations']
        };

        return Object.entries(categories).map(([category, perms]) => {
            const granted = perms.filter(p => permissions[p]).length;
            const total = perms.length;
            const percentage = Math.round((granted / total) * 100);

            return `
                <div class="permission-item ${granted > 0 ? 'permission-granted' : 'permission-denied'}">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l8 8a1 1 0 01.414 1.414z" clip-rule="evenodd"/>
                    </svg>
                    ${category.charAt(0).toUpperCase() + category.slice(1)}: ${granted}/${total}
                </div>
            `;
        }).join('');
    }

    function getFilteredRoles() {
        const filterValue = roleFilter.value;

        return roles.filter(role => {
            switch (filterValue) {
                case 'system':
                    return role.type === 'system';
                case 'custom':
                    return role.type === 'custom';
                case 'active':
                    return role.status === 'active';
                default:
                    return true;
            }
        });
    }

    function filterRoles() {
        renderRoles();
    }

    function attachCheckboxListeners() {
        document.querySelectorAll('.role-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const roleId = parseInt(this.dataset.roleId);
                if (this.checked) {
                    selectedRoles.add(roleId);
                } else {
                    selectedRoles.delete(roleId);
                }
                updateBulkActions();
            });
        });
    }

    function updateBulkActions() {
        if (selectedRoles.size > 0) {
            selectedCount.textContent = `${selectedRoles.size} role${selectedRoles.size === 1 ? '' : 's'} selected`;
            bulkActions.style.display = 'flex';
        } else {
            bulkActions.style.display = 'none';
        }
    }

    function openRoleModal(role = null) {
        if (role) {
            document.getElementById('role-modal-title').textContent = 'Edit Role';
            document.getElementById('role-id').value = role.id;
            document.getElementById('role-name').value = role.name;
            document.getElementById('role-type').value = role.type;
            document.getElementById('role-status').value = role.status;
            document.getElementById('role-description').value = role.description;
        } else {
            document.getElementById('role-modal-title').textContent = 'Create Role';
            roleForm.reset();
        }
        roleModal.classList.remove('hidden');
    }

    function closeRoleModal() {
        roleModal.classList.add('hidden');
        roleForm.reset();
    }

    function closeDeleteModal() {
        deleteModal.classList.add('hidden');
    }

    async function saveRole(e) {
        e.preventDefault();

        const formData = new FormData(roleForm);
        const roleData = Object.fromEntries(formData);

        try {
            // Mock API call - replace with actual API
            if (roleData.id) {
                // Update existing role
                const index = roles.findIndex(r => r.id == roleData.id);
                if (index !== -1) {
                    roles[index] = { ...roles[index], ...roleData, lastModified: new Date().toISOString() };
                }
            } else {
                // Create new role
                const newRole = {
                    id: Math.max(...roles.map(r => r.id)) + 1,
                    ...roleData,
                    permissions: {
                        'app-view': false, 'app-create': false, 'app-edit': false, 'app-delete': false,
                        'cap-view': false, 'cap-create': false, 'cap-edit': false, 'cap-mapping': false,
                        'user-view': false, 'user-manage': false, 'role-view': false, 'role-manage': false,
                        'admin-settings': false, 'admin-logs': false, 'admin-backup': false, 'admin-integrations': false
                    },
                    userCount: 0,
                    users: [],
                    created: new Date().toISOString(),
                    lastModified: new Date().toISOString()
                };
                roles.push(newRole);
            }

            renderRoles();
            closeRoleModal();
            addAuditEntry(`Role "${roleData.name}" ${roleData.id ? 'updated' : 'created'}`);
            showSuccess('Role saved successfully');
        } catch (error) {
            console.error('Failed to save role:', error);
            showError('Failed to save role');
        }
    }

    function editPermissions(roleId) {
        const role = roles.find(r => r.id === roleId);
        if (!role) return;

        selectedRole = role;
        document.getElementById('role-permission-modal-title').textContent = `Edit Permissions: ${role.name}`;

        // Load current permissions
        Object.keys(role.permissions).forEach(perm => {
            const element = document.getElementById(`perm-${perm}`);
            if (element) {
                element.checked = role.permissions[perm];
            }
        });

        permissionModal.classList.remove('hidden');
    }

    function closePermissionModal() {
        permissionModal.classList.add('hidden');
        selectedRole = null;
    }

    async function savePermissions() {
        if (!selectedRole) return;

        const permissions = {};
        document.querySelectorAll('#permission-editor input[type="checkbox"]').forEach(checkbox => {
            permissions[checkbox.id.replace('perm-', '')] = checkbox.checked;
        });

        try {
            // Mock API call - replace with actual API
            selectedRole.permissions = permissions;
            selectedRole.lastModified = new Date().toISOString();

            renderRoles();
            updatePermissionMatrix();
            closePermissionModal();
            addAuditEntry(`Permissions updated for role "${selectedRole.name}"`);
            showSuccess('Permissions saved successfully');
        } catch (error) {
            console.error('Failed to save permissions:', error);
            showError('Failed to save permissions');
        }
    }

    function updatePermissionMatrix() {
        if (!selectedRole) return;

        permissionMatrix.innerHTML = ` /* safe-html: static permission keys, no user input */
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <h4 class="font-medium text-foreground mb-3">Applications</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span>View</span>
                            <span class="${selectedRole.permissions['app-view'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['app-view'] ? '✓' : '✗'}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Create</span>
                            <span class="${selectedRole.permissions['app-create'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['app-create'] ? '✓' : '✗'}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Edit</span>
                            <span class="${selectedRole.permissions['app-edit'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['app-edit'] ? '✓' : '✗'}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Delete</span>
                            <span class="${selectedRole.permissions['app-delete'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['app-delete'] ? '✓' : '✗'}</span>
                        </div>
                    </div>
                </div>
                <div>
                    <h4 class="font-medium text-foreground mb-3">System Admin</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span>Settings</span>
                            <span class="${selectedRole.permissions['admin-settings'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['admin-settings'] ? '✓' : '✗'}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Logs</span>
                            <span class="${selectedRole.permissions['admin-logs'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['admin-logs'] ? '✓' : '✗'}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Backup</span>
                            <span class="${selectedRole.permissions['admin-backup'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['admin-backup'] ? '✓' : '✗'}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span>Integrations</span>
                            <span class="${selectedRole.permissions['admin-integrations'] ? 'text-success' : 'text-destructive'}">${selectedRole.permissions['admin-integrations'] ? '✓' : '✗'}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function deleteRole(roleId) {
        const role = roles.find(r => r.id === roleId);
        if (!role) return;

        document.getElementById('delete-message').textContent = `Are you sure you want to delete the role "${role.name}"? All users assigned to this role will lose their permissions.`;
        deleteModal.classList.remove('hidden');
        deleteModal.dataset.roleId = roleId;
    }

    async function confirmDelete() {
        const roleId = parseInt(deleteModal.dataset.roleId);

        try {
            // Mock API call - replace with actual API
            roles = roles.filter(r => r.id !== roleId);
            selectedRoles.delete(roleId);

            if (selectedRole && selectedRole.id === roleId) {
                selectedRole = null;
                permissionMatrix.innerHTML = '<p class="text-muted-foreground text-sm">Select a role to view permissions</p>'; /* safe-html */
                roleDetails.innerHTML = '<p class="text-muted-foreground text-sm">Select a role to view details</p>'; /* safe-html */
            }

            renderRoles();
            closeDeleteModal();
            addAuditEntry(`Role deleted: ID ${roleId}`);
            showSuccess('Role deleted successfully');
        } catch (error) {
            console.error('Failed to delete role:', error);
            showError('Failed to delete role');
        }
    }

    async function bulkAction(action) {
        if (selectedRoles.size === 0) return;

        try {
            // Mock API call - replace with actual API
            roles.forEach(role => {
                if (selectedRoles.has(role.id)) {
                    if (action === 'delete') {
                        roles = roles.filter(r => r.id !== role.id);
                    } else if (action === 'activate') {
                        role.status = 'active';
                        role.lastModified = new Date().toISOString();
                    } else if (action === 'deactivate') {
                        role.status = 'inactive';
                        role.lastModified = new Date().toISOString();
                    }
                }
            });

            selectedRoles.clear();
            renderRoles();
            addAuditEntry(`Bulk ${action} performed on ${selectedRoles.size} roles`);
            showSuccess(`Bulk ${action} completed successfully`);
        } catch (error) {
            console.error(`Failed to ${action} roles:`, error);
            showError(`Failed to ${action} roles`);
        }
    }

    function bulkClone() {
        // Clone selected roles with new names
        selectedRoles.forEach(roleId => {
            const originalRole = roles.find(r => r.id === roleId);
            if (originalRole) {
                const clonedRole = {
                    ...originalRole,
                    id: Math.max(...roles.map(r => r.id)) + 1,
                    name: `${originalRole.name} (Copy)`,
                    type: 'custom',
                    userCount: 0,
                    users: [],
                    created: new Date().toISOString(),
                    lastModified: new Date().toISOString()
                };
                roles.push(clonedRole);
            }
        });

        selectedRoles.clear();
        renderRoles();
        addAuditEntry(`Bulk clone completed for ${selectedRoles.size} roles`);
        showSuccess('Roles cloned successfully');
    }

    function addAuditEntry(action) {
        const auditEntries = document.getElementById('audit-entries');
        const newEntry = document.createElement('div');
        newEntry.className = 'audit-entry';
        newEntry.innerHTML = ` /* safe-html: action is internal string, escaped for safety */
            <div class="audit-action">${escapeHtml(action)}</div>
            <div class="audit-user">by Current User</div>
            <div class="audit-timestamp">just now</div>
        `;
        auditEntries.insertBefore(newEntry, auditEntries.firstChild);
    }

    // Global functions for inline onclick handlers
    window.editRole = function(roleId) {
        const role = roles.find(r => r.id === roleId);
        if (role) {
            selectedRole = role;
            openRoleModal(role);
            updatePermissionMatrix();
            updateRoleDetails();
        }
    };

    window.editPermissions = editPermissions;
    window.deleteRole = deleteRole;

    function updateRoleDetails() {
        if (!selectedRole) return;

        roleDetails.innerHTML = ` /* safe-html: all values escaped via escapeHtml() */
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-foreground/80">Created</label>
                    <p class="text-sm text-foreground">${escapeHtml(new Date(selectedRole.created).toLocaleDateString())}</p>
                </div>
                <div>
                    <label class="block text-sm font-medium text-foreground/80">Last Modified</label>
                    <p class="text-sm text-foreground">${escapeHtml(new Date(selectedRole.lastModified).toLocaleDateString())}</p>
                </div>
                <div>
                    <label class="block text-sm font-medium text-foreground/80">Users Assigned</label>
                    <p class="text-sm text-foreground">${escapeHtml(selectedRole.userCount)} users</p>
                </div>
                <div>
                    <label class="block text-sm font-medium text-foreground/80">Role Type</label>
                    <p class="text-sm text-foreground">${escapeHtml(selectedRole.type.charAt(0).toUpperCase() + selectedRole.type.slice(1))}</p>
                </div>
            </div>
        `;
    }

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
