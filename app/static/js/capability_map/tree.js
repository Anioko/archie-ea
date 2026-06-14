/**
 * Capability Tree — Observable Plot tree visualization with CRUD.
 *
 * Alpine.js component: capabilityTree()
 * Renders a dendrogram from /capability-map/api/trees/capability
 * with click-to-select, right-click context menu, depth control, and full CRUD.
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('capabilityTree', () => ({
        treeData: null,
        loading: true,
        selected: null,
        editing: false,
        nodeCount: 0,
        visibleCount: 0,
        showDeleteConfirm: false,
        ctx: { show: false, x: 0, y: 0 },
        editForm: {},
        maxDepth: 1,
        expandedIds: new Set(),

        async init() {
            await this.loadTree();
        },

        async loadTree() {
            this.loading = true;
            try {
                const resp = await fetch('/capability-map/api/trees/capability');
                this.treeData = await resp.json();
                this.nodeCount = this.countNodes(this.treeData);
                this.renderTree();
            } catch (e) {
                console.error('Failed to load tree:', e);
            } finally {
                this.loading = false;
            }
        },

        countNodes(node) {
            if (!node) return 0;
            let count = node.id ? 1 : 0;
            for (const child of (node.children || [])) {
                count += this.countNodes(child);
            }
            return count;
        },

        setDepth(d) {
            this.maxDepth = d;
            this.expandedIds.clear();
            this.renderTree();
        },

        // Build a pruned tree based on maxDepth + expanded nodes
        pruneTree(node, depth) {
            if (!node) return null;
            const children = (node.children || []).map(child => {
                const isExpanded = this.expandedIds.has(child.id);
                if (depth < this.maxDepth || isExpanded) {
                    return this.pruneTree(child, depth + 1);
                }
                // Leaf — include the node but not its children
                return {
                    ...child,
                    children: [],
                    _hasChildren: (child.children || []).length > 0,
                };
            }).filter(Boolean);

            return { ...node, children };
        },

        toggleExpand(nodeId) {
            if (this.expandedIds.has(nodeId)) {
                this.expandedIds.delete(nodeId);
            } else {
                this.expandedIds.add(nodeId);
            }
            this.renderTree();
        },

        // ---- Observable Plot rendering ----
        renderTree() {
            const container = document.getElementById('tree-container');
            if (!container || !this.treeData || !this.treeData.children?.length) {
                if (container) container.innerHTML = '';
                return;
            }

            // Prune tree to maxDepth
            const pruned = this.pruneTree(this.treeData, 0);

            // Flatten pruned tree into paths for Plot.tree
            const links = [];
            const nodeByName = {};
            const collapsedNodes = new Set();

            const flatten = (node, parentPath, depth) => {
                const safeName = node.name.replace(/\//g, '|');
                const path = parentPath ? `${parentPath}/${safeName}` : safeName;
                if (parentPath) {
                    links.push(path);
                }
                if (node.id) {
                    nodeByName[safeName] = node;
                }
                if (node._hasChildren && (!node.children || node.children.length === 0)) {
                    collapsedNodes.add(safeName);
                }
                for (const child of (node.children || [])) {
                    flatten(child, path, depth + 1);
                }
            };

            for (const root of pruned.children) {
                flatten(root, '', 1);
            }

            if (links.length === 0 && pruned.children.length > 0) {
                for (const root of pruned.children) {
                    links.push(root.name.replace(/\//g, '|'));
                }
            }

            this.visibleCount = links.length;
            const self = this;
            const treeHeight = Math.max(500, this.visibleCount * 32);

            try {
                const plot = Plot.plot({
                    axis: null,
                    margin: 10,
                    marginLeft: 40,
                    marginRight: 260,
                    width: container.clientWidth || 900,
                    height: treeHeight,
                    marks: [
                        Plot.tree(links, {
                            delimiter: '/',
                            stroke: '#64748b',
                            strokeWidth: 2.5,
                            strokeOpacity: 0.6,
                            fill: '#1e293b',
                            r: 5,
                            fontSize: 13,
                            textLayout: 'mirrored',
                        })
                    ]
                });

                container.innerHTML = '';
                container.appendChild(plot);

                // Post-process text nodes: clean labels, attach handlers, mark collapsed
                const texts = plot.querySelectorAll('text');
                texts.forEach(textEl => {
                    const rawLabel = textEl.textContent.trim();
                    const leafName = rawLabel.includes('/') ? rawLabel.split('/').pop() : rawLabel;
                    const displayName = leafName.replace(/\|/g, '/');
                    const nodeData = nodeByName[leafName];

                    textEl.textContent = displayName;
                    textEl.style.cursor = 'pointer';
                    textEl.style.userSelect = 'none';

                    // Mark collapsed nodes with a + indicator
                    if (collapsedNodes.has(leafName) && nodeData) {
                        textEl.textContent = displayName + ' [+]';
                        textEl.style.fontWeight = '600';
                    }

                    textEl.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (nodeData) {
                            // If collapsed, expand on click
                            if (collapsedNodes.has(leafName)) {
                                self.toggleExpand(nodeData.id);
                            } else {
                                self.selectNode(nodeData);
                            }
                        }
                    });

                    textEl.addEventListener('dblclick', (e) => {
                        e.stopPropagation();
                        if (nodeData && nodeData._hasChildren) {
                            self.toggleExpand(nodeData.id);
                        }
                    });

                    textEl.addEventListener('contextmenu', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (nodeData) {
                            self.selectNode(nodeData);
                            self.ctx = { show: true, x: e.clientX, y: e.clientY };
                        }
                    });
                });

                // Also style the circles for collapsed nodes
                const circles = plot.querySelectorAll('circle');
                circles.forEach(circle => {
                    // Find matching text by position proximity
                    circle.style.cursor = 'pointer';
                });

                container.addEventListener('click', () => {
                    this.ctx.show = false;
                });

            } catch (e) {
                console.error('Observable Plot render error:', e);
                container.innerHTML = '<p class="p-6 text-sm text-muted-foreground">Tree rendering failed. Check console.</p>';
            }

            if (window.lucide) lucide.createIcons();
        },

        resetZoom() {
            this.maxDepth = 2;
            this.expandedIds.clear();
            this.renderTree();
        },

        expandAll() {
            this.maxDepth = 10;
            this.expandedIds.clear();
            this.renderTree();
        },

        // ---- Selection ----
        selectNode(nodeData) {
            this.editing = false;
            this.selected = { ...nodeData };
            this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        // ---- CRUD: Add root ----
        addRoot() {
            this.selected = { name: '' };
            this.editForm = {
                id: null, name: '', description: '', code: '', category: '',
                business_domain: '', strategic_importance: '',
                current_maturity_level: 1, business_owner: '', it_owner: '',
                parent_id: null,
            };
            this.editing = true;
            this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        // ---- CRUD: Add child ----
        startAddChild() {
            if (!this.selected?.id) return;
            const parentId = this.selected.id;
            this.editForm = {
                id: null, name: '', description: '', code: '', category: '',
                business_domain: this.selected.business_domain || '',
                strategic_importance: '',
                current_maturity_level: 1, business_owner: '', it_owner: '',
                parent_id: parentId,
            };
            this.selected = { name: 'New Child' };
            this.editing = true;
            this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        // ---- CRUD: Edit ----
        startEdit() {
            if (!this.selected?.id) return;
            this.editForm = {
                id: this.selected.id,
                name: this.selected.name || '',
                description: this.selected.description || '',
                code: this.selected.code || '',
                category: this.selected.category || '',
                business_domain: this.selected.business_domain || '',
                strategic_importance: this.selected.strategic_importance || '',
                current_maturity_level: this.selected.current_maturity_level || 1,
                business_owner: this.selected.business_owner || '',
                it_owner: this.selected.it_owner || '',
            };
            this.editing = true;
            this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        cancelEdit() {
            this.editing = false;
            if (!this.editForm.id) this.selected = null;
        },

        async saveEdit() {
            const form = this.editForm;
            if (!form.name?.trim()) return;

            try {
                let resp;
                if (form.id) {
                    resp = await fetch(`/capability-map/api/trees/capability/${form.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(form),
                    });
                } else {
                    resp = await fetch('/capability-map/api/trees/capability', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(form),
                    });
                }

                if (!resp.ok) {
                    const err = await resp.json();
                    Platform.toast.error(err.error || 'Save failed');
                    return;
                }

                const saved = await resp.json();
                this.editing = false;
                this.selected = saved;
                await this.loadTree();
            } catch (e) {
                console.error('Save error:', e);
                Platform.toast.error('Save failed. Check console.');
            }
        },

        // ---- CRUD: Delete ----
        confirmDelete() {
            if (!this.selected?.id) return;
            this.showDeleteConfirm = true;
        },

        async doDelete() {
            if (!this.selected?.id) return;
            try {
                const resp = await fetch(`/capability-map/api/trees/capability/${this.selected.id}`, {
                    method: 'DELETE',
                });
                if (!resp.ok) {
                    const err = await resp.json();
                    Platform.toast.error(err.error || 'Delete failed');
                    return;
                }
                this.selected = null;
                this.showDeleteConfirm = false;
                await this.loadTree();
            } catch (e) {
                console.error('Delete error:', e);
            }
        },
    }));
});
