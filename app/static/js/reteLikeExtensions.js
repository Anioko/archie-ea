/**
 * Rete.js-like Extensions for Drawflow
 *
 * Provides advanced UX features to match professional diagramming tools:
 * - Ghost preview during node drag
 * - Smart snap-to-connector with auto-connect
 * - Event bus for extensibility
 * - Pluggable path strategies (bezier, orthogonal, polyline)
 * - Scope containers with rule-based validation
 *
 * Feature-flagged and backward compatible with existing Drawflow usage.
 */

const ReteLikeExtensions = {
    // =========================================================================
    // Configuration & State
    // =========================================================================
    enabled: false,
    snapRadius: 16,  // px distance to trigger snap
    ghostOpacity: 0.6,
    spiralPlacementMaxAttempts: 10,
    spiralPlacementStep: 8,  // px offset per collision retry

    // Internal state
    _drawflowInstance: null,
    _hostComponent: null,
    _ghostPreview: null,
    _draggedData: null,
    _snapTarget: null,
    _eventListeners: new Map(),
    _pathStrategies: new Map(),
    _scopes: new Map(),
    _scopePredicates: new Map(),
    _svgOverlay: null,
    _svgPathElements: new Map(),
    _connectionPathTypes: new Map(),
    _connectionControlPoints: new Map(),  // Phase 3: control points per connection
    _selectedConnection: null,

    // =========================================================================
    // Initialization & Feature Flag
    // =========================================================================

    /**
     * Enable Rete-like extensions on a Drawflow instance
     * @param {Object} drawflowInstance - The Drawflow editor instance
     * @param {Object} hostComponent - The parent component (e.g., SolutionComposer)
     */
    enable(drawflowInstance, hostComponent) {
        if (this.enabled) {
            console.warn('[ReteLike] Already enabled');
            return;
        }

        this.enabled = true;
        this._drawflowInstance = drawflowInstance;
        this._hostComponent = hostComponent;


        // Initialize subsystems
        this._initEventBus();
        this._initGhostPreview();
        this._initSnapSystem();
        this._initSVGOverlay();
        this._registerDefaultPathStrategies();

    },

    /**
     * Disable and cleanup all extensions
     */
    disable() {
        if (!this.enabled) return;

        this._cleanupGhostPreview();
        this._cleanupSnapSystem();
        this._eventListeners.clear();

        this.enabled = false;
    },

    // =========================================================================
    // Event Bus System
    // =========================================================================

    _initEventBus() {
        this._eventListeners = new Map([
            ['beforeInsert', []],
            ['afterInsert', []],
            ['insertFailed', []],
            ['connectAttempt', []],
            ['connectSuccess', []],
            ['connectFailed', []],
            ['scopeCreated', []],
            ['scopeDeleted', []],
            ['pathStrategyRegistered', []],
            ['pathEdited', []]
        ]);
    },

    /**
     * Register event listener
     * @param {string} event - Event name
     * @param {Function} handler - Callback function
     */
    on(event, handler) {
        if (!this._eventListeners.has(event)) {
            this._eventListeners.set(event, []);
        }
        this._eventListeners.get(event).push(handler);
    },

    /**
     * Emit event to all registered listeners
     * @param {string} event - Event name
     * @param {Object} payload - Event data
     * @returns {boolean} - false if event was canceled
     */
    emit(event, payload) {
        const listeners = this._eventListeners.get(event) || [];
        let canceled = false;

        for (const handler of listeners) {
            try {
                const result = handler(payload);
                if (result === false) {
                    canceled = true;
                    break;
                }
            } catch (err) {
                console.error(`[ReteLike] Event handler error for ${event}:`, err);
            }
        }

        return !canceled;
    },

    // =========================================================================
    // Ghost Preview System
    // =========================================================================

    _initGhostPreview() {
        // Create ghost preview container
        this._ghostPreview = document.createElement('div');
        this._ghostPreview.id = 'rete-ghost-preview';
        this._ghostPreview.style.cssText = `
            position: fixed;
            pointer-events: none;
            opacity: ${this.ghostOpacity};
            z-index: 9999;
            display: none;
            transition: opacity 0.15s ease;
        `;
        document.body.appendChild(this._ghostPreview);

        // Enhance existing drag listeners
        this._enhanceDragListeners();
    },

    _enhanceDragListeners() {
        const drawflowContainer = this._drawflowInstance.container;

        // Listen for dragstart on palette items
        document.addEventListener('dragstart', (e) => {
            if (!e.target.classList.contains('palette-item')) return;

            this._draggedData = {
                type: e.target.dataset.elementType,
                layer: e.target.dataset.layer,
                sourceType: e.target.dataset.sourceType || 'manual',
                sourceId: e.target.dataset.sourceId || null,
                name: e.target.dataset.entityName || null,
                icon: e.target.querySelector('[data-lucide]')?.getAttribute('data-lucide'),
                color: this._extractColorClass(e.target)
            };

            this._createGhostContent();
        }, { capture: true });

        // Track mouse position during drag
        document.addEventListener('dragover', (e) => {
            if (!this._ghostPreview || !this._draggedData) return;

            e.preventDefault();
            this._updateGhostPosition(e.clientX, e.clientY);

            // Check for snap targets if over canvas
            if (e.target.closest('#drawflow')) {
                this._checkSnapTargets(e.clientX, e.clientY);
            }
        });

        // Cleanup on drag end
        document.addEventListener('dragend', () => {
            this._hideGhost();
            this._clearSnapHighlight();
            this._draggedData = null;
            this._snapTarget = null;
        });
    },

    _createGhostContent() {
        if (!this._draggedData) return;

        const { type, name, icon, color } = this._draggedData;
        const displayName = name || this._formatTypeName(type);

        safeHTML(this._ghostPreview, `
            <div class="bg-background/90 backdrop-blur-sm border-2 border-primary/50 rounded-lg shadow-xl p-3 flex items-center gap-2">
                ${icon ? `<i data-lucide="${icon}" class="h-4 w-4 ${color || 'text-primary'}"></i>` : ''}
                <div>
                    <div class="text-sm font-medium text-foreground">${displayName}</div>
                    <div class="text-xs text-muted-foreground">${type.replace(/_/g, ' ')}</div>
                </div>
            </div>
        `);

        // Re-render Lucide icons
        if (window.lucide) {
            lucide.createIcons({ icons: this._ghostPreview });
        }

        this._ghostPreview.style.display = 'block';
    },

    _updateGhostPosition(clientX, clientY) {
        this._ghostPreview.style.left = (clientX + 12) + 'px';
        this._ghostPreview.style.top = (clientY + 12) + 'px';
    },

    _hideGhost() {
        this._ghostPreview.style.display = 'none';
    },

    _cleanupGhostPreview() {
        if (this._ghostPreview && this._ghostPreview.parentNode) {
            this._ghostPreview.parentNode.removeChild(this._ghostPreview);
        }
        this._ghostPreview = null;
    },

    // =========================================================================
    // Smart Snap-to-Connector System
    // =========================================================================

    _initSnapSystem() {
        this._snapIndicator = document.createElement('div');
        this._snapIndicator.id = 'rete-snap-indicator';
        this._snapIndicator.style.cssText = `
            position: absolute;
            width: 24px;
            height: 24px;
            border: 2px solid #10b981;
            border-radius: 50%;
            background: rgba(16, 185, 129, 0.1);
            pointer-events: none;
            z-index: 9998;
            display: none;
            animation: pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        `;

        // Add pulse animation
        if (!document.getElementById('rete-snap-styles')) {
            const style = document.createElement('style');
            style.id = 'rete-snap-styles';
            style.textContent = `
                @keyframes pulse {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.5; transform: scale(1.1); }
                }
            `;
            document.head.appendChild(style);
        }

        const drawflowContainer = document.getElementById('drawflow');
        if (drawflowContainer) {
            drawflowContainer.appendChild(this._snapIndicator);
        }
    },

    _checkSnapTargets(clientX, clientY) {
        const drawflowRect = document.getElementById('drawflow').getBoundingClientRect();
        const canvasX = (clientX - drawflowRect.left) / (this._drawflowInstance.zoom || 1);
        const canvasY = (clientY - drawflowRect.top) / (this._drawflowInstance.zoom || 1);

        let closestConnector = null;
        let minDistance = this.snapRadius;

        // Find all connector anchors (input/output ports)
        const connectors = document.querySelectorAll('.drawflow-node .output, .drawflow-node .input');

        connectors.forEach(connector => {
            const rect = connector.getBoundingClientRect();
            const connectorX = (rect.left + rect.width / 2 - drawflowRect.left) / (this._drawflowInstance.zoom || 1);
            const connectorY = (rect.top + rect.height / 2 - drawflowRect.top) / (this._drawflowInstance.zoom || 1);

            const distance = Math.hypot(canvasX - connectorX, canvasY - connectorY);

            if (distance < minDistance) {
                minDistance = distance;
                closestConnector = {
                    element: connector,
                    x: connectorX,
                    y: connectorY,
                    nodeId: connector.closest('.drawflow-node')?.id,
                    type: connector.classList.contains('output') ? 'output' : 'input'
                };
            }
        });

        if (closestConnector) {
            this._showSnapIndicator(closestConnector);
            this._snapTarget = closestConnector;
        } else {
            this._clearSnapHighlight();
            this._snapTarget = null;
        }
    },

    _showSnapIndicator(connector) {
        const drawflowRect = document.getElementById('drawflow').getBoundingClientRect();
        const zoom = this._drawflowInstance.zoom || 1;

        this._snapIndicator.style.display = 'block';
        this._snapIndicator.style.left = (connector.x * zoom - 12) + 'px';
        this._snapIndicator.style.top = (connector.y * zoom - 12) + 'px';
    },

    _clearSnapHighlight() {
        this._snapIndicator.style.display = 'none';
    },

    _cleanupSnapSystem() {
        if (this._snapIndicator && this._snapIndicator.parentNode) {
            this._snapIndicator.parentNode.removeChild(this._snapIndicator);
        }
        this._snapIndicator = null;
    },

    /**
     * Get current snap target during drag
     * @returns {Object|null} - Snap target info or null
     */
    getSnapTarget() {
        return this._snapTarget;
    },

    // =========================================================================
    // Insert Node API (PRD Compliance)
    // =========================================================================

    /**
     * Insert a node with advanced features
     * @param {Object} payload - Node insertion parameters
     * @returns {Object} - { nodeId, success, error? }
     */
    insertNode(payload) {
        const {
            type,
            position,
            data = {},
            scopeId = null,
            insertSource = 'api',
            autoConnect = null
        } = payload;

        // Emit beforeInsert event (cancelable)
        const beforePayload = { type, position, data, scopeId, insertSource };
        if (!this.emit('beforeInsert', beforePayload)) {
            this.emit('insertFailed', { reason: 'Canceled by beforeInsert handler', attemptedPayload: payload });
            return { success: false, error: 'Insert canceled' };
        }

        try {
            // Check for collision and find placement
            const finalPosition = this._findValidPlacement(position);

            // Delegate to host component's addNode method
            const nodeId = this._hostComponent.addNode(
                type,
                data.layer || 'application',
                finalPosition.x,
                finalPosition.y,
                data.name || null,
                insertSource,
                data.sourceId || null,
                { scopeId }
            );

            // Handle auto-connect if snap target exists
            if (autoConnect && this._snapTarget) {
                this._performAutoConnect(nodeId, this._snapTarget);
            }

            // Emit afterInsert event
            this.emit('afterInsert', { nodeId, node: { id: nodeId, type, position: finalPosition, data } });

            return { success: true, nodeId };

        } catch (err) {
            console.error('[ReteLike] Insert failed:', err);
            this.emit('insertFailed', { reason: err.message, attemptedPayload: payload });
            return { success: false, error: err.message };
        }
    },

    /**
     * Find valid placement position avoiding collisions
     * @param {Object} position - Desired { x, y }
     * @returns {Object} - Collision-free { x, y }
     */
    _findValidPlacement(position) {
        // Spiral search for valid placement
        for (let attempt = 0; attempt < this.spiralPlacementMaxAttempts; attempt++) {
            const testPos = this._getSpiralOffset(position, attempt);

            if (!this._hasCollision(testPos)) {
                return testPos;
            }
        }

        // Fallback: return original position
        return position;
    },

    _getSpiralOffset(center, attempt) {
        if (attempt === 0) return center;

        const angle = attempt * 0.618 * Math.PI * 2; // Golden angle spiral
        const radius = attempt * this.spiralPlacementStep;

        return {
            x: center.x + Math.cos(angle) * radius,
            y: center.y + Math.sin(angle) * radius
        };
    },

    _hasCollision(position, threshold = 100) {
        const nodes = document.querySelectorAll('.drawflow-node');

        for (const node of nodes) {
            const rect = node.getBoundingClientRect();
            const nodeX = parseFloat(node.style.left || 0);
            const nodeY = parseFloat(node.style.top || 0);

            const distance = Math.hypot(position.x - nodeX, position.y - nodeY);
            if (distance < threshold) {
                return true;
            }
        }

        return false;
    },

    _performAutoConnect(newNodeId, snapTarget) {
        // Extract node IDs
        const targetNodeElement = document.getElementById(snapTarget.nodeId);
        if (!targetNodeElement) return;

        const targetDfId = parseInt(snapTarget.nodeId.replace('node-', ''));
        const newDfId = this._hostComponent.reverseIdMap[newNodeId];

        if (!targetDfId || !newDfId) return;

        try {
            // Connect based on snap target type
            if (snapTarget.type === 'output') {
                // Target is output, new node is input
                this._drawflowInstance.addConnection(targetDfId, newDfId, 'output_1', 'input_1');
            } else {
                // Target is input, new node is output
                this._drawflowInstance.addConnection(newDfId, targetDfId, 'output_1', 'input_1');
            }

        } catch (err) {
            console.warn('[ReteLike] Auto-connect failed:', err);
        }
    },

    // =========================================================================
    // SVG Overlay Layer for Enhanced Connection Rendering (Phase 2)
    // =========================================================================

    _initSVGOverlay() {
        const drawflowContainer = document.getElementById('drawflow');
        if (!drawflowContainer) {
            console.warn('[ReteLike] Drawflow container not found, SVG overlay disabled');
            return;
        }

        // Create SVG overlay element
        this._svgOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        this._svgOverlay.id = 'rete-svg-overlay';
        this._svgOverlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
        `;

        // Add defs for arrowhead markers
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
        marker.setAttribute('id', 'rete-arrowhead');
        marker.setAttribute('markerWidth', '10');
        marker.setAttribute('markerHeight', '10');
        marker.setAttribute('refX', '9');
        marker.setAttribute('refY', '3');
        marker.setAttribute('orient', 'auto');
        marker.setAttribute('markerUnits', 'strokeWidth');

        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        polygon.setAttribute('points', '0 0, 10 3, 0 6');
        polygon.setAttribute('fill', '#94a3b8');

        marker.appendChild(polygon);
        defs.appendChild(marker);
        this._svgOverlay.appendChild(defs);

        // Insert before nodes but after drawflow canvas
        const precanvas = drawflowContainer.querySelector('.drawflow');
        if (precanvas) {
            precanvas.appendChild(this._svgOverlay);
        }


        // Hook into Drawflow connection events
        this._hookConnectionRendering();
    },

    _hookConnectionRendering() {
        // Listen for connection created events
        this._drawflowInstance.on('connectionCreated', (connection) => {
            setTimeout(() => this._renderConnectionWithStrategy(connection), 100);
        });

        // Listen for node move events to update connections
        this._drawflowInstance.on('nodeMoved', (nodeId) => {
            setTimeout(() => this._updateConnectionsForNode(nodeId), 50);
        });

        // Listen for connection removed
        this._drawflowInstance.on('connectionRemoved', (connection) => {
            this._removeConnectionPath(connection);
        });
    },

    /**
     * Render a connection using the assigned path strategy
     * @param {Object} connection - Drawflow connection object
     */
    _renderConnectionWithStrategy(connection) {
        if (!this._svgOverlay) return;

        const { output_id, input_id, output_class, input_class } = connection;
        const connectionKey = `${output_id}_${input_id}`;

        // Get path type (default to bezier for backward compat)
        const pathType = this._connectionPathTypes.get(connectionKey) || 'bezier';

        // Get connection endpoints
        const endpoints = this._getConnectionEndpoints(output_id, input_id);
        if (!endpoints) return;

        const { start, end } = endpoints;

        // Get control points if available (Phase 3)
        const controlPoints = this._connectionControlPoints.get(connectionKey) || [];

        // Compute path using strategy
        const strategy = this._pathStrategies.get(pathType);
        if (!strategy) {
            console.warn(`[ReteLike] Unknown path strategy: ${pathType}`);
            return;
        }

        const pathData = strategy(start, end, controlPoints, {});

        // Create or update SVG path element
        let pathElement = this._svgPathElements.get(connectionKey);

        if (!pathElement) {
            pathElement = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            pathElement.setAttribute('data-connection-key', connectionKey);
            pathElement.style.cssText = `
                fill: none;
                stroke: #94a3b8;
                stroke-width: 2;
                pointer-events: stroke;
                cursor: pointer;
            `;

            // Click handler for connection selection
            pathElement.addEventListener('click', () => {
                this._selectConnection(connectionKey);
            });

            this._svgOverlay.appendChild(pathElement);
            this._svgPathElements.set(connectionKey, pathElement);
        }

        pathElement.setAttribute('d', pathData);
        pathElement.setAttribute('marker-end', 'url(#rete-arrowhead)');
    },

    /**
     * Get connection endpoint coordinates
     * @param {string} outputId - Source node ID
     * @param {string} inputId - Target node ID
     * @returns {Object|null} - { start: {x, y}, end: {x, y} }
     */
    _getConnectionEndpoints(outputId, inputId) {
        const outputNode = document.getElementById(`node-${outputId}`);
        const inputNode = document.getElementById(`node-${inputId}`);

        if (!outputNode || !inputNode) return null;

        const outputPort = outputNode.querySelector('.output');
        const inputPort = inputNode.querySelector('.input');

        if (!outputPort || !inputPort) return null;

        const drawflowRect = document.getElementById('drawflow').getBoundingClientRect();
        const zoom = this._drawflowInstance.zoom || 1;

        const outputRect = outputPort.getBoundingClientRect();
        const inputRect = inputPort.getBoundingClientRect();

        return {
            start: {
                x: (outputRect.left + outputRect.width / 2 - drawflowRect.left) / zoom,
                y: (outputRect.top + outputRect.height / 2 - drawflowRect.top) / zoom
            },
            end: {
                x: (inputRect.left + inputRect.width / 2 - drawflowRect.left) / zoom,
                y: (inputRect.top + inputRect.height / 2 - drawflowRect.top) / zoom
            }
        };
    },

    /**
     * Update all connections for a moved node
     * @param {number} nodeId - Drawflow node ID
     */
    _updateConnectionsForNode(nodeId) {
        if (!this._svgOverlay) return;

        // Find all connections involving this node
        const nodeIdStr = String(nodeId);

        this._svgPathElements.forEach((pathElement, connectionKey) => {
            const [outputId, inputId] = connectionKey.split('_');

            if (outputId === nodeIdStr || inputId === nodeIdStr) {
                const connection = { output_id: outputId, input_id: inputId };
                this._renderConnectionWithStrategy(connection);
            }
        });
    },

    /**
     * Remove connection path from SVG overlay
     * @param {Object} connection - Drawflow connection object
     */
    _removeConnectionPath(connection) {
        const { output_id, input_id } = connection;
        const connectionKey = `${output_id}_${input_id}`;

        const pathElement = this._svgPathElements.get(connectionKey);
        if (pathElement && pathElement.parentNode) {
            pathElement.parentNode.removeChild(pathElement);
        }

        this._svgPathElements.delete(connectionKey);
        this._connectionPathTypes.delete(connectionKey);
    },

    /**
     * Select a connection for editing
     * @param {string} connectionKey - Connection identifier
     */
    _selectConnection(connectionKey) {
        // Deselect previous
        if (this._selectedConnection) {
            const prevPath = this._svgPathElements.get(this._selectedConnection);
            if (prevPath) {
                prevPath.style.stroke = '#94a3b8';
                prevPath.style.strokeWidth = '2';
            }
        }

        // Select new
        this._selectedConnection = connectionKey;
        const pathElement = this._svgPathElements.get(connectionKey);
        if (pathElement) {
            pathElement.style.stroke = '#3b82f6';
            pathElement.style.strokeWidth = '3';
        }

        this._showPathTypeSelector(connectionKey);
    },

    /**
     * Show UI to change path type for selected connection
     * @param {string} connectionKey - Connection identifier
     */
    _showPathTypeSelector(connectionKey) {
        // Remove existing selector
        const existingSelector = document.getElementById('rete-path-selector');
        if (existingSelector) existingSelector.remove();

        const currentType = this._connectionPathTypes.get(connectionKey) || 'bezier';

        // Create path type selector UI
        const selector = document.createElement('div');
        selector.id = 'rete-path-selector';
        selector.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            z-index: 10000;
        `;

        safeHTML(selector, `
            <div class="text-sm font-medium mb-2">Connection Path Type</div>
            <div class="space-y-1">
                ${Array.from(this._pathStrategies.keys()).map(type => `
                    <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" name="path-type" value="${type}"
                               ${type === currentType ? 'checked' : ''}
                               class="text-primary">
                        <span class="text-sm capitalize">${type}</span>
                    </label>
                `).join('')}
            </div>
            <button id="rete-path-close" class="mt-3 text-xs text-muted-foreground hover:text-foreground">Close</button>
        `);

        document.body.appendChild(selector);

        // Handle path type change
        selector.querySelectorAll('input[name="path-type"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.setConnectionPath(connectionKey, { pathType: e.target.value });
            });
        });

        // Handle close
        document.getElementById('rete-path-close').addEventListener('click', () => {
            selector.remove();
            this._selectedConnection = null;

            // Deselect visual
            const pathElement = this._svgPathElements.get(connectionKey);
            if (pathElement) {
                pathElement.style.stroke = '#94a3b8';
                pathElement.style.strokeWidth = '2';
            }
        });
    },

    // =========================================================================
    // Path Strategy Registry (PRD Compliance)
    // =========================================================================

    _registerDefaultPathStrategies() {
        // Register bezier strategy
        this.registerPathStrategy('bezier', (start, end, controlPoints, options) => {
            return this._computeBezierPath(start, end, controlPoints, options);
        });

        // Register orthogonal strategy
        this.registerPathStrategy('orthogonal', (start, end, controlPoints, options) => {
            return this._computeOrthogonalPath(start, end, options);
        });

        // Register polyline strategy
        this.registerPathStrategy('polyline', (start, end, controlPoints, options) => {
            return this._computePolylinePath(start, end, controlPoints);
        });
    },

    /**
     * Register a custom path strategy
     * @param {string} name - Strategy identifier
     * @param {Function} strategyFn - (start, end, controlPoints, options) => svgPathString
     */
    registerPathStrategy(name, strategyFn) {
        if (typeof strategyFn !== 'function') {
            throw new Error(`[ReteLike] Path strategy must be a function, got ${typeof strategyFn}`);
        }

        this._pathStrategies.set(name, strategyFn);
        this.emit('pathStrategyRegistered', { name });
    },

    /**
     * Compute bezier path (cubic Bezier with smart control points)
     */
    _computeBezierPath(start, end, controlPoints, options = {}) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const dist = Math.max(40, Math.hypot(dx, dy) * 0.5);

        // Smart control point calculation based on port direction
        const c1 = { x: start.x + dist, y: start.y };
        const c2 = { x: end.x - dist, y: end.y };

        return `M ${start.x} ${start.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${end.x} ${end.y}`;
    },

    /**
     * Compute orthogonal path (Manhattan/right-angle routing)
     */
    _computeOrthogonalPath(start, end, options = {}) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;

        // Determine primary axis
        const horizontal = Math.abs(dx) > Math.abs(dy);

        let path = `M ${start.x} ${start.y}`;

        if (horizontal) {
            // Horizontal primary path
            const midX = start.x + dx / 2;
            path += ` L ${midX} ${start.y}`;
            path += ` L ${midX} ${end.y}`;
            path += ` L ${end.x} ${end.y}`;
        } else {
            // Vertical primary path
            const midY = start.y + dy / 2;
            path += ` L ${start.x} ${midY}`;
            path += ` L ${end.x} ${midY}`;
            path += ` L ${end.x} ${end.y}`;
        }

        return path;
    },

    /**
     * Compute polyline path (straight segments through control points)
     */
    _computePolylinePath(start, end, controlPoints = []) {
        let path = `M ${start.x} ${start.y}`;

        for (const cp of controlPoints) {
            path += ` L ${cp.x} ${cp.y}`;
        }

        path += ` L ${end.x} ${end.y}`;
        return path;
    },

    /**
     * Get list of registered path strategies
     * @returns {string[]} - Strategy names
     */
    getPathStrategies() {
        return Array.from(this._pathStrategies.keys());
    },

    /**
     * Set connection path strategy
     * @param {string} connectionKey - Connection identifier (output_id_input_id)
     * @param {Object} config - { pathType, controlPoints? }
     */
    setConnectionPath(connectionKey, config) {
        const { pathType, controlPoints = [] } = config;

        if (!this._pathStrategies.has(pathType)) {
            console.warn(`[ReteLike] Unknown path strategy: ${pathType}`);
            return;
        }

        // Store path type
        this._connectionPathTypes.set(connectionKey, pathType);

        // Re-render connection with new strategy
        const [outputId, inputId] = connectionKey.split('_');
        this._renderConnectionWithStrategy({ output_id: outputId, input_id: inputId });

        this.emit('pathEdited', { connectionKey, pathType, controlPoints });
    },

    // =========================================================================
    // Scope System (PRD Compliance)
    // =========================================================================

    /**
     * Create a new scope container
     * @param {Object} scopeDef - { id?, name, style?, rules? }
     * @returns {Object} - { scopeId }
     */
    createScope(scopeDef) {
        const scopeId = scopeDef.id || `scope-${Date.now()}`;
        const scope = {
            id: scopeId,
            name: scopeDef.name || 'Unnamed Scope',
            style: scopeDef.style || {},
            rules: scopeDef.rules || { allow: null, deny: null, predicates: [] },
            nodeIds: []
        };

        this._scopes.set(scopeId, scope);
        this.emit('scopeCreated', { scope });

        return { scopeId };
    },

    /**
     * Assign node to scope
     * @param {string} nodeId - Node identifier
     * @param {string} scopeId - Scope identifier
     */
    assignNodeToScope(nodeId, scopeId) {
        const scope = this._scopes.get(scopeId);
        if (!scope) {
            console.warn(`[ReteLike] Scope not found: ${scopeId}`);
            return;
        }

        if (!scope.nodeIds.includes(nodeId)) {
            scope.nodeIds.push(nodeId);
        }

    },

    /**
     * Register scope validation predicate
     * @param {string} name - Predicate identifier
     * @param {Function} fn - (nodeA, nodeB) => boolean
     */
    registerScopePredicate(name, fn) {
        if (typeof fn !== 'function') {
            throw new Error(`[ReteLike] Predicate must be a function, got ${typeof fn}`);
        }

        this._scopePredicates.set(name, fn);
    },

    /**
     * Validate connection between two nodes
     * @param {string} nodeAId - Source node ID
     * @param {string} nodeBId - Target node ID
     * @returns {Object} - { allowed: boolean, reason?: string }
     */
    validateConnection(nodeAId, nodeBId) {
        // Get scope IDs for both nodes
        const scopeA = this._getNodeScope(nodeAId);
        const scopeB = this._getNodeScope(nodeBId);

        // Same scope or no scopes: allow by default
        if (scopeA === scopeB) {
            return { allowed: true };
        }

        // Cross-scope validation
        if (scopeA) {
            const result = this._validateScopeRules(scopeA, nodeBId);
            if (!result.allowed) return result;
        }

        if (scopeB) {
            const result = this._validateScopeRules(scopeB, nodeAId);
            if (!result.allowed) return result;
        }

        return { allowed: true };
    },

    _getNodeScope(nodeId) {
        for (const [scopeId, scope] of this._scopes.entries()) {
            if (scope.nodeIds.includes(nodeId)) {
                return scopeId;
            }
        }
        return null;
    },

    _validateScopeRules(scopeId, nodeId) {
        const scope = this._scopes.get(scopeId);
        if (!scope || !scope.rules) {
            return { allowed: true };
        }

        const { allow, deny, predicates = [] } = scope.rules;
        const nodeType = this._getNodeType(nodeId);

        // Check deny list
        if (deny && deny.includes(nodeType)) {
            return { allowed: false, reason: `Node type ${nodeType} denied by scope ${scopeId}` };
        }

        // Check allow list
        if (allow && !allow.includes(nodeType)) {
            return { allowed: false, reason: `Node type ${nodeType} not in allow list for scope ${scopeId}` };
        }

        // Run predicates
        for (const predicateName of predicates) {
            const predicate = this._scopePredicates.get(predicateName);
            if (predicate) {
                try {
                    const result = predicate(nodeId, scopeId);
                    if (!result) {
                        return { allowed: false, reason: `Predicate ${predicateName} rejected connection` };
                    }
                } catch (err) {
                    console.error(`[ReteLike] Predicate ${predicateName} error:`, err);
                    return { allowed: false, reason: `Predicate ${predicateName} failed` };
                }
            }
        }

        return { allowed: true };
    },

    _getNodeType(nodeId) {
        // Delegate to host component to get node type
        const nodeData = this._hostComponent?.nodeDataMap?.[nodeId];
        return nodeData?.elementType || 'unknown';
    },

    /**
     * Get all scopes
     * @returns {Array} - Array of scope objects
     */
    getScopes() {
        return Array.from(this._scopes.values());
    },

    /**
     * Delete a scope
     * @param {string} scopeId - Scope identifier
     * @param {Object} options - { reparentTo?: string|null }
     */
    deleteScope(scopeId, options = {}) {
        const scope = this._scopes.get(scopeId);
        if (!scope) {
            console.warn(`[ReteLike] Scope not found: ${scopeId}`);
            return;
        }

        // Handle reparenting
        if (options.reparentTo) {
            const targetScope = this._scopes.get(options.reparentTo);
            if (targetScope) {
                targetScope.nodeIds.push(...scope.nodeIds);
            }
        }

        this._scopes.delete(scopeId);
        this.emit('scopeDeleted', { scopeId });

    },

    // =========================================================================
    // Visual Scope Containers (Phase 3)
    // =========================================================================

    /**
     * Render visual scope containers on SVG overlay
     * @param {string} scopeId - Scope to render
     */
    renderScopeContainer(scopeId) {
        const scope = this._scopes.get(scopeId);
        if (!scope || !this._svgOverlay) return;

        // Calculate bounding box for all nodes in scope
        const bounds = this._calculateScopeBounds(scopeId);
        if (!bounds) return;

        // Create/update scope rectangle
        let scopeRect = this._svgOverlay.querySelector(`[data-scope-id="${scopeId}"]`);

        if (!scopeRect) {
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('data-scope-id', scopeId);
            g.classList.add('scope-container');

            // Background rectangle
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.classList.add('scope-bg');
            rect.style.cssText = `
                fill: ${scope.style.fill || 'rgba(59, 130, 246, 0.1)'};
                stroke: ${scope.style.stroke || '#3b82f6'};
                stroke-width: 2;
                stroke-dasharray: 5,5;
                rx: 8;
            `;

            // Label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.classList.add('scope-label');
            text.textContent = scope.name;
            text.style.cssText = `
                fill: #3b82f6;
                font-size: 14px;
                font-weight: 600;
                pointer-events: none;
            `;

            // Resize handle
            const handle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            handle.classList.add('scope-resize-handle');
            handle.setAttribute('r', '6');
            handle.style.cssText = `
                fill: white;
                stroke: #3b82f6;
                stroke-width: 2;
                cursor: se-resize;
                pointer-events: all;
            `;

            g.appendChild(rect);
            g.appendChild(text);
            g.appendChild(handle);

            // Insert at beginning (behind connections and nodes)
            this._svgOverlay.insertBefore(g, this._svgOverlay.firstChild);

            scopeRect = g;

            // Add event handlers
            this._attachScopeHandlers(scopeId, g);
        }

        // Update positions
        const rect = scopeRect.querySelector('.scope-bg');
        const text = scopeRect.querySelector('.scope-label');
        const handle = scopeRect.querySelector('.scope-resize-handle');

        const padding = 20;
        rect.setAttribute('x', bounds.x - padding);
        rect.setAttribute('y', bounds.y - padding);
        rect.setAttribute('width', bounds.width + padding * 2);
        rect.setAttribute('height', bounds.height + padding * 2);

        text.setAttribute('x', bounds.x - padding + 10);
        text.setAttribute('y', bounds.y - padding + 20);

        handle.setAttribute('cx', bounds.x + bounds.width + padding);
        handle.setAttribute('cy', bounds.y + bounds.height + padding);
    },

    _calculateScopeBounds(scopeId) {
        const scope = this._scopes.get(scopeId);
        if (!scope || scope.nodeIds.length === 0) return null;

        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;

        for (const nodeId of scope.nodeIds) {
            const nodeEl = document.getElementById(`node-${nodeId}`);
            if (!nodeEl) continue;

            const rect = nodeEl.getBoundingClientRect();
            const drawflowRect = document.getElementById('drawflow').getBoundingClientRect();
            const zoom = this._drawflowInstance.zoom || 1;

            const x = (rect.left - drawflowRect.left) / zoom;
            const y = (rect.top - drawflowRect.top) / zoom;
            const width = rect.width / zoom;
            const height = rect.height / zoom;

            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + width);
            maxY = Math.max(maxY, y + height);
        }

        return {
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY
        };
    },

    _attachScopeHandlers(scopeId, groupElement) {
        const rect = groupElement.querySelector('.scope-bg');
        const handle = groupElement.querySelector('.scope-resize-handle');

        // Drag scope to move
        let isDragging = false;
        let startPos = { x: 0, y: 0 };

        rect.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            isDragging = true;
            startPos = { x: e.clientX, y: e.clientY };
            rect.style.cursor = 'move';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;

            const dx = e.clientX - startPos.x;
            const dy = e.clientY - startPos.y;

            // Scope-level node movement not yet implemented
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                rect.style.cursor = 'pointer';
            }
        });

        // Resize handle
        let isResizing = false;
        handle.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            isResizing = true;
            startPos = { x: e.clientX, y: e.clientY };
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            const dx = e.clientX - startPos.x;
            const dy = e.clientY - startPos.y;

            const currentWidth = parseFloat(rect.getAttribute('width'));
            const currentHeight = parseFloat(rect.getAttribute('height'));

            rect.setAttribute('width', Math.max(100, currentWidth + dx));
            rect.setAttribute('height', Math.max(100, currentHeight + dy));

            handle.setAttribute('cx', parseFloat(handle.getAttribute('cx')) + dx);
            handle.setAttribute('cy', parseFloat(handle.getAttribute('cy')) + dy);

            startPos = { x: e.clientX, y: e.clientY };
        });

        document.addEventListener('mouseup', () => {
            isResizing = false;
        });
    },

    /**
     * Toggle scope collapsed state
     * @param {string} scopeId - Scope identifier
     */
    toggleScopeCollapse(scopeId) {
        const scope = this._scopes.get(scopeId);
        if (!scope) return;

        scope.collapsed = !scope.collapsed;

        // Hide/show nodes
        for (const nodeId of scope.nodeIds) {
            const nodeEl = document.getElementById(`node-${nodeId}`);
            if (nodeEl) {
                nodeEl.style.display = scope.collapsed ? 'none' : 'block';
            }
        }

        // Re-render scope container
        this.renderScopeContainer(scopeId);

        // Update connections
        this._updateConnectionsForScope(scopeId);
    },

    _updateConnectionsForScope(scopeId) {
        const scope = this._scopes.get(scopeId);
        if (!scope) return;

        for (const nodeId of scope.nodeIds) {
            this._updateConnectionsForNode(nodeId);
        }
    },

    // =========================================================================
    // Draggable Control Points (Phase 3)
    // =========================================================================

    /**
     * Add control point to connection path
     * @param {string} connectionKey - Connection identifier
     * @param {Object} point - { x, y }
     */
    addControlPoint(connectionKey, point) {
        const pathElement = this._svgPathElements.get(connectionKey);
        if (!pathElement) return;

        // Store control points in metadata
        if (!this._connectionControlPoints) {
            this._connectionControlPoints = new Map();
        }

        const existingPoints = this._connectionControlPoints.get(connectionKey) || [];
        existingPoints.push(point);
        this._connectionControlPoints.set(connectionKey, existingPoints);

        // Re-render with control points
        const [outputId, inputId] = connectionKey.split('_');
        this._renderConnectionWithStrategy({ output_id: outputId, input_id: inputId });

        // Render control point handles
        this._renderControlPointHandles(connectionKey);
    },

    _renderControlPointHandles(connectionKey) {
        if (!this._svgOverlay) return;

        const controlPoints = this._connectionControlPoints?.get(connectionKey) || [];

        // Remove existing handles
        const existingHandles = this._svgOverlay.querySelectorAll(`[data-connection-key="${connectionKey}"][data-control-point]`);
        existingHandles.forEach(h => h.remove());

        // Render new handles
        controlPoints.forEach((point, index) => {
            const handle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            handle.setAttribute('data-connection-key', connectionKey);
            handle.setAttribute('data-control-point', index);
            handle.setAttribute('cx', point.x);
            handle.setAttribute('cy', point.y);
            handle.setAttribute('r', '5');
            handle.style.cssText = `
                fill: white;
                stroke: #3b82f6;
                stroke-width: 2;
                cursor: move;
                pointer-events: all;
            `;

            // Make draggable
            this._makeControlPointDraggable(handle, connectionKey, index);

            this._svgOverlay.appendChild(handle);
        });
    },

    _makeControlPointDraggable(handle, connectionKey, pointIndex) {
        let isDragging = false;

        handle.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            isDragging = true;
            handle.style.fill = '#3b82f6';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;

            const drawflowRect = document.getElementById('drawflow').getBoundingClientRect();
            const zoom = this._drawflowInstance.zoom || 1;

            const x = (e.clientX - drawflowRect.left) / zoom;
            const y = (e.clientY - drawflowRect.top) / zoom;

            // Update control point position
            handle.setAttribute('cx', x);
            handle.setAttribute('cy', y);

            // Update stored control point
            const controlPoints = this._connectionControlPoints.get(connectionKey);
            if (controlPoints && controlPoints[pointIndex]) {
                controlPoints[pointIndex] = { x, y };
            }

            // Re-render path
            const [outputId, inputId] = connectionKey.split('_');
            this._renderConnectionWithStrategy({ output_id: outputId, input_id: inputId });
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                handle.style.fill = 'white';

                // Emit path edited event
                this.emit('pathEdited', {
                    connectionKey,
                    controlPoints: this._connectionControlPoints.get(connectionKey)
                });
            }
        });
    },

    /**
     * Enable control point editing mode for a connection
     * @param {string} connectionKey - Connection identifier
     */
    enableControlPointEditing(connectionKey) {
        const pathElement = this._svgPathElements.get(connectionKey);
        if (!pathElement) return;

        // Add click-to-add-control-point functionality
        pathElement.style.cursor = 'crosshair';

        const clickHandler = (e) => {
            const drawflowRect = document.getElementById('drawflow').getBoundingClientRect();
            const zoom = this._drawflowInstance.zoom || 1;

            const x = (e.clientX - drawflowRect.left) / zoom;
            const y = (e.clientY - drawflowRect.top) / zoom;

            this.addControlPoint(connectionKey, { x, y });
        };

        pathElement.addEventListener('click', clickHandler);
        pathElement._controlPointClickHandler = clickHandler;
    },

    /**
     * Disable control point editing mode
     * @param {string} connectionKey - Connection identifier
     */
    disableControlPointEditing(connectionKey) {
        const pathElement = this._svgPathElements.get(connectionKey);
        if (!pathElement) return;

        pathElement.style.cursor = 'pointer';

        if (pathElement._controlPointClickHandler) {
            pathElement.removeEventListener('click', pathElement._controlPointClickHandler);
            delete pathElement._controlPointClickHandler;
        }
    },

    // =========================================================================
    // Utilities
    // =========================================================================

    _formatTypeName(type) {
        return type.replace(/_/g, ' ')
            .split(' ')
            .map(w => w.charAt(0).toUpperCase() + w.slice(1))
            .join(' ');
    },

    _extractColorClass(element) {
        const classList = Array.from(element.classList);
        for (const cls of classList) {
            if (cls.startsWith('text-')) {
                return cls;
            }
        }
        return 'text-primary';
    }
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ReteLikeExtensions;
}
